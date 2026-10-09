# Project Structure

```
youtube-agent/
├── app/
│   ├── main.py                # FastAPI app: lifespan, CORS, routers
│   ├── config.py              # Settings (pydantic-settings) + get_settings()
│   ├── api/
│   │   ├── dependencies.py    # DI wiring: get_llm/get_tts/get_orchestrator
│   │   └── routes/
│   │       ├── health.py      # GET /health
│   │       └── generate.py    # POST /generate, GET /voices
│   ├── core/
│   │   ├── logging.py         # configure_logging / get_logger
│   │   └── prompts.py         # ALL LLM prompt templates live here
│   ├── models/
│   │   └── schemas.py         # Pydantic request/response models
│   ├── services/
│   │   ├── orchestrator.py    # Runs the full pipeline, writes output
│   │   ├── script_service.py  # Script generation
│   │   ├── metadata_service.py# Cross-platform metadata
│   │   ├── llm/               # LLMClient interface + OllamaClient
│   │   ├── tts/               # TTSProvider interface + EdgeTTSProvider
│   │   ├── image/             # ImageProvider ABC + ollama/diffusers/comfyui providers + factory
│   │   ├── thumbnail/         # ThumbnailGenerator interface + PIL impl
│   │   └── video/             # Generic video pipeline (see below)
│   └── utils/
│       └── files.py           # Project folder + file writers
├── video/                     # Remotion app (React+TS) - generic video renderer
│   └── src/
│       ├── Root.tsx           # Composition (calculateMetadata -> any size)
│       ├── compositions/ShortVideo.tsx
│       └── components/        # SceneRenderer + per-type element components + SubtitleOverlay
├── cli.py                     # Terminal entrypoint
├── run.py                     # Uvicorn launcher
├── output/                    # Generated content (gitignored)
└── .kiro/                     # Steering + agents for Kiro
```

## Video pipeline (generic, data-driven)
`app/services/video/`:
- `storyboard_service.py` - LLM turns the script into a generic scene timeline.
- `subtitles.py` - groups edge-tts word timings into karaoke subtitle cues.
- `sfx.py` - generates click/pop/whoosh WAVs (stdlib only).
- `asset_manager.py` - per-scene images via the existing `ImageProvider` (PIL fallback).
- `remotion_renderer.py` - writes `props.json` + runs `npx remotion render`.
- `video_orchestrator.py` - ties script -> TTS(+marks) -> subtitles -> storyboard
  -> assets -> SFX -> render; reuses metadata + thumbnail services.
- `jobs.py` - in-process async job manager (statuses: queued, planning,
  generating_tts, generating_subtitles, generating_assets, rendering,
  completed, failed).

The Remotion renderer only knows element TYPES (text/image/video/code/diagram/
shape) via `SceneRenderer` - so ANY topic renders with no new components.
Dimensions/fps/duration come from the storyboard JSON, so one composition
renders both 1080x1920 and 1920x1080.

## Architectural rules
- **Layering**: `routes -> orchestrator -> services -> providers`. Routes never
  call providers directly; they go through the orchestrator via `dependencies`.
- **Interfaces first**: new capabilities implement an ABC in the relevant
  `services/<capability>/base.py`, then register in `api/dependencies.py`.
- **Prompts live in `core/prompts.py`** — never inline prompt strings in service
  logic.
- **Config lives in `config.py`** — never read `os.environ` directly elsewhere.
- **File writing goes through `utils/files.py`** so output layout stays uniform.

## Output folder contract (per run)
```
output/<YYYY-MM-DD_HHMMSS>_<slug>/
├── script.txt
├── metadata.json
├── thumbnail_concept.json
├── summary.json                 # machine-readable manifest of the run
├── social/
│   ├── youtube.txt              # copy-paste ready
│   ├── instagram.txt
│   ├── linkedin.txt
│   └── title_options.txt
├── audio/
│   └── narration.mp3
└── thumbnails/
    ├── thumbnail_youtube_1280x720.png
    ├── thumbnail_reel_1080x1920.png
    └── thumbnail_square_1080x1080.png
```

## How to extend
- **Add a platform** (e.g. TikTok): extend the metadata prompt + normalizer, then
  add a social file writer in the orchestrator.
- **Swap the LLM**: implement `LLMClient` and change `get_llm()`.
- **New image backend** (e.g. a hosted API, ComfyUI, or Ollama once it re-enables
  image gen): implement `ImageProvider` and register it in
  `app/services/image/__init__.py`'s `build_image_provider()` factory.
- **New TTS engine**: implement `TTSProvider` and change `get_tts()`.
- **New video element type** (e.g. "chart"): add it to `VideoElement` (Python)
  + `types.ts`, add a `<ChartElement>` component, and one `case` in
  `SceneRenderer.tsx`. No topic code, no orchestrator changes.
- **New video style**: add a preset to `VIDEO_STYLES` in `app/models/video.py`
  (name, palette, subtitleStyle...). Select it via the `style` request field.

## Thumbnail pipeline (how backgrounds work)
1. Text LLM writes the concept (headline, accent word, subtext, `image_prompt`).
2. If an `ImageProvider` is enabled, it generates ONE square background from the
   `image_prompt`; the renderer cover-crops it to each format and darkens it with
   a legibility scrim before drawing text.
3. If no provider (or it returns None), a brand gradient background is used.
