"""High level orchestration of the refactored Bundestags-Mine pipeline."""
from __future__ import annotations

import logging
from typing import Optional

from ..clients import DIPClient
from ..database import Storage
from ..parsing import parse_speeches
from ..summarization import GeminiSummarizer

LOGGER = logging.getLogger(__name__)


class ImportPipeline:
    """Complete workflow for fetching, parsing and storing protocols."""

    def __init__(
        self,
        *,
        dip_client: DIPClient,
        storage: Storage,
        summarizer: Optional[GeminiSummarizer] = None,
    ) -> None:
        self._dip_client = dip_client
        self._storage = storage
        self._summarizer = summarizer

    def run(self, *, updated_since: Optional[str] = None, limit: Optional[int] = None) -> int:
        """Run the pipeline end-to-end."""

        processed = 0
        for metadata in self._dip_client.iter_protocols(updated_since=updated_since):
            if limit is not None and processed >= limit:
                break
            LOGGER.info("Processing protocol %s", metadata.identifier)
            document = self._dip_client.fetch_protocol_text(metadata.identifier)
            self._storage.upsert_protocol(document.metadata)
            speeches = parse_speeches(document.full_text, document.metadata.identifier)
            self._storage.replace_speeches(document.metadata.identifier, speeches)
            if self._summarizer:
                self._summarize_pending()
            processed += 1
        return processed

    def _summarize_pending(self) -> None:
        assert self._summarizer is not None
        pending = self._storage.pending_summaries(limit=25)
        for speech in pending:
            summary = self._summarizer.summarize(speech.text)
            self._storage.update_summary(speech.id, summary=summary)


__all__ = ["ImportPipeline"]
