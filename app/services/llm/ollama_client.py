"""Ollama-backed LLM client.

Talks to a local Ollama server via its HTTP API. Supports plain text
generation and strict JSON generation (using Ollama's ``format=json`` mode),
with retries for transient failures.
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import Settings
from app.core.logging import get_logger
from app.services.llm.base import LLMClient

logger = get_logger(__name__)


class OllamaError(RuntimeError):
    """Raised when the Ollama backend fails or returns an unusable response."""


# Reasoning models (qwen3, deepseek-r1, ...) may wrap their chain-of-thought in
# <think>...</think>. We disable thinking at the API level, but strip it too in
# case a model inlines it anyway, so downstream parsing never sees reasoning.
_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)


def _strip_think(text: str) -> str:
    """Remove any <think>...</think> reasoning blocks from model output."""
    if "<think>" not in text.lower():
        return text
    cleaned = _THINK_BLOCK.sub("", text)
    # Handle an unclosed <think> (truncated reasoning): keep what follows it.
    lower = cleaned.lower()
    if "<think>" in lower and "</think>" not in lower:
        cleaned = cleaned[: lower.index("<think>")]
    return cleaned


class OllamaClient(LLMClient):
    """Async client for a local Ollama instance."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._text_model = settings.ollama_text_model
        self._timeout = settings.ollama_timeout
        self._temperature = settings.ollama_temperature
        self._think = settings.ollama_think

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def generate_text(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
    ) -> str:
        data = await self._generate(
            prompt=prompt,
            system=system,
            model=model or self._text_model,
            temperature=temperature,
            json_mode=False,
        )
        return _strip_think(data).strip()

    async def generate_json(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        raw = await self._generate(
            prompt=prompt,
            system=system,
            model=model or self._text_model,
            temperature=temperature,
            json_mode=True,
        )
        return self._parse_json(raw)

    async def health(self) -> bool:
        """Return True if the Ollama server responds to a version check."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._base_url}/api/version")
                resp.raise_for_status()
            return True
        except (httpx.HTTPError, OSError) as exc:
            logger.warning("Ollama health check failed: %s", exc)
            return False

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def _generate(
        self,
        *,
        prompt: str,
        system: str | None,
        model: str,
        temperature: float | None,
        json_mode: bool,
    ) -> str:
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": (
                    temperature if temperature is not None else self._temperature
                ),
            },
        }
        if system:
            payload["system"] = system
        if json_mode:
            payload["format"] = "json"
        # Control reasoning for thinking-capable models. Sending think=false is
        # safe for non-thinking models (they already don't think); it keeps the
        # big reasoning models fast and their output clean.
        payload["think"] = self._think

        logger.info("Ollama generate (model=%s, json=%s)", model, json_mode)
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(f"{self._base_url}/api/generate", json=payload)
                # Some Ollama versions/models reject the "think" field with a 400.
                # Drop it and retry once rather than failing the whole call.
                if resp.status_code == 400 and "think" in payload:
                    payload.pop("think", None)
                    resp = await client.post(f"{self._base_url}/api/generate", json=payload)
                resp.raise_for_status()
                body = resp.json()
        except httpx.HTTPStatusError as exc:
            raise OllamaError(
                f"Ollama returned {exc.response.status_code}. "
                f"Is model '{model}' pulled? Try `ollama pull {model}`."
            ) from exc
        except httpx.HTTPError as exc:
            raise OllamaError(
                f"Cannot reach Ollama at {self._base_url}. Is it running? "
                "Start it with `ollama serve`."
            ) from exc

        response_text = body.get("response", "")
        if not response_text:
            raise OllamaError("Ollama returned an empty response.")
        return response_text

    @staticmethod
    def _parse_json(raw: str) -> dict[str, Any]:
        """Parse model output into a dict, tolerating stray markdown fences."""
        text = _strip_think(raw).strip()
        # Strip accidental ```json ... ``` fences if a model adds them.
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
        text = text.strip()

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            # Last resort: extract the outermost {...} block.
            start, end = text.find("{"), text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    parsed = json.loads(text[start : end + 1])
                except json.JSONDecodeError as exc:
                    raise OllamaError(
                        "Failed to parse JSON from model output."
                    ) from exc
            else:
                raise OllamaError("Model did not return JSON.")

        if not isinstance(parsed, dict):
            raise OllamaError("Expected a JSON object from the model.")
        return parsed
