from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from app.database import get_db
from app.exceptions import ValidationException, DatabaseException
from app.schemas import (
    TranscribeVideosRequest,
    TranscribeVideosResponse,
    TranscriptionResult,
    TranscriptionResponse,
    TranscriptionListResponse,
)
from app.models.transcription import Transcription
from app.models.video import Video
from app.services import process_multiple_transcriptions

# Create router and logger
router = APIRouter()
logger = logging.getLogger(__name__)


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


@router.get("", response_model=TranscriptionListResponse)
def list_transcriptions(
    skip: int = 0,
    limit: int = 100,
    video_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    List transcriptions with optional filtering and pagination.
    
    Returns a paginated list of transcriptions, optionally filtered by video_id.
    """
    # Validate parameters
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
        # Build query
        query = db.query(Transcription)
        
        # Apply video_id filter if provided
        if video_id:
            query = query.filter_by(video_id=video_id)
        
        # Get total count
        total = query.count()
        
        # Order by creation date (newest first) and apply pagination
        transcriptions = query.order_by(
            Transcription.created_at.desc()
        ).offset(skip).limit(limit).all()
        
        # Convert ORM objects to Pydantic schemas
        transcription_list = [TranscriptionResponse.model_validate(t) for t in transcriptions]
        
        return TranscriptionListResponse(
            transcriptions=transcription_list,
            total=total
        )
        
    except ValidationException:
        raise
    except Exception as e:
        logger.exception("Error listing transcriptions")
        raise DatabaseException(
            "Failed to retrieve transcriptions",
            details={"error": str(e)}
        )


@router.get("/{transcription_id}", response_model=TranscriptionResponse)
def get_transcription(
    transcription_id: int,
    db: Session = Depends(get_db)
):
    """
    Get details for a specific transcription by its database ID.
    """
    try:
        transcription = db.query(Transcription).filter_by(id=transcription_id).first()
        
        if transcription is None:
            raise ValidationException(
                f"Transcription with ID {transcription_id} not found",
                details={"transcription_id": transcription_id}
            )
        
        return TranscriptionResponse.model_validate(transcription)
        
    except ValidationException:
        raise
    except Exception as e:
        logger.exception(f"Error retrieving transcription {transcription_id}")
        raise DatabaseException(
            "Failed to retrieve transcription",
            details={"transcription_id": transcription_id, "error": str(e)}
        )


@router.get("/video/{video_id}", response_model=List[TranscriptionResponse])
def get_video_transcriptions(
    video_id: str,
    db: Session = Depends(get_db)
):
    """
    Get all transcriptions for a specific video.
    
    Returns all transcriptions associated with the given video_id.
    Multiple transcriptions per video are supported.
    """
    try:
        transcriptions = db.query(Transcription).filter_by(
            video_id=video_id
        ).order_by(
            Transcription.created_at.desc()
        ).all()
        
        # Return empty list if no transcriptions found (not 404)
        return [TranscriptionResponse.model_validate(t) for t in transcriptions]
        
    except Exception as e:
        logger.exception(f"Error retrieving transcriptions for video {video_id}")
        raise DatabaseException(
            "Failed to retrieve video transcriptions",
            details={"video_id": video_id, "error": str(e)}
        )


@router.delete("/{transcription_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transcription(
    transcription_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a specific transcription from the database.
    """
    try:
        transcription = db.query(Transcription).filter_by(id=transcription_id).first()
        
        if not transcription:
            raise ValidationException(
                f"Transcription with ID {transcription_id} not found",
                details={"transcription_id": transcription_id}
            )
        
        db.delete(transcription)
        db.commit()
        
        logger.info(f"Deleted transcription {transcription_id}")
        return None
        
    except ValidationException:
        raise
    except Exception as e:
        logger.exception(f"Error deleting transcription {transcription_id}")
        db.rollback()
        raise DatabaseException(
            "Failed to delete transcription",
            details={"transcription_id": transcription_id, "error": str(e)}
        )
