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
from app.services.web.research_service import ResearchBrief, ResearchService
from app.utils.files import make_project_dir, write_json, write_social_files, write_text

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
        research_service: "ResearchService | None" = None,
    ) -> None:
        self._settings = settings
        self._scripts = script_service
        self._metadata = metadata_service
        self._tts = tts_provider
        self._thumbnails = thumbnail_generator
        self._research = research_service

    async def run(self, request: GenerateRequest) -> GenerateResponse:
        """Execute the pipeline for a single topic and return artifact paths."""
        warnings: list[str] = []
        project_dir = make_project_dir(self._settings.output_path, request.topic)
        logger.info("=== Starting run for '%s' -> %s", request.topic, project_dir.name)

        if request.is_short:
            logger.info("Content type: SHORT reel (~%ds)", request.target_seconds)

        # 0) Optional web research to ground the script in real facts (skipped
        #    when the caller supplies their own script).
        brief = ResearchBrief()
        custom_script = (request.script or "").strip()
        if not custom_script and self._settings.web_enrich and self._research is not None:
            try:
                brief = await self._research.research(request.topic)
            except Exception as exc:  # noqa: BLE001 - enrichment is optional
                logger.warning("Web enrichment failed: %s", exc)
                warnings.append(f"Web enrichment failed: {exc}")

        # 1) Script (required foundation for the rest of the run).
        if custom_script:
            logger.info("Using user-provided script (%d chars); skipping generation.", len(custom_script))
            script = custom_script
        else:
            script = await self._scripts.generate(
                request.topic,
                content_type=request.content_type,
                tone=request.tone,
                audience=request.audience,
                target_minutes=request.target_minutes,
                target_seconds=request.target_seconds,
                language=request.language,
                research=brief.as_prompt_block(),
            )
        script_path = write_text(project_dir / "script.txt", script)
        if brief.sources:
            write_json(
                project_dir / "credits.json",
                {
                    "topic": request.topic,
                    "note": "Research sources used to ground the script.",
                    "research_sources": [{"title": s.title, "url": s.url} for s in brief.sources],
                },
            )

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
                write_social_files(project_dir, metadata)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Metadata generation failed")
                warnings.append(f"Metadata generation failed: {exc}")

        # 3) Audio narration (optional).
        audio_path: Path | None = None
        if request.generate_audio:
            try:
                audio_path = await self._tts.synthesize(
                    script, project_dir / "audio" / "narration.mp3",
                    content_type=request.content_type,
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
