"""Health and readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_llm
from app.config import Settings, get_settings
from app.models.schemas import HealthResponse
from app.services.llm.ollama_client import OllamaClient

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(
    llm: OllamaClient = Depends(get_llm),
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    """Report service status and whether Ollama is reachable."""
    reachable = await llm.health()
    return HealthResponse(
        status="ok" if reachable else "degraded",
        ollama_reachable=reachable,
        text_model=settings.ollama_text_model,
        image_model=settings.ollama_image_model,
        tts_voice=settings.tts_voice,
    )
