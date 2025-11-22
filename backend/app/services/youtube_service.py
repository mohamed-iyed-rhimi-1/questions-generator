import yt_dlp
from yt_dlp.utils import DownloadError, ExtractorError, PostProcessingError
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError, OperationalError
import re
import logging
import shutil
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings
from app.models.video import Video
from app.exceptions import VideoDownloadException, DatabaseException
from app.services.chunk_service import should_create_chunks, create_chunks_for_video

logger = logging.getLogger(__name__)


def extract_video_id_from_url(url: str) -> Optional[str]:
    """Extract YouTube video ID from various URL formats."""
    # Validate URL is not empty or invalid
    if not url or not isinstance(url, str) or len(url.strip()) == 0:
        logger.warning(f"Invalid URL provided: empty or non-string")
        return None
    
    # Check for common invalid patterns
    if not ('youtube.com' in url or 'youtu.be' in url):
        logger.warning(f"Invalid URL provided: not a YouTube URL - {url}")
        return None
    
    # More explicit pattern targeting specific YouTube URL forms
    pattern = r'(?:v=|vi=|v\/|vi\/|youtu\.be\/|shorts\/|embed\/)([0-9A-Za-z_-]{11})'
    match = re.search(pattern, url)
    
    if not match:
        logger.warning(f"Could not extract video ID from URL: {url}")
    
    return match.group(1) if match else None


def get_ydl_opts_base() -> Dict[str, Any]:
    """Get base yt-dlp options with anti-blocking measures."""
    return {
        'quiet': True,
        'no_warnings': True,
        'socket_timeout': 360,  # Increased from 30 to 60 seconds
        # Anti-blocking measures
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
                'player_skip': ['webpage'],
            }
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
            'Sec-Fetch-Mode': 'navigate',
        }
    }


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((DownloadError, ExtractorError))
)
def extract_video_metadata(url: str) -> Dict[str, Any]:
    """Extract video metadata without downloading. Retries up to 3 times for transient failures."""
    ydl_opts = get_ydl_opts_base()
    ydl_opts.update({
        'skip_download': True,
        'noplaylist': True,
        'extract_flat': False,
    })
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            data = ydl.sanitize_info(info)
            
            # Extract thumbnail URL
            thumbnail_url = data.get('thumbnail')
            if not thumbnail_url and data.get('thumbnails'):
                thumbnail_url = data['thumbnails'][-1].get('url')
            
            logger.info(f"Successfully extracted metadata for video: {data.get('id')}")
            
            return {
                'video_id': data.get('id'),
                'title': data.get('title'),
                'thumbnail_url': thumbnail_url,
                'duration': data.get('duration'),
                'uploader': data.get('uploader'),
            }
    except DownloadError as e:
        logger.error(
            "Metadata extraction failed - download error",
            extra={"url": url, "error": str(e), "error_type": "DownloadError"}
        )
        return {'error': 'NETWORK_ERROR', 'message': str(e)}
    except ExtractorError as e:
        logger.error(
            "Metadata extraction failed - extractor error",
            extra={"url": url, "error": str(e), "error_type": "ExtractorError"}
        )
        return {'error': 'EXTRACTION_ERROR', 'message': str(e)}
    except Exception as e:
        logger.error(
            "Metadata extraction failed - unexpected error",
            extra={"url": url, "error": str(e), "error_type": type(e).__name__}
        )
        return {'error': 'UNKNOWN_ERROR', 'message': str(e)}


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    retry=retry_if_exception_type((DownloadError, ConnectionError))
)
def download_audio_as_mp3(url: str, video_id: str) -> Optional[str]:
    """Download video audio and convert to WAV (lossless, better for Whisper). Retries up to 3 times."""
    audio_path = settings.audio_storage_path
    
    # Check available disk space (require at least 10MB)
    try:
        stat = shutil.disk_usage(audio_path)
        available_mb = stat.free / (1024 * 1024)
        if available_mb < 10:
            logger.warning(
                f"Low disk space: {available_mb:.2f}MB available. Download may fail."
            )
    except Exception as e:
        logger.warning(f"Could not check disk space: {e}")
    
    ydl_opts = get_ydl_opts_base()
    ydl_opts.update({
        'format': 'bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best',
        'outtmpl': str(audio_path / f'{video_id}.%(ext)s'),
        'restrictfilenames': True,
        'windowsfilenames': True,
        'writethumbnail': True,  # Enable thumbnail download
        'keepvideo': False,  # Don't keep the original video file after processing
        'postprocessors': [
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',  # WAV is lossless and more reliable for Whisper
            },
            {
                'key': 'FFmpegMetadata',
            },
            # Note: EmbedThumbnail can cause issues with some audio files
            # The thumbnail will be saved separately instead
        ],
        'postprocessor_args': [
            '-ar', '16000',  # 16kHz to match Whisper's expected sample rate
            '-ac', '1',  # Mono audio (Whisper converts to mono anyway)
        ],
        'noprogress': True,
        'retries': 3,  # Retry failed downloads
        'fragment_retries': 3,  # Retry failed fragments
    })
    
    output_file = audio_path / f'{video_id}.wav'
    
    try:
        logger.info(f"Starting audio download for video: {video_id}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # Verify file exists
        if output_file.exists():
            file_size = output_file.stat().st_size
            file_size_kb = file_size / 1024
            file_size_mb = file_size / (1024 * 1024)
            
            # Validate file size
            if file_size == 0:
                logger.error(f"Downloaded file is empty: {output_file}")
                output_file.unlink()  # Delete empty file
                return None
            elif file_size_kb < 10:  # Less than 10KB is definitely too small
                logger.error(
                    f"Downloaded file too small ({file_size_kb:.2f}KB), likely corrupted: {output_file}"
                )
                output_file.unlink()  # Delete suspicious file
                return None
            elif file_size_kb < 100:
                logger.warning(
                    f"Downloaded file seems suspiciously small: {file_size_kb:.2f}KB"
                )
            
            # Verify the audio file can be opened (basic validation)
            try:
                import mutagen
                audio_info = mutagen.File(output_file)
                if audio_info is None:
                    logger.error(f"Downloaded file is not a valid audio file: {output_file}")
                    output_file.unlink()
                    return None
                    
                # Check duration
                if hasattr(audio_info.info, 'length') and audio_info.info.length < 1.0:
                    logger.error(
                        f"Downloaded audio too short ({audio_info.info.length:.2f}s): {output_file}"
                    )
                    output_file.unlink()
                    return None
                    
            except Exception as validation_error:
                logger.warning(
                    f"Could not validate audio file metadata: {validation_error}. "
                    f"Proceeding anyway, but transcription may fail."
                )
            
            # Look for and move thumbnail file to thumbnail storage
            thumbnail_path = None
            thumbnail_extensions = ['.jpg', '.jpeg', '.png', '.webp']
            for ext in thumbnail_extensions:
                potential_thumb = audio_path / f'{video_id}{ext}'
                if potential_thumb.exists():
                    try:
                        # Move thumbnail to thumbnail storage
                        thumbnail_storage = settings.thumbnail_storage_path
                        thumbnail_storage.mkdir(parents=True, exist_ok=True)
                        destination = thumbnail_storage / f'{video_id}{ext}'
                        shutil.move(str(potential_thumb), str(destination))
                        thumbnail_path = str(destination)
                        logger.info(f"Moved thumbnail to: {thumbnail_path}")
                        break
                    except Exception as thumb_error:
                        logger.warning(f"Failed to move thumbnail: {thumb_error}")
            
            if not thumbnail_path:
                logger.debug(f"No thumbnail file found for {video_id}")
            
            logger.info(
                f"Successfully downloaded audio for {video_id} ({file_size_kb:.2f}KB)"
            )
            return str(output_file)
        else:
            logger.error(f"Downloaded file not found: {output_file}")
            return None
    except DownloadError as e:
        logger.error(
            "Audio download failed - download error",
            extra={"url": url, "video_id": video_id, "error": str(e)}
        )
        # Clean up partial downloads
        if output_file.exists():
            output_file.unlink()
        return None
    except PostProcessingError as e:
        logger.error(
            "Audio download failed - post-processing error",
            extra={"url": url, "video_id": video_id, "error": str(e)}
        )
        # Clean up partial downloads
        if output_file.exists():
            output_file.unlink()
        return None
    except Exception as e:
        logger.error(
            "Audio download failed - unexpected error",
            extra={"url": url, "video_id": video_id, "error": str(e)}
        )
        # Clean up partial downloads
        if output_file.exists():
            output_file.unlink()
        return None


def save_video_to_db(session: Session, video_data: Dict[str, Any]) -> Tuple[Video, bool]:
    """Save video to database with atomic duplicate detection."""
    video_id = video_data.get('video_id')
    
    try:
        # Use PostgreSQL's INSERT ... ON CONFLICT DO NOTHING
        stmt = insert(Video).values(**video_data).on_conflict_do_nothing(
            index_elements=['video_id']
        ).returning(Video.id)
        
        result = session.execute(stmt)
        inserted_id = result.scalar()
        
        if inserted_id is not None:
            # New record created
            session.commit()
            video = session.query(Video).filter_by(id=inserted_id).first()
            logger.info(
                f"Saved video to database",
                extra={"video_id": video_id, "is_new": True, "db_id": inserted_id}
            )
            return (video, True)
        else:
            # Duplicate found
            video = session.query(Video).filter_by(video_id=video_id).first()
            logger.info(
                f"Video already exists in database",
                extra={"video_id": video_id, "is_new": False}
            )
            return (video, False)
    except IntegrityError as e:
        session.rollback()
        logger.error(
            f"Database integrity error saving video",
            extra={"video_id": video_id, "error": str(e)}
        )
        # Try to return existing video
        video = session.query(Video).filter_by(video_id=video_id).first()
        if video:
            return (video, False)
        raise DatabaseException(f"Failed to save video {video_id}: duplicate key", details={"video_id": video_id})
    except OperationalError as e:
        session.rollback()
        logger.error(
            f"Database operational error saving video",
            extra={"video_id": video_id, "error": str(e)}
        )
        raise DatabaseException(
            f"Database connection error while saving video {video_id}. Please retry.",
            details={"video_id": video_id, "error_type": "OperationalError"}
        )
    except Exception as e:
        session.rollback()
        logger.error(
            f"Unexpected database error saving video",
            extra={"video_id": video_id, "error": str(e), "error_type": type(e).__name__}
        )
        raise DatabaseException(f"Failed to save video {video_id}", details={"video_id": video_id})


def process_video_url(url: str, session: Session) -> Dict[str, Any]:
    """Process a single YouTube URL: extract metadata, download, and save to database."""
    try:
        # Step 1: Quick validation - extract video_id
        video_id = extract_video_id_from_url(url)
        if not video_id:
            return {
                'status': 'failed',
                'url': url,
                'error': 'INVALID_URL',
                'message': 'Invalid YouTube URL. Please check the URL format. Supported: youtube.com/watch?v=..., youtu.be/..., youtube.com/shorts/...',
            }
        
        # Step 2: Check if video already exists
        existing = session.query(Video).filter_by(video_id=video_id).first()
        if existing:
            return {
                'status': 'duplicate',
                'url': url,
                'video_id': video_id,
                'video': existing,
                'message': 'Video already downloaded',
            }
        
        # Step 3: Extract metadata
        logger.info(f"Extracting metadata for {video_id}")
        metadata = extract_video_metadata(url)
        if 'error' in metadata:
            error_code = metadata.get('error', 'UNKNOWN_ERROR')
            error_msg = metadata.get('message', 'Failed to extract video metadata')
            
            # Provide user-friendly messages
            if error_code == 'NETWORK_ERROR':
                user_message = 'Network error while accessing YouTube. Please check your connection and try again.'
            elif error_code == 'EXTRACTION_ERROR':
                user_message = 'Failed to extract video information. The video may be private, deleted, or restricted.'
            else:
                user_message = f'Failed to extract video metadata: {error_msg}'
            
            return {
                'status': 'failed',
                'url': url,
                'video_id': video_id,
                'error': error_code,
                'message': user_message,
            }
        
        # Step 4: Download audio
        logger.info(f"Downloading audio for {video_id}")
        file_path = download_audio_as_mp3(url, video_id)
        if not file_path:
            return {
                'status': 'failed',
                'url': url,
                'video_id': video_id,
                'error': 'DOWNLOAD_FAILED',
                'message': 'Download failed. This may be due to network issues, video restrictions, or YouTube rate limiting. Please try again later.',
            }
        
        # Step 5: Prepare video data
        video_data = {
            'video_id': metadata['video_id'],
            'title': metadata['title'],
            'thumbnail_url': metadata.get('thumbnail_url'),
            'file_path': file_path,
        }
        
        # Step 6: Save to database
        logger.info(f"Saving {video_id} to database")
        video, is_new = save_video_to_db(session, video_data)
        
        # Step 6.5: Create chunks if needed (after video is saved to database)
        if settings.auto_chunk_enabled and file_path and is_new:
            try:
                if should_create_chunks(file_path, settings.max_chunk_size_mb):
                    logger.info(f"File size exceeds threshold, creating chunks for {video_id}")
                    chunks = create_chunks_for_video(
                        video_id,
                        file_path,
                        settings.max_chunk_size_mb,
                        session
                    )
                    logger.info(f"Successfully created {len(chunks)} chunks for video {video_id}")
                else:
                    logger.debug(f"File size below threshold, skipping chunk creation for {video_id}")
            except Exception as e:
                # Log error but don't fail the download - chunks are optional
                logger.error(
                    f"Failed to create chunks for {video_id}: {e}",
                    extra={"video_id": video_id, "error": str(e), "error_type": type(e).__name__}
                )
        
        # Step 7: Return result
        if is_new:
            return {
                'status': 'success',
                'url': url,
                'video_id': video_id,
                'video': video,
                'message': 'Video downloaded successfully',
            }
        else:
            # Race condition: another process inserted it
            return {
                'status': 'duplicate',
                'url': url,
                'video_id': video_id,
                'video': video,
                'message': 'Video already downloaded (race condition)',
            }
    except Exception as e:
        logger.exception(f"Unexpected error processing {url}")
        return {
            'status': 'failed',
            'url': url,
            'error': str(e),
            'message': 'Unexpected error during processing',
        }


def process_multiple_urls(urls: List[str], session: Session) -> List[Dict[str, Any]]:
    """Process multiple YouTube URLs sequentially."""
    results = []
    total = len(urls)
    
    logger.info(f"Starting batch processing of {total} URLs")
    
    try:
        for idx, url in enumerate(urls, 1):
            logger.info(f"Processing URL {idx}/{total}: {url}")
            result = process_video_url(url, session)
            results.append(result)
            
            # Log progress every 5 videos
            if idx % 5 == 0 or idx == total:
                success_count = sum(1 for r in results if r['status'] == 'success')
                logger.info(
                    f"Progress: {idx}/{total} URLs processed ({success_count} successful)"
                )
    except KeyboardInterrupt:
        logger.warning(f"Batch processing interrupted at {len(results)}/{total}")
        # Return partial results
        return results
    
    # Final summary
    success_count = sum(1 for r in results if r['status'] == 'success')
    duplicate_count = sum(1 for r in results if r['status'] == 'duplicate')
    failed_count = sum(1 for r in results if r['status'] == 'failed')
    
    logger.info(
        f"Batch processing complete: {success_count} successful, "
        f"{duplicate_count} duplicates, {failed_count} failed"
    )
    
    return results