"""Abstract LLM client interface.

Defining an interface keeps the rest of the codebase provider-agnostic. Swapping
Ollama for another backend later only requires a new subclass.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMClient(ABC):
    """Common contract every LLM provider must implement."""

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
    ) -> str:
        """Return free-form generated text for a prompt."""
        raise NotImplementedError

    @abstractmethod
    async def generate_json(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """Return a parsed JSON object for a prompt."""
        raise NotImplementedError

    @abstractmethod
    async def health(self) -> bool:
        """Return True if the backend is reachable."""
        raise NotImplementedError
