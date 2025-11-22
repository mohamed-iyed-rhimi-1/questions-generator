from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional, List, Dict, Any


class DownloadVideosRequest(BaseModel):
    """Request schema for downloading YouTube videos."""
    urls: List[str] = Field(
        min_length=1,
        description="List of YouTube video URLs to download"
    )


class VideoResponse(BaseModel):
    """Response schema for video data."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    video_id: str
    title: str
    thumbnail_url: Optional[str] = None
    file_path: Optional[str] = None
    created_at: datetime
    download_status: str = "completed"
    
    # Chunk support fields
    has_chunks: bool = False
    chunk_count: int = 0


class DownloadResult(BaseModel):
    """Result schema for individual video download."""
    url: str
    status: str
    message: str
    video_id: Optional[str] = None
    video: Optional[VideoResponse] = None
    error: Optional[str] = None


class DownloadVideosResponse(BaseModel):
    """Response schema for batch video downloads."""
    results: List[DownloadResult]
    total: int
    successful: int
    duplicates: int
    failed: int


class DependencyErrorResponse(BaseModel):
    """Response schema for dependency violation errors (409 Conflict)."""
    error: str = Field(default="dependency_violation", description="Error type identifier")
    message: str = Field(description="Human-readable error message")
    details: Dict[str, Any] = Field(description="Additional error details")
    dependent_resources: List[Dict[str, Any]] = Field(
        description="List of dependent resources preventing deletion"
    )
