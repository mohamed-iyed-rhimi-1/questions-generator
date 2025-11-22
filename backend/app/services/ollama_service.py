"""
Question generation service with provider abstraction.

This module provides a unified interface for question generation using different
providers (Ollama, OpenRouter). The provider is selected based on configuration
and initialized conditionally.
"""

import logging
from typing import Optional, List, Dict
from sqlalchemy.orm import Session

from app.config import settings
from app.models.transcription import Transcription
from app.schemas.question import QuestionResponse
from app.exceptions import OllamaConnectionException
from app.services.question_generation import (
    QuestionGenerationProvider,
    OllamaProvider,
    OpenRouterProvider
)


# Configure logger
logger = logging.getLogger(__name__)

# Initialize provider based on configuration
_provider: Optional[QuestionGenerationProvider] = None

def _get_provider() -> QuestionGenerationProvider:
    """
    Get or initialize the question generation provider.
    
    Provider is initialized lazily on first use based on configuration.
    
    Returns:
        QuestionGenerationProvider instance
        
    Raises:
        OllamaConnectionException: If provider initialization fails
    """
    global _provider
    
    if _provider is None:
        provider_name = settings.question_generation_provider.lower()
        
        logger.info(
            f"Initializing question generation provider",
            extra={"provider": provider_name}
        )
        
        if provider_name == "ollama":
            _provider = OllamaProvider()
        elif provider_name == "openrouter":
            _provider = OpenRouterProvider()
        else:
            raise OllamaConnectionException(
                f"Unknown question generation provider: {provider_name}",
                details={"provider": provider_name}
            )
        
        logger.info(
            f"Question generation provider initialized",
            extra={"provider": provider_name}
        )
    
    return _provider


def generate_questions_with_ollama(
    video_id: str,
    transcription_text: str,
    question_count: int = 5,
    embedding_vector: Optional[List[float]] = None
) -> List[QuestionResponse]:
    """
    Generate questions using the configured provider.
    
    This is the main entry point for question generation. It delegates to the
    configured provider (Ollama or OpenRouter) based on settings.
    
    Args:
        video_id: ID of the video
        transcription_text: The transcription text to generate questions from
        question_count: Number of questions to generate (default: 5)
        embedding_vector: Optional 384-dim embedding vector from pgvector
        
    Returns:
        List of QuestionResponse objects (empty list on error)
        
    Raises:
        OllamaConnectionException: If provider is unavailable or fails
    """
    provider = _get_provider()
    
    logger.info(
        f"Generating questions using provider",
        extra={
            "provider": settings.question_generation_provider,
            "video_id": video_id,
            "question_count": question_count
        }
    )
    
    return provider.generate_questions(
        video_id=video_id,
        transcription_text=transcription_text,
        question_count=question_count,
        embedding_vector=embedding_vector
    )


def retrieve_transcriptions_for_videos(
    video_ids: List[str],
    session: Session
) -> Dict[str, Transcription]:
    """
    Batch retrieve transcriptions for multiple videos.
    
    This is more efficient than querying each video individually.
    Returns a lookup dict for O(1) access by video_id.
    
    Args:
        video_ids: List of video IDs to retrieve transcriptions for
        session: Database session
        
    Returns:
        Dict mapping video_id to Transcription object
    """
    transcriptions = session.query(Transcription).filter(
        Transcription.video_id.in_(video_ids)
    ).all()
    
    return {t.video_id: t for t in transcriptions}


def check_ollama_health() -> bool:
    """
    Check if the configured question generation provider is healthy.
    
    Returns:
        True if provider is healthy and available, False otherwise.
    """
    try:
        provider = _get_provider()
        return provider.check_health()
    except Exception as e:
        logger.error(
            f"Health check failed for provider",
            extra={
                "provider": settings.question_generation_provider,
                "error": str(e)
            }
        )
        return False
