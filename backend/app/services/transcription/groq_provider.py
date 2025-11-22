"""Groq transcription provider implementation."""

import logging
from pathlib import Path
from typing import Optional
from groq import Groq
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings
from app.exceptions import TranscriptionException
from .base import TranscriptionProvider


logger = logging.getLogger(__name__)


class GroqTranscriptionProvider(TranscriptionProvider):
    """Groq API transcription provider."""
    
    def __init__(self):
        """Initialize Groq provider with API client."""
        if not settings.groq_api_key:
            logger.error("Groq API key not configured")
            raise TranscriptionException("Groq API key is required but not configured")
        
        try:
            self.client = Groq(api_key=settings.groq_api_key)
            logger.info("Groq transcription provider initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Groq client: {e}")
            raise TranscriptionException(f"Failed to initialize Groq client: {e}")
    
    def validate_audio_file(self, audio_path: str) -> bool:
        """
        Validate audio file before transcription.
        
        Args:
            audio_path: Path to the audio file
            
        Returns:
            True if audio is valid, False otherwise
        """
        try:
            audio_file = Path(audio_path)
            
            # Check if file exists
            if not audio_file.exists():
                logger.error(f"Audio file not found: {audio_path}")
                return False

            # Check file size
            file_size = audio_file.stat().st_size
            file_size_mb = file_size / (1024 * 1024)
            
            if file_size < 1024:  # Less than 1KB
                logger.error(f"Audio file too small ({file_size} bytes): {audio_path}")
                return False
            
            # Groq has a 25MB file size limit
            if file_size_mb > 25:
                logger.error(f"Audio file too large for Groq ({file_size_mb:.2f}MB, max 25MB): {audio_path}")
                return False
            
            # Check file extension
            allowed_extensions = {'.mp3', '.mp4', '.mpeg', '.mpga', '.m4a', '.wav', '.webm'}
            if audio_file.suffix.lower() not in allowed_extensions:
                logger.error(f"Unsupported audio format for Groq: {audio_file.suffix}")
                return False
            
            logger.debug(f"Audio validation passed for Groq: {audio_path} ({file_size_mb:.2f}MB)")
            return True
            
        except Exception as e:
            logger.error(f"Audio validation failed for {audio_path}: {e}")
            return False
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((Exception,))
    )
    def transcribe_audio(self, audio_path: str, language: str = "ar") -> Optional[str]:
        """
        Transcribe audio file using Groq API with retry logic.
        
        Args:
            audio_path: Path to the audio file
            language: Language code (default: "ar" for Arabic)
            
        Returns:
            Transcription text or None if failed
        """
        # Validate audio file first
        if not self.validate_audio_file(audio_path):
            logger.error(f"Audio file validation failed for Groq: {audio_path}")
            return None
        
        audio_file = Path(audio_path)
        file_size_mb = audio_file.stat().st_size / (1024 * 1024)

        try:
            logger.info(
                f"Starting Groq transcription for {audio_file.name} ({file_size_mb:.2f}MB)",
                extra={"language": language, "provider": "groq"}
            )
            
            # Open audio file and send to Groq API
            with open(audio_path, "rb") as file:
                transcription = self.client.audio.transcriptions.create(
                    file=(audio_file.name, file.read()),
                    model=settings.groq_model,
                    language=language,
                    response_format="text",
                    temperature=0.0
                )
            
            # Extract text from response
            if isinstance(transcription, str):
                text = transcription.strip()
            else:
                text = str(transcription).strip()
            
            # Validate text is not empty
            if not text:
                logger.warning(f"Groq transcription resulted in empty text for: {audio_path}")
                return None
            elif len(text) < 10:
                logger.warning(f"Groq transcription seems too short ({len(text)} chars): {audio_path}")
            
            # Check if text contains Arabic characters
            arabic_char_count = sum(1 for char in text if '\u0600' <= char <= '\u06FF')
            total_chars = len(text)
            arabic_percentage = (arabic_char_count / total_chars * 100) if total_chars > 0 else 0
            
            logger.info(
                f"Successfully transcribed {audio_file.name} with Groq",
                extra={
                    "text_length": len(text),
                    "file_size_mb": round(file_size_mb, 2),
                    "language": language,
                    "arabic_percentage": round(arabic_percentage, 1),
                    "provider": "groq"
                }
            )
            
            # Preview first 100 characters (for debugging)
            logger.debug(f"Transcription preview: {text[:100]}...")
            
            return text

        except Exception as e:
            error_msg = str(e)
            
            # Handle authentication errors
            if "authentication" in error_msg.lower() or "api key" in error_msg.lower() or "401" in error_msg:
                logger.error(f"Groq authentication error: {e}")
                raise TranscriptionException("Groq API authentication failed. Please check your API key.")
            
            # Handle rate limiting errors
            if "rate limit" in error_msg.lower() or "429" in error_msg:
                logger.warning(f"Groq rate limit exceeded: {e}")
                raise  # Let retry handle it
            
            # Handle network errors
            if any(keyword in error_msg.lower() for keyword in ["connection", "timeout", "network"]):
                logger.warning(f"Groq network error: {e}")
                raise  # Let retry handle it
            
            # Handle file size errors
            if "file size" in error_msg.lower() or "too large" in error_msg.lower():
                logger.error(f"Groq file size error: {e}")
                return None
            
            # Other errors
            logger.error(
                f"Groq transcription error for {audio_path}: {e}",
                extra={"error_type": type(e).__name__},
                exc_info=True
            )
            
            return None
