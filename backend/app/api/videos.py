from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List
import logging
from pathlib import Path

from app.database import get_db
from app.exceptions import ValidationException, DatabaseException, DependencyException
from app.schemas import (
    DownloadVideosRequest,
    DownloadVideosResponse,
    DownloadResult,
    VideoResponse,
    TranscribeVideosRequest,
    TranscribeVideosResponse,
    TranscriptionResult,
    TranscriptionResponse,
)
from app.models.video import Video
from app.models.transcription import Transcription
from app.services import process_multiple_urls, process_multiple_transcriptions
from app.services.chunk_service import delete_chunks_for_video, get_chunks_for_video

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/download", response_model=DownloadVideosResponse, status_code=status.HTTP_200_OK)
def download_videos(
    request: DownloadVideosRequest,
    db: Session = Depends(get_db)
):
    """
    Download YouTube videos as MP3 audio files.
    
    Accepts a list of YouTube URLs and downloads them as MP3 files with embedded metadata.
    Returns status for each URL (success/duplicate/failed).
    """
    if not request.urls:
        raise ValidationException(
            "No URLs provided",
            details={"field": "urls", "expected": "non-empty list"}
        )
    
    logger.info(f"Received download request for {len(request.urls)} URLs")
    
    try:
        # Call service function directly - FastAPI runs sync routes in threadpool
        results = process_multiple_urls(request.urls, db)
        
        # Calculate summary statistics
        total = len(results)
        successful = sum(1 for r in results if r['status'] == 'success')
        duplicates = sum(1 for r in results if r['status'] == 'duplicate')
        failed = sum(1 for r in results if r['status'] == 'failed')
        
        # Convert service results to Pydantic schemas
        download_results = []
        for result in results:
            # Convert ORM object to VideoResponse if present
            video_response = None
            if result.get('video'):
                video = result['video']
                # Ensure chunks relationship is loaded
                if video.chunks is None:
                    # Refresh to load chunks if not already loaded
                    db.refresh(video, ['chunks'])
                
                video_dict = {
                    'id': video.id,
                    'video_id': video.video_id,
                    'title': video.title,
                    'thumbnail_url': video.thumbnail_url,
                    'file_path': video.file_path,
                    'created_at': video.created_at,
                    'download_status': 'completed',
                    'has_chunks': len(video.chunks) > 0 if video.chunks else False,
                    'chunk_count': len(video.chunks) if video.chunks else 0
                }
                video_response = VideoResponse(**video_dict)
            
            download_result = DownloadResult(
                url=result['url'],
                status=result['status'],
                message=result['message'],
                video_id=result.get('video_id'),
                video=video_response,
                error=result.get('error'),
            )
            download_results.append(download_result)
        
        response = DownloadVideosResponse(
            results=download_results,
            total=total,
            successful=successful,
            duplicates=duplicates,
            failed=failed,
        )
        
        logger.info(f"Download complete: {successful} successful, {duplicates} duplicates, {failed} failed")
        return response
        
    except ValidationException:
        raise
    except Exception as e:
        logger.exception("Unexpected error during download")
        raise DatabaseException(
            "Failed to process download request",
            details={"error": str(e)}
        )


@router.get("", response_model=List[VideoResponse])
def list_videos(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    List all downloaded videos with pagination.
    
    Returns a paginated list of all downloaded videos, ordered by creation date (newest first).
    """
    # Validate and cap limit
    if skip < 0:
        raise ValidationException(
            "Skip parameter must be non-negative",
            details={"field": "skip", "value": skip}
        )
    
    if limit < 1:
        raise ValidationException(
            "Limit parameter must be positive",
            details={"field": "limit", "value": limit}
        )
    
    if limit > 1000:
        limit = 1000
    
    try:
        # Execute query with eager loading of chunks - FastAPI runs sync routes in threadpool
        videos = db.query(Video).options(
            joinedload(Video.chunks)
        ).order_by(
            Video.created_at.desc()
        ).offset(skip).limit(limit).all()
        
        # Convert ORM objects to Pydantic schemas with chunk metadata
        video_responses = []
        for video in videos:
            video_dict = {
                'id': video.id,
                'video_id': video.video_id,
                'title': video.title,
                'thumbnail_url': video.thumbnail_url,
                'file_path': video.file_path,
                'created_at': video.created_at,
                'download_status': 'completed',
                'has_chunks': len(video.chunks) > 0 if video.chunks else False,
                'chunk_count': len(video.chunks) if video.chunks else 0
            }
            video_responses.append(VideoResponse(**video_dict))
        
        return video_responses
        
    except ValidationException:
        raise
    except Exception as e:
        logger.exception("Error listing videos")
        raise DatabaseException(
            "Failed to retrieve videos",
            details={"error": str(e)}
        )


@router.get("/{video_id}", response_model=VideoResponse)
def get_video(
    video_id: str,
    db: Session = Depends(get_db)
):
    """
    Get details for a specific video by its YouTube video ID.
    
    Returns video metadata and file information for the specified video.
    """
    try:
        # Execute query with eager loading of chunks - FastAPI runs sync routes in threadpool
        video = db.query(Video).options(
            joinedload(Video.chunks)
        ).filter_by(video_id=video_id).first()
        
        if video is None:
            raise ValidationException(
                f"Video with ID {video_id} not found",
                details={"video_id": video_id}
            )
        
        # Build response with chunk metadata
        video_dict = {
            'id': video.id,
            'video_id': video.video_id,
            'title': video.title,
            'thumbnail_url': video.thumbnail_url,
            'file_path': video.file_path,
            'created_at': video.created_at,
            'download_status': 'completed',
            'has_chunks': len(video.chunks) > 0 if video.chunks else False,
            'chunk_count': len(video.chunks) if video.chunks else 0
        }
        
        return VideoResponse(**video_dict)
        
    except ValidationException:
        raise
    except Exception as e:
        logger.exception(f"Error retrieving video {video_id}")
        raise DatabaseException(
            "Failed to retrieve video",
            details={"video_id": video_id, "error": str(e)}
        )


@router.post("/transcribe", response_model=TranscribeVideosResponse, status_code=status.HTTP_200_OK)
def transcribe_videos(
    request: TranscribeVideosRequest,
    db: Session = Depends(get_db)
):
    """
    Transcribe videos using Whisper and generate vector embeddings.
    
    This endpoint accepts a list of YouTube video IDs, transcribes their audio
    using OpenAI Whisper (local model), generates 384-dimensional vector embeddings
    using sentence-transformers, and stores both in the database.
    
    Videos must be downloaded first (audio files must exist).
    """
    # Validate request
    if not request.video_ids:
        raise ValidationException(
            "No video IDs provided",
            details={"field": "video_ids", "expected": "non-empty list"}
        )
    
    # Validate video IDs format
    for video_id in request.video_ids:
        if not video_id or not isinstance(video_id, str):
            raise ValidationException(
                "Invalid video ID format",
                details={"video_id": video_id, "expected": "non-empty string"}
            )
    
    logger.info(f"Received transcription request for {len(request.video_ids)} videos")
    
    try:
        # Run the service function (synchronous - FastAPI handles threadpool)
        results = process_multiple_transcriptions(request.video_ids, db)
        
        # Calculate summary statistics
        total = len(results)
        successful = sum(1 for r in results if r['status'] == 'success')
        not_found = sum(1 for r in results if r['status'] == 'not_found')
        no_audio = sum(1 for r in results if r['status'] == 'no_audio')
        failed = sum(1 for r in results if r['status'] == 'failed')
        
        # Convert service results to Pydantic schemas
        transcription_results = []
        for result in results:
            # Convert ORM object to Pydantic schema if present
            transcription_response = None
            if result.get('transcription'):
                transcription_response = TranscriptionResponse.model_validate(result['transcription'])
            
            transcription_results.append(
                TranscriptionResult(
                    video_id=result['video_id'],
                    status=result['status'],
                    message=result['message'],
                    transcription=transcription_response,
                    error=result.get('error'),
                    steps_completed=result.get('steps_completed', 0),
                    total_steps=result.get('total_steps', 5)
                )
            )
        
        # Create response
        response = TranscribeVideosResponse(
            results=transcription_results,
            total=total,
            successful=successful,
            failed=failed,
            not_found=not_found,
            no_audio=no_audio
        )
        
        logger.info(
            f"Transcription complete: {successful} successful, {failed} failed, "
            f"{not_found} not found, {no_audio} no audio"
        )
        return response
        
    except ValidationException:
        raise
    except Exception as e:
        logger.exception("Unexpected error during transcription")
        raise DatabaseException(
            "Failed to process transcription request",
            details={"error": str(e)}
        )


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_video(
    video_id: str,
    db: Session = Depends(get_db)
):
    """
    Delete a video and its associated files (audio and thumbnail).
    
    Checks for dependent transcriptions before deletion. If transcriptions exist,
    returns 409 Conflict. Otherwise, removes the video record from the database
    and deletes associated audio and thumbnail files from storage.
    
    Raises:
        ValidationException: If video not found (404)
        DependencyException: If video has dependent transcriptions (409)
        DatabaseException: If database operation fails (500)
    """
    try:
        # Fetch video from database
        video = db.query(Video).filter_by(video_id=video_id).first()
        
        if not video:
            raise ValidationException(
                f"Video with ID {video_id} not found",
                details={"video_id": video_id}
            )
        
        # Check for dependent transcriptions
        transcription_count = db.query(Transcription).filter_by(
            video_id=video_id
        ).count()
        
        if transcription_count > 0:
            transcriptions = db.query(Transcription).filter_by(
                video_id=video_id
            ).all()
            
            logger.warning(
                f"Cannot delete video {video_id}: has {transcription_count} dependent transcription(s)"
            )
            
            raise DependencyException(
                "Cannot delete video because it has dependent transcriptions",
                details={
                    "video_id": video_id,
                    "transcription_count": transcription_count
                },
                dependent_resources=[
                    {"type": "transcription", "id": t.id}
                    for t in transcriptions
                ]
            )
        
        # Check if chunks exist for this video
        chunks = get_chunks_for_video(video_id, db)
        chunks_deleted = 0
        
        if chunks:
            # Delete chunks before deleting video record
            try:
                chunks_deleted = delete_chunks_for_video(video_id, db)
                logger.info(
                    f"Deleted {chunks_deleted} chunks for video {video_id}",
                    extra={'video_id': video_id, 'chunks_deleted': chunks_deleted}
                )
            except Exception as e:
                logger.error(
                    f"Failed to delete chunks for video {video_id}: {e}",
                    extra={'video_id': video_id}
                )
                # Continue with video deletion even if chunk deletion fails
                # The cascade delete will handle database records
        
        # CRITICAL: Delete files from storage BEFORE deleting database record
        files_deleted = []
        
        # Delete audio file
        if video.file_path:
            try:
                audio_path = Path(video.file_path)
                if audio_path.exists():
                    audio_path.unlink()
                    files_deleted.append(str(audio_path))
                    logger.info(f"Deleted audio file: {audio_path}")
                else:
                    logger.info(f"Audio file not found (already deleted): {audio_path}")
            except Exception as e:
                logger.warning(f"Failed to delete audio file {video.file_path}: {e}")
        
        # Delete thumbnail file if it exists
        # Thumbnails are stored in backend/storage/thumbnails/{video_id}.webp
        thumbnail_path = Path(f"backend/storage/thumbnails/{video_id}.webp")
        if thumbnail_path.exists():
            try:
                thumbnail_path.unlink()
                files_deleted.append(str(thumbnail_path))
                logger.info(f"Deleted thumbnail file: {thumbnail_path}")
            except Exception as e:
                logger.warning(f"Failed to delete thumbnail file {thumbnail_path}: {e}")
        else:
            logger.info(f"Thumbnail file not found (may not exist): {thumbnail_path}")
        
        # Delete database record
        db.delete(video)
        db.commit()
        
        # Log comprehensive deletion summary
        deletion_summary = []
        if chunks_deleted > 0:
            deletion_summary.append(f"{chunks_deleted} chunks")
        if files_deleted:
            deletion_summary.append(f"{len(files_deleted)} file(s)")
        
        logger.info(
            f"Successfully deleted video {video_id}"
            + (f" and {', '.join(deletion_summary)}" if deletion_summary else ""),
            extra={
                'video_id': video_id,
                'chunks_deleted': chunks_deleted,
                'files_deleted': files_deleted
            }
        )
        return None
        
    except (ValidationException, DependencyException):
        raise
    except Exception as e:
        logger.exception(f"Unexpected error deleting video {video_id}")
        db.rollback()
        raise DatabaseException(
            "Failed to delete video",
            details={"video_id": video_id, "error": str(e)}
        )
