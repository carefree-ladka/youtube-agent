"""ComfyUI-backed image generation.

Talks to a running ComfyUI server (Docker or native) over its local HTTP API:

    1. POST /prompt      - queue a text-to-image workflow, get a prompt_id
    2. GET  /history/{id} - poll until the run finishes and lists output images
    3. GET  /view         - download the generated image bytes

By default a standard SD/SDXL text-to-image workflow is built in code. Advanced
users can point ``COMFYUI_WORKFLOW`` at an exported API-format workflow JSON that
uses placeholders (%POSITIVE%, %NEGATIVE%, %WIDTH%, %HEIGHT%, %SEED%, %CKPT%,
%STEPS%, %CFG%) for full control (e.g. a FLUX or Qwen-Image graph).

As with every image backend here, ComfyUI only paints the text-free BACKGROUND;
the crisp headline is drawn on top by the PIL renderer.
"""

from __future__ import annotations

import asyncio
import json
import random
import uuid
from pathlib import Path
from typing import Any

import httpx

from app.config import Settings
from app.core.logging import get_logger
from app.services.image.base import ImageProvider

logger = get_logger(__name__)


class ComfyUIImageProvider(ImageProvider):
    """Generate background images via a running ComfyUI server."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.comfyui_base_url.rstrip("/")
        self._checkpoint = settings.comfyui_checkpoint
        self._steps = settings.comfyui_steps
        self._cfg = settings.comfyui_cfg
        self._sampler = settings.comfyui_sampler
        self._scheduler = settings.comfyui_scheduler
        self._size = settings.comfyui_size
        self._negative = settings.comfyui_negative_prompt
        self._workflow_path = settings.comfyui_workflow
        self._timeout = settings.comfyui_timeout
        self._client_id = uuid.uuid4().hex

    # ------------------------------------------------------------------ #
    # Availability
    # ------------------------------------------------------------------ #
    def is_available(self) -> bool:
        """True if the ComfyUI server responds."""
        try:
            with httpx.Client(timeout=5.0) as client:
                client.get(f"{self._base_url}/system_stats").raise_for_status()
            return True
        except (httpx.HTTPError, OSError) as exc:
            logger.warning(
                "ComfyUI not reachable at %s (%s). Is the server running?",
                self._base_url,
                exc,
            )
            return False

    # ------------------------------------------------------------------ #
    # Generation
    # ------------------------------------------------------------------ #
    async def generate(self, prompt: str, width: int, height: int) -> bytes | None:
        """Run the workflow for ``prompt`` and return PNG bytes, or None."""
        workflow = self._build_workflow(prompt)
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                prompt_id = await self._queue(client, workflow)
                if not prompt_id:
                    return None
                image_ref = await self._await_image(client, prompt_id)
                if not image_ref:
                    return None
                return await self._download(client, image_ref)
        except (httpx.HTTPError, OSError) as exc:
            logger.warning("ComfyUI image generation failed: %s", exc)
            return None

    async def _queue(self, client: httpx.AsyncClient, workflow: dict) -> str | None:
        resp = await client.post(
            f"{self._base_url}/prompt",
            json={"prompt": workflow, "client_id": self._client_id},
        )
        if resp.status_code >= 400:
            logger.warning("ComfyUI /prompt rejected (%s): %s", resp.status_code, resp.text[:300])
            return None
        prompt_id = resp.json().get("prompt_id")
        logger.info("ComfyUI queued prompt %s", prompt_id)
        return prompt_id

    async def _await_image(
        self, client: httpx.AsyncClient, prompt_id: str
    ) -> dict[str, Any] | None:
        """Poll /history until the prompt produces an output image."""
        deadline = asyncio.get_event_loop().time() + self._timeout
        while asyncio.get_event_loop().time() < deadline:
            resp = await client.get(f"{self._base_url}/history/{prompt_id}")
            if resp.status_code == 200:
                history = resp.json().get(prompt_id)
                if history:
                    image = _first_image(history.get("outputs", {}))
                    if image:
                        return image
                    status = history.get("status", {})
                    if status.get("completed") or status.get("status_str") == "error":
                        logger.warning("ComfyUI run finished with no image: %s", status)
                        return None
            await asyncio.sleep(1.5)
        logger.warning("ComfyUI timed out after %ss waiting for an image.", self._timeout)
        return None

    async def _download(self, client: httpx.AsyncClient, ref: dict[str, Any]) -> bytes | None:
        params = {
            "filename": ref.get("filename", ""),
            "subfolder": ref.get("subfolder", ""),
            "type": ref.get("type", "output"),
        }
        resp = await client.get(f"{self._base_url}/view", params=params)
        resp.raise_for_status()
        data = resp.content
        logger.info("ComfyUI image downloaded (%d bytes)", len(data))
        return data or None

    # ------------------------------------------------------------------ #
    # Workflow building
    # ------------------------------------------------------------------ #
    def _build_workflow(self, prompt: str) -> dict:
        seed = random.randint(0, 2**31 - 1)
        if self._workflow_path:
            custom = self._load_custom_workflow(prompt, seed)
            if custom is not None:
                return custom
        return self._default_workflow(prompt, seed)

    def _load_custom_workflow(self, prompt: str, seed: int) -> dict | None:
        """Load a user workflow template and substitute placeholders."""
        path = Path(self._workflow_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        if not path.exists():
            logger.warning("COMFYUI_WORKFLOW not found at %s; using default workflow.", path)
            return None
        text = path.read_text(encoding="utf-8")
        replacements = {
            "%POSITIVE%": _json_safe(prompt),
            "%NEGATIVE%": _json_safe(self._negative),
            "%WIDTH%": str(self._size),
            "%HEIGHT%": str(self._size),
            "%SEED%": str(seed),
            "%CKPT%": _json_safe(self._checkpoint),
            "%STEPS%": str(self._steps),
            "%CFG%": str(self._cfg),
        }
        for key, value in replacements.items():
            text = text.replace(key, value)
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            logger.warning("Custom ComfyUI workflow is not valid JSON after substitution: %s", exc)
            return None

    def _default_workflow(self, prompt: str, seed: int) -> dict:
        """Standard SD/SDXL text-to-image graph in ComfyUI API format."""
        return {
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": self._checkpoint},
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {"width": self._size, "height": self._size, "batch_size": 1},
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": prompt, "clip": ["4", 1]},
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": self._negative, "clip": ["4", 1]},
            },
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": seed,
                    "steps": self._steps,
                    "cfg": self._cfg,
                    "sampler_name": self._sampler,
                    "scheduler": self._scheduler,
                    "denoise": 1.0,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0],
                },
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": "yt_agent", "images": ["8", 0]},
            },
        }


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _first_image(outputs: dict[str, Any]) -> dict[str, Any] | None:
    """Return the first image reference found across all output nodes."""
    for node_output in outputs.values():
        images = node_output.get("images") if isinstance(node_output, dict) else None
        if images:
            return images[0]
    return None


def _json_safe(text: str) -> str:
    """Escape a string so it can be inserted into a JSON template safely."""
    return json.dumps(text)[1:-1]
