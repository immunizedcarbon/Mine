"""Command line interface for controlling the refactored pipeline."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Optional

from .config import AppConfig, load_config
from .dip_client import DIPClient
from .pipeline import ImportPipeline
from .storage import create_storage
from .summarizer import GeminiSummarizer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
LOGGER = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bundestags-Mine refactored pipeline controller")
    parser.add_argument("command", choices=["import"], help="Which pipeline action to execute")
    parser.add_argument("--config", type=Path, help="Path to an explicit configuration file")
    parser.add_argument("--since", dest="updated_since", help="Only fetch protocols updated since this ISO timestamp")
    parser.add_argument("--limit", type=int, help="Maximum number of protocols to import")
    parser.add_argument(
        "--without-summaries",
        action="store_true",
        help="Skip Gemini summarisation even if an API key is configured",
    )
    return parser


def _create_pipeline(config: AppConfig, *, skip_summaries: bool) -> ImportPipeline:
    dip_client = DIPClient(
        config.dip.base_url,
        config.dip.api_key,
        timeout=config.dip.timeout,
        max_retries=config.dip.max_retries,
        page_size=config.dip.page_size,
    )
    storage = create_storage(config.storage.database_url, echo=config.storage.echo_sql)
    summarizer = None
    if not skip_summaries and config.gemini.api_key:
        summarizer = GeminiSummarizer(
            api_key=config.gemini.api_key,
            base_url=config.gemini.base_url,
            model=config.gemini.model,
            timeout=config.gemini.timeout,
            max_retries=config.gemini.max_retries,
        )
    elif not skip_summaries:
        LOGGER.warning("Gemini API key missing - summaries will be skipped")
    return ImportPipeline(dip_client=dip_client, storage=storage, summarizer=summarizer)


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    config = load_config(args.config)
    pipeline = _create_pipeline(config, skip_summaries=args.without_summaries)

    if args.command == "import":
        processed = pipeline.run(updated_since=args.updated_since, limit=args.limit)
        LOGGER.info("Imported %s protocols", processed)
        return 0
    parser.error(f"Unknown command {args.command}")
    return 2


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
