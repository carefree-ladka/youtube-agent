"""Research a topic on the web and distill it into verified, usable content.

Pipeline: gather reference text (Wikipedia / optional DuckDuckGo) -> ask the LLM
to extract concrete facts, stats, and real image search queries -> return a
``ResearchBrief`` the script and storyboard stages use to ground on-screen
content in REAL information instead of vague filler.

Entirely best-effort: if the web is unreachable or the LLM output is unusable,
it falls back to the raw reference text (or returns an empty brief) so the
pipeline proceeds unchanged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.config import Settings
from app.core.logging import get_logger
from app.core.prompts import RESEARCH_SYSTEM, build_research_distill_prompt
from app.services.llm.base import LLMClient
from app.services.web.search import WebSearch, WebSource

logger = get_logger(__name__)


@dataclass
class ResearchBrief:
    """Distilled, verifiable material about a topic."""

    facts: list[str] = field(default_factory=list)
    stats: list[dict] = field(default_factory=list)       # [{"value","label"}]
    image_queries: list[str] = field(default_factory=list)
    sources: list[WebSource] = field(default_factory=list)
    lead_image_url: str | None = None

    @property
    def is_empty(self) -> bool:
        return not (self.facts or self.stats)

    def as_prompt_block(self) -> str:
        """Render the brief as a compact block to inject into other prompts."""
        if self.is_empty:
            return ""
        lines: list[str] = []
        if self.facts:
            lines.append("VERIFIED FACTS (use these; do NOT contradict or invent beyond them):")
            lines += [f"- {f}" for f in self.facts]
        if self.stats:
            lines.append("KEY NUMBERS (real - use for stat/quote visuals):")
            lines += [f"- {s.get('value')}: {s.get('label')}" for s in self.stats if s.get("value")]
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "facts": self.facts,
            "stats": self.stats,
            "image_queries": self.image_queries,
            "sources": [{"title": s.title, "url": s.url} for s in self.sources],
            "lead_image_url": self.lead_image_url,
        }


class ResearchService:
    """Gathers and distills web research for a topic."""

    def __init__(self, llm: LLMClient, settings: Settings) -> None:
        self._llm = llm
        self._settings = settings
        self._search = WebSearch(
            backend=settings.web_search_backend,
            timeout=settings.web_timeout,
            user_agent=settings.web_user_agent,
        )

    async def research(self, topic: str) -> ResearchBrief:
        """Return a ResearchBrief for ``topic`` (never raises)."""
        logger.info("Researching topic on the web: %s", topic)
        try:
            raw = await self._search.gather(topic)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Web research gather failed: %s", exc)
            return ResearchBrief()

        brief = ResearchBrief(sources=raw.sources, lead_image_url=raw.lead_image_url)
        if not raw.text.strip():
            logger.info("No reference text found for '%s'; skipping enrichment.", topic)
            return brief

        # Distill with the LLM into clean, structured, verifiable content.
        try:
            data = await self._llm.generate_json(
                build_research_distill_prompt(topic, raw.text, self._settings.web_max_facts),
                system=RESEARCH_SYSTEM,
            )
            brief.facts = _clean_list(data.get("facts"), self._settings.web_max_facts)
            brief.stats = _clean_stats(data.get("stats"))
            brief.image_queries = _clean_list(data.get("image_queries"), 6)
        except Exception as exc:  # noqa: BLE001 - degrade to raw extract
            logger.warning("Research distillation failed (%s); using raw extract.", exc)
            brief.facts = _sentences(raw.text, self._settings.web_max_facts)

        logger.info(
            "Research brief: %d facts, %d stats, %d image queries, %d sources",
            len(brief.facts), len(brief.stats), len(brief.image_queries), len(brief.sources),
        )
        return brief


def _clean_list(value: object, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = str(item).strip().strip('"').replace("*", "")
        if text and text.lower() not in {"n/a", "none", "unknown"}:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _clean_stats(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    stats: list[dict] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        val = str(item.get("value", "")).strip()
        label = str(item.get("label", "")).strip()
        if val and label:
            stats.append({"value": val[:16], "label": label[:40]})
        if len(stats) >= 6:
            break
    return stats


def _sentences(text: str, limit: int) -> list[str]:
    """Fallback: split reference text into short fact-like sentences."""
    cleaned = re.sub(r"##[^\n]*", " ", text)
    parts = [s.strip() for s in re.split(r"(?<=[.!?])\s+", cleaned) if len(s.split()) >= 4]
    return parts[:limit]
