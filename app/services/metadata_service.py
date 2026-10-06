"""Generates cross-platform publishing metadata (YouTube, Instagram, LinkedIn).

Two-pass, quality-first approach:

1. The LLM produces the full creative package (titles, description, tags,
   hashtags) using a growth-strategist prompt tuned for reach and CTR.
2. After cleaning and de-duplicating, if any tag/hashtag list is below a healthy
   target, a single focused expansion call asks the model for MORE genuinely
   relevant items. We never pad with mechanical or generic filler - if the model
   can't produce more relevant items, we keep the smaller, higher-quality set.
"""

from __future__ import annotations

import re
from typing import Any

from app.core.logging import get_logger
from app.core.prompts import (
    METADATA_EXPANSION_SYSTEM,
    METADATA_SYSTEM,
    build_metadata_expansion_prompt,
    build_metadata_prompt,
)
from app.services.llm.base import LLMClient

logger = get_logger(__name__)

# Healthy target counts. These are goals, not filler quotas - if a quality
# expansion still falls short, we accept the smaller set.
_TARGET_YT_TAGS = 22
_TARGET_YT_HASHTAGS = 12
_TARGET_IG_HASHTAGS = 25
_TARGET_LI_HASHTAGS = 10
_TARGET_KEYWORDS = 12

# Map internal field names to (target, is_hashtag) for the expansion pass.
_EXPANSION_FIELDS = {
    "youtube_tags": (_TARGET_YT_TAGS, False),
    "youtube_hashtags": (_TARGET_YT_HASHTAGS, True),
    "instagram_hashtags": (_TARGET_IG_HASHTAGS, True),
    "linkedin_hashtags": (_TARGET_LI_HASHTAGS, True),
    "keywords": (_TARGET_KEYWORDS, False),
}


class MetadataService:
    """Produces titles, descriptions, tags, and hashtags for each platform."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def generate(
        self,
        topic: str,
        script: str,
        *,
        language: str = "English",
        content_type: str = "long",
    ) -> dict[str, Any]:
        """Return a normalized, quality-expanded metadata dict."""
        logger.info("Generating cross-platform metadata for: %s", topic)
        excerpt = script[:1200]
        prompt = build_metadata_prompt(topic=topic, script_excerpt=excerpt, language=language)
        data = await self._llm.generate_json(prompt, system=METADATA_SYSTEM)

        normalized = self._normalize(data, topic)
        await self._expand_if_short(normalized, topic)
        if content_type == "short":
            self._add_short_form_tags(normalized)
        return normalized

    @staticmethod
    def _add_short_form_tags(meta: dict[str, Any]) -> None:
        """Prepend platform discovery tags for reels / shorts."""
        yt = meta["youtube"]
        yt["hashtags"] = _dedupe(["#Shorts", "#YouTubeShorts", *yt["hashtags"]])
        if "shorts" not in [t.lower() for t in yt["tags"]]:
            yt["tags"] = _dedupe(["shorts", "youtube shorts", *yt["tags"]])
        ig = meta["instagram"]
        ig["hashtags"] = _dedupe(["#Reels", "#ReelsInstagram", "#InstaReels", *ig["hashtags"]])

    # ------------------------------------------------------------------ #
    # Pass 1: clean + dedupe the model's output
    # ------------------------------------------------------------------ #
    def _normalize(self, data: dict[str, Any], topic: str) -> dict[str, Any]:
        youtube = data.get("youtube") or {}
        instagram = data.get("instagram") or {}
        linkedin = data.get("linkedin") or {}

        titles = _dedupe(_as_list(data.get("titles")) or [topic])
        best_title = _as_text(youtube.get("title")) or (titles[0] if titles else topic)

        return {
            "topic": topic,
            "titles": titles,
            "youtube": {
                "title": _one_line(best_title),
                "description": _as_text(youtube.get("description")),
                "tags": _dedupe(_strip_hashes(_as_list(youtube.get("tags")))),
                "hashtags": _dedupe(_normalize_hashtags(_as_list(youtube.get("hashtags")))),
                "chapters": _as_list(youtube.get("chapters")),
            },
            "instagram": {
                "caption": _as_text(instagram.get("caption")),
                "hashtags": _dedupe(_normalize_hashtags(_as_list(instagram.get("hashtags")))),
            },
            "linkedin": {
                "post": _as_text(linkedin.get("post")),
                "hashtags": _dedupe(_normalize_hashtags(_as_list(linkedin.get("hashtags")))),
            },
            "keywords": _dedupe(_strip_hashes(_as_list(data.get("keywords")))),
        }

    # ------------------------------------------------------------------ #
    # Pass 2: one focused LLM call to add MORE relevant items where short
    # ------------------------------------------------------------------ #
    async def _expand_if_short(self, meta: dict[str, Any], topic: str) -> None:
        current = self._current_lists(meta)
        needs = {
            field: target - len(current[field])
            for field, (target, _) in _EXPANSION_FIELDS.items()
            if len(current[field]) < target
        }
        if not needs:
            return

        logger.info("Expanding short metadata lists (quality top-up): %s", needs)
        prompt = build_metadata_expansion_prompt(
            topic=topic,
            title=meta["youtube"]["title"],
            needs=needs,
            existing=current,
        )
        try:
            extra = await self._llm.generate_json(prompt, system=METADATA_EXPANSION_SYSTEM)
        except Exception as exc:  # noqa: BLE001 - expansion is best-effort
            logger.warning("Metadata expansion failed (keeping first pass): %s", exc)
            return

        self._merge_expansion(meta, extra)

    @staticmethod
    def _current_lists(meta: dict[str, Any]) -> dict[str, list[str]]:
        return {
            "youtube_tags": meta["youtube"]["tags"],
            "youtube_hashtags": meta["youtube"]["hashtags"],
            "instagram_hashtags": meta["instagram"]["hashtags"],
            "linkedin_hashtags": meta["linkedin"]["hashtags"],
            "keywords": meta["keywords"],
        }

    @staticmethod
    def _merge_expansion(meta: dict[str, Any], extra: dict[str, Any]) -> None:
        """Merge additional items in, deduped, respecting each field's format."""
        meta["youtube"]["tags"] = _dedupe(
            meta["youtube"]["tags"] + _strip_hashes(_as_list(extra.get("youtube_tags")))
        )
        meta["keywords"] = _dedupe(
            meta["keywords"] + _strip_hashes(_as_list(extra.get("keywords")))
        )
        meta["youtube"]["hashtags"] = _dedupe(
            meta["youtube"]["hashtags"] + _normalize_hashtags(_as_list(extra.get("youtube_hashtags")))
        )
        meta["instagram"]["hashtags"] = _dedupe(
            meta["instagram"]["hashtags"]
            + _normalize_hashtags(_as_list(extra.get("instagram_hashtags")))
        )
        meta["linkedin"]["hashtags"] = _dedupe(
            meta["linkedin"]["hashtags"]
            + _normalize_hashtags(_as_list(extra.get("linkedin_hashtags")))
        )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _as_list(value: Any) -> list[str]:
    """Coerce a value into a list of non-empty trimmed strings."""
    if not value:
        return []
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",")]
        return [p for p in parts if p]
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return []


def _as_text(value: Any) -> str:
    """Coerce a value into a clean string.

    Models sometimes return long text fields (description, caption, post) as a
    list of paragraphs or a dict; join/normalize those into a single string.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        parts = [_as_text(v) for v in value]
        return "\n\n".join(p for p in parts if p)
    if isinstance(value, dict):
        parts = [_as_text(v) for v in value.values()]
        return "\n\n".join(p for p in parts if p)
    return str(value).strip()


def _one_line(text: str) -> str:
    """Collapse a string to a single line (used for titles)."""
    return " ".join(text.split())


def _dedupe(items: list[str]) -> list[str]:
    """Remove case-insensitive duplicates while preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.lower()
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _strip_hashes(items: list[str]) -> list[str]:
    """Turn any '#Foo Bar' into a plain lowercase search tag."""
    return [i.lstrip("#").strip().lower() for i in items if i.strip("# ")]


def _normalize_hashtags(items: list[str]) -> list[str]:
    """Ensure every hashtag is a single '#token' with no spaces or symbols."""
    result: list[str] = []
    for item in items:
        tag = _to_hashtag(item)
        if tag != "#":
            result.append(tag)
    return result


def _to_hashtag(text: str) -> str:
    """Convert 'better sleep' or '#Better Sleep!' into '#bettersleep'."""
    cleaned = re.sub(r"[^0-9a-zA-Z]+", "", text.lstrip("#"))
    return "#" + cleaned.lower()
