"""Content generation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_orchestrator, get_tts
from app.core.logging import get_logger
from app.models.schemas import GenerateRequest, GenerateResponse, VoiceInfo
from app.services.orchestrator import ContentOrchestrator
from app.services.tts.edge_tts_provider import EdgeTTSProvider

logger = get_logger(__name__)
router = APIRouter(tags=["generate"])


@router.post("/generate", response_model=GenerateResponse)
async def generate_content(
    request: GenerateRequest,
    orchestrator: ContentOrchestrator = Depends(get_orchestrator),
) -> GenerateResponse:
    """Run the full pipeline for a topic: script, audio, metadata, thumbnails."""
    try:
        return await orchestrator.run(request)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Generation failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/voices", response_model=list[VoiceInfo])
async def list_voices(
    tts: EdgeTTSProvider = Depends(get_tts),
) -> list[VoiceInfo]:
    """List available TTS voices to help pick a smooth narration voice."""
    try:
        voices = await tts.list_voices()
        return [VoiceInfo(**v) for v in voices]
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to list voices")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
