import logging
import logging.handlers
import sys
from pathlib import Path

from pythonjsonlogger import jsonlogger

from app.config import settings


def setup_logging() -> None:
    """Configure application logging with structured JSON or text format."""
    # Get root logger
    logger = logging.getLogger()
    
    # Set log level from settings
    logger.setLevel(getattr(logging, settings.log_level))
    
    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Console handler setup
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.log_level))
    
    if settings.log_format == 'json':
        # Create JSON formatter with structured fields
        json_formatter = jsonlogger.JsonFormatter(
            '%(asctime)s %(levelname)s %(name)s %(message)s %(pathname)s %(lineno)d %(funcName)s',
            rename_fields={'levelname': 'level', 'asctime': 'timestamp'},
            datefmt='%Y-%m-%dT%H:%M:%S'
        )
        console_handler.setFormatter(json_formatter)
    else:
        # Create standard text formatter
        text_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(text_formatter)
    
    logger.addHandler(console_handler)
    
    # File handler setup (if enabled)
    if settings.enable_log_rotation:
        # Create log directory
        log_path = Path(settings.log_file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create rotating file handler (10MB max, keep 5 backups)
        file_handler = logging.handlers.RotatingFileHandler(
            settings.log_file_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(getattr(logging, settings.log_level))
        
        # Use same formatter as console
        if settings.log_format == 'json':
            file_handler.setFormatter(json_formatter)
        else:
            file_handler.setFormatter(text_formatter)
        
        logger.addHandler(file_handler)
    
    # Suppress noisy third-party loggers
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('yt_dlp').setLevel(logging.WARNING)
    
    # Log startup message
    logger.info(
        f"Logging configured: level={settings.log_level}, "
        f"format={settings.log_format}, rotation={settings.enable_log_rotation}"
    )
