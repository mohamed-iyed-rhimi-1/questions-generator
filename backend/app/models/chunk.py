from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Float, func
from sqlalchemy.orm import relationship
from app.database import Base


class Chunk(Base):
    """
    Chunk model representing a segment of a video's audio file.
    Created when audio files exceed the maximum chunk size.
    """
    __tablename__ = 'chunks'

    # Primary key
    id = Column(Integer, primary_key=True)
    
    # Foreign key to videos table
    video_id = Column(
        String(64),
        ForeignKey('videos.video_id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    # Chunk metadata
    chunk_index = Column(Integer, nullable=False)  # 0-based index
    file_path = Column(String(1024), nullable=False)
    start_time = Column(Float, nullable=False)  # seconds
    end_time = Column(Float, nullable=False)  # seconds
    duration = Column(Float, nullable=False)  # seconds
    file_size = Column(Integer, nullable=False)  # bytes
    
    # Timestamp
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    
    # Relationships
    video = relationship('Video', back_populates='chunks')
    transcription_chunk = relationship(
        'TranscriptionChunk',
        back_populates='chunk',
        uselist=False,
        cascade='all, delete-orphan'
    )
    
    def __repr__(self):
        return f"<Chunk(video_id='{self.video_id}', index={self.chunk_index})>"
