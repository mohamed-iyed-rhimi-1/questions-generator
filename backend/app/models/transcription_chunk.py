from sqlalchemy import Column, DateTime, Integer, ForeignKey, Text, func
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.database import Base


class TranscriptionChunk(Base):
    """
    TranscriptionChunk model representing transcription of a single audio chunk.
    Links transcriptions to specific chunks with independent embeddings.
    """
    __tablename__ = 'transcription_chunks'

    # Primary key
    id = Column(Integer, primary_key=True)
    
    # Foreign keys
    transcription_id = Column(
        Integer,
        ForeignKey('transcriptions.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    chunk_id = Column(
        Integer,
        ForeignKey('chunks.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    # Chunk transcription content
    chunk_text = Column(Text, nullable=False)
    
    # Vector embedding for this chunk (384 dimensions)
    vector_embedding = Column(Vector(384), nullable=True)
    
    # Timestamp
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    
    # Relationships
    transcription = relationship('Transcription', back_populates='chunks')
    chunk = relationship('Chunk', back_populates='transcription_chunk')
    
    def __repr__(self):
        return f"<TranscriptionChunk(id={self.id}, chunk_id={self.chunk_id})>"
