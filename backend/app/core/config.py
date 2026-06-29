import os
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings and environment validation schema.
    Loads configurations from environment variables or .env files.
    """
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Application details
    app_name: str = Field("Enterprise AI Knowledge Platform", validation_alias="APP_NAME")
    app_version: str = Field("1.0.0", validation_alias="APP_VERSION")
    log_level: str = Field("INFO", validation_alias="LOG_LEVEL")
    log_file: str = Field("logs/app.log", validation_alias="LOG_FILE")
    uploads_dir: str = Field("uploads", validation_alias="UPLOADS_DIR")

    # Chunking Configurations
    chunk_size: int = Field(500, validation_alias="CHUNK_SIZE")
    chunk_max_size: int = Field(700, validation_alias="CHUNK_MAX_SIZE")
    chunk_overlap: int = Field(50, validation_alias="CHUNK_OVERLAP")

    # PostgreSQL Relational DB Configuration
    database_url: str = Field(
        "postgresql://postgres:postgres@db:5432/rag_db",
        validation_alias="DATABASE_URL"
    )

    # ChromaDB Vector DB Configuration
    chroma_host: str = Field("chroma", validation_alias="CHROMA_HOST")
    chroma_port: int = Field(8000, validation_alias="CHROMA_PORT")
    chroma_collection_name: str = Field("enterprise_knowledge_chunks", validation_alias="CHROMA_COLLECTION_NAME")

    # AI Provider configuration
    gemini_api_key: str = Field("mock-key", validation_alias="GEMINI_API_KEY")
    google_api_key: str = Field("", validation_alias="GOOGLE_API_KEY")
    embedding_model: str = Field("models/text-embedding-004", validation_alias="EMBEDDING_MODEL")

    # Security Configuration
    jwt_secret: str = Field(
        "secret-key-for-development-only-change-in-production",
        validation_alias="JWT_SECRET"
    )
    jwt_algorithm: str = Field("HS256", validation_alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(30, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_minutes: int = Field(1440, validation_alias="REFRESH_TOKEN_EXPIRE_MINUTES")



# Global settings instance
settings = Settings()
