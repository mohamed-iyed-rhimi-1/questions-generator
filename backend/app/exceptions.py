from typing import Optional, Dict, Any

from fastapi import HTTPException, status


class AppException(Exception):
    """Base class for all application exceptions."""
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or 'UNKNOWN_ERROR'
        self.details = details or {}


class VideoDownloadException(AppException):
    """Exception raised when video download fails."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_code='VIDEO_DOWNLOAD_FAILED', details=details)


class TranscriptionException(AppException):
    """Exception raised when transcription fails."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_code='TRANSCRIPTION_FAILED', details=details)


class EmbeddingException(AppException):
    """Exception raised when embedding generation fails."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_code='EMBEDDING_FAILED', details=details)


class OllamaConnectionException(AppException):
    """Exception raised when Ollama connection/communication fails."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_code='OLLAMA_CONNECTION_FAILED', details=details)


class DatabaseException(AppException):
    """Exception raised when database operation fails."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_code='DATABASE_ERROR', details=details)


class ValidationException(AppException):
    """Exception raised when input validation fails."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_code='VALIDATION_ERROR', details=details)


def to_http_exception(exc: AppException) -> HTTPException:
    """Convert AppException to HTTPException for FastAPI."""
    # Map error codes to HTTP status codes
    status_code_map = {
        'VALIDATION_ERROR': status.HTTP_400_BAD_REQUEST,
        'VIDEO_DOWNLOAD_FAILED': status.HTTP_500_INTERNAL_SERVER_ERROR,
        'TRANSCRIPTION_FAILED': status.HTTP_500_INTERNAL_SERVER_ERROR,
        'EMBEDDING_FAILED': status.HTTP_500_INTERNAL_SERVER_ERROR,
        'OLLAMA_CONNECTION_FAILED': status.HTTP_503_SERVICE_UNAVAILABLE,
        'DATABASE_ERROR': status.HTTP_500_INTERNAL_SERVER_ERROR,
    }
    
    status_code = status_code_map.get(exc.error_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    detail = {
        'error_code': exc.error_code,
        'message': exc.message,
        'details': exc.details
    }
    
    return HTTPException(status_code=status_code, detail=detail)
