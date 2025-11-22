#!/usr/bin/env python3
"""
Audio file splitting script for large files that exceed provider limits.

Splits audio files into chunks of ≤25MB at silence points for clean breaks.
Uses FFmpeg for efficient processing (already available in the codebase).

Usage:
    python scripts/split_audio.py <video_id> [--max-size 25] [--output-dir chunks]

Examples:
    python scripts/split_audio.py Fvx9ie6uJWo
    python scripts/split_audio.py Fvx9ie6uJWo --max-size 20
    python scripts/split_audio.py Fvx9ie6uJWo --output-dir /tmp/chunks
"""

import sys
import argparse
import logging
import subprocess
import json
from pathlib import Path
from typing import List, Tuple, Optional

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def find_audio_file(video_id: str) -> Path:
    """Find the audio file for a video ID (supports both .wav and .mp3)."""
    audio_path = settings.audio_storage_path
    
    # Try WAV first (new format)
    wav_file = audio_path / f"{video_id}.wav"
    if wav_file.exists():
        return wav_file
    
    # Try MP3 (old format)
    mp3_file = audio_path / f"{video_id}.mp3"
    if mp3_file.exists():
        return mp3_file
    
    raise FileNotFoundError(f"No audio file found for video ID: {video_id}")


def get_audio_duration(audio_path: Path) -> float:
    """Get audio duration in seconds using ffprobe."""
    try:
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            str(audio_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        duration = float(data['format']['duration'])
        
        return duration
        
    except Exception as e:
        logger.error(f"Failed to get audio duration: {e}")
        raise


def detect_silence_points(
    audio_path: Path,
    min_silence_duration: float = 0.3,
    noise_threshold: int = -35
) -> List[float]:
    """
    Detect silence points in audio using FFmpeg silencedetect filter.
    
    Args:
        audio_path: Path to audio file
        min_silence_duration: Minimum silence duration in seconds (default: 0.3)
        noise_threshold: Noise threshold in dB (default: -35, higher = more lenient)
        
    Returns:
        List of silence midpoints in seconds
    """
    try:
        logger.info(f"Detecting silence (threshold: {noise_threshold}dB, min duration: {min_silence_duration}s)...")
        
        cmd = [
            'ffmpeg',
            '-i', str(audio_path),
            '-af', f'silencedetect=noise={noise_threshold}dB:d={min_silence_duration}',
            '-f', 'null',
            '-'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        # Parse silence detection output
        silence_starts = []
        silence_ends = []
        
        for line in result.stderr.split('\n'):
            if 'silence_start' in line:
                try:
                    # Parse: [silencedetect @ 0x...] silence_start: 123.456
                    parts = line.split('silence_start:')
                    if len(parts) > 1:
                        start = float(parts[1].strip().split()[0])
                        silence_starts.append(start)
                        logger.debug(f"  Found silence start: {start:.2f}s")
                except (IndexError, ValueError) as e:
                    logger.debug(f"  Failed to parse silence_start: {line.strip()}")
                    continue
            elif 'silence_end' in line:
                try:
                    # Parse: [silencedetect @ 0x...] silence_end: 124.567 | silence_duration: 1.111
                    parts = line.split('silence_end:')
                    if len(parts) > 1:
                        end_part = parts[1].strip().split('|')[0].strip()
                        end = float(end_part)
                        silence_ends.append(end)
                        
                        # Extract duration if available
                        if 'silence_duration' in line:
                            duration_part = line.split('silence_duration:')[1].strip()
                            duration = float(duration_part)
                            logger.debug(f"  Found silence end: {end:.2f}s (duration: {duration:.2f}s)")
                        else:
                            logger.debug(f"  Found silence end: {end:.2f}s")
                except (IndexError, ValueError) as e:
                    logger.debug(f"  Failed to parse silence_end: {line.strip()}")
                    continue
        
        # Calculate midpoints of silence periods
        silence_points = []
        min_pairs = min(len(silence_starts), len(silence_ends))
        
        for i in range(min_pairs):
            start = silence_starts[i]
            end = silence_ends[i]
            midpoint = (start + end) / 2
            duration = end - start
            silence_points.append(midpoint)
            logger.debug(f"  Silence #{i+1}: {start:.2f}s - {end:.2f}s (midpoint: {midpoint:.2f}s, duration: {duration:.2f}s)")
        
        logger.info(f"Detected {len(silence_points)} silence points")
        
        if len(silence_points) == 0:
            logger.warning("No silence detected. Try adjusting threshold with --silence-threshold")
            logger.warning("  More lenient (detect more): -30 to -25")
            logger.warning("  More strict (detect less): -45 to -50")
        
        return silence_points
        
    except Exception as e:
        logger.warning(f"Failed to detect silence: {e}")
        return []


def calculate_split_points(
    duration: float,
    file_size_mb: float,
    max_chunk_mb: float,
    silence_points: List[float]
) -> List[float]:
    """
    Calculate optimal split points based on file size and silence detection.
    
    Args:
        duration: Total audio duration in seconds
        file_size_mb: Total file size in MB
        max_chunk_mb: Maximum chunk size in MB
        silence_points: List of detected silence points in seconds
        
    Returns:
        List of split points in seconds
    """
    # Calculate how many chunks we need
    num_chunks = int(file_size_mb / max_chunk_mb) + 1
    
    if num_chunks == 1:
        logger.info("File is already under size limit, no splitting needed")
        return []
    
    logger.info(f"File needs to be split into ~{num_chunks} chunks")
    
    # Calculate target split positions (evenly distributed)
    target_duration_per_chunk = duration / num_chunks
    target_positions = [target_duration_per_chunk * i for i in range(1, num_chunks)]
    
    # Find best silence point near each target position
    split_points = []
    search_range = 10.0  # seconds to search around target
    
    for target in target_positions:
        if not silence_points:
            # No silence detected, use target position
            split_points.append(target)
            logger.info(f"  Split at {target:.1f}s (no silence detected)")
            continue
        
        # Find silence point closest to target
        nearby_silences = [
            s for s in silence_points
            if abs(s - target) <= search_range
        ]
        
        if nearby_silences:
            best_split = min(nearby_silences, key=lambda s: abs(s - target))
            split_points.append(best_split)
            logger.info(f"  Split at {best_split:.1f}s (silence, target was {target:.1f}s)")
        else:
            split_points.append(target)
            logger.info(f"  Split at {target:.1f}s (no nearby silence)")
    
    return split_points


def split_audio_file(
    audio_path: Path,
    split_points: List[float],
    output_dir: Path
) -> List[Path]:
    """
    Split audio file at specified points using FFmpeg.
    
    Args:
        audio_path: Path to input audio file
        split_points: List of split points in seconds
        output_dir: Directory to save chunks
        
    Returns:
        List of paths to created chunk files
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Get file extension
    extension = audio_path.suffix
    base_name = audio_path.stem
    
    chunk_files = []
    start_time = 0.0
    
    # Add final split point (end of file)
    duration = get_audio_duration(audio_path)
    all_splits = split_points + [duration]
    
    for i, end_time in enumerate(all_splits):
        chunk_duration = end_time - start_time
        chunk_name = f"{base_name}_chunk_{i+1:03d}{extension}"
        chunk_path = output_dir / chunk_name
        
        logger.info(f"Creating chunk {i+1}/{len(all_splits)}: {chunk_name} ({chunk_duration:.1f}s)")
        
        # Use FFmpeg to extract chunk
        cmd = [
            'ffmpeg',
            '-i', str(audio_path),
            '-ss', str(start_time),
            '-t', str(chunk_duration),
            '-c', 'copy',  # Copy codec (fast, no re-encoding)
            '-y',  # Overwrite output
            str(chunk_path)
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=300
            )
            
            # Verify chunk was created
            if chunk_path.exists():
                chunk_size_mb = chunk_path.stat().st_size / (1024 * 1024)
                logger.info(f"  ✓ Created {chunk_name} ({chunk_size_mb:.2f} MB)")
                chunk_files.append(chunk_path)
            else:
                logger.error(f"  ✗ Failed to create {chunk_name}")
                
        except subprocess.TimeoutExpired:
            logger.error(f"  ✗ Timeout creating {chunk_name}")
        except subprocess.CalledProcessError as e:
            logger.error(f"  ✗ FFmpeg error: {e.stderr}")
        
        start_time = end_time
    
    return chunk_files


def split_audio(
    video_id: str,
    max_chunk_mb: float = 25.0,
    output_dir: Optional[Path] = None,
    silence_threshold: int = -35,
    min_silence_duration: float = 0.3,
    use_silence_detection: bool = True
) -> List[Path]:
    """
    Split an audio file into chunks of maximum size.
    
    Args:
        video_id: YouTube video ID
        max_chunk_mb: Maximum chunk size in MB
        output_dir: Output directory (default: storage/audio/chunks/<video_id>)
        silence_threshold: Silence detection threshold in dB
        min_silence_duration: Minimum silence duration in seconds
        use_silence_detection: Whether to use silence detection
        
    Returns:
        List of paths to created chunk files
    """
    try:
        # Step 1: Find the audio file
        logger.info(f"Looking for audio file for video: {video_id}")
        audio_path = find_audio_file(video_id)
        logger.info(f"Found audio file: {audio_path}")
        
        # Step 2: Check file size
        file_size_mb = audio_path.stat().st_size / (1024 * 1024)
        logger.info(f"File size: {file_size_mb:.2f} MB")
        
        if file_size_mb <= max_chunk_mb:
            logger.info(f"File is already under {max_chunk_mb}MB limit, no splitting needed")
            return [audio_path]
        
        # Step 3: Get audio duration
        duration = get_audio_duration(audio_path)
        logger.info(f"Audio duration: {duration/60:.2f} minutes")
        
        # Step 4: Detect silence points
        if use_silence_detection:
            silence_points = detect_silence_points(
                audio_path,
                min_silence_duration=min_silence_duration,
                noise_threshold=silence_threshold
            )
        else:
            logger.info("Silence detection disabled, will split at exact intervals")
            silence_points = []
        
        # Step 5: Calculate split points
        logger.info("Calculating optimal split points...")
        split_points = calculate_split_points(
            duration,
            file_size_mb,
            max_chunk_mb,
            silence_points
        )
        
        # Step 6: Set output directory
        if output_dir is None:
            output_dir = settings.audio_storage_path / "chunks" / video_id
        
        logger.info(f"Output directory: {output_dir}")
        
        # Step 7: Split the audio file
        logger.info("Splitting audio file...")
        chunk_files = split_audio_file(audio_path, split_points, output_dir)
        
        logger.info(f"✓ Successfully created {len(chunk_files)} chunks")
        
        return chunk_files
        
    except Exception as e:
        logger.error(f"Error splitting audio: {e}", exc_info=True)
        return []


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Split large audio files into smaller chunks at silence points",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python scripts/split_audio.py Fvx9ie6uJWo
  
  # Custom chunk size
  python scripts/split_audio.py Fvx9ie6uJWo --max-size 20
  
  # Adjust silence detection (more lenient)
  python scripts/split_audio.py Fvx9ie6uJWo --silence-threshold -30
  
  # Adjust silence detection (more strict)
  python scripts/split_audio.py Fvx9ie6uJWo --silence-threshold -45
  
  # Disable silence detection (split at exact intervals)
  python scripts/split_audio.py Fvx9ie6uJWo --no-silence
  
  # Custom output directory
  python scripts/split_audio.py Fvx9ie6uJWo --output-dir /tmp/chunks

Silence Detection Tips:
  -30 to -25 dB: More lenient (detects more silence, including quiet speech)
  -35 to -40 dB: Balanced (default, good for most content)
  -45 to -50 dB: More strict (only very quiet sections)
        """
    )
    
    parser.add_argument(
        'video_id',
        help='YouTube video ID to split'
    )
    
    parser.add_argument(
        '--max-size',
        type=float,
        default=25.0,
        help='Maximum chunk size in MB (default: 25)'
    )
    
    parser.add_argument(
        '--output-dir',
        type=Path,
        help='Output directory for chunks (default: storage/audio/chunks/<video_id>)'
    )
    
    parser.add_argument(
        '--silence-threshold',
        type=int,
        default=-35,
        help='Silence detection threshold in dB (default: -35, higher = more lenient)'
    )
    
    parser.add_argument(
        '--min-silence',
        type=float,
        default=0.3,
        help='Minimum silence duration in seconds (default: 0.3)'
    )
    
    parser.add_argument(
        '--no-silence',
        action='store_true',
        help='Disable silence detection, split at exact intervals'
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Audio File Splitting Script")
    logger.info("=" * 60)
    
    chunk_files = split_audio(
        video_id=args.video_id,
        max_chunk_mb=args.max_size,
        output_dir=args.output_dir,
        silence_threshold=args.silence_threshold,
        min_silence_duration=args.min_silence,
        use_silence_detection=not args.no_silence
    )
    
    logger.info("=" * 60)
    
    if chunk_files:
        logger.info(f"✓ Split completed successfully")
        logger.info(f"✓ Created {len(chunk_files)} chunks:")
        for chunk in chunk_files:
            logger.info(f"  - {chunk.name}")
        sys.exit(0)
    else:
        logger.error("✗ Split failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
