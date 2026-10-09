# 🎬 YouTube Agent

Turn a single **topic** into a complete, publish-ready content package:

- 📝 **Narration script** written for smooth text-to-speech delivery
- 🔊 **Audio** narration (MP3) using natural neural voices (free, via edge-tts)
- 🏷️ **Cross-platform metadata**: catchy titles, SEO descriptions, tags, and
  hashtags for **YouTube**, **Instagram**, and **LinkedIn**
- 🖼️ **Thumbnails** in three formats: YouTube 16:9, Reel/Story 9:16, square 1:1,
  with optional **AI-generated backgrounds** (local Stable Diffusion / FLUX)

Everything for one run is written into a single, timestamped folder under
`output/`. Built with **FastAPI** and powered by local **Ollama** models.

---

## ✨ Why it's built this way
- **Local-first & free** — text and creative work run on your local Ollama
  models; TTS uses free neural voices. No paid API keys required.
- **Pluggable & scalable** — LLM, TTS, and thumbnail engines each sit behind an
  interface, so you can swap providers without touching the pipeline.
- **Partial success over failure** — if one stage fails, the run still produces
  the script and everything else that succeeded, recording issues as warnings.

---

## 🚀 Quick start

### 1. Prerequisites
- Python 3.10+
- [Ollama](https://ollama.com) installed and running
- Internet access (edge-tts voices are served online)

```bash
# Start Ollama and pull a model
ollama serve            # in one terminal (if not already running)
ollama pull llama3.1    # the default text model
```

### 2. Install
```bash
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                # then tweak values if you like
```

Optional — enable AI-generated thumbnail backgrounds (local, no API keys):
```bash
pip install -r requirements-image.txt   # torch, diffusers, transformers (large)
# in .env set: IMAGE_BACKEND=diffusers
```
The first generation downloads the model (several GB) to `~/.cache/huggingface`.
On Apple Silicon it runs on the MPS GPU automatically. Set `IMAGE_BACKEND=none`
to skip AI images and use the built-in gradient background.

### 3. Generate content

**From the CLI (simplest):**
```bash
python cli.py "How compound interest builds wealth" --minutes 6
```
Fast check that only exercises the LLM (skips audio + thumbnails):
```bash
python cli.py "Your topic" --no-audio --no-thumbnails
```

**From the API:**
```bash
python run.py
# open http://localhost:8000/docs
```
```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"topic": "The science of good sleep", "target_minutes": 5}'
```

---

## 📁 Output layout
Each run creates:
```
output/2026-09-20_143012_the-science-of-good-sleep/
├── script.txt
├── metadata.json
├── thumbnail_concept.json
├── summary.json              # manifest of the whole run + warnings
├── social/
│   ├── youtube.txt           # copy-paste ready
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

---

## ⚙️ Configuration (`.env`)
| Variable | Purpose | Default |
|---|---|---|
| `OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` |
| `OLLAMA_TEXT_MODEL` | Model for scripts + metadata | `llama3.1` |
| `OLLAMA_IMAGE_MODEL` | Model for thumbnail concepts | `llama3.1` |
| `TTS_VOICE` | edge-tts voice | `en-US-JennyNeural` |
| `TTS_RATE` / `TTS_PITCH` / `TTS_VOLUME` | Voice delivery tuning | `+0%` / `+0Hz` / `+0%` |
| `OUTPUT_DIR` | Where runs are written | `output` |
| `BRAND_NAME` | Text drawn on thumbnails | `YourChannel` |
| `BRAND_PRIMARY_COLOR` / `BRAND_SECONDARY_COLOR` / `BRAND_TEXT_COLOR` | Thumbnail palette | red / dark / white |
| `IMAGE_BACKEND` | `diffusers` for AI backgrounds, or `none` for gradient | `none` |
| `DIFFUSERS_MODEL` | HF text-to-image model | `stabilityai/sdxl-turbo` |
| `DIFFUSERS_DEVICE` | `auto` / `mps` / `cuda` / `cpu` | `auto` |
| `DIFFUSERS_STEPS` / `DIFFUSERS_GUIDANCE` | Inference steps / guidance | `4` / `0.0` |
| `THUMBNAIL_OVERLAY_OPACITY` | Darkening scrim over AI images (0-255) | `110` |

### Choosing an image model (diffusers backend)
- `stabilityai/sdxl-turbo` — recommended on Mac: fast, good quality, 1-4 steps.
- `stabilityai/sd-turbo` — smaller/faster, lower detail.
- `black-forest-labs/FLUX.1-schnell` — higher quality + text; large and slower on
  Mac. For FLUX set `DIFFUSERS_STEPS=4`, `DIFFUSERS_GUIDANCE=0.0`.

### ComfyUI backend (`IMAGE_BACKEND=comfyui`)
Generates backgrounds by calling a running ComfyUI server over its HTTP API
(`/prompt` → `/history` → `/view`). The agent never bundles ComfyUI; you run it
separately and point `COMFYUI_BASE_URL` at it.

1. Run ComfyUI and note the URL (default `http://localhost:8188`).
   - **macOS**: run it **natively** so it uses the Apple GPU (MPS). Docker
     Desktop on macOS can't access the GPU, so a container would be CPU-only and
     very slow. The [Comfy-Org/ComfyUI](https://github.com/comfy-org/comfyui)
     repo has **no Dockerfile** — use the desktop app / manual install on Mac.
   - **Linux + NVIDIA**: a community Docker image with `--gpus all` works well.
2. Put a checkpoint in `ComfyUI/models/checkpoints/` (e.g. an SDXL checkpoint)
   and set `COMFYUI_CHECKPOINT` to that exact filename.
3. In `.env`: `IMAGE_BACKEND=comfyui`. Tune `COMFYUI_STEPS`, `COMFYUI_CFG`,
   `COMFYUI_SAMPLER`, `COMFYUI_SIZE`.
4. Advanced: export any workflow from the ComfyUI UI in **API format**, save it,
   and set `COMFYUI_WORKFLOW=/path/to/workflow.json`. Use placeholders
   `%POSITIVE% %NEGATIVE% %WIDTH% %HEIGHT% %SEED% %CKPT% %STEPS% %CFG%` where you
   want the agent to inject values (great for FLUX / Qwen-Image graphs).

As with every backend, ComfyUI only paints the **text-free background**; PIL
draws the crisp headline on top. If the server is unreachable, the agent falls
back to the designed gradient/shape background automatically.

### Picking a smooth voice
```bash
edge-tts --list-voices          # or GET /voices when the server is running
```
Great natural voices: `en-US-JennyNeural`, `en-US-AriaNeural`,
`en-US-GuyNeural`, `en-GB-SoniaNeural`, `en-US-AndrewMultilingualNeural`.

---

## 🎥 Automatic video generation (Shorts / Reels + long-form)
Turn a topic into a complete **vertical (1080×1920)** or **landscape (1920×1080)**
MP4 with **burned-in, karaoke-highlighted subtitles**, animated visuals, and
transition SFX — fully generic and data-driven (no topic-specific code, ever).

Pipeline: `script → storyboard → visual assets → (reused) TTS → word-synced
subtitles → Remotion render → <title-slug>.mp4`. It reuses the existing script,
metadata, thumbnail, TTS, and image-provider services.

One-time setup of the video engine (Node 18+ required):
```bash
cd video && npm install        # first render also downloads a headless Chromium
```

Generate a video (asynchronous / background job):
```bash
curl -X POST localhost:8000/videos/generate \
  -H 'Content-Type: application/json' \
  -d '{"topic":"What is pgvector?","content_type":"short","target_seconds":30,"style":"modern-tech"}'
# -> {"jobId":"<uuid>","status":"queued"}

curl localhost:8000/videos/<jobId>
# -> {"status":"completed","videoUrl":"/media/<project>/<title-slug>.mp4", ...}
```
- `content_type`: `short` → portrait 1080×1920, `long` → landscape 1920×1080
  (override with `"orientation": "portrait" | "landscape"`).
- `style`: `modern-tech` (default), `minimal`, `cinematic`, `educational`, `news`.
- Statuses: `queued → planning → generating_tts → generating_subtitles →
  generating_assets → rendering → completed` (or `failed`).
- Subtitles are synced from edge-tts word timestamps — no Whisper needed.
- Scene backgrounds use your configured `IMAGE_BACKEND`; if none/unreachable,
  a designed gradient+shape background is generated so videos always render.

## 🔌 API endpoints
| Method | Path | Description |
|---|---|---|
| `POST` | `/generate` | Run the full content pipeline for a topic |
| `POST` | `/videos/generate` | Queue a background video render; returns a jobId |
| `GET` | `/videos/{jobId}` | Poll video job status + result (videoUrl when done) |
| `GET` | `/voices` | List available TTS voices |
| `GET` | `/health` | Service status + Ollama reachability |
| `GET` | `/media/{path}` | Download generated artifacts (the video, thumbnails) |
| `GET` | `/docs` | Interactive Swagger UI |

### `POST /generate` body
```json
{
  "topic": "The science of good sleep",
  "tone": "engaging and friendly",
  "audience": "busy professionals",
  "target_minutes": 5,
  "language": "English",
  "generate_audio": true,
  "generate_thumbnails": true,
  "generate_metadata": true
}
```

---

## 🧩 Architecture
```
routes -> orchestrator -> services -> providers
```
- `app/services/llm/` — `LLMClient` interface + `OllamaClient`
- `app/services/tts/` — `TTSProvider` interface + `EdgeTTSProvider`
- `app/services/image/` — `ImageProvider` interface + `DiffusersImageProvider` + factory
- `app/services/thumbnail/` — `ThumbnailGenerator` interface + PIL renderer
- `app/services/orchestrator.py` — ties stages together, writes output
- `app/core/prompts.py` — all LLM prompts live here
- `app/config.py` — all settings live here

**Extend it:**
- Swap the LLM → implement `LLMClient`, update `get_llm()`.
- New TTS engine → implement `TTSProvider`, update `get_tts()`.
- New image backend → implement `ImageProvider`, register it in
  `app/services/image/__init__.py`'s `build_image_provider()`.
- New platform (e.g. TikTok) → extend the metadata prompt + normalizer, add a
  social file writer in the orchestrator.

---

## 🤖 Running with Kiro
This repo ships Kiro steering and a custom agent:
- **Steering** (`.kiro/steering/`): `product`, `tech`, `structure`,
  `conventions` are always active; `agent-guide` is manual — pull it with
  `#agent-guide`.
- **Custom agent** (`.kiro/agents/youtube-producer.json`): the
  **youtube-producer** agent knows how to check Ollama, run generations, and
  extend the pipeline safely.

Just tell Kiro your topic (e.g. *"generate a package on intermittent fasting"*)
and it will run the agent for you.

---

## 🛠️ Troubleshooting
- **"Cannot reach Ollama"** → start it: `ollama serve`.
- **404 / model missing** → `ollama pull llama3.1` (or your configured model).
- **Metadata not valid JSON** → use a strong instruction-following model such as
  `llama3.1` or `qwen2.5`.
- **Plain thumbnail text** → no system TrueType font found; install fonts or
  accept the bitmap fallback.

# Vertical Short/Reel (1080x1920)
python cli.py "How closures work in JavaScript" --video --reel --seconds 40

# Landscape long-form (1920x1080)
python cli.py "What is Docker?" --video --minutes 2

# Optional: force orientation / pick a style
python cli.py "Kubernetes basics" --video --orientation landscape --style educational
