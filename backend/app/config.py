from pathlib import Path
from typing import List, Union

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database configuration
    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/youtube_qa_db",
        env="DATABASE_URL"
    )
    postgres_user: str = Field(default="postgres", env="POSTGRES_USER")
    postgres_password: str = Field(default="postgres", env="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="youtube_qa_db", env="POSTGRES_DB")
    
    # Application ports
    backend_port: int = Field(default=8000, env="BACKEND_PORT")
    frontend_port: int = Field(default=5173, env="FRONTEND_PORT")
    
    # Ollama configuration
    ollama_base_url: str = Field(default="http://localhost:11434", env="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="iKhalid/ALLaM:7b", env="OLLAMA_MODEL")
    
    # Whisper configuration
    whisper_model: str = Field(default="turbo", env="WHISPER_MODEL")
    
    # Transcription provider configuration
    transcription_provider: str = Field(default="groq", env="TRANSCRIPTION_PROVIDER")
    groq_api_key: str = Field(default="", env="GROQ_API_KEY")
    groq_model: str = Field(default="whisper-large-v3", env="GROQ_MODEL")
    
    # Question generation provider configuration
    question_generation_provider: str = Field(default="openrouter", env="QUESTION_GENERATION_PROVIDER")
    openrouter_api_key: str = Field(default="", env="OPENROUTER_API_KEY")
    openrouter_model: str = Field(default="openai/gpt-4o-mini", env="OPENROUTER_MODEL")
    openrouter_site_url: str = Field(default="", env="OPENROUTER_SITE_URL")
    openrouter_site_name: str = Field(default="", env="OPENROUTER_SITE_NAME")
    
    # Embedding configuration
    embedding_model_name: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        env="EMBEDDING_MODEL_NAME"
    )
    embedding_dim: int = Field(default=384, env="EMBEDDING_DIM")
    
    # Storage configuration
    storage_path: str = Field(default="./storage", env="STORAGE_PATH")
    
    # Chunk configuration
    max_chunk_size_mb: float = Field(default=25.0, env="MAX_CHUNK_SIZE_MB")
    silence_threshold_db: int = Field(default=-35, env="SILENCE_THRESHOLD_DB")
    min_silence_duration: float = Field(default=0.3, env="MIN_SILENCE_DURATION")
    auto_chunk_enabled: bool = Field(default=True, env="AUTO_CHUNK_ENABLED")
    delete_original_after_chunking: bool = Field(default=False, env="DELETE_ORIGINAL_AFTER_CHUNKING")
    
    # CORS configuration (stored as string, parsed in model_validator)
    cors_origins: str = Field(
        default="http://localhost:5173,http://localhost:3000",
        env="CORS_ORIGINS"
    )
    _cors_origins_list: List[str] = []
    
    # Logging configuration
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(default="json", env="LOG_FORMAT")
    enable_log_rotation: bool = Field(default=False, env="ENABLE_LOG_ROTATION")
    log_file_path: str = Field(default="./logs/app.log", env="LOG_FILE_PATH")
    
    @model_validator(mode='after')
    def parse_cors_origins(self):
        """Parse CORS origins from comma-separated string."""
        if isinstance(self.cors_origins, str):
            self._cors_origins_list = [
                origin.strip()
                for origin in self.cors_origins.split(',')
                if origin.strip()
            ]
        return self
    
    @model_validator(mode='after')
    def validate_api_keys(self):
        """Validate that required API keys are present for selected providers."""
        if self.transcription_provider == 'groq' and not self.groq_api_key:
            raise ValueError("GROQ_API_KEY is required when TRANSCRIPTION_PROVIDER is 'groq'")
        if self.question_generation_provider == 'openrouter' and not self.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY is required when QUESTION_GENERATION_PROVIDER is 'openrouter'")
        return self
    
    def get_cors_origins(self) -> List[str]:
        """Get parsed CORS origins as a list."""
        return self._cors_origins_list if self._cors_origins_list else ["http://localhost:5173", "http://localhost:3000"]
    
    @field_validator('transcription_provider')
    @classmethod
    def validate_transcription_provider(cls, v: str) -> str:
        """Validate transcription provider is one of the allowed values."""
        allowed = ['whisper', 'groq']
        v_lower = v.lower()
        if v_lower not in allowed:
            raise ValueError(f"transcription_provider must be one of {allowed}, got {v}")
        return v_lower
    
    @field_validator('question_generation_provider')
    @classmethod
    def validate_question_generation_provider(cls, v: str) -> str:
        """Validate question generation provider is one of the allowed values."""
        allowed = ['ollama', 'openrouter']
        v_lower = v.lower()
        if v_lower not in allowed:
            raise ValueError(f"question_generation_provider must be one of {allowed}, got {v}")
        return v_lower
    
    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is one of the allowed values."""
        allowed_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        v_upper = v.upper()
        if v_upper not in allowed_levels:
            raise ValueError(f"log_level must be one of {allowed_levels}, got {v}")
        return v_upper
    
    model_config = {
        "env_file": str(Path(__file__).resolve().parents[2] / ".env"),
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "env_parse_enums": None,
    }
    
    @property
    def audio_storage_path(self) -> Path:
        """Computed path for audio file storage."""
        path = Path(self.storage_path) / "audio"
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def thumbnail_storage_path(self) -> Path:
        """Computed path for thumbnail storage."""
        path = Path(self.storage_path) / "thumbnails"
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def chunk_storage_path(self) -> Path:
        """Computed path for chunk file storage."""
        path = Path(self.storage_path) / "audio" / "chunks"
        path.mkdir(parents=True, exist_ok=True)
        return path


# Singleton settings instance
settings = Settings()
