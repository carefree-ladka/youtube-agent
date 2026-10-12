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
    # Thinking/reasoning models (e.g. qwen3) emit long <think> blocks that are
    # slow and pollute output. Keep OFF for fast, clean generations; set true
    # only if you specifically want chain-of-thought behavior.
    ollama_think: bool = Field(default=False)
    # Image generation can be slow; give it a longer timeout.
    ollama_image_timeout: float = Field(default=600.0)

    # ---------- TTS ----------
    # Which TTS backend to use: "edge" (edge-tts, online neural voices, free,
    # word-synced subtitles) or "f5" (F5-TTS, LOCAL zero-shot voice cloning).
    tts_provider: str = Field(default="edge")
    tts_voice: str = Field(default="en-US-JennyNeural")
    tts_rate: str = Field(default="+0%")
    tts_pitch: str = Field(default="+0Hz")
    tts_volume: str = Field(default="+0%")

    # ---------- F5-TTS (local voice cloning; used when TTS_PROVIDER=f5) ----------
    # NOTE: F5-TTS code is MIT, but its pretrained WEIGHTS are CC-BY-NC
    # (non-commercial). Review the license before using cloned audio commercially.
    # Path to a short (~6-12s), clean reference clip of the voice to clone (wav/mp3).
    f5_ref_audio: str = Field(default="")
    # Transcript of the reference clip. Leave empty to auto-transcribe it.
    f5_ref_text: str = Field(default="")
    # F5-TTS model preset (downloaded from Hugging Face on first use).
    f5_model: str = Field(default="F5TTS_v1_Base")
    # Device for F5 inference: "auto" (cuda>mps>cpu), or force "mps"/"cuda"/"cpu".
    f5_device: str = Field(default="auto")
    # Playback speed: long-form uses f5_speed, shorts/reels use f5_speed_short.
    # Below 1.0 = slower, more deliberate/human delivery (not rushed).
    f5_speed: float = Field(default=0.9)
    f5_speed_short: float = Field(default=0.95)
    # Human pacing: synthesize sentence-by-sentence and insert a short pause
    # between sentences (and a longer "breath" at paragraph breaks) so narration
    # isn't a flat, run-on read. Seconds; set both to 0 to disable per-sentence.
    f5_sentence_pause: float = Field(default=0.33)
    f5_paragraph_pause: float = Field(default=0.6)
    # Loudness: F5's internal RMS normalization target (higher = louder) plus a
    # final peak-normalization of the output WAV (0..1; 0 disables) so cloned
    # narration isn't quiet.
    f5_target_rms: float = Field(default=0.18)
    f5_peak: float = Field(default=0.98)
    # Keep F5's natural within-sentence silences (do NOT trim) so it sounds like
    # a person pausing, not a continuous read.
    f5_remove_silence: bool = Field(default=False)
    # Fixed random seed for reproducible voices (-1 = random each run).
    f5_seed: int = Field(default=-1)

    # ---------- Web content enrichment (opt-in) --------------------------------
    # When true, the pipeline researches the topic on the web (facts/stats) and
    # grounds the script + on-screen stat/quote/bullets in REAL information, and
    # (with IMAGE_BACKEND=web) uses real, license-aware photos for backgrounds.
    web_enrich: bool = Field(default=False)
    # Fact sources: "wikipedia" (no key), "duckduckgo" (needs ddgs), "both", "none".
    web_search_backend: str = Field(default="wikipedia")
    # How many distilled facts to feed downstream.
    web_max_facts: int = Field(default=8)
    # Network timeout for all web-enrichment HTTP calls (seconds).
    web_timeout: float = Field(default=20.0)
    # Polite UA string sent with web requests (Wikipedia/Openverse ask for one).
    web_user_agent: str = Field(default="youtube-agent/0.1 (local content generator)")
    # Image source for IMAGE_BACKEND=web: "openverse" (no key),
    # "pexels"/"pixabay" (need keys), "wikimedia" (no key).
    web_image_source: str = Field(default="openverse")
    # Openverse license filter - keep this commercial+modification friendly so
    # fetched images are safe to reuse (change at your own risk).
    web_image_license: str = Field(default="commercial,modification")
    # Filter out mature/NSFW results where the source supports it.
    web_safe: bool = Field(default=True)
    # Optional API keys for higher-quality stock sources (free tiers).
    pexels_api_key: str = Field(default="")
    pixabay_api_key: str = Field(default="")

    # ---------- Subtitle alignment (for providers without word timings) --------
    # When a provider (e.g. F5-TTS) returns no word timings, optionally use
    # faster-whisper to recover accurate per-word timestamps for karaoke subs.
    # If false or faster-whisper is not installed, subtitles are estimated by
    # evenly distributing the script across the real audio duration.
    tts_align: bool = Field(default=True)
    # faster-whisper model size (tiny|base|small|medium|large-v3) and device.
    align_model: str = Field(default="base")
    align_device: str = Field(default="auto")

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

    # ---------- Video generation (Remotion) ----------
    # Max seconds to allow a single Remotion render before timing out.
    video_render_timeout: float = Field(default=1800.0)
    # How many video jobs may render at once (renders are heavy; keep low).
    video_max_concurrent: int = Field(default=1)
    # Default visual style preset for videos.
    video_style: str = Field(default="modern-tech")
    # Transition/emphasis SFX playback volume (0..1). Low = subtle but noticeable.
    video_sfx_volume: float = Field(default=0.2)
    # Background music bed. Enabled by default with a soft, slow generated pad;
    # set VIDEO_MUSIC to a royalty-free track to use your own instead.
    video_music_enabled: bool = Field(default=True)
    video_music: str = Field(default="")  # path to a music file (loops); empty = generated bed
    video_music_volume: float = Field(default=0.12)  # low, sits under narration
    # Generate per-scene SVG visuals (topic-specific illustrations / mock screens
    # / diagrams) with the text LLM instead of reusing raster backgrounds. These
    # are crisp at any resolution and vary per scene. Falls back to a designed
    # SVG if the model is unavailable or returns something invalid.
    video_svg_assets: bool = Field(default=True)
    # Cap on how many SVGs to author per video (each is one LLM call); extra
    # svg elements beyond this use the designed fallback.
    video_svg_max: int = Field(default=8)
    # Max seconds to wait for a single SVG to be authored before falling back to
    # the designed SVG (keeps slow/large models from stalling the whole render).
    video_svg_timeout: float = Field(default=90.0)

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
