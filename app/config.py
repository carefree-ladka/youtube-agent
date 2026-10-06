"""Centralized application configuration loaded from the environment / .env file.

All tunables live here so services stay free of hard-coded values. Import the
cached `get_settings()` accessor rather than instantiating `Settings` directly.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = two levels up from this file (app/config.py -> app -> root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Strongly-typed settings sourced from environment variables / `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---------- App ----------
    app_name: str = Field(default="YouTube Agent")
    app_env: str = Field(default="development")
    log_level: str = Field(default="INFO")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)

    # ---------- Output ----------
    output_dir: str = Field(default="output")

    # ---------- Ollama ----------
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_text_model: str = Field(default="llama3.1")
    ollama_image_model: str = Field(default="llama3.1")
    ollama_timeout: float = Field(default=180.0)
    ollama_temperature: float = Field(default=0.8)
    # Image generation can be slow; give it a longer timeout.
    ollama_image_timeout: float = Field(default=600.0)

    # ---------- TTS ----------
    tts_voice: str = Field(default="en-US-JennyNeural")
    tts_rate: str = Field(default="+0%")
    tts_pitch: str = Field(default="+0Hz")
    tts_volume: str = Field(default="+0%")

    # ---------- Branding ----------
    # Channel name shown as a pill on thumbnails. Leave empty to show nothing.
    channel_name: str = Field(default="")
    brand_primary_color: str = Field(default="#FF0033")
    brand_secondary_color: str = Field(default="#111827")
    brand_text_color: str = Field(default="#FFFFFF")

    # ---------- Image generation (thumbnail backgrounds) ----------
    # Backend: "none" (designed PIL background), "ollama" (Ollama image model),
    # "diffusers" (local HF diffusers), or "comfyui" (a running ComfyUI server).
    image_backend: str = Field(default="none")
    # Any diffusers-compatible text-to-image model on Hugging Face.
    # Mac-friendly defaults: "stabilityai/sdxl-turbo" (fast, good quality) or
    # "stabilityai/sd-turbo" (smaller). For FLUX: "black-forest-labs/FLUX.1-schnell".
    diffusers_model: str = Field(default="stabilityai/sdxl-turbo")
    # Device: "auto" picks mps (Apple Silicon) > cuda > cpu.
    diffusers_device: str = Field(default="auto")
    # Turbo models need very few steps (1-4) and guidance 0.0.
    diffusers_steps: int = Field(default=4)
    diffusers_guidance: float = Field(default=0.0)
    # Native generation size (square is safest across models). The thumbnail
    # renderer cover-crops this to each platform format.
    diffusers_size: int = Field(default=1024)
    # Darkness (0-255) of the scrim drawn over the AI image so text stays legible.
    thumbnail_overlay_opacity: int = Field(default=110)

    # ---------- ComfyUI backend (used when IMAGE_BACKEND=comfyui) ----------
    # Base URL of a running ComfyUI server (Docker or native).
    comfyui_base_url: str = Field(default="http://localhost:8188")
    # Checkpoint file name as it appears in ComfyUI/models/checkpoints/.
    comfyui_checkpoint: str = Field(default="sd_xl_base_1.0.safetensors")
    comfyui_steps: int = Field(default=25)
    comfyui_cfg: float = Field(default=7.0)
    comfyui_sampler: str = Field(default="euler")
    comfyui_scheduler: str = Field(default="normal")
    comfyui_size: int = Field(default=1024)
    comfyui_negative_prompt: str = Field(
        default="text, words, letters, captions, watermark, logo, blurry, low quality, deformed"
    )
    # Optional path to a custom ComfyUI API-format workflow JSON with
    # placeholders (%POSITIVE% %NEGATIVE% %WIDTH% %HEIGHT% %SEED% %CKPT% %STEPS% %CFG%).
    # Leave empty to use the built-in SD/SDXL text-to-image workflow.
    comfyui_workflow: str = Field(default="")
    # Image generation can be slow; allow a long timeout.
    comfyui_timeout: float = Field(default=600.0)

    @property
    def output_path(self) -> Path:
        """Absolute path to the output root, created on first access."""
        path = Path(self.output_dir)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (loaded once per process)."""
    return Settings()
