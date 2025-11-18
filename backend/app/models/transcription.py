from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Text, func
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.database import Base


class Transcription(Base):
    """
    Transcription model representing a video transcription with vector embeddings.
    Supports semantic search via pgvector extension.
    """
    __tablename__ = 'transcriptions'

    # Primary key
    id = Column(Integer, primary_key=True)
    
    # Foreign key to videos table
    video_id = Column(
        String(64),
        ForeignKey('videos.video_id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    # Transcription content
    transcription_text = Column(Text, nullable=False)
    
    # Vector embedding for semantic search
    # 384 dimensions for sentence-transformers 'all-MiniLM-L6-v2' model
    vector_embedding = Column(Vector(384), nullable=True)  # Generated after transcription
    
    # Timestamp
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    
    # Relationships
    video = relationship('Video', back_populates='transcriptions')

    def __repr__(self):
        return f"<Transcription(id={self.id}, video_id='{self.video_id}')>"
