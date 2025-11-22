"""
Chunk service for splitting large audio files into manageable segments.

This service handles:
- Detection of files that need chunking based on size
- Silence point detection using FFmpeg
- Calculation of optimal split points
- Audio file splitting with codec copy
- Chunk metadata management
- Database operations for chunk records
"""

import logging
import os
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

from app.models.chunk import Chunk
from app.models.video import Video
from app.config import settings

logger = logging.getLogger(__name__)


def should_create_chunks(file_path: str, max_chunk_mb: float) -> bool:
    """
    Determine if an audio file should be split into chunks.
    
    Args:
        file_path: Path to the audio file
        max_chunk_mb: Maximum chunk size in megabytes
        
    Returns:
        True if file size exceeds threshold, False otherwise
    """
    try:
        file_size_bytes = os.path.getsize(file_path)
        file_size_mb = file_size_bytes / (1024 * 1024)
        
        should_chunk = file_size_mb > max_chunk_mb
        
        if should_chunk:
            logger.info(
                f"File {file_path} size {file_size_mb:.2f}MB exceeds "
                f"threshold {max_chunk_mb}MB, chunking required"
            )
        else:
            logger.debug(
                f"File {file_path} size {file_size_mb:.2f}MB is below "
                f"threshold {max_chunk_mb}MB, no chunking needed"
            )
        
        return should_chunk
    except OSError as e:
        logger.error(f"Failed to check file size for {file_path}: {e}")
        return False


def detect_silence_points(
    audio_path: str,
    min_silence_duration: float,
    noise_threshold: int
) -> List[float]:
    """
    Detect silence points in audio file using FFmpeg silencedetect filter.
    
    Args:
        audio_path: Path to the audio file
        min_silence_duration: Minimum silence duration in seconds
        noise_threshold: Noise threshold in dB (e.g., -35)
        
    Returns:
        List of silence midpoint timestamps in seconds
    """
    try:
        # FFmpeg command to detect silence
        cmd = [
            'ffmpeg',
            '-i', audio_path,
            '-af', f'silencedetect=noise={noise_threshold}dB:d={min_silence_duration}',
            '-f', 'null',
            '-'
        ]
        
        logger.debug(f"Running silence detection: {' '.join(cmd)}")
        
        # Run FFmpeg and capture stderr (where silencedetect outputs)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )
        
        # Parse silence_start and silence_end from stderr
        silence_starts = []
        silence_ends = []
        
        for line in result.stderr.split('\n'):
            # Look for patterns like: [silencedetect @ ...] silence_start: 12.345
            start_match = re.search(r'silence_start:\s*([\d.]+)', line)
            if start_match:
                silence_starts.append(float(start_match.group(1)))
            
            # Look for patterns like: [silencedetect @ ...] silence_end: 15.678
            end_match = re.search(r'silence_end:\s*([\d.]+)', line)
            if end_match:
                silence_ends.append(float(end_match.group(1)))
        
        # Calculate midpoints of silence periods
        silence_points = []
        for start, end in zip(silence_starts, silence_ends):
            midpoint = (start + end) / 2
            silence_points.append(midpoint)
        
        logger.info(
            f"Detected {len(silence_points)} silence points in {audio_path}"
        )
        logger.debug(f"Silence points: {silence_points}")
        
        return silence_points
        
    except Exception as e:
        logger.error(f"Failed to detect silence points in {audio_path}: {e}")
        return []


def calculate_split_points(
    duration: float,
    file_size_mb: float,
    max_chunk_mb: float,
    silence_points: List[float]
) -> List[float]:
    """
    Calculate optimal split positions for audio file.
    
    Distributes chunks evenly and prefers silence points within 10 seconds
    of target positions. Falls back to exact time intervals if no silence
    points are found nearby.
    
    Args:
        duration: Total audio duration in seconds
        file_size_mb: Total file size in megabytes
        max_chunk_mb: Maximum chunk size in megabytes
        silence_points: List of silence timestamps in seconds
        
    Returns:
        List of split point timestamps in seconds (sorted)
    """
    # Calculate number of chunks needed
    num_chunks = int(file_size_mb / max_chunk_mb) + 1
    
    if num_chunks <= 1:
        logger.debug("File fits in single chunk, no split points needed")
        return []
    
    # Calculate target split positions (evenly distributed)
    chunk_duration = duration / num_chunks
    target_positions = [chunk_duration * i for i in range(1, num_chunks)]
    
    logger.debug(
        f"Calculated {len(target_positions)} target split positions "
        f"for {num_chunks} chunks"
    )
    
    # Find nearest silence point within 10 seconds of each target
    split_points = []
    search_range = 10.0  # seconds
    
    for target in target_positions:
        best_silence = None
        min_distance = float('inf')
        
        # Find closest silence point within range
        for silence in silence_points:
            distance = abs(silence - target)
            if distance <= search_range and distance < min_distance:
                best_silence = silence
                min_distance = distance
        
        if best_silence is not None:
            split_points.append(best_silence)
            logger.debug(
                f"Target {target:.2f}s -> silence point {best_silence:.2f}s "
                f"(distance: {min_distance:.2f}s)"
            )
        else:
            # No silence point found, use exact target position
            split_points.append(target)
            logger.debug(
                f"Target {target:.2f}s -> no silence found, using exact position"
            )
    
    # Sort and return
    split_points.sort()
    logger.info(f"Calculated {len(split_points)} split points: {split_points}")
    
    return split_points


def split_audio_file(
    audio_path: Path,
    split_points: List[float],
    output_dir: Path,
    video_id: str
) -> List[Dict[str, Any]]:
    """
    Split audio file at specified points using FFmpeg with codec copy.
    
    Args:
        audio_path: Path to the source audio file
        split_points: List of split timestamps in seconds (sorted)
        output_dir: Directory to store chunk files
        video_id: Video ID for naming chunks
        
    Returns:
        List of chunk metadata dictionaries with keys:
        - chunk_index: 0-based index
        - file_path: Path to chunk file
        - start_time: Start time in seconds
        - end_time: End time in seconds
        - duration: Duration in seconds
        - file_size: File size in bytes
    """
    try:
        # Get audio file extension
        extension = audio_path.suffix
        
        # Get total duration using ffprobe
        duration = _get_audio_duration(str(audio_path))
        if duration is None:
            raise ValueError(f"Could not determine duration of {audio_path}")
        
        # Create output directory
        chunk_dir = output_dir / video_id
        chunk_dir.mkdir(parents=True, exist_ok=True)
        
        # Create chunks
        chunk_metadata = []
        start_times = [0.0] + split_points
        end_times = split_points + [duration]
        
        for idx, (start, end) in enumerate(zip(start_times, end_times)):
            chunk_filename = f"{video_id}_chunk_{idx:03d}{extension}"
            chunk_path = chunk_dir / chunk_filename
            
            # FFmpeg command with codec copy (no re-encoding)
            cmd = [
                'ffmpeg',
                '-i', str(audio_path),
                '-ss', str(start),
                '-to', str(end),
                '-c', 'copy',
                '-y',  # Overwrite output file
                str(chunk_path)
            ]
            
            logger.debug(f"Creating chunk {idx}: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Get chunk file size
            chunk_size = os.path.getsize(chunk_path)
            chunk_duration = end - start
            
            metadata = {
                'chunk_index': idx,
                'file_path': str(chunk_path),
                'start_time': start,
                'end_time': end,
                'duration': chunk_duration,
                'file_size': chunk_size
            }
            
            chunk_metadata.append(metadata)
            
            logger.info(
                f"Created chunk {idx}: {chunk_filename} "
                f"({chunk_duration:.2f}s, {chunk_size / (1024 * 1024):.2f}MB)"
            )
        
        logger.info(
            f"Successfully created {len(chunk_metadata)} chunks for {video_id}"
        )
        
        return chunk_metadata
        
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg failed to split audio: {e.stderr}")
        raise
    except Exception as e:
        logger.error(f"Failed to split audio file {audio_path}: {e}")
        raise


def _get_audio_duration(audio_path: str) -> Optional[float]:
    """
    Get audio file duration using ffprobe.
    
    Args:
        audio_path: Path to audio file
        
    Returns:
        Duration in seconds, or None if failed
    """
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            audio_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        duration = float(result.stdout.strip())
        return duration
        
    except Exception as e:
        logger.error(f"Failed to get duration for {audio_path}: {e}")
        return None



@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(SQLAlchemyError),
    reraise=True
)
def save_chunks_to_db(
    video_id: str,
    chunk_metadata: List[Dict[str, Any]],
    session: Session
) -> List[Chunk]:
    """
    Save chunk records to database with retry logic.
    
    Args:
        video_id: Video ID the chunks belong to
        chunk_metadata: List of chunk metadata dictionaries
        session: Database session
        
    Returns:
        List of created Chunk objects
        
    Raises:
        SQLAlchemyError: If database operation fails after retries
    """
    try:
        chunks = []
        
        for metadata in chunk_metadata:
            chunk = Chunk(
                video_id=video_id,
                chunk_index=metadata['chunk_index'],
                file_path=metadata['file_path'],
                start_time=metadata['start_time'],
                end_time=metadata['end_time'],
                duration=metadata['duration'],
                file_size=metadata['file_size']
            )
            session.add(chunk)
            chunks.append(chunk)
        
        session.commit()
        
        # Refresh to get generated IDs
        for chunk in chunks:
            session.refresh(chunk)
        
        logger.info(
            f"Successfully saved {len(chunks)} chunk records for video {video_id}",
            extra={
                'video_id': video_id,
                'chunk_count': len(chunks),
                'total_size': sum(m['file_size'] for m in chunk_metadata)
            }
        )
        
        return chunks
        
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(
            f"Failed to save chunks to database for video {video_id}: {e}",
            extra={'video_id': video_id, 'chunk_count': len(chunk_metadata)}
        )
        raise
    except Exception as e:
        session.rollback()
        logger.error(
            f"Unexpected error saving chunks for video {video_id}: {e}",
            extra={'video_id': video_id}
        )
        raise


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(SQLAlchemyError),
    reraise=True
)
def get_chunks_for_video(video_id: str, session: Session) -> List[Chunk]:
    """
    Retrieve all chunks for a video, ordered by chunk_index.
    
    Args:
        video_id: Video ID to get chunks for
        session: Database session
        
    Returns:
        List of Chunk objects ordered by chunk_index
        
    Raises:
        SQLAlchemyError: If database query fails after retries
    """
    try:
        chunks = (
            session.query(Chunk)
            .filter(Chunk.video_id == video_id)
            .order_by(Chunk.chunk_index)
            .all()
        )
        
        logger.debug(
            f"Retrieved {len(chunks)} chunks for video {video_id}",
            extra={'video_id': video_id, 'chunk_count': len(chunks)}
        )
        
        return chunks
        
    except SQLAlchemyError as e:
        logger.error(
            f"Failed to retrieve chunks for video {video_id}: {e}",
            extra={'video_id': video_id}
        )
        raise


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(SQLAlchemyError),
    reraise=True
)
def delete_chunks_for_video(video_id: str, session: Session) -> int:
    """
    Delete all chunks for a video (files and database records).
    
    Args:
        video_id: Video ID to delete chunks for
        session: Database session
        
    Returns:
        Number of chunks deleted
        
    Raises:
        SQLAlchemyError: If database operation fails after retries
    """
    try:
        # Get all chunks for the video
        chunks = get_chunks_for_video(video_id, session)
        
        if not chunks:
            logger.debug(f"No chunks found for video {video_id}")
            return 0
        
        chunk_count = len(chunks)
        deleted_files = 0
        failed_deletions = []
        
        # Delete chunk files from filesystem
        for chunk in chunks:
            try:
                chunk_path = Path(chunk.file_path)
                if chunk_path.exists():
                    chunk_path.unlink()
                    deleted_files += 1
                    logger.debug(f"Deleted chunk file: {chunk_path}")
                else:
                    logger.warning(
                        f"Chunk file not found: {chunk_path}",
                        extra={'video_id': video_id, 'chunk_index': chunk.chunk_index}
                    )
            except OSError as e:
                logger.error(
                    f"Failed to delete chunk file {chunk.file_path}: {e}",
                    extra={'video_id': video_id, 'chunk_index': chunk.chunk_index}
                )
                failed_deletions.append(chunk.chunk_index)
        
        # Delete chunk directory if empty
        try:
            chunk_dir = settings.chunk_storage_path / video_id
            if chunk_dir.exists() and chunk_dir.is_dir():
                # Check if directory is empty
                if not any(chunk_dir.iterdir()):
                    chunk_dir.rmdir()
                    logger.debug(f"Deleted empty chunk directory: {chunk_dir}")
                else:
                    logger.warning(
                        f"Chunk directory not empty after deletion: {chunk_dir}",
                        extra={'video_id': video_id}
                    )
        except OSError as e:
            logger.error(
                f"Failed to delete chunk directory for video {video_id}: {e}",
                extra={'video_id': video_id}
            )
        
        # Delete chunk records from database
        session.query(Chunk).filter(Chunk.video_id == video_id).delete()
        session.commit()
        
        logger.info(
            f"Deleted {chunk_count} chunks for video {video_id} "
            f"({deleted_files} files deleted)",
            extra={
                'video_id': video_id,
                'chunk_count': chunk_count,
                'deleted_files': deleted_files,
                'failed_deletions': failed_deletions
            }
        )
        
        return chunk_count
        
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(
            f"Failed to delete chunks from database for video {video_id}: {e}",
            extra={'video_id': video_id}
        )
        raise
    except Exception as e:
        session.rollback()
        logger.error(
            f"Unexpected error deleting chunks for video {video_id}: {e}",
            extra={'video_id': video_id}
        )
        raise


def create_chunks_for_video(
    video_id: str,
    audio_path: str,
    max_chunk_mb: float,
    session: Session
) -> List[Chunk]:
    """
    Orchestration function to create chunks for a video.
    
    This function:
    1. Detects silence points in the audio
    2. Calculates optimal split points
    3. Splits the audio file into chunks
    4. Saves chunk records to database
    5. Cleans up on failure
    
    Args:
        video_id: Video ID to create chunks for
        audio_path: Path to the audio file
        max_chunk_mb: Maximum chunk size in megabytes
        session: Database session
        
    Returns:
        List of created Chunk objects
        
    Raises:
        ValueError: If audio file is invalid or doesn't need chunking
        Exception: If chunk creation fails
    """
    audio_path_obj = Path(audio_path)
    
    # Validate video exists in database
    video = session.query(Video).filter(Video.video_id == video_id).first()
    if not video:
        raise ValueError(
            f"Video {video_id} not found in database. "
            f"Cannot create chunks for non-existent video."
        )
    
    # Validate audio file exists
    if not audio_path_obj.exists():
        raise ValueError(f"Audio file not found: {audio_path}")
    
    # Check if chunking is needed
    if not should_create_chunks(audio_path, max_chunk_mb):
        logger.info(
            f"Audio file for video {video_id} does not require chunking",
            extra={'video_id': video_id}
        )
        return []
    
    try:
        logger.info(
            f"Starting chunk creation for video {video_id}",
            extra={'video_id': video_id, 'audio_path': audio_path}
        )
        
        # Step 1: Detect silence points
        silence_points = detect_silence_points(
            audio_path,
            settings.min_silence_duration,
            settings.silence_threshold_db
        )
        
        # Step 2: Get audio duration and file size
        duration = _get_audio_duration(audio_path)
        if duration is None:
            raise ValueError(f"Could not determine duration of {audio_path}")
        
        file_size_bytes = os.path.getsize(audio_path)
        file_size_mb = file_size_bytes / (1024 * 1024)
        
        # Step 3: Calculate split points
        split_points = calculate_split_points(
            duration,
            file_size_mb,
            max_chunk_mb,
            silence_points
        )
        
        if not split_points:
            logger.warning(
                f"No split points calculated for video {video_id}, "
                f"file may not need chunking",
                extra={'video_id': video_id}
            )
            return []
        
        # Step 4: Split audio file
        logger.info(
            f"Splitting audio file into chunks",
            extra={
                'video_id': video_id,
                'split_points_count': len(split_points),
                'expected_chunks': len(split_points) + 1,
                'file_size_mb': file_size_mb,
                'duration': duration
            }
        )
        
        chunk_metadata = split_audio_file(
            audio_path_obj,
            split_points,
            settings.chunk_storage_path,
            video_id
        )
        
        # Validate chunk sizes don't exceed maximum
        oversized_chunks = []
        for metadata in chunk_metadata:
            chunk_size_mb = metadata['file_size'] / (1024 * 1024)
            if chunk_size_mb > max_chunk_mb:
                oversized_chunks.append({
                    'chunk_index': metadata['chunk_index'],
                    'size_mb': chunk_size_mb,
                    'file_path': metadata['file_path']
                })
                logger.warning(
                    f"Chunk {metadata['chunk_index']} size {chunk_size_mb:.2f}MB "
                    f"exceeds maximum {max_chunk_mb}MB",
                    extra={
                        'video_id': video_id,
                        'chunk_index': metadata['chunk_index'],
                        'chunk_size_mb': chunk_size_mb,
                        'file_path': metadata['file_path']
                    }
                )
        
        # If any chunks exceed the limit, cleanup and raise error
        if oversized_chunks:
            logger.error(
                f"Chunk validation failed: {len(oversized_chunks)} chunks exceed size limit",
                extra={
                    'video_id': video_id,
                    'oversized_chunks': oversized_chunks,
                    'max_chunk_mb': max_chunk_mb
                }
            )
            # Cleanup partial chunks
            try:
                chunk_dir = settings.chunk_storage_path / video_id
                if chunk_dir.exists():
                    import shutil
                    shutil.rmtree(chunk_dir)
                    logger.info(
                        f"Cleaned up oversized chunks for video {video_id}",
                        extra={'video_id': video_id}
                    )
            except Exception as cleanup_error:
                logger.error(
                    f"Failed to cleanup oversized chunks for video {video_id}: {cleanup_error}",
                    extra={'video_id': video_id}
                )
            
            raise ValueError(
                f"Chunk validation failed: {len(oversized_chunks)} chunks exceed "
                f"{max_chunk_mb}MB limit. Largest chunk: "
                f"{oversized_chunks[0]['size_mb']:.2f}MB at index {oversized_chunks[0]['chunk_index']}"
            )
        
        # Step 5: Save to database
        chunks = save_chunks_to_db(video_id, chunk_metadata, session)
        
        # Calculate statistics for logging
        total_chunk_size = sum(m['file_size'] for m in chunk_metadata)
        chunk_sizes_mb = [m['file_size'] / (1024 * 1024) for m in chunk_metadata]
        avg_chunk_size_mb = sum(chunk_sizes_mb) / len(chunk_sizes_mb) if chunk_sizes_mb else 0
        
        logger.info(
            f"Successfully created {len(chunks)} chunks for video {video_id}",
            extra={
                'video_id': video_id,
                'chunk_count': len(chunks),
                'total_duration': duration,
                'file_sizes': [m['file_size'] for m in chunk_metadata],
                'chunk_sizes_mb': chunk_sizes_mb,
                'avg_chunk_size_mb': round(avg_chunk_size_mb, 2),
                'total_chunk_size_mb': round(total_chunk_size / (1024 * 1024), 2),
                'original_size_mb': round(file_size_mb, 2)
            }
        )
        
        return chunks
        
    except Exception as e:
        logger.error(
            f"Failed to create chunks for video {video_id}: {e}",
            extra={
                'video_id': video_id,
                'audio_path': audio_path,
                'error_type': type(e).__name__,
                'error_message': str(e)
            }
        )
        
        # Cleanup: Try to delete any partial chunks created
        _cleanup_partial_chunks(video_id)
        
        raise


def _cleanup_partial_chunks(video_id: str) -> None:
    """
    Clean up partial chunks if chunk creation fails midway.
    
    Args:
        video_id: Video ID to clean up chunks for
    """
    try:
        chunk_dir = settings.chunk_storage_path / video_id
        if chunk_dir.exists():
            import shutil
            
            # Count files before deletion for logging
            chunk_files = list(chunk_dir.glob('*'))
            file_count = len(chunk_files)
            
            shutil.rmtree(chunk_dir)
            
            logger.info(
                f"Cleaned up {file_count} partial chunk files for video {video_id}",
                extra={
                    'video_id': video_id,
                    'files_deleted': file_count,
                    'cleanup_path': str(chunk_dir)
                }
            )
        else:
            logger.debug(
                f"No partial chunks to clean up for video {video_id}",
                extra={'video_id': video_id}
            )
    except Exception as cleanup_error:
        logger.error(
            f"Failed to cleanup partial chunks for video {video_id}: {cleanup_error}",
            extra={
                'video_id': video_id,
                'error_type': type(cleanup_error).__name__,
                'error_message': str(cleanup_error)
            }
        )
