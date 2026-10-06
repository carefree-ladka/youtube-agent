"""Command-line interface for the YouTube Agent.

Generate a full content package straight from the terminal, no server needed:

    python cli.py "How compound interest builds wealth"
    python cli.py "Topic" --minutes 8 --tone "calm and educational" --no-audio
    python cli.py "3 git tricks pros use" --reel --seconds 30

Useful for scripting and for running the agent from Kiro tasks.
"""

from __future__ import annotations

import argparse
import asyncio

from app.api.dependencies import get_orchestrator
from app.config import get_settings
from app.core.logging import configure_logging
from app.models.schemas import GenerateRequest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a YouTube content package from a topic.")
    parser.add_argument("topic", help="The video topic or idea.")
    parser.add_argument(
        "--reel",
        action="store_true",
        help="Short-form mode: a punchy vertical Reel / YouTube Short script.",
    )
    parser.add_argument("--minutes", type=int, default=5, help="Target length for long videos (1-30).")
    parser.add_argument("--seconds", type=int, default=40, help="Target length for reels (10-180).")
    parser.add_argument("--tone", default="engaging and friendly", help="Narration tone.")
    parser.add_argument("--audience", default="a general YouTube audience", help="Target audience.")
    parser.add_argument("--language", default="English", help="Output language.")
    parser.add_argument("--no-audio", action="store_true", help="Skip TTS audio generation.")
    parser.add_argument("--no-thumbnails", action="store_true", help="Skip thumbnail generation.")
    parser.add_argument("--no-metadata", action="store_true", help="Skip metadata generation.")
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> None:
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


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    args = _parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
