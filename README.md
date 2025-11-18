# YouTube Video Question Generator

## Overview

A full-stack application that downloads YouTube videos, transcribes them using OpenAI Whisper, and generates AI-powered educational questions using Ollama LLM. The application leverages PostgreSQL with pgvector for semantic search capabilities across video transcriptions.

## Features

1. **Video Download**: Download YouTube videos as MP3 audio with metadata using yt-dlp
2. **Transcription**: Convert audio to text using OpenAI Whisper (local), generate embeddings for semantic search using sentence-transformers
3. **Question Generation**: AI-powered educational question generation using Ollama LLM (local inference)

## Tech Stack

- **Backend**: FastAPI (Python 3.11+)
- **Frontend**: React 18 + TypeScript + Vite + Tailwind CSS
- **Database**: PostgreSQL 15+ with pgvector extension
- **AI/ML**:
  - OpenAI Whisper (local speech-to-text)
  - sentence-transformers (text embeddings)
  - Ollama (local LLM inference for question generation)
- **Video Download**: yt-dlp
- **DevOps**: Docker & Docker Compose

## Prerequisites

**Option 1: Docker Setup (Recommended)**
- Docker and Docker Compose
- Ollama (for AI-powered question generation) - [Installation Guide](https://ollama.ai)

**Option 2: Manual Setup**
- Python 3.11 or higher
- Node.js 18 or higher
- PostgreSQL 15+ with pgvector extension
- Ollama (for AI-powered question generation) - [Installation Guide](https://ollama.ai)

## Quick Start

### Docker Setup (Recommended)

**Prerequisites:**
- Docker and Docker Compose installed
- Ollama installed and running on host machine ([Installation Guide](https://ollama.ai))
- **Linux users**: The setup uses `host.docker.internal` to connect to Ollama on the host. This is automatically configured via `extra_hosts` in docker-compose.yml

**Steps:**

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd wiem-questions-generator
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration if needed
   ```

3. **Install and start Ollama, then pull model** (run on host machine, not in Docker)
   ```bash
   # Install Ollama (visit https://ollama.ai for installation)
   # Start Ollama service
   ollama serve
   # Pull the model
   ollama pull iKhalid/ALLaM:7b
   ```
   
   **Note**: Ollama runs on your host machine (not in Docker) and is accessed by the backend container via `http://host.docker.internal:11434`

4. **Build and start services**
   ```bash
   docker-compose up -d --build
   ```

5. **Run database migrations**
   ```bash
   docker-compose exec backend alembic upgrade head
   ```

6. **Access the application**
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

### Manual Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd wiem-questions-generator
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Backend Setup**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   alembic upgrade head
   uvicorn app.main:app --reload --port 8000
   ```

4. **Frontend Setup**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

5. **Access the application**
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

## Project Structure

```
wiem-questions-generator/
├── backend/              # FastAPI backend application
│   ├── app/             # Application code
│   ├── alembic/         # Database migrations
│   └── storage/         # File storage (audio, thumbnails)
├── frontend/            # React frontend application
│   ├── src/            # Source code
│   └── public/         # Static assets
└── docker-compose.yml  # Docker orchestration (to be added)
```

## Docker Commands

**Start services:**
```bash
docker-compose up -d
```

**Stop services:**
```bash
docker-compose down
```

**View logs:**
```bash
docker-compose logs -f [service_name]
# Examples:
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f postgres
```

**Rebuild after changes:**
```bash
docker-compose up -d --build
```

**Run migrations:**
```bash
docker-compose exec backend alembic upgrade head
```

**Access backend shell:**
```bash
docker-compose exec backend bash
```

**Access database:**
```bash
docker-compose exec postgres psql -U postgres -d youtube_qa_db
```

## Development with Docker

Code changes are automatically reflected with hot-reload:
- **Backend**: Volume mounted at `./backend:/app`
- **Frontend**: Volume mounted at `./frontend/src:/app/src`

**Installing new dependencies requires rebuild:**
```bash
# Backend dependencies
docker-compose up -d --build backend

# Frontend dependencies
docker-compose up -d --build frontend
```

## Troubleshooting

**Ollama connection fails:**
- Ensure Ollama is running on host: `ollama serve`
- Verify the model is downloaded: `ollama list`
- Check `OLLAMA_BASE_URL` in `.env` file
- Test Ollama connection: `curl http://localhost:11434/api/tags`

**Question generation fails:**
- Ensure Ollama is running on host (`ollama serve`) and model is pulled (`ollama list`)
- Check backend logs: `docker-compose logs backend | grep -i ollama`
- Verify videos are transcribed first before generating questions

**Database connection fails:**
- Check postgres service health: `docker-compose ps`
- View postgres logs: `docker-compose logs postgres`
- Ensure port 5432 is not already in use

**Port conflicts:**
- Modify `BACKEND_PORT` or `FRONTEND_PORT` in `.env` file
- Restart services: `docker-compose down && docker-compose up -d`

**Reset database (WARNING: deletes all data):**
```bash
docker-compose down -v
docker-compose up -d
docker-compose exec backend alembic upgrade head
```

**View Whisper model download progress:**
```bash
docker-compose logs backend
```

**Check Ollama status:**
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# List available models
ollama list

# View backend Ollama logs
docker-compose logs backend | grep -i ollama
```

## Production Deployment

The current `docker-compose.yml` is configured for development. For production:

1. **Use production compose file:**
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

2. **Key production differences:**
   - No code volume mounts (baked into images)
   - Frontend uses nginx production stage
   - Backend runs with multiple workers (no --reload)
   - Resource limits applied
   - Production-grade logging

3. **Additional production considerations:**
   - Use environment-specific `.env` files
   - Implement Docker secrets for sensitive data
   - Add reverse proxy (nginx/traefik) for SSL termination
   - Enable rate limiting and security headers
   - Set up monitoring and alerting
   - Regular security updates for base images

## Development

### Backend Development

See [backend/README.md](backend/README.md) for detailed backend setup and development instructions.

### Frontend Development

See [frontend/README.md](frontend/README.md) for detailed frontend setup and development instructions.

## API Documentation

Once the backend is running, visit http://localhost:8000/docs for interactive API documentation powered by FastAPI's automatic OpenAPI generation.

## Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch
3. Make your changes with clear commit messages
4. Submit a pull request

## License

MIT License - feel free to use this project for your own purposes.
