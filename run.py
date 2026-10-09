"""Convenience launcher for local development.

Usage:
    python run.py
"""

from __future__ import annotations

# Ensure the project's virtualenv is used (re-execs if needed) before importing
# third-party packages like uvicorn.
from app.bootstrap import ensure_venv

ensure_venv()

import uvicorn  # noqa: E402

from app.config import get_settings  # noqa: E402


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.app_env == "development",
    )


if __name__ == "__main__":
    main()
