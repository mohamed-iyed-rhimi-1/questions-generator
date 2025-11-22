"""
Pydantic schemas for generation management API operations.

These schemas provide type safety and automatic OpenAPI documentation
for generation session tracking and management.
"""

from datetime import datetime
from typing import List
from pydantic import BaseModel, ConfigDict


class GenerationBase(BaseModel):
    """Base schema for generation data."""
    
    video_ids: List[str]
    question_count: int


class GenerationResponse(GenerationBase):
    """Response schema for a generation record."""
    
    id: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class GenerationDetailResponse(GenerationResponse):
    """Detailed response schema for a generation with its questions."""
    
    questions: List["QuestionResponse"]


class GenerationListResponse(BaseModel):
    """Response schema for listing generations."""
    
    generations: List[GenerationResponse]
    total: int


# Import QuestionResponse for type hint resolution
from app.schemas.question import QuestionResponse

# Update forward references
GenerationDetailResponse.model_rebuild()
