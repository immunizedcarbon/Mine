from __future__ import annotations

from datetime import date
from threading import Event
from typing import List

import pytest

from mine.core.types import ProtocolDocument, ProtocolMetadata
from mine.database import create_storage
from mine.pipeline import ImportPipeline, PipelineEvent


class DummyDIPClient:
    def __init__(self, documents: List[ProtocolDocument]):
        self._documents = {doc.metadata.identifier: doc for doc in documents}

    def iter_protocols(self, updated_since=None):
        for document in self._documents.values():
            yield document.metadata

    def fetch_protocol_text(self, identifier: str) -> ProtocolDocument:
        return self._documents[identifier]


@pytest.fixture()
def sample_documents() -> List[ProtocolDocument]:
    base_text = (
        "Präsidentin Bärbel Bas:\nIch eröffne die Sitzung.\n"
        "Abg. Max Mustermann (SPD):\nVielen Dank für das Wort.\n"
    )
    doc1 = ProtocolDocument(
        metadata=ProtocolMetadata(
            identifier="BT-PL-1",
            legislative_period=20,
            session_number=1,
            date=date(2024, 5, 1),
            title="1. Sitzung",
        ),
        full_text=base_text,
    )
    doc2 = ProtocolDocument(
        metadata=ProtocolMetadata(
            identifier="BT-PL-2",
            legislative_period=20,
            session_number=2,
            date=date(2024, 5, 2),
            title="2. Sitzung",
        ),
        full_text=base_text,
    )
    return [doc1, doc2]


def test_pipeline_emits_events_and_persists_speeches(tmp_path, sample_documents):
    database_url = f"sqlite:///{(tmp_path / 'pipeline.db').as_posix()}"
    storage = create_storage(database_url)
    client = DummyDIPClient(sample_documents[:1])
    pipeline = ImportPipeline(dip_client=client, storage=storage)

    captured: List[PipelineEvent] = []
    processed = pipeline.run(progress_callback=captured.append)

    kinds = [event.kind for event in captured]
    assert kinds[0] == "start"
    assert "progress" in kinds
    assert kinds[-1] == "finished"
    assert processed == 1

    overview = storage.list_protocols()
    assert overview[0].identifier == "BT-PL-1"
    assert overview[0].speech_count > 0


def test_pipeline_cancellation_stops_execution(tmp_path, sample_documents):
    database_url = f"sqlite:///{(tmp_path / 'cancel.db').as_posix()}"
    storage = create_storage(database_url)
    client = DummyDIPClient(sample_documents)
    pipeline = ImportPipeline(dip_client=client, storage=storage)

    cancel_event = Event()
    captured: List[PipelineEvent] = []

    def record(event: PipelineEvent) -> None:
        captured.append(event)
        if event.kind == "progress":
            cancel_event.set()

    processed = pipeline.run(progress_callback=record, cancel_event=cancel_event)

    kinds = [event.kind for event in captured]
    assert "cancelled" in kinds
    assert processed == 1
