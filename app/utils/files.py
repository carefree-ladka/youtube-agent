"""Filesystem helpers for creating and writing organized project output."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from slugify import slugify


def make_project_dir(output_root: Path, topic: str) -> Path:
    """Create a unique, human-readable project directory for a run.

    Layout example: ``output/2026-09-20_143012_how-to-invest``
    """
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    slug = slugify(topic)[:60] or "untitled"
    project_dir = output_root / f"{stamp}_{slug}"
    (project_dir / "thumbnails").mkdir(parents=True, exist_ok=True)
    (project_dir / "audio").mkdir(parents=True, exist_ok=True)
    return project_dir


def write_text(path: Path, content: str) -> Path:
    """Write UTF-8 text, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def write_json(path: Path, data: Any) -> Path:
    """Write pretty-printed JSON, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path
