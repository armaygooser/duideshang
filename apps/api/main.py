"""Vercel FastAPI entrypoint.

The application implementation stays in ``app.main``; this root-level module
exists so Vercel's zero-configuration Python detection can discover it.
"""

from app.main import app

__all__ = ["app"]
