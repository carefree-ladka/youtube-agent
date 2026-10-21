"""Build a storyboard from user-supplied scene images.

Lets a creator design full scenes in an external tool (Gemini, Midjourney,
Canva, Figma, a screen recording exported to stills, ...) and drop them into a
folder. When such a folder is provided, the pipeline SKIPS its own storyboard +
asset generation and uses those images as the scenes instead - one full-bleed
image per scene - while still doing narration, timing, subtitles, SFX, and the
final render.

Ordering:
  * If the folder has a ``manifest.json`` it is authoritative (order + optional
    per-scene duration/transition/camera).
  * Otherwise images are used in natural filename order (so ``scene-2`` sorts
    before ``scene-10``).

Timing: scene durations are proportional; the orchestrator's ``retime()`` scales
them to the real narration length, so you do not have to match audio by hand.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from app.core.logging import get_logger
from app.models.video import VideoElement, VideoScene

logger = get_logger(__name__)

# Raster formats Chromium (Remotion) renders directly - no conversion needed.
SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}

_VALID_TRANSITIONS = {"fade", "slide", "zoom", "none"}
_VALID_CAMERAS = {"none", "push-in", "pull-back", "pan-left", "pan-right"}

# Gentle camera moves cycled across scenes when motion is enabled, so a deck of
# static stills still feels alive.
_MOTION_CAMERAS = ("push-in", "pan-right", "pull-back", "pan-left")


@dataclass
class _SceneSpec:
    """One resolved external scene before it is staged/built."""

    path: Path
    duration: float = 4.0
    transition: str = "fade"
    camera: str | None = None  # None -> auto (cycle when motion on, else "none")


def resolve_scenes_dir(raw: str | None, *, project_root: Path) -> Path | None:
    """Resolve a user-provided scenes folder (absolute, ~, or relative)."""
    raw = (raw or "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        # Try the current working directory first, then the project root.
        cwd_candidate = Path.cwd() / path
        path = cwd_candidate if cwd_candidate.exists() else (project_root / path)
    return path


def _natural_key(name: str) -> list:
    """Sort key that orders embedded numbers naturally (scene-2 < scene-10)."""
    return [int(tok) if tok.isdigit() else tok.lower() for tok in re.split(r"(\d+)", name)]


def _load_manifest(scenes_dir: Path) -> list[_SceneSpec] | None:
    """Parse an optional manifest.json into ordered scene specs (or None)."""
    manifest = scenes_dir / "manifest.json"
    if not manifest.is_file():
        return None
    try:
        raw = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Ignoring unreadable scenes manifest %s: %s", manifest, exc)
        return None

    items = raw.get("scenes") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        logger.warning("Scenes manifest has no 'scenes' list; ignoring it.")
        return None

    specs: list[_SceneSpec] = []
    for item in items:
        if isinstance(item, str):
            item = {"file": item}
        if not isinstance(item, dict):
            continue
        filename = str(item.get("file") or item.get("src") or "").strip()
        if not filename:
            continue
        path = (scenes_dir / filename).expanduser()
        if not path.is_absolute():
            path = scenes_dir / filename
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTS:
            logger.warning("Manifest scene file missing/unsupported, skipping: %s", filename)
            continue
        try:
            duration = float(item.get("duration", 4.0) or 4.0)
        except (TypeError, ValueError):
            duration = 4.0
        duration = max(0.8, min(duration, 20.0))
        transition = str(item.get("transition", "fade")).lower()
        if transition not in _VALID_TRANSITIONS:
            transition = "fade"
        camera = item.get("camera")
        camera = str(camera).lower() if camera is not None else None
        if camera is not None and camera not in _VALID_CAMERAS:
            camera = None
        specs.append(_SceneSpec(path=path, duration=duration, transition=transition, camera=camera))
    return specs or None


def _discover(scenes_dir: Path) -> list[_SceneSpec]:
    """Return ordered scene specs from a manifest or natural filename order."""
    manifest_specs = _load_manifest(scenes_dir)
    if manifest_specs:
        logger.info("Using scenes manifest (%d scenes) from %s", len(manifest_specs), scenes_dir)
        return manifest_specs

    files = [
        p
        for p in scenes_dir.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS
    ]
    files.sort(key=lambda p: _natural_key(p.name))
    return [_SceneSpec(path=p) for p in files]


def prepare_external_scenes(
    scenes_dir: Path,
    assets_dir: Path,
    *,
    motion: bool = True,
    fit: str = "cover",
    scrim: bool = True,
) -> list[VideoScene]:
    """Stage external images into the render dir and build full-bleed scenes.

    Copies each image into ``assets_dir`` (the Remotion public dir) under a safe
    sequential name and returns one ``VideoScene`` per image. Returns an empty
    list when the folder has no usable images (caller falls back to normal
    generation).
    """
    if not scenes_dir.is_dir():
        logger.warning("Scene images dir does not exist: %s", scenes_dir)
        return []

    specs = _discover(scenes_dir)
    if not specs:
        logger.warning(
            "No supported images (%s) found in %s",
            ", ".join(sorted(SUPPORTED_EXTS)),
            scenes_dir,
        )
        return []

    assets_dir.mkdir(parents=True, exist_ok=True)
    fit = fit if fit in ("cover", "contain") else "cover"

    scenes: list[VideoScene] = []
    for i, spec in enumerate(specs):
        ext = spec.path.suffix.lower()
        staged_name = f"scene_ext_{i + 1:02d}{ext}"
        try:
            shutil.copyfile(spec.path, assets_dir / staged_name)
        except OSError as exc:
            logger.warning("Could not stage scene image %s: %s", spec.path.name, exc)
            continue

        if spec.camera is not None:
            camera = spec.camera
        elif motion:
            camera = _MOTION_CAMERAS[i % len(_MOTION_CAMERAS)]
        else:
            camera = "none"

        element = VideoElement(
            type="image",
            src=staged_name,
            animation="fade",
            # Style hints the renderer honors: how to fit the frame, whether to
            # apply the slow Ken Burns drift, and whether to darken for captions.
            style={"fit": fit, "motion": motion, "external": True, "scrim": scrim},
        )
        scenes.append(
            VideoScene(
                id=f"scene-{i + 1}",
                duration=spec.duration,
                transition=spec.transition,
                camera=camera,
                elements=[element],
            )
        )

    logger.info("Built %d scene(s) from external images in %s", len(scenes), scenes_dir)
    return scenes
