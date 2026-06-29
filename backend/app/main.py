import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging_config import setup_logging
from app.routers import health, auth, documents, retrieval, prompt

# Initialize application logging before other operations
setup_logging()
logger = logging.getLogger(__name__)

# Boot FastAPI application instance
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Stateless Backend Services API for RAG Knowledge Platform"
)

# Configure Cross-Origin Resource Sharing (CORS) Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Wildcard allowed for baseline foundation testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(retrieval.router)
app.include_router(prompt.router)

logger.info(f"Successfully initialized application foundation: {settings.app_name} v{settings.app_version}")
