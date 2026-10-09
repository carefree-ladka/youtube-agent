"""Interpreter bootstrap for the CLI / launcher entrypoints.

Lets you run ``python cli.py`` or ``python run.py`` with ANY Python: if the
current interpreter is missing the project's dependencies, we automatically
re-launch the same command under the project's virtualenv (``.venv``). This
avoids the common "ModuleNotFoundError: No module named 'pydantic'" that happens
when the system Python is used instead of the venv.

Only the standard library is imported here, so this module is always importable.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _venv_python() -> Path | None:
    """Return the project's virtualenv Python path, if it exists."""
    candidates = [
        _PROJECT_ROOT / ".venv" / "bin" / "python",       # macOS / Linux
        _PROJECT_ROOT / ".venv" / "Scripts" / "python.exe",  # Windows
    ]
    return next((p for p in candidates if p.exists()), None)


def _deps_available() -> bool:
    """True if the current interpreter has the core third-party dependencies."""
    import importlib.util

    for module in ("pydantic", "fastapi", "httpx", "tenacity", "edge_tts", "PIL"):
        if importlib.util.find_spec(module) is None:
            return False
    return True


def ensure_venv() -> None:
    """Run under the project's virtualenv, re-exec'ing into it when needed.

    Strategy: if a ``.venv`` exists and we're not already running it, always
    switch to it (the venv is the single source of truth for dependencies).
    Only if there's no venv do we fall back to checking the current interpreter.
    """
    venv_python = _venv_python()
    current = Path(sys.executable).resolve()

    # Prefer the project venv whenever it exists and we're not already in it.
    if venv_python and venv_python.resolve() != current:
        os.execv(str(venv_python), [str(venv_python), *sys.argv])

    # Either we're in the venv now, or there is no venv. Verify deps are present.
    if _deps_available():
        return

    sys.stderr.write(
        "\n[youtube-agent] Dependencies are not installed for this interpreter:\n"
        f"    {sys.executable}\n\n"
        "Set up the virtualenv and install requirements:\n"
        "    python3 -m venv .venv\n"
        "    .venv/bin/python -m pip install -r requirements.txt\n\n"
        "Then run with the venv, e.g.:\n"
        "    .venv/bin/python cli.py \"<topic>\"\n"
        "  or activate it first:\n"
        "    source .venv/bin/activate   # then: python cli.py \"<topic>\"\n\n"
    )
    raise SystemExit(1)
