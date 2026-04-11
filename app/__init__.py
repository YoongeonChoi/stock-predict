"""Repo-root shim so root-level tooling can import the backend app package."""

from pathlib import Path

_BACKEND_APP_DIR = Path(__file__).resolve().parent.parent / "backend" / "app"

if not _BACKEND_APP_DIR.is_dir():  # pragma: no cover - guard for broken repo layouts
    raise ImportError(f"Expected backend app package at {_BACKEND_APP_DIR}")

__path__ = [str(_BACKEND_APP_DIR)]
