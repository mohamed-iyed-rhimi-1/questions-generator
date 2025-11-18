from app.schemas.video import (
    DownloadVideosRequest,
    VideoResponse,
    DownloadResult,
    DownloadVideosResponse,
)
from app.schemas.transcription import (
    TranscribeVideosRequest,
    TranscriptionResponse,
    TranscriptionResult,
    TranscribeVideosResponse,
    TranscriptionListResponse,
)
from app.schemas.question import (
    GenerateQuestionsRequest,
    QuestionResponse,
    QuestionGenerationResult,
    GenerateQuestionsResponse,
)

__all__ = [
    "DownloadVideosRequest",
    "VideoResponse",
    "DownloadResult",
    "DownloadVideosResponse",
    "TranscribeVideosRequest",
    "TranscriptionResponse",
    "TranscriptionResult",
    "TranscribeVideosResponse",
    "TranscriptionListResponse",
    "GenerateQuestionsRequest",
    "QuestionResponse",
    "QuestionGenerationResult",
    "GenerateQuestionsResponse",
]
