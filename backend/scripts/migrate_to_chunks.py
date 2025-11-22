#!/usr/bin/env python3
"""
Migration script to convert existing videos to chunk-based architecture.

This script identifies videos with audio files larger than the chunk size threshold
and creates chunks for them. It can be run in dry-run mode to preview changes
without making modifications.

Usage:
    # Migrate all videos (dry-run)
    python scripts/migrate_to_chunks.py --dry-run
    
    # Migrate all videos (actual migration)
    python scripts/migrate_to_chunks.py
    
    # Migrate specific video
    python scripts/migrate_to_chunks.py --video-id VIDEO_ID
    
    # Migrate specific video (dry-run)
    python scripts/migrate_to_chunks.py --video-id VIDEO_ID --dry-run
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.database import SessionLocal, check_database_connection
from app.models.video import Video
from app.models.chunk import Chunk
from app.config import settings
from app.services.chunk_service import (
    should_create_chunks,
    create_chunks_for_video,
    get_chunks_for_video
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def migrate_video_to_chunks(
    video_id: str,
    session: Session,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Migrate a single video to chunk-based architecture.
    
    Checks if the video's audio file exceeds the chunk size threshold,
    and creates chunks if needed. Skips videos that already have chunks
    or don't need chunking.
    
    Args:
        video_id: Video ID to migrate
        session: Database session
        dry_run: If True, only check and log without making changes
        
    Returns:
        Dictionary with migration result:
        - status: 'success', 'skipped', or 'failed'
        - video_id: Video ID
        - message: Description of what happened
        - chunk_count: Number of chunks created (if applicable)
        - error: Error message (if failed)
    """
    try:
        # Query video from database
        video = session.query(Video).filter(Video.video_id == video_id).first()
        
        if not video:
            logger.warning(f"Video {video_id} not found in database")
            return {
                'status': 'skipped',
                'video_id': video_id,
                'message': 'Video not found in database'
            }
        
        # Check if video already has chunks
        existing_chunks = get_chunks_for_video(video_id, session)
        if existing_chunks:
            logger.info(
                f"Video {video_id} already has {len(existing_chunks)} chunks, skipping"
            )
            return {
                'status': 'skipped',
                'video_id': video_id,
                'message': f'Already has {len(existing_chunks)} chunks',
                'chunk_count': len(existing_chunks)
            }
        
        # Check if video has audio file
        if not video.file_path:
            logger.warning(f"Video {video_id} has no audio file path")
            return {
                'status': 'skipped',
                'video_id': video_id,
                'message': 'No audio file path'
            }
        
        audio_path = Path(video.file_path)
        if not audio_path.exists():
            logger.warning(f"Audio file not found for video {video_id}: {audio_path}")
            return {
                'status': 'skipped',
                'video_id': video_id,
                'message': f'Audio file not found: {audio_path}'
            }
        
        # Check if file size exceeds threshold
        if not should_create_chunks(str(audio_path), settings.max_chunk_size_mb):
            file_size_mb = audio_path.stat().st_size / (1024 * 1024)
            logger.info(
                f"Video {video_id} file size {file_size_mb:.2f}MB is below "
                f"threshold {settings.max_chunk_size_mb}MB, skipping"
            )
            return {
                'status': 'skipped',
                'video_id': video_id,
                'message': f'File size {file_size_mb:.2f}MB below threshold',
                'file_size_mb': file_size_mb
            }
        
        file_size_mb = audio_path.stat().st_size / (1024 * 1024)
        
        if dry_run:
            logger.info(
                f"[DRY RUN] Would create chunks for video {video_id} "
                f"(file size: {file_size_mb:.2f}MB)"
            )
            return {
                'status': 'success',
                'video_id': video_id,
                'message': f'Would create chunks (file size: {file_size_mb:.2f}MB)',
                'file_size_mb': file_size_mb,
                'dry_run': True
            }
        
        # Create chunks
        logger.info(
            f"Creating chunks for video {video_id} "
            f"(file size: {file_size_mb:.2f}MB)"
        )
        
        chunks = create_chunks_for_video(
            video_id,
            str(audio_path),
            settings.max_chunk_size_mb,
            session
        )
        
        logger.info(
            f"Successfully created {len(chunks)} chunks for video {video_id}"
        )
        
        return {
            'status': 'success',
            'video_id': video_id,
            'message': f'Created {len(chunks)} chunks',
            'chunk_count': len(chunks),
            'file_size_mb': file_size_mb
        }
        
    except Exception as e:
        logger.error(
            f"Failed to migrate video {video_id}: {e}",
            exc_info=True
        )
        return {
            'status': 'failed',
            'video_id': video_id,
            'message': 'Migration failed',
            'error': str(e)
        }


def migrate_all_videos(session: Session, dry_run: bool = False) -> Dict[str, Any]:
    """
    Migrate all videos that exceed the chunk size threshold.
    
    Queries all videos from the database, filters by file size threshold,
    and creates chunks for eligible videos. Continues processing even if
    individual videos fail.
    
    Args:
        session: Database session
        dry_run: If True, only check and log without making changes
        
    Returns:
        Dictionary with migration summary:
        - total_videos: Total number of videos in database
        - processed: Number of videos processed
        - successful: Number of successful migrations
        - skipped: Number of videos skipped
        - failed: Number of failed migrations
        - results: List of individual migration results
    """
    try:
        # Query all videos
        videos = session.query(Video).all()
        total_videos = len(videos)
        
        logger.info(f"Found {total_videos} videos in database")
        
        if dry_run:
            logger.info("[DRY RUN] No changes will be made")
        
        results = []
        successful = 0
        skipped = 0
        failed = 0
        processed = 0
        
        for idx, video in enumerate(videos, 1):
            # Progress logging every 5 videos
            if idx % 5 == 0:
                logger.info(
                    f"Progress: {idx}/{total_videos} videos processed "
                    f"(successful: {successful}, skipped: {skipped}, failed: {failed})"
                )
            
            result = migrate_video_to_chunks(video.video_id, session, dry_run)
            results.append(result)
            processed += 1
            
            if result['status'] == 'success':
                successful += 1
            elif result['status'] == 'skipped':
                skipped += 1
            elif result['status'] == 'failed':
                failed += 1
        
        # Summary statistics
        summary = {
            'total_videos': total_videos,
            'processed': processed,
            'successful': successful,
            'skipped': skipped,
            'failed': failed,
            'results': results
        }
        
        logger.info("=" * 80)
        logger.info("Migration Summary:")
        logger.info(f"  Total videos in database: {total_videos}")
        logger.info(f"  Videos processed: {processed}")
        logger.info(f"  Successful migrations: {successful}")
        logger.info(f"  Videos skipped: {skipped}")
        logger.info(f"  Failed migrations: {failed}")
        
        if dry_run:
            logger.info("[DRY RUN] No changes were made")
        
        logger.info("=" * 80)
        
        # Log failed videos if any
        if failed > 0:
            logger.warning("Failed videos:")
            for result in results:
                if result['status'] == 'failed':
                    logger.warning(
                        f"  - {result['video_id']}: {result.get('error', 'Unknown error')}"
                    )
        
        return summary
        
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        raise


def main():
    """Main entry point for the migration script."""
    parser = argparse.ArgumentParser(
        description='Migrate existing videos to chunk-based architecture',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run for all videos
  python scripts/migrate_to_chunks.py --dry-run
  
  # Migrate all videos
  python scripts/migrate_to_chunks.py
  
  # Migrate specific video
  python scripts/migrate_to_chunks.py --video-id dQw4w9WgXcQ
  
  # Dry run for specific video
  python scripts/migrate_to_chunks.py --video-id dQw4w9WgXcQ --dry-run
        """
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without making modifications'
    )
    
    parser.add_argument(
        '--video-id',
        type=str,
        help='Migrate specific video by ID (optional)'
    )
    
    args = parser.parse_args()
    
    # Check database connection
    logger.info("Checking database connection...")
    if not check_database_connection():
        logger.error("Database connection failed. Please check your configuration.")
        sys.exit(1)
    
    logger.info("Database connection successful")
    logger.info(f"Chunk size threshold: {settings.max_chunk_size_mb}MB")
    logger.info(f"Silence threshold: {settings.silence_threshold_db}dB")
    logger.info(f"Min silence duration: {settings.min_silence_duration}s")
    
    # Create database session
    session = SessionLocal()
    
    try:
        if args.video_id:
            # Migrate specific video
            logger.info(f"Migrating video: {args.video_id}")
            result = migrate_video_to_chunks(args.video_id, session, args.dry_run)
            
            logger.info("=" * 80)
            logger.info("Migration Result:")
            logger.info(f"  Status: {result['status']}")
            logger.info(f"  Video ID: {result['video_id']}")
            logger.info(f"  Message: {result['message']}")
            
            if 'chunk_count' in result:
                logger.info(f"  Chunks created: {result['chunk_count']}")
            if 'file_size_mb' in result:
                logger.info(f"  File size: {result['file_size_mb']:.2f}MB")
            if 'error' in result:
                logger.error(f"  Error: {result['error']}")
            
            logger.info("=" * 80)
            
            # Exit with appropriate code
            if result['status'] == 'failed':
                sys.exit(1)
            
        else:
            # Migrate all videos
            logger.info("Migrating all videos...")
            summary = migrate_all_videos(session, args.dry_run)
            
            # Exit with error code if any migrations failed
            if summary['failed'] > 0:
                sys.exit(1)
    
    except KeyboardInterrupt:
        logger.warning("Migration interrupted by user")
        sys.exit(130)
    
    except Exception as e:
        logger.error(f"Migration failed with error: {e}", exc_info=True)
        sys.exit(1)
    
    finally:
        session.close()
        logger.info("Database session closed")


if __name__ == '__main__':
    main()
