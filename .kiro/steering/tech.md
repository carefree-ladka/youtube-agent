# Technology & Commands

## Stack
- **Language**: Python 3.10+
- **API**: FastAPI + Uvicorn
- **Config**: pydantic-settings (loads from `.env`)
- **LLM**: Ollama (local) via its HTTP API, using `httpx` (async)
- **TTS**: `edge-tts` (free, natural neural voices, no API key)
- **Thumbnails**: Pillow (PIL) for text/branding composition; the text LLM writes the concept
- **Image generation (optional)**: `diffusers` (Stable Diffusion / FLUX) on
  Apple Silicon MPS / CUDA / CPU, behind a pluggable `ImageProvider`
- **Resilience**: `tenacity` for retries; graceful per-stage error handling

## Image generation notes
- Enabled via `IMAGE_BACKEND=diffusers` in `.env`. When `none`, thumbnails use a
  brand gradient background (no heavy deps needed).
- Deps live in a separate `requirements-image.txt` (torch, diffusers,
  transformers, accelerate, safetensors) to keep the base app light.
- Ollama's own image models (e.g. `x/flux2-klein`) are NOT usable for generation
  right now: the current Ollama engine rejects image models on `/api/generate`
  and `ollama run` ("image generation models are not currently supported").
  That's why we use `diffusers` for real local image generation.
- First generation downloads model weights to `~/.cache/huggingface` (several GB).
- Recommended Mac model: `stabilityai/sdxl-turbo` (fast, 1-4 steps, guidance 0).

## Image backends (pluggable, via IMAGE_BACKEND)
- `none` (default): PIL-designed gradient/shape backgrounds, instant, no deps.
- `ollama`: calls an Ollama image model (e.g. `x/flux2-klein:9b`) via `/api/generate`.
- `diffusers`: local Hugging Face model (needs `requirements-image.txt`).
- `comfyui`: calls a running ComfyUI server (`/prompt`→`/history`→`/view`).
  The Comfy-Org/ComfyUI repo has NO Dockerfile; run it natively on macOS (Docker
  Desktop can't use the Apple GPU, so a container is CPU-only). Docker is best on
  Linux/NVIDIA. Provider builds a standard SD/SDXL graph, or loads a custom
  API-format workflow from `COMFYUI_WORKFLOW` with `%PLACEHOLDER%` substitution.
- All backends only paint the TEXT-FREE background; PIL always draws the headline.
- Any backend that's unreachable/unavailable falls back to the designed background.

## External dependencies
- **Ollama must be running** for script/metadata/thumbnail-concept generation.
  - Install: https://ollama.com
  - Start: `ollama serve`
  - Pull a model: `ollama pull llama3.1`
- **edge-tts** requires internet access (voices are served by Microsoft).

## Environment
All configuration is via `.env` (copy from `.env.example`). Never hard-code
values that belong in settings. Access settings only through
`app.config.get_settings()`.

Key variables: `OLLAMA_BASE_URL`, `OLLAMA_TEXT_MODEL`, `OLLAMA_IMAGE_MODEL`,
`TTS_VOICE`, `OUTPUT_DIR`, and the `BRAND_*` values used on thumbnails.

## Common commands
Setup:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Optional: local AI thumbnail backgrounds (large download)
pip install -r requirements-image.txt
cp .env.example .env
```

Run the API (dev):
```bash
python run.py
# or
uvicorn app.main:app --reload
```

Generate from the CLI:
```bash
python cli.py "How compound interest builds wealth" --minutes 6
```

List voices:
```bash
edge-tts --list-voices
# or GET /voices when the server is running
```

Lint (if ruff installed):
```bash
ruff check app
```

## Verification expectations
- After changing service code, at minimum import-check the app:
  `python -c "import app.main"`.
- Prefer running `python cli.py "<topic>" --no-audio --no-thumbnails` for a fast
  end-to-end sanity check that only exercises the LLM path.
