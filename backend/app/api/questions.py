"""
Questions API router for AI-powered question generation.

This module provides endpoints for generating questions from transcribed videos.
Uses Ollama LLM to generate AI-powered educational questions from video transcriptions.
"""

import logging
import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.exceptions import ValidationException, OllamaConnectionException
from app.schemas import (
    GenerateQuestionsRequest,
    GenerateQuestionsResponse,
    QuestionGenerationResult,
    QuestionResponse,
)
from app.models.transcription import Transcription
from app.models.video import Video
from app.services import generate_questions_with_ollama, retrieve_transcriptions_for_videos, check_ollama_health


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/generate",
    response_model=GenerateQuestionsResponse,
    status_code=status.HTTP_200_OK
)
def generate_questions(
    request: GenerateQuestionsRequest,
    db: Session = Depends(get_db)
):
    """
    Generate questions from transcribed videos using Ollama LLM.
    
    Validates that videos are downloaded and transcribed, then uses AI to generate
    educational questions from the transcription text.
    
    Args:
        request: Request containing list of video IDs
        db: Database session
    
    Returns:
        GenerateQuestionsResponse with per-video results and summary statistics
    
    Raises:
        HTTPException: If no video IDs provided or internal error occurs
    """
    try:
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
        
        logger.info(f"Received question generation request for {len(request.video_ids)} videos")
        
        # Deduplicate video_ids while preserving order
        seen = set()
        unique_video_ids = []
        for video_id in request.video_ids:
            if video_id not in seen:
                seen.add(video_id)
                unique_video_ids.append(video_id)
        
        # Batch fetch all transcriptions up-front to avoid N+1 queries
        transcriptions_dict = retrieve_transcriptions_for_videos(unique_video_ids, db)
        
        # Process each video_id
        results = []
        
        for video_id in unique_video_ids:
            # Query video
            video = db.query(Video).filter_by(video_id=video_id).first()
            
            if not video:
                # Video not found
                result = QuestionGenerationResult(
                    video_id=video_id,
                    status="failed",
                    message="Video not found",
                    error="Video must be downloaded first",
                    questions=None,
                    question_count=0
                )
                results.append(result)
                continue
            
            # Lookup transcription from batch-fetched dict
            transcription = transcriptions_dict.get(video_id)
            
            if not transcription:
                # No transcription available
                result = QuestionGenerationResult(
                    video_id=video_id,
                    status="no_transcription",
                    message="No transcription available",
                    error="Video must be transcribed first",
                    questions=None,
                    question_count=0
                )
                results.append(result)
                continue
            
            # Generate questions using Ollama
            try:
                questions = generate_questions_with_ollama(
                    video_id=video_id,
                    transcription_text=transcription.transcription_text,
                    question_count=5,
                    embedding_vector=transcription.vector_embedding
                )
                
                if not questions:
                    # Empty result from Ollama (graceful degradation)
                    result = QuestionGenerationResult(
                        video_id=video_id,
                        status="failed",
                        message="No questions generated",
                        error="Ollama returned no valid questions",
                        questions=[],
                        question_count=0
                    )
                else:
                    result = QuestionGenerationResult(
                        video_id=video_id,
                        status="success",
                        message=f"Generated {len(questions)} questions using Ollama",
                        questions=questions,
                        question_count=len(questions),
                        error=None
                    )
                results.append(result)
                
            except OllamaConnectionException as e:
                # Ollama unavailable - record as failed for this video
                logger.warning(f"Ollama unavailable for video {video_id}: {e.message}")
                result = QuestionGenerationResult(
                    video_id=video_id,
                    status="failed",
                    message="AI service unavailable",
                    error=e.message,
                    questions=[],
                    question_count=0
                )
                results.append(result)
        
        # Calculate summary statistics
        total = len(results)
        successful = sum(1 for r in results if r.status == "success")
        no_transcription = sum(1 for r in results if r.status == "no_transcription")
        failed = sum(1 for r in results if r.status == "failed")
        total_questions = sum(r.question_count for r in results)
        
        # Create response
        response = GenerateQuestionsResponse(
            results=results,
            total=total,
            successful=successful,
            failed=failed,
            no_transcription=no_transcription,
            total_questions=total_questions
        )
        
        logger.info(
            f"Question generation complete: {successful} successful, "
            f"{failed} failed, {no_transcription} no transcription, "
            f"{total_questions} total questions"
        )
        
        return response
        
    except ValidationException:
        raise
    except OllamaConnectionException:
        # Let global handler convert to 503
        raise
    except Exception as e:
        logger.exception("Unexpected error during question generation")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during question generation"
        )


@router.get("/health", status_code=status.HTTP_200_OK)
def check_questions_health(db: Session = Depends(get_db)):
    """
    Check health of question generation service (Ollama).
    
    Returns:
        Health status with model information and availability
    """
    try:
        from app.services.ollama_service import ollama_client
        from app.config import settings
        
        if ollama_client is None:
            return {
                "status": "offline",
                "message": "Ollama client not initialized",
                "model": settings.ollama_model,
                "available": False
            }
        
        # Check if Ollama is healthy
        is_healthy = check_ollama_health()
        
        if is_healthy:
            # Try to get model list
            try:
                models_response = ollama_client.list()
                available_models = [m['name'] for m in models_response.get('models', [])]
                
                return {
                    "status": "online",
                    "message": "Ollama is available",
                    "model": settings.ollama_model,
                    "available": True,
                    "available_models": available_models
                }
            except Exception as e:
                logger.warning(f"Could not retrieve model list: {e}")
                return {
                    "status": "degraded",
                    "message": "Ollama is available but model list unavailable",
                    "model": settings.ollama_model,
                    "available": True
                }
        else:
            return {
                "status": "degraded",
                "message": "Ollama health check failed",
                "model": settings.ollama_model,
                "available": False
            }
            
    except Exception as e:
        logger.error(f"Error checking Ollama health: {e}")
        return {
            "status": "error",
            "message": f"Health check error: {str(e)}",
            "available": False
        }
