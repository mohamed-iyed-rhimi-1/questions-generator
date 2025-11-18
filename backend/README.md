# Backend - YouTube Question Generator API

FastAPI-based backend service for downloading YouTube videos, transcribing audio using Whisper, and generating questions using Ollama.

## Architecture

The backend follows a layered architecture:

- **`app/`** - Main application package
  - **`api/`** - API route handlers and endpoints
  - **`models/`** - SQLAlchemy database models
  - **`schemas/`** - Pydantic models for request/response validation
  - **`services/`** - Business logic layer (YouTube, Whisper, Ollama services)
  - **`config.py`** - Application configuration and settings
  - **`main.py`** - FastAPI application entry point
- **`alembic/`** - Database migration scripts
- **`storage/`** - File storage for downloaded videos and thumbnails
- **`tests/`** - Test suite (to be implemented)

## Setup

### 1. Create Virtual Environment

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
# Production dependencies
pip install -r requirements.txt

# Development dependencies (includes testing, linting, formatting)
pip install -r requirements-dev.txt
```

### 3. Configure Environment Variables

Copy the example environment file and configure it:

```bash
cp ../.env.example ../.env
# Edit .env with your configuration
```

See `../.env.example` for all available configuration options.

### 4. Set Up Database

Ensure PostgreSQL is running with the pgvector extension installed, then run migrations:

```bash
# Run all migrations to set up the database schema
alembic upgrade head
```

## Running the Server

### Development Mode

```bash
uvicorn app.main:app --reload --port 8000
```

The `--reload` flag enables auto-reloading on code changes.

### Production Mode

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## API Documentation

Once the server is running, access the interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## API Endpoints

### Videos API

#### POST /api/videos/download
Download YouTube videos as MP3 audio files.

**Request Body:**
```json
{
  "urls": [
    "https://youtube.com/watch?v=dQw4w9WgXcQ",
    "https://youtu.be/abc123def45"
  ]
}
```

**Response:**
```json
{
  "results": [
    {
      "url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
      "status": "success",
      "message": "Video downloaded successfully",
      "video_id": "dQw4w9WgXcQ",
      "video": {
        "id": 1,
        "video_id": "dQw4w9WgXcQ",
        "title": "Video Title",
        "thumbnail_url": "https://...",
        "file_path": "/path/to/audio.mp3",
        "created_at": "2024-01-01T00:00:00",
        "download_status": "completed"
      }
    }
  ],
  "total": 1,
  "successful": 1,
  "duplicates": 0,
  "failed": 0
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/videos/download \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://youtube.com/watch?v=dQw4w9WgXcQ"]}'
```

#### GET /api/videos
List all downloaded videos with pagination.

**Query Parameters:**
- `skip` (default: 0) - Number of records to skip
- `limit` (default: 100, max: 1000) - Maximum number of records to return

**Response:**
```json
[
  {
    "id": 1,
    "video_id": "dQw4w9WgXcQ",
    "title": "Video Title",
    "thumbnail_url": "https://...",
    "file_path": "/path/to/audio.mp3",
    "created_at": "2024-01-01T00:00:00",
    "download_status": "completed"
  }
]
```

**Example:**
```bash
curl http://localhost:8000/api/videos?skip=0&limit=10
```

#### GET /api/videos/{video_id}
Get details for a specific video by its YouTube video ID.

**Path Parameter:**
- `video_id` - YouTube video ID (11 characters)

**Response:**
```json
{
  "id": 1,
  "video_id": "dQw4w9WgXcQ",
  "title": "Video Title",
  "thumbnail_url": "https://...",
  "file_path": "/path/to/audio.mp3",
  "created_at": "2024-01-01T00:00:00",
  "download_status": "completed"
}
```

**Example:**
```bash
curl http://localhost:8000/api/videos/dQw4w9WgXcQ
```

#### DELETE /api/videos/{video_id}
Delete a video and its associated audio file.

**Path Parameter:**
- `video_id` - YouTube video ID (11 characters)

**Response:** 204 No Content

**Example:**
```bash
curl -X DELETE http://localhost:8000/api/videos/dQw4w9WgXcQ
```

### Notes

- Downloaded audio files are stored in `backend/app/storage/audio/`
- Duplicate videos are automatically detected and skipped
- The service handles various YouTube URL formats:
  - `https://youtube.com/watch?v=VIDEO_ID`
  - `https://youtu.be/VIDEO_ID`
  - `https://youtube.com/shorts/VIDEO_ID`
  - `https://youtube.com/embed/VIDEO_ID`
- All audio files are converted to MP3 format (192 kbps) with embedded metadata and thumbnails

### Troubleshooting API Issues

- **Download failures**: Ensure FFmpeg is installed and available on PATH
  ```bash
  # Check FFmpeg installation
  ffmpeg -version
  ```
- **Invalid URLs**: The API will report specific errors for each failed URL in the response
- **Rate limiting**: YouTube may rate limit requests if too many videos are downloaded concurrently
- **Missing thumbnails**: Some videos may not have thumbnails available
- **Check logs**: Detailed error messages are logged to the console with timestamps

### Transcriptions API

#### POST /api/videos/transcribe (Primary Endpoint)
Transcribe videos using Whisper and generate vector embeddings.

**Request Body:**
```json
{
  "video_ids": ["dQw4w9WgXcQ", "abc123def45"]
}
```

**Response:**
```json
{
  "results": [
    {
      "video_id": "dQw4w9WgXcQ",
      "status": "success",
      "message": "Transcription completed successfully",
      "transcription": {
        "id": 1,
        "video_id": "dQw4w9WgXcQ",
        "transcription_text": "Full transcription text...",
        "vector_embedding": [0.123, -0.456, ...],
        "created_at": "2024-01-01T00:00:00",
        "status": "completed"
      },
      "error": null,
      "steps_completed": 5,
      "total_steps": 5
    }
  ],
  "total": 1,
  "successful": 1,
  "failed": 0,
  "not_found": 0,
  "no_audio": 0
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/videos/transcribe \
  -H "Content-Type: application/json" \
  -d '{"video_ids": ["dQw4w9WgXcQ"]}'
```

**Notes:**
- **Primary endpoint**: Use `/api/videos/transcribe` for all transcription requests
- Videos must be downloaded first (audio files must exist)
- Uses OpenAI Whisper (local model, no API key required)
- Generates embeddings using configured model (default: sentence-transformers/all-MiniLM-L6-v2, 384 dimensions)
- Embeddings are normalized for cosine similarity search
- Transcription is CPU-intensive and may take time for long videos
- Progress tracking: Each result includes `steps_completed` and `total_steps` (5 steps total)
- Status counts: Response includes `successful`, `failed`, `not_found`, and `no_audio` counts

**Status Values:**
- `success` - Transcription completed successfully
- `not_found` - Video not found in database (must download first)
- `no_audio` - Audio file missing or not downloaded
- `failed` - Transcription or embedding generation failed

#### POST /api/transcriptions/transcribe (Deprecated)
Alternative endpoint for backward compatibility. Use `/api/videos/transcribe` instead.

#### GET /api/transcriptions
List all transcriptions with optional filtering and pagination.

**Query Parameters:**
- `skip` (default: 0) - Number of records to skip
- `limit` (default: 100, max: 1000) - Maximum number of records to return
- `video_id` (optional) - Filter by specific video ID

**Response:**
```json
{
  "transcriptions": [
    {
      "id": 1,
      "video_id": "dQw4w9WgXcQ",
      "transcription_text": "Full transcription text...",
      "vector_embedding": [0.123, -0.456, ...],
      "created_at": "2024-01-01T00:00:00",
      "status": "completed"
    }
  ],
  "total": 1
}
```

**Example:**
```bash
curl http://localhost:8000/api/transcriptions?video_id=dQw4w9WgXcQ
```

#### GET /api/transcriptions/{transcription_id}
Get details for a specific transcription by its database ID.

**Path Parameter:**
- `transcription_id` - Transcription database ID (integer)

**Response:**
```json
{
  "id": 1,
  "video_id": "dQw4w9WgXcQ",
  "transcription_text": "Full transcription text...",
  "vector_embedding": [0.123, -0.456, ...],
  "created_at": "2024-01-01T00:00:00",
  "status": "completed"
}
```

**Example:**
```bash
curl http://localhost:8000/api/transcriptions/1
```

#### GET /api/transcriptions/video/{video_id}
Get all transcriptions for a specific video.

**Path Parameter:**
- `video_id` - YouTube video ID (11 characters)

**Response:**
```json
[
  {
    "id": 1,
    "video_id": "dQw4w9WgXcQ",
    "transcription_text": "Full transcription text...",
    "vector_embedding": [0.123, -0.456, ...],
    "created_at": "2024-01-01T00:00:00",
    "status": "completed"
  }
]
```

**Example:**
```bash
curl http://localhost:8000/api/transcriptions/video/dQw4w9WgXcQ
```

**Note:** Multiple transcriptions per video are supported (no unique constraint).

#### DELETE /api/transcriptions/{transcription_id}
Delete a specific transcription from the database.

**Path Parameter:**
- `transcription_id` - Transcription database ID (integer)

**Response:** 204 No Content

**Example:**
```bash
curl -X DELETE http://localhost:8000/api/transcriptions/1
```

### Transcription Notes

- **Model Loading**: Whisper and embedding models are loaded once at startup for efficiency
- **Vector Storage**: Embeddings are stored in PostgreSQL with pgvector extension for semantic search
- **Multiple Transcriptions**: The same video can be transcribed multiple times (no unique constraint)
- **Normalization**: Embeddings are normalized for cosine similarity search with pgvector's vector_cosine_ops index
- **Sequential Processing**: Videos are processed one at a time to prevent memory issues
- **Embedding Configuration**: Model and dimension are configurable via environment variables
  - `EMBEDDING_MODEL_NAME` - Default: `sentence-transformers/all-MiniLM-L6-v2`
  - `EMBEDDING_DIM` - Default: `384` (must match model output dimension)
  - **Important**: Changing embedding dimensions requires database migration for the `transcriptions.vector_embedding` column

### Transcription Performance

- **Whisper Model Size**: Affects accuracy and speed (configurable via `WHISPER_MODEL` env var)
  - `tiny` - Fastest, lowest accuracy
  - `base` - Default, good balance
  - `small` - Better accuracy, slower
  - `medium` - High accuracy, much slower
  - `large` - Best accuracy, very slow
- **Processing Time**: Depends on video length and model size
  - Short videos (< 5 min): Seconds to minutes
  - Long videos (> 30 min): Several minutes to hours
- **Batch Processing**: Consider transcribing in smaller batches for better responsiveness
- **GPU Acceleration**: Not enabled by default (CPU-only for compatibility)

### Troubleshooting Transcription Issues

- **Transcription fails**: Ensure the video was downloaded first (audio file exists)
- **FFmpeg required**: Whisper needs FFmpeg for audio processing
  ```bash
  # Check FFmpeg installation
  ffmpeg -version
  ```
- **Model loading errors**: Check logs during startup for model loading failures
- **Memory issues**: For long videos or large batches, consider using smaller Whisper model
- **Empty transcriptions**: Some videos may have no speech or inaudible audio
- **Check logs**: Detailed error messages are logged with full context

### Questions API

#### `POST /api/questions/generate` - Generate AI-powered questions from transcribed videos using Ollama

**Request Body:**
```json
{
  "video_ids": ["dQw4w9WgXcQ", "abc123def45"]
}
```

**Response:**
```json
{
  "results": [
    {
      "video_id": "dQw4w9WgXcQ",
      "status": "success",
      "message": "Generated 5 questions (placeholder)",
      "questions": [
        {
          "id": "uuid-string",
          "video_id": "dQw4w9WgXcQ",
          "question_text": "Question text here?",
          "context": "Context snippet from transcription...",
          "difficulty": "medium",
          "question_type": "factual",
          "created_at": "2024-01-01T00:00:00"
        }
      ],
      "question_count": 5,
      "error": null
    }
  ],
  "total": 1,
  "successful": 1,
  "failed": 0,
  "no_transcription": 0,
  "total_questions": 5
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/questions/generate \
  -H "Content-Type: application/json" \
  -d '{"video_ids": ["dQw4w9WgXcQ"]}'
```

**Notes:**
- **AI-Powered**: Uses Ollama LLM (default: iKhalid/ALLaM:7b) to generate educational questions from video transcriptions
- **Requirements**: Videos must be downloaded and transcribed first
- **Question Generation**: Generates 5 AI-powered questions per video by default
- **Question Properties**:
  - `question_text` - The AI-generated question
  - `context` - Relevant snippet from transcription to support the question
  - `difficulty` - One of: "easy", "medium", "hard"
  - `question_type` - One of: "factual", "conceptual", "analytical"
  - `created_at` - Timestamp when generated
- **Transient Data**: Questions are not stored in database—generated fresh each time
- **Validation**: Endpoint validates that videos exist and have transcriptions before generating questions
- **Graceful Degradation**: If Ollama is unavailable, the endpoint returns success with 0 questions

**Status Values:**
- `success` - Questions generated successfully
- `no_transcription` - Video has no transcription (must transcribe first)
- `failed` - Video not found in database (must download first)

### Ollama Setup

**Prerequisites:**
- Ollama must be installed and running on the host machine
- Installation: Visit https://ollama.ai or run `curl https://ollama.ai/install.sh | sh`
- Pull the model: `ollama pull iKhalid/ALLaM:7b` (or the model specified in OLLAMA_MODEL env var)
- Start Ollama: `ollama serve` (runs on port 11434 by default)

**Configuration:**
- Set `OLLAMA_BASE_URL` in `.env` (default: http://localhost:11434)
- Set `OLLAMA_MODEL` in `.env` (default: iKhalid/ALLaM:7b)
- For Docker: Use `http://host.docker.internal:11434` to reach Ollama on host

**Performance Notes:**
- Ollama client is initialized once at startup (not per request)
- Question generation typically takes 5-30 seconds depending on model and transcription length
- The endpoint is synchronous—frontend shows loading state during generation
- Multiple concurrent requests are handled by FastAPI's threadpool

**Troubleshooting:**
- **"no transcription" error**: Transcribe the video first using `/api/videos/transcribe`
- **"video not found" error**: Download the video first using `/api/videos/download`
- **Check logs**: Detailed error messages are logged with full context
- **If generation returns 0 questions**:
  - Check that Ollama is running: `curl http://localhost:11434/api/tags`
  - Check that the model is pulled: `ollama list`
  - Check backend logs for Ollama connection errors
  - Verify OLLAMA_BASE_URL is correct in `.env`
- **If questions are low quality**:
  - Try a different model: `ollama pull mistral` and set `OLLAMA_MODEL=mistral`
  - Larger models (llama3:70b, mixtral) produce better questions but are slower
  - Ensure transcriptions are accurate (better transcriptions = better questions)
- **If generation is slow**:
  - First request may be slow (model loading)
  - Subsequent requests are faster (model stays in memory)
  - Consider using a smaller model for faster generation

## Database Migrations

### Create a New Migration

After modifying models in `app/models/`, generate a migration:

```bash
alembic revision --autogenerate -m "Description of changes"
```

### Apply Migrations

```bash
alembic upgrade head
```

### Rollback Migration

```bash
# Rollback one migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade <revision_id>
```

### View Migration History

```bash
alembic history
alembic current
```

## Code Quality

### Format Code

```bash
# Format with Black
black .

# Sort imports with isort
isort .
```

### Lint Code

```bash
# Check code style with flake8
flake8 .

# Type checking with mypy
mypy app/
```

### Run Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_api.py
```

## Project Dependencies

### Core Framework
- **FastAPI** - Modern async web framework
- **Uvicorn** - ASGI server with WebSocket support

### Database
- **SQLAlchemy** - ORM for database operations
- **Alembic** - Database migration tool
- **psycopg2-binary** - PostgreSQL adapter
- **pgvector** - Vector similarity search

### AI/ML Services
- **openai-whisper** - Speech-to-text transcription
- **sentence-transformers** - Generate embeddings
- **ollama** - Local LLM inference

### Utilities
- **yt-dlp** - YouTube video downloader
- **pydantic-settings** - Settings management
- **python-dotenv** - Environment variable loading
- **aiofiles** - Async file operations
- **httpx** - Async HTTP client

## Environment Variables

All configuration is managed through environment variables. See `../.env.example` for the complete list:

- `DATABASE_URL` - PostgreSQL connection string
- `OLLAMA_BASE_URL` - Ollama API endpoint
- `OLLAMA_MODEL` - LLM model to use
- `WHISPER_MODEL` - Whisper model size (tiny/base/small/medium/large)
- `EMBEDDING_MODEL_NAME` - Sentence transformer model name (default: sentence-transformers/all-MiniLM-L6-v2)
- `EMBEDDING_DIM` - Embedding vector dimension (default: 384, must match model output)
- `STORAGE_PATH` - File storage location
- `CORS_ORIGINS` - Allowed CORS origins

## Development Workflow

1. Create a new branch for your feature
2. Make changes to the code
3. Format code with `black` and `isort`
4. Run linters (`flake8`, `mypy`)
5. Write/update tests
6. Run test suite with `pytest`
7. Create database migrations if models changed
8. Submit pull request

## Troubleshooting

### Database Connection Issues

- Ensure PostgreSQL is running
- Verify `DATABASE_URL` in `.env` is correct
- Check that the database exists: `createdb youtube_qa_db`
- Ensure pgvector extension is installed

### Ollama Connection Issues

- Verify Ollama is running: `ollama serve`
- Check `OLLAMA_BASE_URL` in `.env`
- Test connection: `curl http://localhost:11434/api/tags`

### Import Errors

- Ensure virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt`
- Check Python version: `python --version` (should be 3.11+)
