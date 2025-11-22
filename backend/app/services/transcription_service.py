from sentence_transformers import SentenceTransformer
from pathlib import Path
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, IntegrityError
import numpy as np
import logging
import torch
from tenacity import retry, stop_after_attempt, wait_fixed, wait_exponential, retry_if_exception_type

from app.config import settings
from app.models.video import Video
from app.models.transcription import Transcription
from app.models.chunk import Chunk
from app.models.transcription_chunk import TranscriptionChunk
from app.exceptions import TranscriptionException, EmbeddingException, DatabaseException
from app.services.transcription import TranscriptionProvider, WhisperTranscriptionProvider, GroqTranscriptionProvider
from app.services.chunk_service import get_chunks_for_video

# Module-level logger
logger = logging.getLogger(__name__)

# Load models once at module level for efficiency
transcription_provider: Optional[TranscriptionProvider] = None
embedding_model = None


def _initialize_transcription_provider() -> TranscriptionProvider:
    """Initialize the transcription provider based on configuration."""
    provider_name = settings.transcription_provider.lower()
    
    logger.info(f"Initializing transcription provider: {provider_name}")
    
    if provider_name == 'whisper':
        return WhisperTranscriptionProvider()
    elif provider_name == 'groq':
        return GroqTranscriptionProvider()
    else:
        raise ValueError(f"Unknown transcription provider: {provider_name}")


def clear_gpu_cache():
    """Clear GPU cache for both CUDA and MPS devices."""
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    elif torch.backends.mps.is_available():
        torch.mps.empty_cache()

try:
    transcription_provider = _initialize_transcription_provider()
    logger.info(f"Transcription provider initialized: {settings.transcription_provider}")
except Exception as e:
    logger.critical(
        f"Failed to initialize transcription provider '{settings.transcription_provider}': {e}",
        exc_info=True
    )
    transcription_provider = None

# Lazy load embedding model to speed up startup
embedding_model = None
_embedding_model_loading = False


def _get_embedding_model():
    """
    Lazy load embedding model on first use.
    This speeds up application startup significantly.
    """
    global embedding_model, _embedding_model_loading
    
    if embedding_model is not None:
        return embedding_model
    
    if _embedding_model_loading:
        # Prevent concurrent loading attempts
        import time
        max_wait = 30  # seconds
        waited = 0
        while embedding_model is None and waited < max_wait:
            time.sleep(0.5)
            waited += 0.5
        return embedding_model
    
    _embedding_model_loading = True
    
    try:
        logger.info("Loading embedding model (first use)...")
        
        # Determine device
        if torch.cuda.is_available():
            embedding_device = 'cuda'
        elif torch.backends.mps.is_available():
            embedding_device = 'mps'
        else:
            embedding_device = 'cpu'
        
        embedding_model = SentenceTransformer(settings.embedding_model_name, device=embedding_device)
        logger.info(
            f"Loaded embedding model: {settings.embedding_model_name}",
            extra={"dimensions": settings.embedding_dim, "device": embedding_device}
        )
        return embedding_model
        
    except Exception as e:
        logger.critical(f"Failed to load embedding model: {e}", exc_info=True)
        return None
    finally:
        _embedding_model_loading = False


def validate_audio_file(audio_path: str) -> bool:
    """
    Validate audio file using the configured transcription provider.
    
    Args:
        audio_path: Path to the audio file
        
    Returns:
        True if audio is valid, False otherwise
    """
    if transcription_provider is None:
        logger.error("Transcription provider not initialized")
        return False
    
    return transcription_provider.validate_audio_file(audio_path)


def transcribe_audio(audio_path: str, language: str = "ar") -> Optional[str]:
    """
    Transcribe audio file using the configured transcription provider.
    
    Args:
        audio_path: Path to the audio file (MP3)
        language: Language code (default: "ar" for Arabic)
        
    Returns:
        Transcription text or None if failed
    """
    if transcription_provider is None:
        logger.error("Transcription provider not initialized")
        raise TranscriptionException("Transcription provider not initialized. Please restart the application.")
    
    logger.info(
        f"Transcribing audio with provider: {settings.transcription_provider}",
        extra={"audio_path": audio_path, "language": language, "provider": settings.transcription_provider}
    )
    
    return transcription_provider.transcribe_audio(audio_path, language)

@retry(
    stop=stop_after_attempt(2),
    wait=wait_fixed(3),
    retry=retry_if_exception_type((RuntimeError, torch.cuda.OutOfMemoryError))
)
def generate_embedding(text: str) -> Optional[List[float]]:
    """
    Generate vector embedding from text using configured embedding model.
    Retries up to 2 times for transient failures.
    Model is loaded lazily on first use to speed up application startup.
    
    Args:
        text: Text to encode
        
    Returns:
        List of floats (normalized for cosine similarity) or None if failed
    """
    model = _get_embedding_model()
    if model is None:
        logger.error("Embedding model not loaded")
        raise EmbeddingException("Embedding model failed to load. Please check logs and restart.")
    
    # Validate text is not empty
    if not text or not text.strip():
        logger.error("Cannot generate embedding for empty text")
        return None
    
    # Validate text length
    text_length = len(text)
    if text_length < 50:
        logger.warning(
            f"Text very short ({text_length} chars) - embedding quality may be poor"
        )
    elif text_length > 100000:
        logger.warning(
            f"Text very long ({text_length} chars) - truncating to 100K chars"
        )
        text = text[:100000]
    
    try:
        # Generate embedding with normalization for cosine similarity
        embedding = model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False
        )
        
        # Convert numpy array to Python list
        embedding_list = embedding.tolist()
        
        # Validate embedding dimension matches configuration
        if len(embedding_list) != settings.embedding_dim:
            logger.error(
                f"Invalid embedding dimension: {len(embedding_list)} "
                f"(expected {settings.embedding_dim} from config)"
            )
            return None
        
        # Quality checks
        embedding_array = np.array(embedding_list)
        
        # Check for all zeros (model failure)
        if np.all(embedding_array == 0):
            logger.error("Embedding is all zeros - model failure")
            return None
        
        # Check for NaN values
        if np.any(np.isnan(embedding_array)):
            logger.error("Embedding contains NaN values")
            return None
        
        # Verify normalization (L2 norm should be ~1.0)
        l2_norm = np.linalg.norm(embedding_array)
        if not (0.99 <= l2_norm <= 1.01):
            logger.warning(f"Embedding L2 norm is {l2_norm:.4f} (expected ~1.0)")
        
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        logger.info(
            f"Generated embedding for text",
            extra={
                "text_length": text_length,
                "embedding_dim": len(embedding_list),
                "mean": round(float(embedding_array.mean()), 4),
                "std": round(float(embedding_array.std()), 4),
                "device": device
            }
        )
        return embedding_list
        
    except (torch.cuda.OutOfMemoryError, RuntimeError) as e:
        # Handle OOM for both CUDA and MPS
        if "out of memory" in str(e).lower():
            logger.error(f"GPU out of memory during embedding generation: {e}")
            clear_gpu_cache()
            raise
        
        # Other runtime errors
        logger.error(
            f"Embedding generation runtime error: {e}",
            extra={"error_type": "RuntimeError"},
            exc_info=True
        )
        clear_gpu_cache()
        raise
        
    except Exception as e:
        logger.error(
            f"Embedding generation error: {e}",
            extra={"error_type": type(e).__name__},
            exc_info=True
        )
        clear_gpu_cache()
        return None

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(OperationalError)
)
def save_transcription_to_db(session: Session, transcription_data: Dict[str, Any]) -> Transcription:
    """
    Save transcription to database. Retries up to 3 times for connection issues.
    
    Args:
        session: Database session
        transcription_data: Dictionary with video_id, transcription_text, vector_embedding
        
    Returns:
        Saved Transcription object
        
    Raises:
        DatabaseException if database operation fails
    """
    video_id = transcription_data.get('video_id')
    
    try:
        transcription = Transcription(**transcription_data)
        session.add(transcription)
        session.commit()
        session.refresh(transcription)
        
        # Log metadata
        text_length = len(transcription_data.get('transcription_text', ''))
        vector_embedding = transcription_data.get('vector_embedding', [])
        embedding_dim = len(vector_embedding) if vector_embedding else 0
        
        logger.info(
            f"Saved transcription to database",
            extra={
                "transcription_id": transcription.id,
                "video_id": video_id,
                "text_length": text_length,
                "embedding_dim": embedding_dim
            }
        )
        return transcription
        
    except IntegrityError as e:
        session.rollback()
        logger.error(
            f"Database integrity error saving transcription",
            extra={"video_id": video_id, "error": str(e)}
        )
        raise DatabaseException(
            f"Transcription already exists for video {video_id}",
            details={"video_id": video_id}
        )
    except OperationalError as e:
        session.rollback()
        logger.error(
            f"Database operational error saving transcription",
            extra={"video_id": video_id, "error": str(e)}
        )
        raise  # Let retry handle it
    except Exception as e:
        session.rollback()
        logger.error(
            f"Unexpected database error saving transcription",
            extra={"video_id": video_id, "error": str(e), "error_type": type(e).__name__}
        )
        raise DatabaseException(
            f"Failed to save transcription for video {video_id}",
            details={"video_id": video_id}
        )


def transcribe_chunk(chunk: Chunk, language: str = "ar") -> Optional[str]:
    """
    Transcribe a single audio chunk.
    
    Args:
        chunk: Chunk object with file_path
        language: Language code (default: "ar" for Arabic)
        
    Returns:
        Transcription text or None if failed
        
    Raises:
        FileNotFoundError: If chunk file doesn't exist
    """
    # Validate chunk file exists before transcription
    chunk_path = Path(chunk.file_path)
    if not chunk_path.exists():
        error_msg = (
            f"Chunk file not found: chunk index {chunk.chunk_index}, "
            f"file path: {chunk.file_path}"
        )
        logger.error(
            error_msg,
            extra={
                "chunk_id": chunk.id,
                "chunk_index": chunk.chunk_index,
                "video_id": chunk.video_id,
                "file_path": chunk.file_path,
                "expected_path": str(chunk_path.absolute())
            }
        )
        raise FileNotFoundError(error_msg)
    
    logger.info(
        f"Transcribing chunk {chunk.chunk_index}",
        extra={
            "chunk_id": chunk.id,
            "chunk_index": chunk.chunk_index,
            "video_id": chunk.video_id,
            "file_path": chunk.file_path,
            "file_size": chunk.file_size,
            "duration": chunk.duration
        }
    )
    
    return transcribe_audio(chunk.file_path, language)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(OperationalError)
)
def save_transcription_chunk(
    transcription_id: int,
    chunk_id: int,
    chunk_text: str,
    embedding: List[float],
    session: Session
) -> TranscriptionChunk:
    """
    Save transcription chunk to database. Retries up to 3 times for connection issues.
    
    Args:
        transcription_id: ID of parent transcription
        chunk_id: ID of chunk
        chunk_text: Transcribed text for this chunk
        embedding: Vector embedding for this chunk
        session: Database session
        
    Returns:
        Saved TranscriptionChunk object
        
    Raises:
        DatabaseException if database operation fails
    """
    try:
        transcription_chunk = TranscriptionChunk(
            transcription_id=transcription_id,
            chunk_id=chunk_id,
            chunk_text=chunk_text,
            vector_embedding=embedding
        )
        session.add(transcription_chunk)
        session.commit()
        session.refresh(transcription_chunk)
        
        logger.info(
            f"Saved transcription chunk to database",
            extra={
                "transcription_chunk_id": transcription_chunk.id,
                "transcription_id": transcription_id,
                "chunk_id": chunk_id,
                "text_length": len(chunk_text)
            }
        )
        return transcription_chunk
        
    except IntegrityError as e:
        session.rollback()
        logger.error(
            f"Database integrity error saving transcription chunk",
            extra={"transcription_id": transcription_id, "chunk_id": chunk_id, "error": str(e)}
        )
        raise DatabaseException(
            f"Transcription chunk already exists for chunk {chunk_id}",
            details={"transcription_id": transcription_id, "chunk_id": chunk_id}
        )
    except OperationalError as e:
        session.rollback()
        logger.error(
            f"Database operational error saving transcription chunk",
            extra={"transcription_id": transcription_id, "chunk_id": chunk_id, "error": str(e)}
        )
        raise  # Let retry handle it
    except Exception as e:
        session.rollback()
        logger.error(
            f"Unexpected database error saving transcription chunk",
            extra={
                "transcription_id": transcription_id,
                "chunk_id": chunk_id,
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
        raise DatabaseException(
            f"Failed to save transcription chunk for chunk {chunk_id}",
            details={"transcription_id": transcription_id, "chunk_id": chunk_id}
        )


def process_chunked_video_transcription(
    video_id: str,
    chunks: List[Chunk],
    session: Session
) -> Dict[str, Any]:
    """
    Process video transcription using chunks.
    
    Steps:
    1. Validate all chunk files exist
    2. Process each chunk sequentially
    3. Generate embeddings for each chunk
    4. Save TranscriptionChunk records
    5. Concatenate chunk texts for complete transcription
    6. Save Transcription record with complete text
    
    Args:
        video_id: YouTube video ID
        chunks: List of Chunk objects for this video
        session: Database session
        
    Returns:
        Dictionary with status, video_id, message, steps_completed, total_steps, and optionally transcription or error
    """
    num_chunks = len(chunks)
    # Total steps: detection (1) + per chunk (transcription + embedding) + aggregation (1)
    total_steps = 1 + (num_chunks * 2) + 1
    steps_completed = 0
    
    try:
        logger.info(
            f"Starting chunk-based transcription for video {video_id}",
            extra={"video_id": video_id, "num_chunks": num_chunks}
        )
        
        # Step 1: Validate all chunk files exist before starting transcription
        missing_chunks = []
        for chunk in chunks:
            chunk_path = Path(chunk.file_path)
            if not chunk_path.exists():
                missing_chunks.append({
                    'chunk_index': chunk.chunk_index,
                    'chunk_id': chunk.id,
                    'file_path': chunk.file_path
                })
                logger.error(
                    f"Chunk file missing for validation",
                    extra={
                        "video_id": video_id,
                        "chunk_index": chunk.chunk_index,
                        "chunk_id": chunk.id,
                        "file_path": chunk.file_path,
                        "expected_path": str(chunk_path.absolute())
                    }
                )
        
        # If any chunks are missing, fail immediately with detailed error
        if missing_chunks:
            missing_indices = [c['chunk_index'] for c in missing_chunks]
            error_details = "; ".join([
                f"chunk {c['chunk_index']} at {c['file_path']}"
                for c in missing_chunks
            ])
            
            logger.error(
                f"Chunk validation failed: {len(missing_chunks)} chunk files missing",
                extra={
                    "video_id": video_id,
                    "missing_count": len(missing_chunks),
                    "missing_chunks": missing_chunks,
                    "total_chunks": num_chunks
                }
            )
            
            return {
                "status": "failed",
                "video_id": video_id,
                "message": f"Chunk validation failed: {len(missing_chunks)} of {num_chunks} chunk files missing",
                "error": f"Missing chunk files: {error_details}",
                "missing_chunk_indices": missing_indices,
                "steps_completed": steps_completed,
                "total_steps": total_steps
            }
        
        logger.info(
            f"Chunk validation passed: all {num_chunks} chunk files exist",
            extra={
                "video_id": video_id,
                "num_chunks": num_chunks,
                "chunk_paths": [chunk.file_path for chunk in chunks]
            }
        )
        
        steps_completed += 1  # Validation complete
        
        # Step 2-N: Process each chunk sequentially
        chunk_texts = []
        failed_chunks = []
        successful_chunks = []
        
        # Create a temporary transcription record to get an ID for chunk records
        # We'll update it with the complete text later
        temp_transcription_data = {
            "video_id": video_id,
            "transcription_text": "",  # Will be updated later
            "vector_embedding": None  # Will be updated later
        }
        transcription = save_transcription_to_db(session, temp_transcription_data)
        
        for chunk in chunks:
            chunk_index = chunk.chunk_index
            
            try:
                # Transcribe chunk
                logger.info(
                    f"Processing chunk {chunk_index + 1}/{num_chunks} for video {video_id}",
                    extra={
                        "video_id": video_id,
                        "chunk_index": chunk_index,
                        "chunk_id": chunk.id,
                        "file_path": chunk.file_path,
                        "progress": f"{chunk_index + 1}/{num_chunks}"
                    }
                )
                
                chunk_text = transcribe_chunk(chunk)
                
                if chunk_text is None:
                    logger.error(
                        f"Chunk transcription returned None",
                        extra={
                            "video_id": video_id,
                            "chunk_index": chunk_index,
                            "chunk_id": chunk.id,
                            "file_path": chunk.file_path
                        }
                    )
                    failed_chunks.append(chunk_index)
                    steps_completed += 2  # Skip both transcription and embedding steps
                    continue
                
                steps_completed += 1  # Transcription complete
                
                # Generate embedding for chunk
                logger.debug(
                    f"Generating embedding for chunk {chunk_index}",
                    extra={
                        "video_id": video_id,
                        "chunk_index": chunk_index,
                        "text_length": len(chunk_text)
                    }
                )
                
                chunk_embedding = generate_embedding(chunk_text)
                
                if chunk_embedding is None:
                    logger.error(
                        f"Chunk embedding generation returned None",
                        extra={
                            "video_id": video_id,
                            "chunk_index": chunk_index,
                            "chunk_id": chunk.id,
                            "text_length": len(chunk_text)
                        }
                    )
                    failed_chunks.append(chunk_index)
                    steps_completed += 1  # Embedding step failed
                    continue
                
                steps_completed += 1  # Embedding complete
                
                # Save transcription chunk
                save_transcription_chunk(
                    transcription_id=transcription.id,
                    chunk_id=chunk.id,
                    chunk_text=chunk_text,
                    embedding=chunk_embedding,
                    session=session
                )
                
                chunk_texts.append(chunk_text)
                successful_chunks.append(chunk_index)
                
                logger.info(
                    f"Successfully processed chunk {chunk_index + 1}/{num_chunks}",
                    extra={
                        "video_id": video_id,
                        "chunk_index": chunk_index,
                        "chunk_id": chunk.id,
                        "text_length": len(chunk_text),
                        "embedding_dim": len(chunk_embedding),
                        "progress": f"{len(successful_chunks)}/{num_chunks} successful"
                    }
                )
                
            except FileNotFoundError as e:
                # Specific handling for missing chunk files
                logger.error(
                    f"Chunk file not found during processing",
                    extra={
                        "video_id": video_id,
                        "chunk_index": chunk_index,
                        "chunk_id": chunk.id,
                        "file_path": chunk.file_path,
                        "error": str(e)
                    },
                    exc_info=True
                )
                failed_chunks.append(chunk_index)
                steps_completed += 2  # Skip both steps for this chunk
                
            except Exception as e:
                # General error handling with detailed logging
                logger.error(
                    f"Unexpected error processing chunk {chunk_index}",
                    extra={
                        "video_id": video_id,
                        "chunk_index": chunk_index,
                        "chunk_id": chunk.id,
                        "file_path": chunk.file_path,
                        "error_type": type(e).__name__,
                        "error": str(e)
                    },
                    exc_info=True
                )
                failed_chunks.append(chunk_index)
                steps_completed += 2  # Skip both steps for this chunk
        
        # Check if any chunks succeeded
        if not chunk_texts:
            logger.error(f"All chunks failed for video {video_id}")
            return {
                "status": "failed",
                "video_id": video_id,
                "message": "All chunks failed to process",
                "error": f"Failed chunks: {failed_chunks}",
                "steps_completed": steps_completed,
                "total_steps": total_steps,
                "failed_chunks": failed_chunks,
                "successful_chunks": successful_chunks
            }
        
        # Step N+1: Concatenate chunk texts
        complete_text = " ".join(chunk_texts)
        
        # Generate embedding for complete text
        complete_embedding = generate_embedding(complete_text)
        
        if complete_embedding is None:
            logger.error(f"Failed to generate embedding for complete transcription of video {video_id}")
            return {
                "status": "failed",
                "video_id": video_id,
                "message": "Failed to generate embedding for complete transcription",
                "error": "Embedding generation failed for aggregated text",
                "steps_completed": steps_completed,
                "total_steps": total_steps,
                "failed_chunks": failed_chunks,
                "successful_chunks": successful_chunks
            }
        
        # Update transcription with complete text and embedding
        transcription.transcription_text = complete_text
        transcription.vector_embedding = complete_embedding
        session.commit()
        session.refresh(transcription)
        
        steps_completed += 1  # Aggregation complete
        
        logger.info(
            f"Completed chunk-based transcription for video {video_id}",
            extra={
                "video_id": video_id,
                "total_chunks": num_chunks,
                "successful_chunks": len(successful_chunks),
                "failed_chunks": len(failed_chunks),
                "total_text_length": len(complete_text)
            }
        )
        
        result = {
            "status": "success" if not failed_chunks else "partial_success",
            "video_id": video_id,
            "transcription": transcription,
            "message": f"Chunk-based transcription completed: {len(successful_chunks)}/{num_chunks} chunks successful",
            "steps_completed": steps_completed,
            "total_steps": total_steps,
            "successful_chunks": successful_chunks
        }
        
        if failed_chunks:
            result["failed_chunks"] = failed_chunks
        
        return result
        
    except Exception as e:
        logger.exception(f"Unexpected error in chunk-based transcription for video {video_id}")
        return {
            "status": "failed",
            "video_id": video_id,
            "message": "Unexpected error in chunk-based transcription",
            "error": str(e),
            "steps_completed": steps_completed,
            "total_steps": total_steps
        }


def process_complete_video_transcription(video_id: str, session: Session) -> Dict[str, Any]:
    """
    Complete transcription workflow for a single non-chunked video.
    Original processing logic for backward compatibility.
    
    Args:
        video_id: YouTube video ID
        session: Database session
        
    Returns:
        Dictionary with status, video_id, message, steps_completed, total_steps, and optionally transcription or error
    """
    try:
        # Step 1: Query video from database (1/5)
        video = session.query(Video).filter_by(video_id=video_id).first()
        if not video:
            return {
                "status": "not_found",
                "video_id": video_id,
                "message": "Video not found in database",
                "error": "Video must be downloaded first",
                "steps_completed": 0,
                "total_steps": 5
            }
        
        # Step 2: Verify audio file exists (2/5)
        if not video.file_path or not Path(video.file_path).exists():
            return {
                "status": "no_audio",
                "video_id": video_id,
                "message": "Audio file not found",
                "error": "Audio file missing or not downloaded",
                "steps_completed": 1,
                "total_steps": 5
            }
        
        # Step 3: Transcribe audio (3/5)
        logger.info(f"Transcribing audio for video {video_id}")
        transcription_text = transcribe_audio(video.file_path)
        if transcription_text is None:
            return {
                "status": "failed",
                "video_id": video_id,
                "message": "Transcription failed",
                "error": "Whisper transcription error",
                "steps_completed": 2,
                "total_steps": 5
            }
        
        # Step 4: Generate embedding (4/5)
        logger.info(f"Generating embedding for video {video_id}")
        embedding = generate_embedding(transcription_text)
        if embedding is None:
            return {
                "status": "failed",
                "video_id": video_id,
                "message": "Embedding generation failed",
                "error": "Failed to generate vector embedding",
                "steps_completed": 3,
                "total_steps": 5
            }
        
        # Step 5: Prepare transcription data
        transcription_data = {
            "video_id": video_id,
            "transcription_text": transcription_text,
            "vector_embedding": embedding
        }
        
        # Step 6: Save to database (5/5)
        logger.info(f"Saving transcription for video {video_id}")
        transcription = save_transcription_to_db(session, transcription_data)
        
        # Step 7: Return success result
        return {
            "status": "success",
            "video_id": video_id,
            "transcription": transcription,
            "message": "Transcription completed successfully",
            "steps_completed": 5,
            "total_steps": 5
        }
        
    except Exception as e:
        logger.exception(f"Unexpected error processing video {video_id}")
        return {
            "status": "failed",
            "video_id": video_id,
            "message": "Unexpected error",
            "error": str(e),
            "steps_completed": 0,
            "total_steps": 5
        }


def process_video_transcription(video_id: str, session: Session) -> Dict[str, Any]:
    """
    Complete transcription workflow for a single video.
    Automatically detects and processes chunks if they exist, otherwise processes complete file.
    
    Args:
        video_id: YouTube video ID
        session: Database session
        
    Returns:
        Dictionary with status, video_id, message, steps_completed, total_steps, and optionally transcription or error
    """
    try:
        # Check if chunks exist for this video
        chunks = get_chunks_for_video(video_id, session)
        
        if chunks:
            logger.info(
                f"Detected {len(chunks)} chunks for video {video_id}, using chunk-based processing",
                extra={"video_id": video_id, "num_chunks": len(chunks)}
            )
            return process_chunked_video_transcription(video_id, chunks, session)
        else:
            logger.info(
                f"No chunks detected for video {video_id}, using complete file processing",
                extra={"video_id": video_id}
            )
            return process_complete_video_transcription(video_id, session)
            
    except Exception as e:
        logger.exception(f"Unexpected error in process_video_transcription for video {video_id}")
        return {
            "status": "failed",
            "video_id": video_id,
            "message": "Unexpected error",
            "error": str(e),
            "steps_completed": 0,
            "total_steps": 5
        }


def process_multiple_videos(video_ids: List[str], session: Session) -> List[Dict[str, Any]]:
    """
    Process multiple videos sequentially.
    
    Sequential processing is intentional for memory management (Whisper can be memory-intensive).
    
    Args:
        video_ids: List of YouTube video IDs
        session: Database session
        
    Returns:
        List of result dictionaries
    """
    results = []
    total = len(video_ids)
    
    for idx, video_id in enumerate(video_ids, 1):
        logger.info(f"Processing video {idx}/{total}: {video_id}")
        result = process_video_transcription(video_id, session)
        results.append(result)
        logger.info(f"Completed video {idx}/{total}: {video_id} - Status: {result['status']}")
    
    return results
