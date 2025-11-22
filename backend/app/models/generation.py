from sqlalchemy import Column, Integer, DateTime, ARRAY, String, func
from sqlalchemy.orm import relationship
from app.database import Base


class Generation(Base):
    """
    Generation model representing a question generation session.
    Tracks when questions were generated and from which videos.
    """
    __tablename__ = 'generations'

    # Primary key
    id = Column(Integer, primary_key=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Array of video IDs used for this generation
    video_ids = Column(ARRAY(String), nullable=False)
    
    # Total count of questions in this generation
    question_count = Column(Integer, nullable=False, default=0)
    
    # Relationships
    questions = relationship(
        'Question',
        back_populates='generation',
        cascade='all, delete-orphan'  # Delete questions when generation is deleted
    )

    def __repr__(self):
        return f"<Generation(id={self.id}, question_count={self.question_count}, created_at='{self.created_at}')>"
