from pydantic import BaseModel, ConfigDict
from datetime import datetime


class ChunkResponse(BaseModel):
    """Response schema for chunk data."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    video_id: str
    chunk_index: int
    file_path: str
    start_time: float
    end_time: float
    duration: float
    file_size: int
    created_at: datetime
