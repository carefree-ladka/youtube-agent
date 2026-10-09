"""Shared heuristics for classifying a topic.

Used to decide when a topic is technical (programming / algorithms / CS), so the
script is accuracy-first and the storyboard may include code snippets. Non-technical
topics must never get code elements.
"""

from __future__ import annotations

import re

# Signals that a topic is technical and may warrant code/accuracy-first handling.
_TECHNICAL_TERMS: set[str] = {
    "algorithm", "algorithms", "kadane", "dijkstra", "sort", "sorting",
    "recursion", "closure", "closures", "hashmap", "hashtable", "big", "complexity",
    "linkedlist", "tree", "graph", "dp", "pointer", "pointers", "javascript", "js",
    "typescript", "ts", "python", "java", "golang", "go", "rust", "cpp", "csharp",
    "react", "vue", "angular", "node", "nodejs", "api", "rest", "graphql", "database",
    "sql", "nosql", "postgres", "postgresql", "pgvector", "mongodb", "redis", "docker",
    "kubernetes", "k8s", "function", "async", "await", "promise", "regex", "compiler",
    "memory", "concurrency", "thread", "threading", "cache", "code", "coding",
    "programming", "variable", "array", "arrays", "stack", "queue", "heap", "bitwise",
    "oop", "linux", "bash", "git", "html", "css", "webpack", "vite", "tailwind",
    "tensorflow", "pytorch", "ml", "llm", "embedding", "embeddings", "vector",
    "datastructure", "datastructures", "binary", "hashing", "iterator", "generator",
    "lambda", "middleware", "framework", "backend", "frontend", "devops", "terraform",
}

# Multi-word technical phrases to catch (checked as substrings).
_TECHNICAL_PHRASES: tuple[str, ...] = (
    "data structure", "big o", "binary search", "linked list", "dynamic programming",
    "machine learning", "time complexity", "space complexity", "design pattern",
    "system design", "rest api", "web development", "software engineering",
)


def is_technical_heuristic(topic: str) -> bool:
    """Fast, offline keyword heuristic. Used as a fallback when no LLM is available."""
    if not topic:
        return False
    low = topic.lower()
    words = set(re.findall(r"[a-z0-9+#]+", low))
    if words & _TECHNICAL_TERMS:
        return True
    return any(phrase in low for phrase in _TECHNICAL_PHRASES)


# Backwards-compatible alias.
is_technical = is_technical_heuristic


# --------------------------------------------------------------------------- #
# LLM-based classification (scalable; heuristic is only a fallback)
# --------------------------------------------------------------------------- #
# Cache results per topic so we classify each topic at most once per process.
_CLASSIFY_CACHE: dict[str, "TopicInfo"] = {}


class TopicInfo:
    """Result of classifying a topic."""

    __slots__ = ("technical", "language")

    def __init__(self, technical: bool, language: str | None = None) -> None:
        self.technical = technical
        self.language = language


async def classify_topic(llm, topic: str) -> TopicInfo:
    """Classify a topic as technical (code-worthy) using the LLM.

    Falls back to the keyword heuristic if the LLM is unavailable or errors.
    ``llm`` is any object with an async ``generate_json(prompt, system=...)``.
    Results are cached per topic.
    """
    # Imported here to avoid a circular import (prompts has no deps on this).
    from app.core.logging import get_logger
    from app.core.prompts import TOPIC_CLASSIFY_SYSTEM, build_topic_classify_prompt

    logger = get_logger(__name__)
    key = (topic or "").strip().lower()
    if key in _CLASSIFY_CACHE:
        return _CLASSIFY_CACHE[key]

    info: TopicInfo
    if llm is None:
        info = TopicInfo(is_technical_heuristic(topic))
    else:
        try:
            data = await llm.generate_json(
                build_topic_classify_prompt(topic), system=TOPIC_CLASSIFY_SYSTEM
            )
            technical = bool(data.get("technical"))
            language = data.get("code_language")
            if not isinstance(language, str) or not language.strip() or language == "null":
                language = None
            info = TopicInfo(technical, language)
            logger.info("Topic '%s' classified technical=%s (%s)", topic, technical,
                        data.get("reason", ""))
        except Exception as exc:  # noqa: BLE001 - fall back to heuristic
            logger.warning("LLM topic classification failed (%s); using heuristic.", exc)
            info = TopicInfo(is_technical_heuristic(topic))

    _CLASSIFY_CACHE[key] = info
    return info
