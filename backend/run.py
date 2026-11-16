"""
SysForge backend — development entry point.

Run from the backend/ directory::

    python run.py

Or use uvicorn directly for more control::

    uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

This file is NOT used in production — production deployments should
invoke uvicorn (or gunicorn + uvicorn workers) directly.
"""

from __future__ import annotations

import uvicorn

from app.core.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.is_development,
        log_level=settings.log_level,
    )
