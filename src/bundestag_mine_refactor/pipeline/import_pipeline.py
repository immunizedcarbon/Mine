"""High level orchestration of the refactored Bundestags-Mine pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from threading import Event
from typing import Callable, Literal, Optional
import logging

from ..clients import DIPClient
from ..core.types import ProtocolMetadata
from ..database import Storage
from ..parsing import parse_speeches
from ..summarization import GeminiSummarizer

LOGGER = logging.getLogger(__name__)

PipelineEventKind = Literal[
    "start",
    "metadata",
    "fetched",
    "parsed",
    "stored",
    "summaries",
    "progress",
    "finished",
    "cancelled",
    "error",
]


@dataclass(slots=True)
class PipelineEvent:
    """Fine grained progress notification emitted by :class:`ImportPipeline`."""

    kind: PipelineEventKind
    processed: int
    metadata: ProtocolMetadata | None = None
    message: str | None = None
    speech_count: int | None = None
    summary_count: int | None = None


ProgressCallback = Callable[[PipelineEvent], None]


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

    def run(
        self,
        *,
        updated_since: Optional[str] = None,
        limit: Optional[int] = None,
        progress_callback: Optional[ProgressCallback] = None,
        cancel_event: Optional[Event] = None,
    ) -> int:
        """Run the pipeline end-to-end."""

        processed = 0
        cancelled = False
        had_error = False
        current_metadata: ProtocolMetadata | None = None
        self._notify(
            progress_callback,
            PipelineEvent(kind="start", processed=processed, message="Pipeline run started"),
        )
        try:
            for metadata in self._dip_client.iter_protocols(updated_since=updated_since):
                if limit is not None and processed >= limit:
                    break
                if cancel_event and cancel_event.is_set():
                    cancelled = True
                    break
                current_metadata = metadata
                LOGGER.info("Processing protocol %s", metadata.identifier)
                self._notify(
                    progress_callback,
                    PipelineEvent(
                        kind="metadata",
                        processed=processed,
                        metadata=current_metadata,
                        message=f"Processing protocol {metadata.identifier}",
                    ),
                )
                document = self._dip_client.fetch_protocol_text(metadata.identifier)
                self._notify(
                    progress_callback,
                    PipelineEvent(
                        kind="fetched",
                        processed=processed,
                        metadata=document.metadata,
                        message="Fetched protocol text",
                    ),
                )
                self._storage.upsert_protocol(document.metadata)
                speeches = parse_speeches(document.full_text, document.metadata.identifier)
                self._notify(
                    progress_callback,
                    PipelineEvent(
                        kind="parsed",
                        processed=processed,
                        metadata=document.metadata,
                        message=f"Parsed {len(speeches)} speeches",
                        speech_count=len(speeches),
                    ),
                )
                self._storage.replace_speeches(document.metadata.identifier, speeches)
                self._notify(
                    progress_callback,
                    PipelineEvent(
                        kind="stored",
                        processed=processed,
                        metadata=document.metadata,
                        message=f"Persisted {len(speeches)} speeches",
                        speech_count=len(speeches),
                    ),
                )
                if self._summarizer:
                    summary_count = self._summarize_pending(cancel_event=cancel_event)
                    if summary_count:
                        self._notify(
                            progress_callback,
                            PipelineEvent(
                                kind="summaries",
                                processed=processed,
                                metadata=document.metadata,
                                message=f"Updated {summary_count} summaries",
                                summary_count=summary_count,
                            ),
                        )
                    if cancel_event and cancel_event.is_set():
                        cancelled = True
                        break
                processed += 1
                self._notify(
                    progress_callback,
                    PipelineEvent(
                        kind="progress",
                        processed=processed,
                        metadata=document.metadata,
                        message=f"Completed protocol {metadata.identifier}",
                        speech_count=len(speeches),
                    ),
                )
            if cancel_event and cancel_event.is_set():
                cancelled = True
        except Exception as exc:  # pragma: no cover - re-raised for visibility in tests
            had_error = True
            LOGGER.exception("Import pipeline failed: %s", exc)
            self._notify(
                progress_callback,
                PipelineEvent(
                    kind="error",
                    processed=processed,
                    metadata=current_metadata,
                    message=str(exc),
                ),
            )
            raise
        finally:
            if cancelled:
                self._notify(
                    progress_callback,
                    PipelineEvent(
                        kind="cancelled",
                        processed=processed,
                        metadata=current_metadata,
                        message="Pipeline run cancelled",
                    ),
                )
            elif not had_error:
                self._notify(
                    progress_callback,
                    PipelineEvent(
                        kind="finished",
                        processed=processed,
                        metadata=current_metadata,
                        message="Pipeline run finished",
                    ),
                )
        return processed

    def _summarize_pending(self, *, cancel_event: Optional[Event] = None) -> int:
        assert self._summarizer is not None
        pending = self._storage.pending_summaries(limit=25)
        generated = 0
        for speech in pending:
            if cancel_event and cancel_event.is_set():
                break
            summary = self._summarizer.summarize(speech.text)
            self._storage.update_summary(speech.id, summary=summary)
            generated += 1
        return generated

    @staticmethod
    def _notify(callback: Optional[ProgressCallback], event: PipelineEvent) -> None:
        if callback:
            callback(event)


__all__ = ["ImportPipeline", "PipelineEvent"]
