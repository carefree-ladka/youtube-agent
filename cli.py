"""Command-line interface for the YouTube Agent.

Generate a full content package straight from the terminal, no server needed:

    python cli.py "How compound interest builds wealth"
    python cli.py "Topic" --minutes 8 --tone "calm and educational" --no-audio
    python cli.py "3 git tricks pros use" --reel --seconds 30

Add --video to ALSO render a complete MP4 (Short/Reel or long-form) with
burned-in karaoke subtitles, animated visuals, and SFX:

    python cli.py "How closures work in JavaScript" --video --reel --seconds 40
    python cli.py "What is Docker?" --video --minutes 2            # landscape 1920x1080

Useful for scripting and for running the agent from Kiro tasks.
"""

from __future__ import annotations

import argparse
import asyncio

# Ensure we're running under the project's virtualenv (re-execs if needed)
# BEFORE importing anything that depends on third-party packages.
from app.bootstrap import ensure_venv

ensure_venv()

from app.api.dependencies import get_orchestrator, get_video_orchestrator  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402
from app.models.schemas import GenerateRequest, VideoRequest  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a YouTube content package from a topic.")
    parser.add_argument("topic", help="The video topic or idea.")
    parser.add_argument(
        "--reel",
        action="store_true",
        help="Short-form mode: a punchy vertical Reel / YouTube Short script.",
    )
    parser.add_argument(
        "--video",
        action="store_true",
        help="Also render a full MP4 video (storyboard + subtitles + Remotion).",
    )
    parser.add_argument(
        "--orientation",
        choices=["auto", "portrait", "landscape"],
        default="auto",
        help="Video orientation (default: auto -> portrait for --reel, else landscape).",
    )
    parser.add_argument("--style", default="modern-tech", help="Video visual style preset.")
    parser.add_argument("--minutes", type=int, default=5, help="Target length for long videos (1-30).")
    parser.add_argument("--seconds", type=int, default=40, help="Target length for reels (10-180).")
    parser.add_argument("--tone", default="engaging and friendly", help="Narration tone.")
    parser.add_argument("--audience", default="a general YouTube audience", help="Target audience.")
    parser.add_argument("--language", default="English", help="Output language.")
    parser.add_argument("--no-audio", action="store_true", help="Skip TTS audio generation.")
    parser.add_argument("--no-thumbnails", action="store_true", help="Skip thumbnail generation.")
    parser.add_argument("--no-metadata", action="store_true", help="Skip metadata generation.")
    return parser.parse_args()


async def _run_video(args: argparse.Namespace) -> None:
    """Run the full video pipeline (also produces metadata + thumbnail)."""
    request = VideoRequest(
        topic=args.topic,
        content_type="short" if args.reel else "long",
        orientation=args.orientation,
        tone=args.tone,
        audience=args.audience,
        target_minutes=args.minutes,
        target_seconds=args.seconds,
        language=args.language,
        style=args.style,
        generate_metadata=not args.no_metadata,
        generate_thumbnails=not args.no_thumbnails,
    )
    orchestrator = get_video_orchestrator()
    result = await orchestrator.run(request, progress=lambda s: print(f"  … {s}", flush=True))

    print("\n" + "=" * 60)
    print(f"  DONE (Video, {result.orientation} {result.width}x{result.height}): {result.title}")
    print("=" * 60)
    print(f"  Project folder : {result.project_dir}")
    print(f"  Script         : {result.script_path}")
    print(f"  Audio          : {result.audio_path or '(skipped)'}")
    print(f"  Subtitles      : {result.subtitles_path or '(none)'}")
    print(f"  Storyboard     : {result.storyboard_path or '(none)'}")
    print(f"  Metadata       : {result.metadata_path or '(skipped)'}")
    print(f"  Thumbnails     : {len(result.thumbnail_paths)} file(s)")
    print(f"  VIDEO          : {result.video_path or '(FAILED - see warnings)'}")
    if result.warnings:
        print("\n  WARNINGS:")
        for warning in result.warnings:
            print(f"    ! {warning}")
    print("=" * 60 + "\n")


async def _run_package(args: argparse.Namespace) -> None:
    """Run the content package pipeline (no video render)."""
    request = GenerateRequest(
        topic=args.topic,
        content_type="short" if args.reel else "long",
        tone=args.tone,
        audience=args.audience,
        target_minutes=args.minutes,
        target_seconds=args.seconds,
        language=args.language,
        generate_audio=not args.no_audio,
        generate_thumbnails=not args.no_thumbnails,
        generate_metadata=not args.no_metadata,
    )
    orchestrator = get_orchestrator()
    result = await orchestrator.run(request)

    mode = "SHORT / Reel" if args.reel else "Long video"
    print("\n" + "=" * 60)
    print(f"  DONE ({mode}): {result.title}")
    print("=" * 60)
    print(f"  Project folder : {result.project_dir}")
    print(f"  Script         : {result.script_path}")
    print(f"  Audio          : {result.audio_path or '(skipped)'}")
    print(f"  Metadata       : {result.metadata_path or '(skipped)'}")
    print(f"  Thumbnails     : {len(result.thumbnail_paths)} file(s)")
    for path in result.thumbnail_paths:
        print(f"                   - {path}")
    if result.warnings:
        print("\n  WARNINGS:")
        for warning in result.warnings:
            print(f"    ! {warning}")
    print("=" * 60 + "\n")


async def _run(args: argparse.Namespace) -> None:
    if args.video:
        await _run_video(args)
    else:
        await _run_package(args)


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    args = _parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
