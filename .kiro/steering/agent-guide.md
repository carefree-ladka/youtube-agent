---
inclusion: manual
---

# YouTube Agent — Operating Guide

This is the playbook for running and extending the YouTube Agent. Pull it into
context with `#agent-guide` when you want Kiro to drive a generation run or build
on the pipeline.

## Before running a generation
1. Confirm setup: dependencies installed and `.env` exists (copy from
   `.env.example` if missing).
2. Confirm Ollama is up: `GET /health` or `curl http://localhost:11434/api/version`.
   If down, tell the user to run `ollama serve` and `ollama pull <model>`.
3. Confirm the model in `OLLAMA_TEXT_MODEL` is pulled.

## Running a generation
Preferred (no server needed):
```bash
python cli.py "<topic>" --minutes <n> --tone "<tone>"
```
Fast sanity check (LLM only, skips audio + images):
```bash
python cli.py "<topic>" --no-audio --no-thumbnails
```
Via API:
```bash
python run.py            # then POST /generate with a JSON body
```

## Inspecting results
- Everything lands in `output/<timestamp>_<slug>/`.
- Read `summary.json` first — it lists every artifact and any `warnings`.
- Scripts are in `script.txt`; social copy is in `social/*.txt`.

## Choosing a smooth voice
- Default is `en-US-JennyNeural` (natural, warm). Other strong picks:
  `en-US-AriaNeural`, `en-US-GuyNeural`, `en-GB-SoniaNeural`,
  `en-US-AndrewMultilingualNeural`.
- List all with `GET /voices` or `edge-tts --list-voices`.
- Tune delivery with `TTS_RATE`, `TTS_PITCH`, `TTS_VOLUME` in `.env`.

## When extending the code
- Respect the layering: `routes -> orchestrator -> services -> providers`.
- New provider? Implement the capability's ABC in `base.py`, then wire it in
  `app/api/dependencies.py`. Do not touch the orchestrator's flow to swap a
  provider.
- New prompt or prompt change? Edit `app/core/prompts.py` only.
- New config value? Add it to `Settings` and `.env.example`.

## After any code change
- Import-check: `python -c "import app.main"`.
- If the LLM path changed, run the fast sanity check above.
- Clean up any throwaway files you created while testing.

## Common failure modes
- **"Cannot reach Ollama"**: server not running -> `ollama serve`.
- **404 / model missing**: `ollama pull <OLLAMA_TEXT_MODEL>`.
- **Empty/!JSON metadata**: the model ignored JSON mode; retry or switch to a
  stronger instruction-following model (e.g. `llama3.1`, `qwen2.5`).
- **Thumbnail text looks plain**: no TrueType font found; install system fonts or
  accept the default bitmap font fallback.
