import logging
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from app.core.config import settings

logger = logging.getLogger(__name__)

# Declarative base class for downstream ORM model definitions
Base = declarative_base()

# Configure SQLAlchemy engine with pools for FastAPI
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # Checks connections before issuing queries
    pool_size=5,
    max_overflow=10
)

# Session factory configuration
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency yielding a PostgreSQL database session.
    Ensures session is closed cleanly after the request lifecycle.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> bool:
    """
    Performs a simple query against PostgreSQL to check connectivity.

    Returns:
        bool: True if connection is active, False otherwise.
    """
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"PostgreSQL connection check failed: {str(e)}")
        return False
