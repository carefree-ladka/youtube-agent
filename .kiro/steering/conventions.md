# Coding Conventions

## Python style
- Target Python 3.10+; use modern typing (`str | None`, `list[str]`).
- Add `from __future__ import annotations` at the top of modules.
- Every public function/method gets a concise docstring describing intent.
- Line length 100 (see `pyproject.toml` ruff config).
- Prefer `pathlib.Path` over `os.path`.

## Async
- All I/O-bound work (LLM calls, TTS, HTTP) is `async`.
- PIL rendering is CPU-bound and stays synchronous; call it from async code
  directly (runs fast) — do not fake async around it.

## Errors & resilience
- Providers raise specific errors (e.g. `OllamaError`) with actionable messages
  (tell the user how to fix it: start Ollama, pull the model, etc.).
- The orchestrator wraps optional stages (metadata, audio, thumbnails) in
  try/except and appends to `warnings` instead of aborting the whole run.
- The required stage (script) is allowed to fail the request — without a script
  there is nothing to build on.

## Configuration
- All tunables come from `Settings` in `config.py`, sourced from `.env`.
- Access via `get_settings()` (cached). Never call `os.environ` in services.

## Prompts
- All prompt text lives in `core/prompts.py` as builder functions returning the
  fully-rendered string, plus a matching `*_SYSTEM` constant.
- When the output must be structured, instruct the model to return JSON only and
  read it with `llm.generate_json(...)`.

## Naming
- Services: `<Thing>Service` or `<Thing>Provider` / `<Thing>Generator`.
- Interfaces (ABCs): live in `base.py` within each capability package.
- Files/dirs: snake_case for modules, kebab-case slugs for output folders.

## Do / Don't
- DO keep the pipeline stages independent and individually toggleable.
- DO write new output through `utils/files.py`.
- DON'T add paid third-party services without making them optional and opt-in.
- DON'T inline secrets or model names; use settings.
- DON'T add tests unless asked, but keep code import-clean and runnable.
