#!/usr/bin/env python3
"""
Manual transcription script for troubleshooting and re-processing videos.

Usage:
    python scripts/manual_transcribe.py <video_id> [--language ar] [--provider whisper]

Examples:
    python scripts/manual_transcribe.py Fvx9ie6uJWo
    python scripts/manual_transcribe.py Fvx9ie6uJWo --language ar --provider groq
"""

import sys
import argparse
import logging
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.video import Video
from app.models.transcription import Transcription
from app.config import settings
from app.services.transcription import WhisperTranscriptionProvider, GroqTranscriptionProvider
from sentence_transformers import SentenceTransformer
import torch

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


def manual_transcribe(
    video_id: str,
    language: str = "ar",
    provider: str = None,
    force: bool = False
) -> bool:
    """
    Manually transcribe a video by ID and save to database.
    
    Args:
        video_id: YouTube video ID
        language: Language code (default: "ar")
        provider: Transcription provider ("whisper" or "groq", default: from config)
        force: Force re-transcription even if transcription exists
        
    Returns:
        True if successful, False otherwise
    """
    db: Session = SessionLocal()
    
    try:
        # Step 1: Find the video in database
        logger.info(f"Looking up video: {video_id}")
        video = db.query(Video).filter(Video.video_id == video_id).first()
        
        if not video:
            logger.error(f"Video not found in database: {video_id}")
            logger.info("Please download the video first using the API or UI")
            return False
        
        logger.info(f"Found video: {video.title}")
        
        # Step 2: Check if transcription already exists
        existing_transcription = db.query(Transcription).filter(
            Transcription.video_id == video.video_id
        ).first()
        
        if existing_transcription and not force:
            logger.warning(f"Transcription already exists for video: {video_id}")
            logger.info("Use --force to re-transcribe")
            logger.info(f"Existing transcription: {len(existing_transcription.text)} characters")
            return False
        
        if existing_transcription and force:
            logger.info("Force flag set - deleting existing transcription")
            db.delete(existing_transcription)
            db.commit()
        
        # Step 3: Find the audio file
        logger.info(f"Looking for audio file...")
        try:
            audio_file = find_audio_file(video_id)
            logger.info(f"Found audio file: {audio_file}")
            file_size_mb = audio_file.stat().st_size / (1024 * 1024)
            logger.info(f"File size: {file_size_mb:.2f} MB")
        except FileNotFoundError as e:
            logger.error(str(e))
            return False
        
        # Step 4: Initialize transcription provider
        provider_name = provider or settings.transcription_provider
        logger.info(f"Using transcription provider: {provider_name}")
        
        if provider_name.lower() == 'whisper':
            transcription_provider = WhisperTranscriptionProvider()
        elif provider_name.lower() == 'groq':
            transcription_provider = GroqTranscriptionProvider()
        else:
            logger.error(f"Unknown provider: {provider_name}")
            return False
        
        # Step 5: Transcribe the audio
        logger.info(f"Starting transcription (language: {language})...")
        logger.info("This may take several minutes depending on file size and provider...")
        
        transcription_text = transcription_provider.transcribe_audio(
            str(audio_file),
            language=language
        )
        
        if not transcription_text:
            logger.error("Transcription failed - no text returned")
            return False
        
        logger.info(f"Transcription successful! Length: {len(transcription_text)} characters")
        logger.info(f"Preview: {transcription_text[:200]}...")
        
        # Step 6: Generate embeddings
        logger.info("Generating embeddings...")
        try:
            # Determine device
            if torch.cuda.is_available():
                device = 'cuda'
            elif torch.backends.mps.is_available():
                device = 'mps'
            else:
                device = 'cpu'
            
            logger.info(f"Loading embedding model on {device}...")
            embedding_model = SentenceTransformer(settings.embedding_model_name, device=device)
            
            # Generate embeddings
            embeddings_array = embedding_model.encode(transcription_text, convert_to_numpy=True)
            embeddings = embeddings_array.tolist()
            
            logger.info(f"Generated {len(embeddings)} embedding dimensions")
            
        except Exception as e:
            logger.warning(f"Failed to generate embeddings: {e}")
            logger.warning("Saving transcription without embeddings")
            embeddings = None
        
        # Step 7: Save to database
        logger.info("Saving transcription to database...")
        transcription = Transcription(
            video_id=video.video_id,
            transcription_text=transcription_text,
            vector_embedding=embeddings if embeddings else None
        )
        
        db.add(transcription)
        db.commit()
        db.refresh(transcription)
        
        logger.info(f"✓ Transcription saved successfully (ID: {transcription.id})")
        logger.info(f"✓ Video: {video.title}")
        logger.info(f"✓ Text length: {len(transcription_text)} characters")
        logger.info(f"✓ Provider: {provider_name}")
        logger.info(f"✓ Embeddings: {'Yes' if embeddings else 'No'}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error during transcription: {e}", exc_info=True)
        db.rollback()
        return False
        
    finally:
        db.close()


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Manually transcribe a video by ID and save to database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/manual_transcribe.py Fvx9ie6uJWo
  python scripts/manual_transcribe.py Fvx9ie6uJWo --language ar
  python scripts/manual_transcribe.py Fvx9ie6uJWo --provider whisper
  python scripts/manual_transcribe.py Fvx9ie6uJWo --force
        """
    )
    
    parser.add_argument(
        'video_id',
        help='YouTube video ID to transcribe'
    )
    
    parser.add_argument(
        '--language',
        default='ar',
        help='Language code for transcription (default: ar)'
    )
    
    parser.add_argument(
        '--provider',
        choices=['whisper', 'groq'],
        help='Transcription provider to use (default: from config)'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force re-transcription even if transcription exists'
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Manual Transcription Script")
    logger.info("=" * 60)
    
    success = manual_transcribe(
        video_id=args.video_id,
        language=args.language,
        provider=args.provider,
        force=args.force
    )
    
    logger.info("=" * 60)
    
    if success:
        logger.info("✓ Transcription completed successfully")
        sys.exit(0)
    else:
        logger.error("✗ Transcription failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
