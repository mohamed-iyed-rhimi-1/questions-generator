import logging

from sqlalchemy import create_engine, Engine, text
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.exc import OperationalError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings

logger = logging.getLogger(__name__)

# Create SQLAlchemy engine with connection pooling
try:
    engine: Engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,  # Verify connections before using
        pool_size=5,
        max_overflow=10,
        echo=False  # Set to True for SQL query debugging
    )
    logger.info("Database engine created successfully")
except Exception as e:
    logger.critical(f"Failed to create database engine: {e}", exc_info=True)
    raise

# Session factory for dependency injection
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Declarative base for all models
Base = declarative_base()


def get_db():
    """
    Database session dependency for FastAPI routes.
    Yields a database session and ensures it's closed after the request.
    
    Note: Retry logic should be applied at call sites for specific DB operations
    prone to transient failures, not on the generator itself.
    
    Usage:
        @app.get("/endpoint")
        def endpoint(db: Session = Depends(get_db)):
            # Use db session here
            pass
    """
    db = SessionLocal()
    try:
        logger.debug("Database session created")
        yield db
    except OperationalError as e:
        logger.error(f"Database operational error: {e}", exc_info=True)
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"Database error: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        logger.debug("Database session closed")
        db.close()


def init_db():
    """
    Initialize database by creating all tables.
    
    NOTE: This is for development only. In production, use Alembic migrations.
    Run 'alembic upgrade head' to apply migrations properly.
    """
    Base.metadata.create_all(bind=engine)


def check_database_connection() -> bool:
    """
    Check if database connection is healthy.
    
    Returns:
        True if connection is successful, False otherwise.
    """
    try:
        with engine.connect() as connection:
            connection.execute(text('SELECT 1'))
        logger.info("Database connection health check passed")
        return True
    except Exception as e:
        logger.error(f"Database connection health check failed: {e}", exc_info=True)
        return False
