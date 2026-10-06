"""Local text-to-image generation using the `diffusers` library.

Runs Stable Diffusion / FLUX style models entirely on-device (Apple Silicon
MPS, NVIDIA CUDA, or CPU). The heavy model pipeline is loaded lazily and cached
on the instance, and generation runs in a worker thread so it never blocks the
async event loop.

Heavy imports (torch, diffusers) are done inside methods so the base app stays
importable even when the image extra isn't installed.
"""

from __future__ import annotations

import asyncio
import io
from typing import Any

from app.config import Settings
from app.core.logging import get_logger
from app.services.image.base import ImageProvider

logger = get_logger(__name__)


class DiffusersImageProvider(ImageProvider):
    """Generate images locally via a diffusers text-to-image pipeline."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = settings.diffusers_model
        self._steps = settings.diffusers_steps
        self._guidance = settings.diffusers_guidance
        self._size = settings.diffusers_size
        self._device = self._resolve_device(settings.diffusers_device)
        self._pipe: Any | None = None
        self._load_failed = False

    # ------------------------------------------------------------------ #
    # Availability
    # ------------------------------------------------------------------ #
    def is_available(self) -> bool:
        """True if torch + diffusers can be imported."""
        try:
            import diffusers  # noqa: F401
            import torch  # noqa: F401
        except ImportError:
            return False
        return not self._load_failed

    # ------------------------------------------------------------------ #
    # Generation
    # ------------------------------------------------------------------ #
    async def generate(self, prompt: str, width: int, height: int) -> bytes | None:
        """Generate a square image for ``prompt`` and return PNG bytes.

        ``width``/``height`` are accepted for interface parity; the model
        generates at its configured native square size and the thumbnail
        renderer cover-crops to the exact target dimensions.
        """
        if not self.is_available():
            logger.warning(
                "diffusers/torch not installed. Install with: "
                "pip install -r requirements-image.txt"
            )
            return None
        try:
            return await asyncio.to_thread(self._generate_sync, prompt)
        except Exception as exc:  # noqa: BLE001 - never break the pipeline
            logger.exception("Image generation failed: %s", exc)
            return None

    def _generate_sync(self, prompt: str) -> bytes | None:
        pipe = self._get_pipeline()
        if pipe is None:
            return None

        import torch

        logger.info(
            "Generating image (model=%s, device=%s, steps=%d)",
            self._model,
            self._device,
            self._steps,
        )
        # Turbo models expect guidance_scale=0.0; honor whatever is configured.
        with torch.inference_mode():
            result = pipe(
                prompt=prompt,
                num_inference_steps=max(self._steps, 1),
                guidance_scale=self._guidance,
                height=self._size,
                width=self._size,
            )
        image = result.images[0]

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        logger.info("Image generated (%d bytes)", buffer.tell())
        return buffer.getvalue()

    # ------------------------------------------------------------------ #
    # Pipeline lifecycle
    # ------------------------------------------------------------------ #
    def _get_pipeline(self) -> Any | None:
        """Load and cache the diffusers pipeline on first use."""
        if self._pipe is not None or self._load_failed:
            return self._pipe

        try:
            import torch
            from diffusers import AutoPipelineForText2Image
        except ImportError:
            self._load_failed = True
            return None

        dtype = torch.float32 if self._device == "cpu" else torch.float16
        logger.info("Loading diffusers model '%s' (%s, %s)...", self._model, self._device, dtype)
        try:
            # Prefer the smaller fp16 weight variant on GPU devices (roughly half
            # the download and memory). Fall back to the default weights if the
            # model doesn't publish an fp16 variant.
            try:
                pipe = AutoPipelineForText2Image.from_pretrained(
                    self._model,
                    torch_dtype=dtype,
                    variant="fp16" if self._device != "cpu" else None,
                )
            except Exception:  # noqa: BLE001 - variant may not exist
                pipe = AutoPipelineForText2Image.from_pretrained(
                    self._model,
                    torch_dtype=dtype,
                )
            pipe = pipe.to(self._device)
            # Reduce memory pressure - important on Apple Silicon.
            if hasattr(pipe, "enable_attention_slicing"):
                pipe.enable_attention_slicing()
            if hasattr(pipe, "set_progress_bar_config"):
                pipe.set_progress_bar_config(disable=True)
            # Some SD pipelines ship a safety checker that can blank images.
            if getattr(pipe, "safety_checker", None) is not None:
                pipe.safety_checker = None
            self._pipe = pipe
            logger.info("Model loaded and ready on %s.", self._device)
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Failed to load diffusers model '%s': %s. "
                "First run downloads the weights (several GB) - ensure disk space "
                "and network access, or set IMAGE_BACKEND=none.",
                self._model,
                exc,
            )
            self._load_failed = True
            self._pipe = None
        return self._pipe

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _resolve_device(preference: str) -> str:
        """Resolve 'auto' to the best available device: mps > cuda > cpu."""
        preference = (preference or "auto").strip().lower()
        try:
            import torch
        except ImportError:
            return "cpu"

        if preference in ("mps", "cuda", "cpu"):
            return preference
        if torch.backends.mps.is_available():
            return "mps"
        if torch.cuda.is_available():
            return "cuda"
        return "cpu"
