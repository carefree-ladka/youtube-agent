"""Pydantic models for API requests and responses."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    """Input for a full content-generation run."""

    topic: str = Field(..., min_length=3, description="The video topic or idea.")
    # "long" = standard YouTube video; "short" = vertical Reel / YouTube Short.
    content_type: Literal["long", "short"] = Field(
        default="long", description="'long' video or 'short' reel."
    )
    tone: str = Field(
        default="engaging and friendly",
        description="Desired narration tone.",
    )
    audience: str = Field(
        default="a general YouTube audience",
        description="Who the video is for.",
    )
    target_minutes: int = Field(
        default=5, ge=1, le=30, description="Approx spoken length (long videos)."
    )
    target_seconds: int = Field(
        default=40, ge=10, le=180, description="Approx spoken length (short reels)."
    )
    language: str = Field(default="English", description="Output language.")

    # Toggles let callers skip expensive stages when they only need part of the run.
    generate_audio: bool = Field(default=True)
    generate_thumbnails: bool = Field(default=True)
    generate_metadata: bool = Field(default=True)

    @property
    def is_short(self) -> bool:
        """True when producing a short-form reel."""
        return self.content_type == "short"


class PlatformMetadata(BaseModel):
    """Loosely-typed container mirroring the normalized metadata dict."""

    topic: str
    titles: list[str] = []
    youtube: dict = {}
    instagram: dict = {}
    linkedin: dict = {}
    keywords: list[str] = []


class GenerateResponse(BaseModel):
    """Result of a generation run, including on-disk artifact paths."""

    topic: str
    project_dir: str
    title: str
    script_path: str | None = None
    audio_path: str | None = None
    metadata_path: str | None = None
    thumbnail_paths: list[str] = []
    metadata: dict | None = None
    warnings: list[str] = []


class VoiceInfo(BaseModel):
    """A single available TTS voice."""

    name: str | None = None
    gender: str | None = None
    locale: str | None = None
    friendly: str | None = None


class HealthResponse(BaseModel):
    """Service health, including Ollama reachability."""

    status: str
    ollama_reachable: bool
    text_model: str
    image_model: str
    tts_voice: str
