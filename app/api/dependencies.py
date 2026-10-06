"""Dependency wiring for the API.

Builds the service graph once and exposes cached accessors that FastAPI can
inject into route handlers. This keeps construction logic out of the routes and
makes swapping providers a one-line change.
"""

from __future__ import annotations

from functools import lru_cache

from app.config import Settings, get_settings
from app.services.image import ImageProvider, build_image_provider
from app.services.llm.ollama_client import OllamaClient
from app.services.metadata_service import MetadataService
from app.services.orchestrator import ContentOrchestrator
from app.services.script_service import ScriptService
from app.services.thumbnail.pil_thumbnail import PILThumbnailGenerator
from app.services.tts.edge_tts_provider import EdgeTTSProvider


@lru_cache
def get_llm() -> OllamaClient:
    return OllamaClient(get_settings())


@lru_cache
def get_tts() -> EdgeTTSProvider:
    return EdgeTTSProvider(get_settings())


@lru_cache
def get_image_provider() -> ImageProvider | None:
    """Build the configured image provider (or None if disabled)."""
    return build_image_provider(get_settings())


@lru_cache
def get_orchestrator() -> ContentOrchestrator:
    """Assemble the full pipeline with its dependencies."""
    settings: Settings = get_settings()
    llm = get_llm()
    return ContentOrchestrator(
        settings=settings,
        script_service=ScriptService(llm),
        metadata_service=MetadataService(llm),
        tts_provider=get_tts(),
        thumbnail_generator=PILThumbnailGenerator(settings, llm, get_image_provider()),
    )
