from sqlalchemy import Column, String, DateTime, Integer, func
from sqlalchemy.orm import relationship
from app.database import Base


class Video(Base):
    """
    Video model representing a YouTube video in the system.
    Stores video metadata and file path to downloaded audio.
    """
    __tablename__ = 'videos'

    # Primary key
    id = Column(Integer, primary_key=True)
    
    # YouTube video identifier (extracted from URL)
    video_id = Column(String(64), unique=True, nullable=False)
    
    # Video metadata
    title = Column(String(512), nullable=False)
    thumbnail_url = Column(String(1024), nullable=True)  # Nullable in case download fails
    
    # File system path to downloaded MP3
    file_path = Column(String(1024), nullable=True)  # Nullable until download completes
    
    # Timestamp
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    
    # Relationships
    transcriptions = relationship(
        'Transcription',
        back_populates='video',
        cascade='all, delete-orphan'  # Delete transcriptions when video is deleted
    )
    chunks = relationship(
        'Chunk',
        back_populates='video',
        cascade='all, delete-orphan',
        order_by='Chunk.chunk_index'
    )

    def __repr__(self):
        return f"<Video(video_id='{self.video_id}', title='{self.title}')>"
