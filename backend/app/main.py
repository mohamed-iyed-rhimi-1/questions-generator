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
from app.exceptions import AppException, DependencyException, to_http_exception

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
            "transcription_provider": settings.transcription_provider,
            "transcription_model": settings.groq_model if settings.transcription_provider == "groq" else settings.whisper_model,
            "question_generation_provider": settings.question_generation_provider,
            "question_generation_model": settings.openrouter_model if settings.question_generation_provider == "openrouter" else settings.ollama_model,
            "embedding_model": "all-MiniLM-L6-v2",
            "embedding_dim": 384
        }
    )
    
    # Log active provider configuration
    logger.info(
        f"📡 Transcription provider: {settings.transcription_provider}",
        extra={
            "provider": settings.transcription_provider,
            "model": settings.groq_model if settings.transcription_provider == "groq" else settings.whisper_model,
            "api_key_configured": bool(settings.groq_api_key) if settings.transcription_provider == "groq" else "N/A"
        }
    )
    
    logger.info(
        f"🤖 Question generation provider: {settings.question_generation_provider}",
        extra={
            "provider": settings.question_generation_provider,
            "model": settings.openrouter_model if settings.question_generation_provider == "openrouter" else settings.ollama_model,
            "api_key_configured": bool(settings.openrouter_api_key) if settings.question_generation_provider == "openrouter" else "N/A"
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
    
    # Verify transcription provider loaded
    try:
        from app.services.transcription_service import transcription_provider
        if transcription_provider is None:
            logger.warning(
                "⚠️  Transcription provider failed to initialize",
                extra={
                    "service": "transcription",
                    "provider": settings.transcription_provider,
                    "status": "unavailable"
                }
            )
        else:
            logger.info(
                "✅ Transcription provider initialized",
                extra={
                    "provider": settings.transcription_provider,
                    "status": "available"
                }
            )
        
        # Note: Embedding model is lazy-loaded on first use for faster startup
        logger.info(
            "📦 Embedding model will load on first use",
            extra={"model": settings.embedding_model_name, "dim": settings.embedding_dim}
        )
    except Exception as e:
        logger.warning(
            "⚠️  Could not verify transcription provider",
            extra={"error": str(e)}
        )
    
    # Verify question generation provider loaded
    try:
        from app.services.ollama_service import check_ollama_health
        
        # Use asyncio for non-blocking health check
        import asyncio
        
        async def check_provider_health():
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, check_ollama_health)
        
        try:
            # 3-second timeout for health check
            is_healthy = await asyncio.wait_for(check_provider_health(), timeout=3.0)
            if is_healthy:
                logger.info(
                    "✅ Question generation provider healthy",
                    extra={
                        "provider": settings.question_generation_provider,
                        "status": "available"
                    }
                )
            else:
                logger.warning(
                    "⚠️  Question generation provider unhealthy",
                    extra={
                        "provider": settings.question_generation_provider,
                        "status": "degraded"
                    }
                )
        except asyncio.TimeoutError:
            logger.warning(
                "⚠️  Question generation provider health check timed out",
                extra={
                    "provider": settings.question_generation_provider,
                    "status": "degraded",
                    "timeout_seconds": 3
                }
            )
    except Exception as e:
        logger.warning(
            "⚠️  Could not verify question generation provider",
            extra={"provider": settings.question_generation_provider, "error": str(e)}
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
@app.exception_handler(DependencyException)
async def dependency_exception_handler(request: Request, exc: DependencyException):
    """Handle dependency violation exceptions (409 Conflict)."""
    logger.warning(
        f"Dependency violation: {exc.detail['message']}",
        extra={
            "error": "dependency_violation",
            "details": exc.detail.get('details', {}),
            "dependent_resources": exc.detail.get('dependent_resources', [])
        }
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail
    )


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """Handle custom application exceptions."""
    # Build logging context with provider information if available
    log_extra = {
        "error_code": exc.error_code,
        "details": exc.details
    }
    
    # Add provider context for provider-specific exceptions
    if hasattr(exc, 'provider'):
        log_extra['provider'] = exc.provider
    
    logger.error(
        f"Application error: {exc.error_code} - {exc.message}",
        extra=log_extra
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
