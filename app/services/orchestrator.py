"""Pipeline orchestrator.

Coordinates the full topic-to-content flow and writes every artifact into a
single, organized project folder:

    output/<timestamp>_<slug>/
        script.txt
        metadata.json
        social/
            youtube.txt
            instagram.txt
            linkedin.txt
        audio/
            narration.mp3
        thumbnails/
            thumbnail_youtube_1280x720.png
            thumbnail_reel_1080x1920.png
            thumbnail_square_1080x1080.png
        thumbnail_concept.json
        summary.json

Each stage is independent and failures are captured as warnings so a partial
run still produces useful output.
"""

from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.core.logging import get_logger
from app.models.schemas import GenerateRequest, GenerateResponse
from app.services.metadata_service import MetadataService
from app.services.script_service import ScriptService
from app.services.thumbnail.base import ThumbnailGenerator
from app.services.tts.base import TTSProvider
from app.utils.files import make_project_dir, write_json, write_text

logger = get_logger(__name__)


class ContentOrchestrator:
    """Runs the end-to-end content generation pipeline."""

    def __init__(
        self,
        *,
        settings: Settings,
        script_service: ScriptService,
        metadata_service: MetadataService,
        tts_provider: TTSProvider,
        thumbnail_generator: ThumbnailGenerator,
    ) -> None:
        self._settings = settings
        self._scripts = script_service
        self._metadata = metadata_service
        self._tts = tts_provider
        self._thumbnails = thumbnail_generator

    async def run(self, request: GenerateRequest) -> GenerateResponse:
        """Execute the pipeline for a single topic and return artifact paths."""
        warnings: list[str] = []
        project_dir = make_project_dir(self._settings.output_path, request.topic)
        logger.info("=== Starting run for '%s' -> %s", request.topic, project_dir.name)

        if request.is_short:
            logger.info("Content type: SHORT reel (~%ds)", request.target_seconds)

        # 1) Script (required foundation for the rest of the run).
        script = await self._scripts.generate(
            request.topic,
            content_type=request.content_type,
            tone=request.tone,
            audience=request.audience,
            target_minutes=request.target_minutes,
            target_seconds=request.target_seconds,
            language=request.language,
        )
        script_path = write_text(project_dir / "script.txt", script)

        # 2) Metadata (optional).
        metadata: dict | None = None
        metadata_path: Path | None = None
        title = request.topic
        if request.generate_metadata:
            try:
                metadata = await self._metadata.generate(
                    request.topic,
                    script,
                    language=request.language,
                    content_type=request.content_type,
                )
                title = metadata["youtube"].get("title") or title
                metadata_path = write_json(project_dir / "metadata.json", metadata)
                self._write_social_files(project_dir, metadata)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Metadata generation failed")
                warnings.append(f"Metadata generation failed: {exc}")

        # 3) Audio narration (optional).
        audio_path: Path | None = None
        if request.generate_audio:
            try:
                audio_path = await self._tts.synthesize(
                    script, project_dir / "audio" / "narration.mp3"
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Audio synthesis failed")
                warnings.append(f"Audio synthesis failed: {exc}")

        # 4) Thumbnails (optional).
        thumbnail_paths: list[Path] = []
        if request.generate_thumbnails:
            try:
                concept = await self._thumbnails.generate_concept(request.topic, title)
                write_json(project_dir / "thumbnail_concept.json", concept)
                # Optional AI background (diffusers); None falls back to gradient.
                background = await self._thumbnails.generate_background(concept)
                thumbnail_paths = self._thumbnails.render(
                    concept, project_dir / "thumbnails", background=background
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Thumbnail generation failed")
                warnings.append(f"Thumbnail generation failed: {exc}")

        response = GenerateResponse(
            topic=request.topic,
            project_dir=str(project_dir),
            title=title,
            script_path=str(script_path),
            audio_path=str(audio_path) if audio_path else None,
            metadata_path=str(metadata_path) if metadata_path else None,
            thumbnail_paths=[str(p) for p in thumbnail_paths],
            metadata=metadata,
            warnings=warnings,
        )

        # A machine-readable manifest of the whole run.
        write_json(project_dir / "summary.json", response.model_dump())
        logger.info("=== Completed run for '%s' (%d warnings)", request.topic, len(warnings))
        return response

    @staticmethod
    def _write_social_files(project_dir: Path, metadata: dict) -> None:
        """Write human-friendly, copy-paste-ready social files per platform."""
        social_dir = project_dir / "social"

        yt = metadata.get("youtube", {})
        yt_text = (
            f"TITLE:\n{yt.get('title', '')}\n\n"
            f"DESCRIPTION:\n{yt.get('description', '')}\n\n"
            f"TAGS:\n{', '.join(yt.get('tags', []))}\n\n"
            f"HASHTAGS:\n{' '.join(yt.get('hashtags', []))}\n\n"
            f"CHAPTERS:\n" + "\n".join(yt.get("chapters", []))
        )
        write_text(social_dir / "youtube.txt", yt_text)

        ig = metadata.get("instagram", {})
        ig_text = (
            f"CAPTION:\n{ig.get('caption', '')}\n\n"
            f"HASHTAGS:\n{' '.join(ig.get('hashtags', []))}"
        )
        write_text(social_dir / "instagram.txt", ig_text)

        li = metadata.get("linkedin", {})
        li_text = (
            f"POST:\n{li.get('post', '')}\n\n"
            f"HASHTAGS:\n{' '.join(li.get('hashtags', []))}"
        )
        write_text(social_dir / "linkedin.txt", li_text)

        titles = metadata.get("titles", [])
        if titles:
            write_text(
                social_dir / "title_options.txt",
                "\n".join(f"{i + 1}. {t}" for i, t in enumerate(titles)),
            )
