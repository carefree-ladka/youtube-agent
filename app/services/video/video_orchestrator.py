"""End-to-end video generation pipeline.

ONE TOPIC IN -> script, (reused) metadata + thumbnail, TTS with word timings,
synced subtitles, a generic storyboard, generated visual assets, SFX, and a
final MP4 (portrait 1080x1920 or landscape 1920x1080) with burned-in,
karaoke-highlighted subtitles.

Every stage is generic and data-driven; no topic-specific code anywhere.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

from app.config import PROJECT_ROOT, Settings
from app.core.logging import get_logger
from app.core.topics import classify_topic
from app.models.schemas import VideoJobStatus, VideoRequest, VideoResult
from app.models.video import (
    ORIENTATION_SIZES,
    VideoStoryboard,
    get_style,
    orientation_for,
    palette_for_topic,
)
from app.services.llm.base import LLMClient
from app.services.metadata_service import MetadataService
from app.services.script_service import ScriptService
from app.services.thumbnail.base import ThumbnailGenerator
from app.services.tts.base import TTSProvider
from app.services.video.asset_manager import AssetManager
from app.services.video.external_scenes import prepare_external_scenes, resolve_scenes_dir
from app.services.video.music import prepare_music
from app.services.video.remotion_renderer import RemotionRenderer
from app.services.video.sfx import generate_sfx
from app.services.video.storyboard_service import StoryboardService
from app.services.video.subtitles import build_subtitles, estimate_subtitles
from app.services.video.svg_service import SvgService
from app.services.web.research_service import ResearchBrief, ResearchService
from app.utils.files import (
    audio_duration_seconds,
    make_project_dir,
    slug_filename,
    write_json,
    write_social_files,
    write_text,
)

logger = get_logger(__name__)

ProgressCallback = Callable[[VideoJobStatus], None]

# Average speaking rate used only when word timings are unavailable.
_WORDS_PER_SECOND = 2.6


class VideoOrchestrator:
    """Runs the full topic-to-video pipeline."""

    def __init__(
        self,
        *,
        settings: Settings,
        script_service: ScriptService,
        storyboard_service: StoryboardService,
        asset_manager: AssetManager,
        tts_provider: TTSProvider,
        renderer: RemotionRenderer,
        llm: LLMClient | None = None,
        svg_service: SvgService | None = None,
        metadata_service: MetadataService | None = None,
        thumbnail_generator: ThumbnailGenerator | None = None,
        research_service: "ResearchService | None" = None,
    ) -> None:
        self._settings = settings
        self._scripts = script_service
        self._storyboards = storyboard_service
        self._assets = asset_manager
        self._svg = svg_service
        self._tts = tts_provider
        self._renderer = renderer
        self._llm = llm
        self._metadata = metadata_service
        self._thumbnails = thumbnail_generator
        self._research = research_service

    async def run(
        self, request: VideoRequest, progress: ProgressCallback | None = None
    ) -> VideoResult:
        """Execute the pipeline, reporting coarse status via ``progress``."""

        def report(status: VideoJobStatus) -> None:
            if progress:
                progress(status)

        warnings: list[str] = []
        orientation = orientation_for(
            request.content_type, None if request.orientation == "auto" else request.orientation
        )
        project_dir = make_project_dir(self._settings.output_path, request.topic)
        assets_dir = project_dir / "video_assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        logger.info(
            "=== Video run for '%s' (%s) -> %s", request.topic, orientation, project_dir.name
        )

        target_seconds = (
            request.target_seconds if request.is_short else request.target_minutes * 60
        )

        # 0) Classify the topic ONCE (LLM-based, heuristic fallback) and reuse it.
        report("planning")
        info = await classify_topic(self._llm, request.topic)
        logger.info("Topic technical=%s for '%s'", info.technical, request.topic)

        # 0b) Optional web research: grounds the script + on-screen facts in REAL
        #     information and provides real image subjects. Best-effort. Skipped
        #     when the caller supplies their own script.
        brief = ResearchBrief()
        custom_script = (request.script or "").strip()
        if not custom_script and self._settings.web_enrich and self._research is not None:
            try:
                brief = await self._research.research(request.topic)
            except Exception as exc:  # noqa: BLE001 - enrichment is optional
                logger.warning("Web enrichment failed: %s", exc)
                warnings.append(f"Web enrichment failed: {exc}")
        research_block = brief.as_prompt_block()

        # 1) Script + storyboard -------------------------------------------------
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
                technical=info.technical,
                research=research_block,
            )
        script_path = write_text(project_dir / "script.txt", script)

        # Bring-your-own visuals: if a scene-images folder is configured (per
        # request or via VIDEO_SCENES_DIR), use those images as the scenes and
        # SKIP the storyboard LLM + asset generation entirely.
        scenes_dir = resolve_scenes_dir(
            request.scene_images_dir or self._settings.video_scenes_dir,
            project_root=PROJECT_ROOT,
        )
        external_scenes = []
        if scenes_dir is not None:
            external_scenes = prepare_external_scenes(
                scenes_dir,
                assets_dir,
                motion=request.scene_motion,
                fit=request.scene_fit,
                scrim=request.burn_subtitles,
            )
            if not external_scenes:
                warnings.append(
                    f"No usable scene images in {scenes_dir}; generated scenes instead."
                )

        if external_scenes:
            logger.info(
                "Using %d external scene image(s) from %s (skipping storyboard + asset gen)",
                len(external_scenes), scenes_dir,
            )
            width, height = ORIENTATION_SIZES.get(orientation, ORIENTATION_SIZES["portrait"])
            storyboard = VideoStoryboard(
                width=width,
                height=height,
                fps=request.fps,
                orientation=orientation,  # type: ignore[arg-type]
                scenes=external_scenes,
                style=get_style(request.style),
                title=request.topic,
            )
        else:
            storyboard = await self._storyboards.generate(
                request.topic,
                script,
                orientation=orientation,
                target_seconds=target_seconds,
                style_name=request.style,
                language=request.language,
                fps=request.fps,
                technical=info.technical,
                research=research_block,
                image_queries=brief.image_queries,
            )

        # Theme the video by topic so different topics look different (unless the
        # user picked a specific non-default style preset).
        if request.style.strip().lower() in ("", "modern-tech", "auto"):
            palette, accent = palette_for_topic(request.topic)
            storyboard.style.palette = palette
            storyboard.style.accentColor = accent

        # Companion package (best-effort, reuses existing services) -------------
        title = request.topic
        metadata_path: Path | None = None
        if request.generate_metadata and self._metadata is not None:
            try:
                metadata = await self._metadata.generate(
                    request.topic, script, language=request.language,
                    content_type=request.content_type,
                )
                title = metadata["youtube"].get("title") or title
                metadata_path = write_json(project_dir / "metadata.json", metadata)
                # Copy-paste-ready, quote-free social files (youtube/instagram/
                # linkedin + standalone tags.txt / keywords.txt).
                write_social_files(project_dir, metadata)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Metadata generation failed")
                warnings.append(f"Metadata generation failed: {exc}")

        thumbnail_paths: list[Path] = []
        if request.generate_thumbnails and self._thumbnails is not None:
            try:
                concept = await self._thumbnails.generate_concept(request.topic, title)
                write_json(project_dir / "thumbnail_concept.json", concept)
                background = await self._thumbnails.generate_background(concept)
                thumbnail_paths = self._thumbnails.render(
                    concept, project_dir / "thumbnails", background=background
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Thumbnail generation failed")
                warnings.append(f"Thumbnail generation failed: {exc}")

        # 2) TTS with word timings ----------------------------------------------
        report("generating_tts")
        # Providers may write a different container (e.g. F5-TTS -> .wav) and
        # return the ACTUAL path, so we always use what the provider gives back.
        audio_path = project_dir / "audio" / "narration.mp3"
        marks: list = []
        try:
            audio_path, marks = await self._tts.synthesize_timed(
                script, audio_path, language=request.language, content_type=request.content_type
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Timed TTS failed; retrying plain synth")
            warnings.append(f"Timed TTS failed, used plain audio: {exc}")
            audio_path = await self._tts.synthesize(
                script, audio_path, content_type=request.content_type
            )

        if marks:
            audio_duration = max(m.end for m in marks)
        else:
            # No word marks (e.g. a voice-cloning provider): prefer the REAL file
            # duration over a word-count guess so scenes/subtitles stay in sync.
            audio_duration = audio_duration_seconds(audio_path) or max(
                len(script.split()) / _WORDS_PER_SECOND, 1.0
            )

        # 3) Subtitles -----------------------------------------------------------
        report("generating_subtitles")
        subtitles = (
            build_subtitles(
                marks,
                max_words=storyboard.style.subtitleStyle.maxWordsPerCue,
                max_chars=storyboard.style.subtitleStyle.maxCharsPerLine,
            )
            if marks
            else estimate_subtitles(script, audio_duration)
        )
        subtitles_path = write_json(
            project_dir / "subtitles.json", [s.model_dump() for s in subtitles]
        )

        # Align scene timing to the real narration length.
        StoryboardService.retime(storyboard, audio_duration)

        # 4) Assets + SFX + audio into the Remotion public dir ------------------
        report("generating_assets")
        # Topic-specific inline SVG visuals (illustrations / mock screens /
        # diagrams) so every scene looks different; falls back to a designed SVG.
        if self._svg is not None and not external_scenes:
            try:
                await self._svg.generate(
                    storyboard, topic=request.topic, language=request.language
                )
            except Exception as exc:  # noqa: BLE001 - visuals are best-effort
                logger.exception("SVG asset generation failed")
                warnings.append(f"SVG asset generation failed: {exc}")
        image_credits = await self._assets.generate(storyboard, assets_dir)
        sfx = generate_sfx(assets_dir)
        # Soft, slow background-music bed (generated pad or user's VIDEO_MUSIC).
        music_src = prepare_music(
            assets_dir,
            enabled=self._settings.video_music_enabled,
            music_path=self._settings.video_music,
        )

        # Attribution: record image sources + research sources (CC licensing duty).
        if image_credits or brief.sources:
            credits = {
                "topic": request.topic,
                "note": "Verify each image's license + attribution before publishing.",
                "images": image_credits,
                "research_sources": [{"title": s.title, "url": s.url} for s in brief.sources],
            }
            write_json(project_dir / "credits.json", credits)
            if image_credits:
                logger.info("Wrote credits.json (%d image sources)", len(image_credits))
        # Stage the narration into the Remotion public dir under its real name
        # (keeps the correct extension, e.g. .wav for F5-TTS or .mp3 for edge).
        audio_name = audio_path.name
        try:
            shutil.copyfile(audio_path, assets_dir / audio_name)
        except OSError as exc:
            warnings.append(f"Could not stage narration audio: {exc}")

        storyboard.audioSrc = audio_name
        storyboard.musicSrc = music_src
        storyboard.style.sfxVolume = self._settings.video_sfx_volume
        storyboard.style.musicVolume = self._settings.video_music_volume
        storyboard.subtitles = subtitles if request.burn_subtitles else []
        storyboard.sfx = sfx
        storyboard.title = title
        storyboard_path = write_json(project_dir / "storyboard.json", storyboard.model_dump())

        # 5) Render --------------------------------------------------------------
        report("rendering")
        # Name the file after the (title or topic) so outputs are easy to find,
        # e.g. "javascript-closures-explained.mp4" instead of "final.mp4".
        video_filename = slug_filename(title or request.topic, ".mp4", fallback="video")
        video_path: Path | None = None
        try:
            video_path = await self._renderer.render(
                storyboard,
                public_dir=assets_dir,
                output_path=project_dir / video_filename,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Video render failed")
            warnings.append(f"Video render failed: {exc}")

        result = VideoResult(
            topic=request.topic,
            title=title,
            project_dir=str(project_dir),
            orientation=orientation,
            width=storyboard.width,
            height=storyboard.height,
            duration=storyboard.duration,
            script_path=str(script_path),
            audio_path=str(audio_path) if audio_path else None,
            subtitles_path=str(subtitles_path),
            storyboard_path=str(storyboard_path),
            video_path=str(video_path) if video_path else None,
            metadata_path=str(metadata_path) if metadata_path else None,
            thumbnail_paths=[str(p) for p in thumbnail_paths],
            warnings=warnings,
        )
        write_json(project_dir / "video_summary.json", result.model_dump())
        logger.info(
            "=== Video run complete for '%s' (video=%s, %d warnings)",
            request.topic,
            "yes" if video_path else "no",
            len(warnings),
        )
        return result
