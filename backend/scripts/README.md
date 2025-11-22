# Backend Scripts

Utility scripts for manual operations and troubleshooting.

## Scripts Overview

1. **Manual Transcription** (`manual_transcribe.py`) - Transcribe videos and save to database
2. **Audio Splitting** (`split_audio.py`) - Split large audio files into smaller chunks
3. **Chunk Migration** (`migrate_to_chunks.py`) - Migrate existing videos to chunk-based architecture

---

## Manual Transcription Script

Manually transcribe a video by ID and save the transcription to the database.

### Usage

**Option 1: Using the wrapper script (recommended for local):**
```bash
# From anywhere in the project
./backend/scripts/transcribe.sh <video_id> [options]
```

**Option 2: Direct Python execution:**
```bash
# From the backend directory
cd backend

# Activate virtual environment
source venv/bin/activate

# Run the script
python scripts/manual_transcribe.py <video_id> [options]
```

### Options

- `video_id` (required): YouTube video ID to transcribe
- `--language LANG`: Language code for transcription (default: `ar`)
- `--provider PROVIDER`: Transcription provider (`whisper` or `groq`, default: from config)
- `--force`: Force re-transcription even if transcription already exists

### Examples

**Basic usage (uses default language and provider from config):**
```bash
./backend/scripts/transcribe.sh Fvx9ie6uJWo
```

**Specify language:**
```bash
./backend/scripts/transcribe.sh Fvx9ie6uJWo --language ar
```

**Force use of Whisper provider:**
```bash
./backend/scripts/transcribe.sh Fvx9ie6uJWo --provider whisper
```

**Force use of Groq provider:**
```bash
./backend/scripts/transcribe.sh Fvx9ie6uJWo --provider groq
```

**Force re-transcription (overwrite existing):**
```bash
./backend/scripts/transcribe.sh Fvx9ie6uJWo --force
```

**Combine options:**
```bash
./backend/scripts/transcribe.sh Fvx9ie6uJWo --language ar --provider whisper --force
```

### Running in Docker

If you're running the backend in Docker, you can execute the script inside the container:

```bash
# From the project root
docker compose exec backend python scripts/manual_transcribe.py Fvx9ie6uJWo
```

With options:
```bash
docker compose exec backend python scripts/manual_transcribe.py Fvx9ie6uJWo --provider whisper --force
```

### When to Use

This script is useful for:

1. **Troubleshooting failed transcriptions** - Manually retry with detailed logging
2. **Testing different providers** - Compare Whisper vs Groq results
3. **Re-processing videos** - Fix transcriptions after model updates
4. **Batch processing** - Script can be called from shell scripts for bulk operations

### Prerequisites

- Video must already be downloaded (audio file must exist in `storage/audio/`)
- Video must exist in the database
- Database must be accessible
- For Groq: API key must be configured
- For Whisper: Model must be downloaded

### Output

The script provides detailed logging:
- Video lookup and validation
- Audio file detection
- Transcription progress
- Embedding generation
- Database save confirmation

### Error Handling

The script will exit with:
- **Exit code 0**: Success
- **Exit code 1**: Failure (check logs for details)

Common errors:
- Video not found in database → Download the video first
- Audio file not found → Check storage path
- Transcription already exists → Use `--force` to overwrite
- Provider error → Check API keys and configuration

---

## Audio Splitting Script

Split large audio files into smaller chunks at silence points. Useful for files that exceed provider limits (e.g., Groq's 25MB limit).

### Usage

**Using the wrapper script (recommended):**
```bash
./backend/scripts/split.sh <video_id> [options]
```

**Direct Python execution:**
```bash
cd backend
source venv/bin/activate
python scripts/split_audio.py <video_id> [options]
```

### Options

- `video_id` (required): YouTube video ID to split
- `--max-size SIZE`: Maximum chunk size in MB (default: `25`)
- `--output-dir DIR`: Output directory for chunks (default: `storage/audio/chunks/<video_id>`)
- `--silence-threshold DB`: Silence detection threshold in dB (default: `-35`)
  - Higher values (e.g., `-30`) = more lenient (detects more silence)
  - Lower values (e.g., `-45`) = more strict (only very quiet sections)
- `--min-silence SECONDS`: Minimum silence duration in seconds (default: `0.3`)
- `--no-silence`: Disable silence detection, split at exact intervals

### Examples

**Basic usage (split into 25MB chunks):**
```bash
./backend/scripts/split.sh Fvx9ie6uJWo
```

**Custom chunk size (20MB):**
```bash
./backend/scripts/split.sh Fvx9ie6uJWo --max-size 20
```

**Custom output directory:**
```bash
./backend/scripts/split.sh Fvx9ie6uJWo --output-dir /tmp/audio_chunks
```

**Adjust silence detection (more lenient):**
```bash
./backend/scripts/split.sh Fvx9ie6uJWo --silence-threshold -30
```

**Adjust silence detection (more strict):**
```bash
./backend/scripts/split.sh Fvx9ie6uJWo --silence-threshold -45
```

**Disable silence detection (split at exact intervals):**
```bash
./backend/scripts/split.sh Fvx9ie6uJWo --no-silence
```

### How It Works

1. **Finds audio file** - Locates the audio file for the video ID (supports .wav and .mp3)
2. **Checks file size** - If under limit, no splitting needed
3. **Detects silence** - Uses FFmpeg to find natural break points
4. **Calculates splits** - Determines optimal split points near silence
5. **Creates chunks** - Splits audio using FFmpeg (fast, no re-encoding)

### Features

- ✅ Splits at silence points for clean breaks (no mid-word cuts)
- ✅ Uses FFmpeg (already in codebase, no new dependencies)
- ✅ Fast processing (uses codec copy, no re-encoding)
- ✅ Supports both WAV and MP3 files
- ✅ Detailed logging of each step

### When to Use

- **Large files exceeding Groq's 25MB limit** - Split before transcription
- **Long videos** - Break into manageable chunks
- **Batch processing** - Process chunks in parallel

### Workflow Example

```bash
# 1. Split a large audio file
./backend/scripts/split.sh Fvx9ie6uJWo --max-size 25

# 2. Transcribe each chunk manually (if needed)
# Chunks are saved in: storage/audio/chunks/Fvx9ie6uJWo/
# You can then transcribe each chunk separately
```

### Output

The script creates numbered chunks in the output directory:
```
storage/audio/chunks/Fvx9ie6uJWo/
├── Fvx9ie6uJWo_chunk_001.wav
├── Fvx9ie6uJWo_chunk_002.wav
└── Fvx9ie6uJWo_chunk_003.wav
```

Each chunk will be ≤ the specified max size (default 25MB).

### Prerequisites

- Audio file must exist in `storage/audio/`
- FFmpeg must be installed (already available in Docker)
- Virtual environment with dependencies installed

---

## Chunk Migration Script

Migrate existing videos to the chunk-based architecture. This script identifies videos with audio files larger than the configured chunk size threshold and automatically creates chunks for them.

### Usage

**Direct Python execution:**
```bash
# From the backend directory
cd backend
source venv/bin/activate

# Dry run (preview changes without making modifications)
python scripts/migrate_to_chunks.py --dry-run

# Migrate all videos
python scripts/migrate_to_chunks.py

# Migrate specific video
python scripts/migrate_to_chunks.py --video-id VIDEO_ID

# Dry run for specific video
python scripts/migrate_to_chunks.py --video-id VIDEO_ID --dry-run
```

### Running in Docker

```bash
# From the project root

# Dry run for all videos
docker compose exec backend python scripts/migrate_to_chunks.py --dry-run

# Migrate all videos
docker compose exec backend python scripts/migrate_to_chunks.py

# Migrate specific video
docker compose exec backend python scripts/migrate_to_chunks.py --video-id UI4i4w29AUs

# Dry run for specific video
docker compose exec backend python scripts/migrate_to_chunks.py --video-id UI4i4w29AUs --dry-run
```

### Options

- `--dry-run`: Preview changes without making modifications (recommended first step)
- `--video-id VIDEO_ID`: Migrate a specific video by ID (optional, migrates all if omitted)

### How It Works

1. **Checks database connection** - Verifies database is accessible
2. **Queries videos** - Retrieves all videos or specific video by ID
3. **Checks file size** - Determines if video exceeds chunk size threshold (default: 25MB)
4. **Skips if needed**:
   - Video already has chunks
   - Video file is below threshold
   - Audio file doesn't exist
5. **Creates chunks** - Splits audio at silence points and saves chunk records to database
6. **Continues on error** - Logs failures and continues with remaining videos

### Features

- ✅ **Dry-run mode** - Preview changes before making them
- ✅ **Progress logging** - Shows progress every 5 videos
- ✅ **Summary statistics** - Reports successful, skipped, and failed migrations
- ✅ **Error handling** - Continues processing even if individual videos fail
- ✅ **Idempotent** - Safe to run multiple times (skips videos that already have chunks)
- ✅ **Backward compatible** - Doesn't affect existing transcriptions

### When to Use

This script is useful for:

1. **Initial migration** - Convert existing videos to chunk-based architecture
2. **Batch processing** - Migrate multiple large videos at once
3. **Troubleshooting** - Re-create chunks for specific videos
4. **Testing** - Use dry-run mode to preview changes

### Examples

**Preview what would be migrated (recommended first step):**
```bash
docker compose exec backend python scripts/migrate_to_chunks.py --dry-run
```

**Migrate all videos that need chunking:**
```bash
docker compose exec backend python scripts/migrate_to_chunks.py
```

**Migrate a specific large video:**
```bash
docker compose exec backend python scripts/migrate_to_chunks.py --video-id UI4i4w29AUs
```

**Check what would happen for a specific video:**
```bash
docker compose exec backend python scripts/migrate_to_chunks.py --video-id UI4i4w29AUs --dry-run
```

### Output

The script provides detailed logging:

**Dry-run output example:**
```
2025-11-19 11:06:03,179 - __main__ - INFO - Checking database connection...
2025-11-19 11:06:03,179 - __main__ - INFO - Database connection successful
2025-11-19 11:06:03,179 - __main__ - INFO - Chunk size threshold: 25.0MB
2025-11-19 11:06:03,205 - __main__ - INFO - Found 1 videos in database
2025-11-19 11:06:03,205 - __main__ - INFO - [DRY RUN] No changes will be made
2025-11-19 11:06:03,214 - __main__ - INFO - [DRY RUN] Would create chunks for video UI4i4w29AUs (file size: 131.15MB)
2025-11-19 11:06:03,214 - __main__ - INFO - ================================================================================
2025-11-19 11:06:03,214 - __main__ - INFO - Migration Summary:
2025-11-19 11:06:03,214 - __main__ - INFO -   Total videos in database: 1
2025-11-19 11:06:03,214 - __main__ - INFO -   Videos processed: 1
2025-11-19 11:06:03,214 - __main__ - INFO -   Successful migrations: 1
2025-11-19 11:06:03,214 - __main__ - INFO -   Videos skipped: 0
2025-11-19 11:06:03,214 - __main__ - INFO -   Failed migrations: 0
2025-11-19 11:06:03,214 - __main__ - INFO - [DRY RUN] No changes were made
```

**Progress logging (every 5 videos):**
```
2025-11-19 11:06:03,214 - __main__ - INFO - Progress: 5/20 videos processed (successful: 3, skipped: 2, failed: 0)
2025-11-19 11:06:03,214 - __main__ - INFO - Progress: 10/20 videos processed (successful: 7, skipped: 3, failed: 0)
```

### Configuration

The script uses the following settings from your `.env` file:

- `MAX_CHUNK_SIZE_MB` - Maximum chunk size threshold (default: 25.0)
- `SILENCE_THRESHOLD_DB` - Silence detection threshold (default: -35)
- `MIN_SILENCE_DURATION` - Minimum silence duration (default: 0.3)

### Error Handling

The script handles various scenarios:

- **Video not found** - Skips with warning
- **No audio file** - Skips with warning
- **Audio file missing** - Skips with warning
- **File below threshold** - Skips (no chunking needed)
- **Already has chunks** - Skips (idempotent)
- **Chunk creation fails** - Logs error and continues with remaining videos

Exit codes:
- **0** - Success (all videos processed successfully or skipped)
- **1** - Failure (one or more videos failed to migrate)
- **130** - Interrupted by user (Ctrl+C)

### Prerequisites

- Database must be accessible
- Videos must exist in the database
- Audio files must exist in `storage/audio/`
- FFmpeg must be installed (for chunk creation)
- Sufficient disk space for chunk files

### Important Notes

1. **Existing transcriptions are preserved** - The script only creates chunks, it doesn't modify or delete existing transcriptions
2. **Re-transcription required** - After migration, you may want to re-transcribe videos to take advantage of chunk-based processing
3. **Disk space** - Chunks are created in addition to original files (unless `DELETE_ORIGINAL_AFTER_CHUNKING=true`)
4. **Safe to re-run** - The script is idempotent and will skip videos that already have chunks
