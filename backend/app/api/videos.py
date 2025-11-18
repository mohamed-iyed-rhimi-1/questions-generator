from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import logging
from pathlib import Path

from app.database import get_db
from app.exceptions import ValidationException, DatabaseException
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
from app.services import process_multiple_urls, process_multiple_transcriptions

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
                video_response = VideoResponse.model_validate(result['video'])
            
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
        # Execute query directly - FastAPI runs sync routes in threadpool
        videos = db.query(Video).order_by(
            Video.created_at.desc()
        ).offset(skip).limit(limit).all()
        
        # Convert ORM objects to Pydantic schemas
        return [VideoResponse.model_validate(video) for video in videos]
        
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
        # Execute query directly - FastAPI runs sync routes in threadpool
        video = db.query(Video).filter_by(video_id=video_id).first()
        
        if video is None:
            raise ValidationException(
                f"Video with ID {video_id} not found",
                details={"video_id": video_id}
            )
        
        return VideoResponse.model_validate(video)
        
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
    Delete a video and its associated audio file.
    
    Removes the video record from the database and deletes the audio file from storage.
    """
    try:
        # Execute deletion directly - FastAPI runs sync routes in threadpool
        video = db.query(Video).filter_by(video_id=video_id).first()
        if not video:
            raise ValidationException(
                f"Video with ID {video_id} not found",
                details={"video_id": video_id}
            )
        
        # Delete audio file if it exists
        if video.file_path:
            try:
                Path(video.file_path).unlink(missing_ok=True)
            except Exception as e:
                logger.warning(f"Failed to delete audio file {video.file_path}: {e}")
        
        # Delete database record
        db.delete(video)
        db.commit()
        
        logger.info(f"Deleted video {video_id}")
        return None
        
    except ValidationException:
        raise
    except Exception as e:
        logger.exception(f"Error deleting video {video_id}")
        raise DatabaseException(
            "Failed to delete video",
            details={"video_id": video_id, "error": str(e)}
        )
