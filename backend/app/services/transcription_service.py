import whisper
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
from app.exceptions import TranscriptionException, EmbeddingException, DatabaseException

# Module-level logger
logger = logging.getLogger(__name__)

# Load models once at module level for efficiency
whisper_model = None
embedding_model = None


def clear_gpu_cache():
    """Clear GPU cache for both CUDA and MPS devices."""
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    elif torch.backends.mps.is_available():
        torch.mps.empty_cache()

try:
    # Check for GPU availability (CUDA for NVIDIA, MPS for Apple Silicon)
    # Note: Whisper has issues with MPS sparse tensors, so we force CPU on Apple Silicon
    if torch.cuda.is_available():
        whisper_device = 'cuda'
        gpu_name = torch.cuda.get_device_name(0)
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
        logger.info(f"NVIDIA GPU detected: {gpu_name} ({gpu_memory:.1f} GB)")
    elif torch.backends.mps.is_available():
        whisper_device = 'cpu'  # Force CPU for Whisper on Apple Silicon due to MPS sparse tensor bug
        logger.info("Apple Silicon GPU (MPS) detected - using CPU for Whisper due to PyTorch MPS limitations")
    else:
        whisper_device = 'cpu'
        logger.warning("No GPU detected, falling back to CPU (this will be slow)")
    
    logger.info(f"Loading Whisper model on device: {whisper_device}")
    
    import time
    start_time = time.time()
    whisper_model = whisper.load_model(settings.whisper_model, device=whisper_device)
    load_time = time.time() - start_time
    
    logger.info(
        f"Loaded Whisper model: {settings.whisper_model}",
        extra={"device": whisper_device, "load_time_seconds": round(load_time, 2)}
    )
except Exception as e:
    logger.critical(
        f"Failed to load Whisper model '{settings.whisper_model}': {e}",
        exc_info=True
    )
    whisper_model = None

try:
    # Embedding model can use MPS without issues
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
except Exception as e:
    logger.critical(f"Failed to load embedding model: {e}", exc_info=True)
    embedding_model = None


def validate_audio_file(audio_path: str) -> bool:
    """
    Validate that audio file contains valid audio data that Whisper can process.
    
    Args:
        audio_path: Path to the audio file
        
    Returns:
        True if audio is valid, False otherwise
    """
    try:
        # Use Whisper's own audio loading to match its expectations
        audio = whisper.load_audio(audio_path)
        
        # Check if we got any audio samples
        if len(audio) == 0:
            logger.error(f"Audio file contains no audio data: {audio_path}")
            return False
        
        # Check minimum duration (Whisper needs at least 0.1 seconds of audio)
        # Audio is sampled at 16kHz, so 0.1 seconds = 1600 samples
        min_samples = 1600
        if len(audio) < min_samples:
            logger.error(
                f"Audio file too short: {audio_path} "
                f"(has {len(audio)} samples, needs at least {min_samples})"
            )
            return False
            
        # Check if audio is not just silence (all zeros or near-zeros)
        if np.abs(audio).max() < 1e-6:
            logger.error(f"Audio file appears to contain only silence: {audio_path}")
            return False
        
        # Try to compute the mel spectrogram (this is what Whisper does internally)
        try:
            # Pad audio to 30 seconds like Whisper does
            audio = whisper.pad_or_trim(audio)
            mel = whisper.log_mel_spectrogram(audio)
            
            # Check mel dimensions - should be [80, frames] where frames > 0
            if mel.shape[0] == 0 or mel.shape[1] == 0:
                logger.error(
                    f"Audio file produces empty mel spectrogram: {audio_path} "
                    f"(shape: {mel.shape})"
                )
                return False
                
            # Mel should have at least a few frames
            if mel.shape[1] < 10:
                logger.error(
                    f"Audio file produces too few mel frames: {audio_path} "
                    f"(frames: {mel.shape[1]})"
                )
                return False
                
        except Exception as mel_error:
            logger.error(f"Failed to compute mel spectrogram for {audio_path}: {mel_error}")
            return False
            
        logger.debug(
            f"Audio validation passed: {audio_path} "
            f"(samples: {len(audio)}, duration: {len(audio)/16000:.2f}s, mel_shape: {mel.shape})"
        )
        return True
        
    except Exception as e:
        logger.error(f"Audio validation failed for {audio_path}: {e}")
        return False


def transcribe_audio(audio_path: str, language: str = "ar") -> Optional[str]:
    """
    Transcribe audio file using Whisper with fallback strategies for robustness.
    
    Args:
        audio_path: Path to the audio file (MP3)
        language: Language code (default: "ar" for Arabic)
        
    Returns:
        Transcription text or None if failed
    """
    if whisper_model is None:
        logger.error("Whisper model not loaded")
        raise TranscriptionException("Whisper model not loaded. Please restart the application.")
    
    # Verify audio file exists
    audio_file = Path(audio_path)
    if not audio_file.exists():
        logger.error(f"Audio file not found: {audio_path}")
        return None
    
    # Validate file size
    file_size = audio_file.stat().st_size
    file_size_mb = file_size / (1024 * 1024)
    
    if file_size < 1024:  # Less than 1KB
        logger.error(f"Audio file too small ({file_size} bytes): {audio_path}")
        return None
    elif file_size_mb > 500:  # Larger than 500MB
        logger.warning(f"Audio file very large ({file_size_mb:.2f}MB): {audio_path}")
    
    # Validate audio content before attempting transcription
    if not validate_audio_file(audio_path):
        logger.error(f"Audio file validation failed, skipping transcription: {audio_path}")
        return None
    
    # Determine device and precision
    if torch.cuda.is_available():
        device = 'cuda'
        use_fp16 = True  # NVIDIA GPUs support FP16
    elif torch.backends.mps.is_available():
        device = 'mps'
        use_fp16 = False  # MPS doesn't support FP16 in Whisper yet
    else:
        device = 'cpu'
        use_fp16 = False
    
    # Strategy 1: Try with optimized settings (beam_size=5)
    try:
        logger.info(
            f"Starting transcription for {audio_file.name} ({file_size_mb:.2f}MB)",
            extra={"language": language, "strategy": "optimized"}
        )
        
        if use_fp16:
            logger.info(f"Using GPU with FP16 precision for faster transcription")
        
        result = whisper_model.transcribe(
            audio_path,
            language=language,
            task="transcribe",
            fp16=use_fp16,
            verbose=False,
            beam_size=5,
            best_of=5,
            temperature=0.0,
            compression_ratio_threshold=2.4,
            logprob_threshold=-1.0,
            no_speech_threshold=0.6,
            condition_on_previous_text=True,
            word_timestamps=False,
        )
        text = result['text'].strip()
        
        # Get detected language info
        detected_language = result.get('language', 'unknown')
        language_probability = result.get('language_probability', 0.0)
        
        # Log language detection results
        logger.info(
            f"Language detection results",
            extra={
                "requested_language": language,
                "detected_language": detected_language,
                "language_probability": round(language_probability, 3)
            }
        )
        
        # Validate text is not empty and has minimum length
        if not text:
            logger.warning(f"Transcription resulted in empty text for: {audio_path}")
            return None
        elif len(text) < 10:
            logger.warning(
                f"Transcription seems too short ({len(text)} chars): {audio_path}"
            )
        
        # Check if text contains Arabic characters
        arabic_char_count = sum(1 for char in text if '\u0600' <= char <= '\u06FF')
        total_chars = len(text)
        arabic_percentage = (arabic_char_count / total_chars * 100) if total_chars > 0 else 0
        
        logger.info(
            f"Successfully transcribed {audio_file.name}",
            extra={
                "text_length": len(text),
                "file_size_mb": round(file_size_mb, 2),
                "device": device,
                "language": language,
                "arabic_percentage": round(arabic_percentage, 1),
                "strategy": "optimized"
            }
        )
        
        # Preview first 100 characters (for debugging)
        logger.debug(f"Transcription preview: {text[:100]}...")
        
        return text
        
    except RuntimeError as e:
        error_msg = str(e)
        
        # Handle OOM for both CUDA and MPS (MPS raises RuntimeError for OOM)
        if "out of memory" in error_msg.lower():
            logger.error(f"GPU out of memory for {audio_path}: {e}")
            clear_gpu_cache()
            return None
        
        # Handle tensor errors (empty segments, size mismatches, corrupted audio) - fallback to simpler settings
        if any(keyword in error_msg for keyword in [
            "cannot reshape tensor", 
            "0 elements", 
            "is ambiguous",
            "Sizes of tensors must match",
            "Expected size"
        ]):
            logger.warning(
                f"Whisper encountered tensor error, trying fallback strategy: {e}",
                extra={"error_type": "TensorError", "strategy": "fallback"}
            )
            
            # Clear GPU cache
            clear_gpu_cache()
            
            # Strategy 2: Fallback with simpler settings (beam_size=1, no best_of)
            try:
                logger.info(f"Retrying with simplified settings (beam_size=1)")
                
                result = whisper_model.transcribe(
                    audio_path,
                    language=language,
                    task="transcribe",
                    fp16=use_fp16,
                    verbose=False,
                    beam_size=1,  # Simpler decoding
                    temperature=0.0,
                    compression_ratio_threshold=2.4,
                    logprob_threshold=-1.0,
                    no_speech_threshold=0.6,
                    condition_on_previous_text=False,  # Disable context to avoid state issues
                    word_timestamps=False,
                )
                
                text = result['text'].strip()
                
                if not text:
                    logger.error(f"Fallback strategy produced empty text for: {audio_path}")
                    return None
                
                logger.info(
                    f"Successfully transcribed with fallback strategy",
                    extra={
                        "text_length": len(text),
                        "strategy": "fallback"
                    }
                )
                
                return text
                
            except Exception as fallback_error:
                logger.error(
                    f"Fallback strategy also failed for {audio_path}: {fallback_error}",
                    extra={"error_type": type(fallback_error).__name__},
                    exc_info=True
                )
                
                clear_gpu_cache()
                
                return None
        
        # Other runtime errors
        logger.error(
            f"Whisper runtime error for {audio_path}: {e}",
            extra={"error_type": "RuntimeError"},
            exc_info=True
        )
        
        clear_gpu_cache()
        
        return None
        
    except Exception as e:
        logger.error(
            f"Whisper transcription error for {audio_path}: {e}",
            extra={"error_type": type(e).__name__},
            exc_info=True
        )
        
        clear_gpu_cache()
        
        return None

@retry(
    stop=stop_after_attempt(2),
    wait=wait_fixed(3),
    retry=retry_if_exception_type((RuntimeError, torch.cuda.OutOfMemoryError))
)
def generate_embedding(text: str) -> Optional[List[float]]:
    """
    Generate vector embedding from text using configured embedding model.
    Retries up to 2 times for transient failures.
    
    Args:
        text: Text to encode
        
    Returns:
        List of floats (normalized for cosine similarity) or None if failed
    """
    if embedding_model is None:
        logger.error("Embedding model not loaded")
        raise EmbeddingException("Embedding model not loaded. Please restart the application.")
    
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
        embedding = embedding_model.encode(
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
        embedding_dim = len(transcription_data.get('vector_embedding', []))
        
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


def process_video_transcription(video_id: str, session: Session) -> Dict[str, Any]:
    """
    Complete transcription workflow for a single video.
    
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
