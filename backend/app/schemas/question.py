"""
Pydantic schemas for question generation API operations.

These schemas provide type safety and automatic OpenAPI documentation.
Questions are transient (response-only) until Ollama integration in next phase.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class GenerateQuestionsRequest(BaseModel):
    """Request schema for generating questions from videos."""
    
    video_ids: List[str] = Field(
        min_length=1,
        description="List of YouTube video IDs to generate questions from"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "video_ids": ["abc123", "xyz789"]
            }
        }
    )


class QuestionResponse(BaseModel):
    """
    Response schema for a single generated question.
    
    Note: This is a response-only schema (no database model).
    Questions are transient until Ollama integration in next phase.
    """
    
    id: str
    video_id: str
    question_text: str
    context: Optional[str] = None
    difficulty: Optional[str] = None
    question_type: Optional[str] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class QuestionGenerationResult(BaseModel):
    """Per-video generation result returned by the generate endpoint."""
    
    video_id: str
    status: str  # One of: "success", "no_transcription", "failed"
    message: str
    questions: Optional[List[QuestionResponse]] = None
    error: Optional[str] = None
    question_count: int = 0


class GenerateQuestionsResponse(BaseModel):
    """Wrapper for batch question generation results with summary statistics."""
    
    results: List[QuestionGenerationResult]
    total: int
    successful: int
    failed: int
    no_transcription: int
    total_questions: int
