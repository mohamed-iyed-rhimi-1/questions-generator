"""
API endpoints for generation management.

Provides CRUD operations for generation sessions and their associated questions.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import logging

from app.database import get_db
from app.exceptions import ValidationException, DatabaseException
from app.schemas import (
    GenerationListResponse,
    GenerationResponse,
    GenerationDetailResponse,
    QuestionResponse,
    UpdateQuestionRequest,
    UpdateQuestionsOrderRequest,
)
from app.models import Generation, Question

router = APIRouter()
logger = logging.getLogger(__name__)



@router.get("", response_model=GenerationListResponse)
def list_generations(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    List all generations with pagination.
    
    Returns a paginated list of all generation sessions, ordered by creation date (newest first).
    Each generation includes metadata about the number of questions and source videos.
    """
    # Validate pagination parameters
    if skip < 0:
        raise ValidationException(
            "Skip parameter must be non-negative",
            details={"field": "skip", "value": skip}
        )
    
    if limit < 1:
        raise ValidationException(
            "Limit parameter must be positive",
            details={"field": "limit", "value": limit}
        )
    
    if limit > 1000:
        limit = 1000
    
    try:
        # Query generations ordered by created_at DESC
        generations = db.query(Generation).order_by(
            Generation.created_at.desc()
        ).offset(skip).limit(limit).all()
        
        # Get total count
        total = db.query(Generation).count()
        
        # Convert ORM objects to Pydantic schemas
        generation_responses = [
            GenerationResponse.model_validate(gen) for gen in generations
        ]
        
        return GenerationListResponse(
            generations=generation_responses,
            total=total
        )
        
    except ValidationException:
        raise
    except Exception as e:
        logger.exception("Error listing generations")
        raise DatabaseException(
            "Failed to retrieve generations",
            details={"error": str(e)}
        )



@router.get("/{generation_id}", response_model=GenerationDetailResponse)
def get_generation(
    generation_id: int,
    db: Session = Depends(get_db)
):
    """
    Get details for a specific generation by ID.
    
    Returns generation metadata along with all associated questions,
    ordered by their order_index. Questions are eagerly loaded for efficiency.
    """
    try:
        # Query generation with eager loading of questions
        from sqlalchemy.orm import joinedload
        
        generation = db.query(Generation).options(
            joinedload(Generation.questions)
        ).filter(Generation.id == generation_id).first()
        
        if generation is None:
            raise ValidationException(
                f"Generation with ID {generation_id} not found",
                details={"generation_id": generation_id}
            )
        
        # Sort questions by order_index (in Python since they're already loaded)
        generation.questions.sort(key=lambda q: q.order_index)
        
        # Convert to Pydantic schema
        return GenerationDetailResponse.model_validate(generation)
        
    except ValidationException:
        raise
    except Exception as e:
        logger.exception(f"Error retrieving generation {generation_id}")
        raise DatabaseException(
            "Failed to retrieve generation",
            details={"generation_id": generation_id, "error": str(e)}
        )



@router.put("/{generation_id}/questions/{question_id}", response_model=QuestionResponse)
def update_question(
    generation_id: int,
    question_id: int,
    request: UpdateQuestionRequest,
    db: Session = Depends(get_db)
):
    """
    Update a specific question within a generation.
    
    Allows updating question text, context, difficulty, type, and order.
    Only provided fields will be updated. The updated_at timestamp is automatically set.
    """
    try:
        # Verify generation exists
        generation = db.query(Generation).filter(
            Generation.id == generation_id
        ).first()
        
        if generation is None:
            raise ValidationException(
                f"Generation with ID {generation_id} not found",
                details={"generation_id": generation_id}
            )
        
        # Query the question and verify it belongs to the generation
        question = db.query(Question).filter(
            Question.id == question_id,
            Question.generation_id == generation_id
        ).first()
        
        if question is None:
            raise ValidationException(
                f"Question with ID {question_id} not found in generation {generation_id}",
                details={"generation_id": generation_id, "question_id": question_id}
            )
        
        # Update only the provided fields
        update_data = request.model_dump(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(question, field, value)
        
        # Commit changes (updated_at is automatically set by onupdate)
        db.commit()
        db.refresh(question)
        
        logger.info(f"Updated question {question_id} in generation {generation_id}")
        
        # Convert to Pydantic schema
        return QuestionResponse.model_validate(question)
        
    except ValidationException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Error updating question {question_id}")
        raise DatabaseException(
            "Failed to update question",
            details={"generation_id": generation_id, "question_id": question_id, "error": str(e)}
        )



@router.delete("/{generation_id}/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question(
    generation_id: int,
    question_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a specific question from a generation.
    
    Removes the question from the database and updates the generation's question_count.
    Returns 204 No Content on success.
    """
    try:
        # Verify generation exists
        generation = db.query(Generation).filter(
            Generation.id == generation_id
        ).first()
        
        if generation is None:
            raise ValidationException(
                f"Generation with ID {generation_id} not found",
                details={"generation_id": generation_id}
            )
        
        # Query the question and verify it belongs to the generation
        question = db.query(Question).filter(
            Question.id == question_id,
            Question.generation_id == generation_id
        ).first()
        
        if question is None:
            raise ValidationException(
                f"Question with ID {question_id} not found in generation {generation_id}",
                details={"generation_id": generation_id, "question_id": question_id}
            )
        
        # Delete the question
        db.delete(question)
        
        # Update generation question_count
        generation.question_count = max(0, generation.question_count - 1)
        
        # Commit changes
        db.commit()
        
        logger.info(f"Deleted question {question_id} from generation {generation_id}")
        
        return None
        
    except ValidationException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Error deleting question {question_id}")
        raise DatabaseException(
            "Failed to delete question",
            details={"generation_id": generation_id, "question_id": question_id, "error": str(e)}
        )



@router.put("/{generation_id}/questions/reorder", response_model=GenerationDetailResponse)
def reorder_questions(
    generation_id: int,
    request: UpdateQuestionsOrderRequest,
    db: Session = Depends(get_db)
):
    """
    Reorder questions within a generation.
    
    Accepts an ordered list of question IDs and updates their order_index
    based on their position in the array. Returns the updated generation with
    all questions in the new order.
    """
    try:
        # Verify generation exists
        from sqlalchemy.orm import joinedload
        
        generation = db.query(Generation).filter(
            Generation.id == generation_id
        ).first()
        
        if generation is None:
            raise ValidationException(
                f"Generation with ID {generation_id} not found",
                details={"generation_id": generation_id}
            )
        
        # Verify all question IDs belong to this generation
        question_ids = request.question_ids
        questions = db.query(Question).filter(
            Question.id.in_(question_ids),
            Question.generation_id == generation_id
        ).all()
        
        if len(questions) != len(question_ids):
            found_ids = {q.id for q in questions}
            missing_ids = set(question_ids) - found_ids
            raise ValidationException(
                f"Some question IDs not found in generation {generation_id}",
                details={
                    "generation_id": generation_id,
                    "missing_question_ids": list(missing_ids)
                }
            )
        
        # Create a mapping of question_id to question object
        question_map = {q.id: q for q in questions}
        
        # Update order_index for each question based on position in array
        for index, question_id in enumerate(question_ids):
            question = question_map[question_id]
            question.order_index = index
        
        # Commit changes
        db.commit()
        
        # Reload generation with questions for response
        generation = db.query(Generation).options(
            joinedload(Generation.questions)
        ).filter(Generation.id == generation_id).first()
        
        # Sort questions by order_index
        generation.questions.sort(key=lambda q: q.order_index)
        
        logger.info(f"Reordered {len(question_ids)} questions in generation {generation_id}")
        
        # Convert to Pydantic schema
        return GenerationDetailResponse.model_validate(generation)
        
    except ValidationException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Error reordering questions in generation {generation_id}")
        raise DatabaseException(
            "Failed to reorder questions",
            details={"generation_id": generation_id, "error": str(e)}
        )



@router.delete("/{generation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_generation(
    generation_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a generation and all its associated questions.
    
    Removes the generation from the database. All associated questions are
    automatically deleted via cascade delete. Returns 204 No Content on success.
    """
    try:
        # Query the generation
        generation = db.query(Generation).filter(
            Generation.id == generation_id
        ).first()
        
        if generation is None:
            raise ValidationException(
                f"Generation with ID {generation_id} not found",
                details={"generation_id": generation_id}
            )
        
        # Get question count for logging
        question_count = generation.question_count
        
        # Delete the generation (cascade will delete all questions)
        db.delete(generation)
        db.commit()
        
        logger.info(
            f"Deleted generation {generation_id} with {question_count} questions"
        )
        
        return None
        
    except ValidationException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Error deleting generation {generation_id}")
        raise DatabaseException(
            "Failed to delete generation",
            details={"generation_id": generation_id, "error": str(e)}
        )
