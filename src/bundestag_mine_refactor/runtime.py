"""Application level helpers for assembling pipeline dependencies."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .clients import DIPClient
from .config import AppConfig
from .database import Storage, create_storage
from .pipeline import ImportPipeline
from .summarization import GeminiSummarizer


@dataclass(slots=True)
class PipelineResources:
    """Container bundling the objects needed to run the pipeline."""

    pipeline: ImportPipeline
    dip_client: DIPClient
    storage: Storage
    summarizer: GeminiSummarizer | None
    owns_client: bool = True
    owns_storage: bool = True

    def close(self) -> None:
        if self.owns_client:
            self.dip_client.close()
        if self.owns_storage:
            self.storage.dispose()


def create_pipeline(
    config: AppConfig,
    *,
    skip_summaries: bool,
    storage: Storage | None = None,
    dip_client: DIPClient | None = None,
) -> PipelineResources:
    owns_client = dip_client is None
    owns_storage = storage is None
    client = dip_client or DIPClient(
        config.dip.base_url,
        config.dip.api_key,
        timeout=config.dip.timeout,
        max_retries=config.dip.max_retries,
        page_size=config.dip.page_size,
    )
    storage_instance = storage or create_storage(config.storage.database_url, echo=config.storage.echo_sql)
    summarizer: Optional[GeminiSummarizer] = None
    if not skip_summaries and config.gemini.api_key:
        summarizer = GeminiSummarizer(
            api_key=config.gemini.api_key,
            base_url=config.gemini.base_url,
            model=config.gemini.model,
            timeout=config.gemini.timeout,
            max_retries=config.gemini.max_retries,
            enable_safety_settings=config.gemini.enable_safety_settings,
        )
    elif not skip_summaries:
        import logging

        logging.getLogger(__name__).warning("Gemini API key missing - summaries will be skipped")
    pipeline = ImportPipeline(dip_client=client, storage=storage_instance, summarizer=summarizer)
    return PipelineResources(
        pipeline=pipeline,
        dip_client=client,
        storage=storage_instance,
        summarizer=summarizer,
        owns_client=owns_client,
        owns_storage=owns_storage,
    )


__all__ = ["PipelineResources", "create_pipeline"]
