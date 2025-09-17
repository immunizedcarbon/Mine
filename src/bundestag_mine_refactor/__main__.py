"""Entry point for ``python -m bundestag_mine_refactor``."""
from __future__ import annotations

from .cli import main


if __name__ == "__main__":  # pragma: no cover - module entry point
    raise SystemExit(main())
