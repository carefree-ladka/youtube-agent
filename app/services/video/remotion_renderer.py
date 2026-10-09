"""Invoke the Remotion renderer (Node/TypeScript) as a subprocess.

The Python pipeline produces a fully-resolved ``VideoStoryboard`` (scenes with
asset filenames, narration audio, subtitles, SFX, style, dimensions). This
module serializes it to ``props.json`` and calls the Remotion CLI to render the
final MP4. The Remotion composition reads the dimensions/fps/duration from the
props via ``calculateMetadata``, so the SAME composition renders both 1080x1920
and 1920x1080 without any code changes.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.config import PROJECT_ROOT
from app.core.logging import get_logger
from app.models.video import VideoStoryboard

logger = get_logger(__name__)

VIDEO_APP_DIR = PROJECT_ROOT / "video"
_ENTRY = "src/index.ts"
_COMPOSITION_ID = "ShortVideo"


class RemotionError(RuntimeError):
    """Raised when the Remotion render fails or its environment is missing."""


class RemotionRenderer:
    """Renders a storyboard to MP4 using the local Remotion project."""

    def __init__(self, *, timeout: float = 1800.0, concurrency: int | None = None) -> None:
        self._timeout = timeout
        self._concurrency = concurrency

    def is_available(self) -> bool:
        """True if the Remotion app and its dependencies are installed."""
        return (VIDEO_APP_DIR / "node_modules").is_dir() and (VIDEO_APP_DIR / _ENTRY).is_file()

    async def render(
        self,
        storyboard: VideoStoryboard,
        *,
        public_dir: Path,
        output_path: Path,
    ) -> Path:
        """Render ``storyboard`` to ``output_path`` and return it."""
        if not (VIDEO_APP_DIR / _ENTRY).is_file():
            raise RemotionError(
                f"Remotion entry not found at {VIDEO_APP_DIR / _ENTRY}. "
                "The 'video/' app is missing."
            )
        if not (VIDEO_APP_DIR / "node_modules").is_dir():
            raise RemotionError(
                "Remotion dependencies are not installed. Run:\n"
                f"    cd {VIDEO_APP_DIR} && npm install"
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        props_path = public_dir / "props.json"
        props_path.write_text(
            json.dumps(storyboard.model_dump(), ensure_ascii=False), encoding="utf-8"
        )

        cmd = [
            "npx",
            "remotion",
            "render",
            _ENTRY,
            _COMPOSITION_ID,
            str(output_path),
            f"--props={props_path}",
            f"--public-dir={public_dir}",
            "--log=error",
        ]
        if self._concurrency:
            cmd.append(f"--concurrency={self._concurrency}")

        logger.info("Rendering video via Remotion -> %s", output_path.name)
        logger.debug("Remotion cmd: %s (cwd=%s)", " ".join(cmd), VIDEO_APP_DIR)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(VIDEO_APP_DIR),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=self._timeout)
        except asyncio.TimeoutError as exc:
            with _suppress():
                proc.kill()
            raise RemotionError(f"Remotion render timed out after {self._timeout:.0f}s") from exc
        except FileNotFoundError as exc:
            raise RemotionError(
                "`npx` not found. Install Node.js (https://nodejs.org) to render video."
            ) from exc

        output = (stdout or b"").decode("utf-8", errors="replace")
        if proc.returncode != 0:
            tail = "\n".join(output.strip().splitlines()[-25:])
            raise RemotionError(f"Remotion render failed (exit {proc.returncode}):\n{tail}")

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RemotionError("Remotion reported success but no output file was produced.")

        logger.info("Video rendered: %s (%d bytes)", output_path, output_path.stat().st_size)
        return output_path


class _suppress:
    """Tiny context manager to ignore cleanup errors."""

    def __enter__(self) -> None:
        return None

    def __exit__(self, *exc: object) -> bool:
        return True
