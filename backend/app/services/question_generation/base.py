"""
Base provider interface for question generation.

This module defines the abstract base class that all question generation providers
must implement, ensuring a consistent interface across different providers.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from app.schemas.question import GeneratedQuestion


class QuestionGenerationProvider(ABC):
    """
    Abstract base class for question generation providers.
    
    All question generation providers (Ollama, OpenRouter, etc.) must implement
    this interface to ensure consistent behavior across the application.
    """
    
    @abstractmethod
    def generate_questions(
        self,
        video_id: str,
        transcription_text: str,
        question_count: int = 5,
        embedding_vector: Optional[List[float]] = None
    ) -> List[GeneratedQuestion]:
        """
        Generate educational questions from transcription text.
        
        Args:
            video_id: ID of the video
            transcription_text: The transcription text to generate questions from
            question_count: Number of questions to generate (default: 5)
            embedding_vector: Optional 384-dim embedding vector from pgvector
            
        Returns:
            List of GeneratedQuestion objects (empty list on error)
            
        Raises:
            OllamaConnectionException: If the provider is unavailable or fails
        """
        pass
    
    @abstractmethod
    def check_health(self) -> bool:
        """
        Check if the provider is available and healthy.
        
        Returns:
            True if the provider is healthy and ready to generate questions,
            False otherwise.
        """
        pass
