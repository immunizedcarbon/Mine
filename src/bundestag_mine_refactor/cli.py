"""Command line interface for controlling the refactored pipeline."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Optional

from .config import load_config
from .database import create_storage
from .runtime import create_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
LOGGER = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bundestags-Mine refactored pipeline controller")
    parser.add_argument("command", choices=["import", "ui"], help="Which pipeline action to execute")
    parser.add_argument("--config", type=Path, help="Path to an explicit configuration file")
    parser.add_argument("--since", dest="updated_since", help="Only fetch protocols updated since this ISO timestamp")
    parser.add_argument("--limit", type=int, help="Maximum number of protocols to import")
    parser.add_argument(
        "--without-summaries",
        action="store_true",
        help="Skip Gemini summarisation even if an API key is configured",
    )
    parser.add_argument(
        "--ui-host",
        default="127.0.0.1",
        help="Host interface for the UI server (only used with the 'ui' command)",
    )
    parser.add_argument(
        "--ui-port",
        type=int,
        default=8080,
        help="Port for the UI server (only used with the 'ui' command)",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    config = load_config(args.config)

    if args.command == "import":
        resources = create_pipeline(config, skip_summaries=args.without_summaries)
        try:
            processed = resources.pipeline.run(updated_since=args.updated_since, limit=args.limit)
            LOGGER.info("Imported %s protocols", processed)
            return 0
        finally:
            resources.close()
    if args.command == "ui":
        from .ui.app import run_ui

        storage = create_storage(config.storage.database_url, echo=config.storage.echo_sql)
        run_ui(
            config,
            storage=storage,
            host=args.ui_host,
            port=args.ui_port,
        )
        storage.dispose()
        return 0
    parser.error(f"Unknown command {args.command}")
    return 2


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
