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
from app.services.video.asset_manager import AssetManager
from app.services.video.jobs import VideoJobManager
from app.services.video.remotion_renderer import RemotionRenderer
from app.services.video.storyboard_service import StoryboardService
from app.services.video.svg_service import SvgService
from app.services.video.video_orchestrator import VideoOrchestrator


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


@lru_cache
def get_video_orchestrator() -> VideoOrchestrator:
    """Assemble the video pipeline, reusing existing script/TTS/metadata/thumbnail."""
    settings: Settings = get_settings()
    llm = get_llm()
    return VideoOrchestrator(
        settings=settings,
        script_service=ScriptService(llm),
        storyboard_service=StoryboardService(llm),
        asset_manager=AssetManager(get_image_provider()),
        svg_service=SvgService(llm, settings),
        tts_provider=get_tts(),
        renderer=RemotionRenderer(timeout=settings.video_render_timeout),
        llm=llm,
        metadata_service=MetadataService(llm),
        thumbnail_generator=PILThumbnailGenerator(settings, llm, get_image_provider()),
    )


@lru_cache
def get_job_manager() -> VideoJobManager:
    """Singleton job manager so background jobs persist across requests."""
    settings = get_settings()
    return VideoJobManager(
        get_video_orchestrator(), settings, max_concurrent=settings.video_max_concurrent
    )
