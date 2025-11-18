from contextlib import asynccontextmanager
from datetime import datetime
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError, OperationalError

from app.api import api_router
from app.config import settings
from app.database import engine
from app.logging_config import setup_logging
from app.exceptions import AppException, to_http_exception

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    Handles database connection initialization and cleanup.
    """
    # Startup: Initialize database connection, load models, etc.
    logger.info(
        "🚀 Application startup",
        extra={
            "database_url": settings.database_url,
            "ollama_base_url": settings.ollama_base_url,
            "ollama_model": settings.ollama_model,
            "whisper_model": settings.whisper_model,
            "embedding_model": "all-MiniLM-L6-v2",
            "embedding_dim": 384
        }
    )
    
    # Test database connection
    try:
        with engine.connect() as connection:
            connection.execute(text('SELECT 1'))
        logger.info(
            "✅ Database connection successful",
            extra={"note": "Run 'alembic upgrade head' to apply migrations"}
        )
    except Exception as e:
        logger.error(
            "❌ Database connection failed",
            extra={"error": str(e)},
            exc_info=True
        )
    
    # Verify transcription models loaded
    try:
        from app.services.transcription_service import whisper_model, embedding_model
        if whisper_model is None:
            logger.warning(
                "⚠️  Whisper model failed to load",
                extra={"service": "transcription", "model": settings.whisper_model}
            )
        if embedding_model is None:
            logger.warning(
                "⚠️  Embedding model failed to load",
                extra={"service": "embedding", "model": "all-MiniLM-L6-v2"}
            )
    except Exception as e:
        logger.warning(
            "⚠️  Could not verify transcription models",
            extra={"error": str(e)}
        )
    
    # Verify Ollama client loaded
    try:
        from app.services.ollama_service import ollama_client
        if ollama_client is None:
            logger.warning(
                "⚠️  Ollama client failed to initialize - question generation will be unavailable",
                extra={"service": "ollama", "status": "unavailable"}
            )
        else:
            # Try to verify connection with non-blocking check
            try:
                # Use asyncio timeout for non-blocking check
                import asyncio
                
                async def check_ollama():
                    # Run in executor to avoid blocking
                    loop = asyncio.get_event_loop()
                    return await loop.run_in_executor(None, ollama_client.list)
                
                try:
                    # 3-second timeout for health check
                    await asyncio.wait_for(check_ollama(), timeout=3.0)
                    logger.info(
                        "✅ Ollama connection successful",
                        extra={
                            "service": "ollama",
                            "model": settings.ollama_model,
                            "status": "available"
                        }
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        "⚠️  Ollama health check timed out - service may be slow or unavailable",
                        extra={"service": "ollama", "status": "degraded", "timeout_seconds": 3}
                    )
                except Exception as e:
                    logger.warning(
                        "⚠️  Ollama connection failed",
                        extra={"service": "ollama", "status": "degraded", "error": str(e)}
                    )
            except Exception as e:
                logger.warning(
                    "⚠️  Could not perform Ollama health check",
                    extra={"service": "ollama", "error": str(e)}
                )
    except Exception as e:
        logger.warning(
            "⚠️  Could not verify Ollama client",
            extra={"service": "ollama", "error": str(e)}
        )
    
    yield
    
    # Shutdown: Close database connections, cleanup resources
    logger.info(
        "👋 Application shutdown",
        extra={"timestamp": datetime.utcnow().isoformat()}
    )


app = FastAPI(
    title="YouTube Question Generator API",
    description="API for downloading YouTube videos, transcribing them, and generating questions using AI",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router)


# Global exception handlers
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """Handle custom application exceptions."""
    logger.error(
        f"Application error: {exc.error_code} - {exc.message}",
        extra={"error_code": exc.error_code, "details": exc.details}
    )
    http_exc = to_http_exception(exc)
    return JSONResponse(
        status_code=http_exc.status_code,
        content=http_exc.detail
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors."""
    logger.warning(
        "Request validation failed",
        extra={"errors": exc.errors(), "body": exc.body}
    )
    return JSONResponse(
        status_code=422,
        content={
            "error_code": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "errors": exc.errors()
        }
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """Handle database errors."""
    logger.error("Database error occurred", exc_info=True)
    
    # Check if it's a connection error
    if isinstance(exc, OperationalError):
        return JSONResponse(
            status_code=503,
            content={
                "error_code": "DATABASE_CONNECTION_ERROR",
                "message": "Database is temporarily unavailable. Please try again later."
            }
        )
    
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "DATABASE_ERROR",
            "message": "A database error occurred. Please try again."
        }
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors."""
    logger.exception("Unexpected error occurred")
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred. Please try again later."
        }
    )


@app.get("/")
async def root():
    """Root endpoint returning API status and welcome message."""
    return {
        "message": "Welcome to YouTube Question Generator API",
        "status": "online",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring service status."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "youtube-qa-api",
    }
