# Production-ready Dockerfile for FastAPI backend with Whisper
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Set cache directories for ML models
ENV TORCH_HOME=/app/.cache/torch
ENV HF_HOME=/app/.cache/huggingface

# Create cache directories for model persistence
RUN mkdir -p /app/.cache/torch /app/.cache/huggingface

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Pre-download Whisper model during build time
# This speeds up first transcription by caching the model
# Model is cached in /app/.cache/torch/
ARG WHISPER_MODEL=turbo
RUN python -c "import whisper; whisper.load_model('${WHISPER_MODEL}')"

# Copy application code
COPY . .

# Create storage directories for volume mounts
RUN mkdir -p /app/storage/audio /app/storage/thumbnails

# Expose application port
EXPOSE 8000

# Environment variables for Python optimization
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Health check to monitor application status
# The /health endpoint exists in app.main
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Default command (overridden by docker-compose for development)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
