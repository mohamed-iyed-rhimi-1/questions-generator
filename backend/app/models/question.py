from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base


class Question(Base):
    """
    Question model representing an AI-generated educational question.
    Associated with a generation session and source video.
    """
    __tablename__ = 'questions'

    # Primary key
    id = Column(Integer, primary_key=True)
    
    # Foreign key to generations table
    generation_id = Column(
        Integer,
        ForeignKey('generations.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    # Foreign key to videos table
    video_id = Column(
        String(64),
        ForeignKey('videos.video_id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    # Question content
    question_text = Column(Text, nullable=False)
    answer = Column(Text, nullable=True)  # Comprehensive answer to the question
    context = Column(Text, nullable=True)  # Context from transcription
    
    # Question metadata
    difficulty = Column(String(20), nullable=True)  # easy, medium, hard
    question_type = Column(String(50), nullable=True)  # factual, conceptual, analytical
    
    # Order within the generation
    order_index = Column(Integer, nullable=False, default=0, index=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    generation = relationship('Generation', back_populates='questions')
    video = relationship('Video')

    def __repr__(self):
        return f"<Question(id={self.id}, generation_id={self.generation_id}, video_id='{self.video_id}')>"
