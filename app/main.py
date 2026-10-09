"""FastAPI application entrypoint.

Run with:
    uvicorn app.main:app --reload
or use the convenience launcher:
    python run.py
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.routes import generate, health, videos
from app.config import get_settings
from app.core.logging import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Log startup/shutdown and surface key configuration."""
    logger.info("Starting %s v%s (env=%s)", settings.app_name, __version__, settings.app_env)
    logger.info("Ollama: %s | text=%s image=%s", settings.ollama_base_url,
                settings.ollama_text_model, settings.ollama_image_model)
    logger.info("Output dir: %s", settings.output_path)
    yield
    logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description=(
        "Turn a topic into a complete content package: narration script, "
        "smooth TTS audio, multi-platform metadata, and thumbnails."
    ),
    lifespan=lifespan,
)

# CORS is permissive by default for local development. Restrict in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(generate.router)
app.include_router(videos.router)

# Serve generated artifacts (the rendered video, thumbnails, etc.) under /media.
app.mount("/media", StaticFiles(directory=str(settings.output_path)), name="media")


@app.get("/", tags=["root"])
async def root() -> dict:
    """Basic index with pointers to the docs."""
    return {
        "name": settings.app_name,
        "version": __version__,
        "docs": "/docs",
        "endpoints": [
            "/health",
            "/generate",
            "/voices",
            "/videos/generate",
            "/videos/{jobId}",
            "/media/{path}",
        ],
    }
