from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional, List


class TranscribeVideosRequest(BaseModel):
    """Request schema for batch video transcription."""
    video_ids: List[str] = Field(
        min_length=1,
        description="List of YouTube video IDs to transcribe"
    )


class TranscriptionResponse(BaseModel):
    """Response schema for a single transcription."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    video_id: str
    transcription_text: str
    vector_embedding: Optional[List[float]] = None
    created_at: datetime
    status: str = "completed"


class TranscriptionResult(BaseModel):
    """Result schema for a single video transcription attempt."""
    video_id: str
    status: str  # "success", "not_found", "no_audio", "failed"
    message: str
    transcription: Optional[TranscriptionResponse] = None
    error: Optional[str] = None
    steps_completed: int = 0
    total_steps: int = 5
    
    @property
    def progress(self) -> float:
        """Calculate progress as a percentage (0-100)."""
        if self.total_steps == 0:
            return 0.0
        return (self.steps_completed / self.total_steps) * 100


class TranscribeVideosResponse(BaseModel):
    """Response schema for batch video transcription."""
    results: List[TranscriptionResult]
    total: int
    successful: int
    failed: int
    not_found: int = 0
    no_audio: int = 0


class TranscriptionListResponse(BaseModel):
    """Response schema for listing transcriptions."""
    transcriptions: List[TranscriptionResponse]
    total: int
