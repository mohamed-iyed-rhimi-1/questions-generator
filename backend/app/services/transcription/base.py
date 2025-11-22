"""Base transcription provider interface."""

from abc import ABC, abstractmethod
from typing import Optional


class TranscriptionProvider(ABC):
    """Abstract base class for transcription providers."""
    
    @abstractmethod
    def transcribe_audio(self, audio_path: str, language: str = "ar") -> Optional[str]:
        """
        Transcribe audio file to text.
        
        Args:
            audio_path: Path to the audio file
            language: Language code (default: "ar" for Arabic)
            
        Returns:
            Transcription text or None if failed
        """
        pass
    
    @abstractmethod
    def validate_audio_file(self, audio_path: str) -> bool:
        """
        Validate audio file before transcription.
        
        Args:
            audio_path: Path to the audio file
            
        Returns:
            True if audio is valid, False otherwise
        """
        pass
