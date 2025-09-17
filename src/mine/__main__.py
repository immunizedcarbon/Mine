"""Entry point for ``python -m mine``."""
from __future__ import annotations

from .cli import main


if __name__ == "__main__":  # pragma: no cover - module entry point
    raise SystemExit(main())
