from __future__ import annotations

from datetime import date

from bundestag_mine_refactor.core.types import ProtocolMetadata, Speech
from bundestag_mine_refactor.database import create_storage


def test_list_protocols_returns_ordered_snapshots(tmp_path):
    database_url = f"sqlite:///{(tmp_path / 'overview.db').as_posix()}"
    storage = create_storage(database_url)

    metadata_old = ProtocolMetadata(
        identifier="BT-PL-1",
        legislative_period=19,
        session_number=200,
        date=date(2023, 12, 12),
        title="200. Sitzung",
    )
    storage.upsert_protocol(metadata_old)
    storage.replace_speeches(
        metadata_old.identifier,
        [
            Speech(protocol_id=metadata_old.identifier, sequence_number=1, speaker_name="A", text="Test"),
        ],
    )

    metadata_new = ProtocolMetadata(
        identifier="BT-PL-2",
        legislative_period=20,
        session_number=10,
        date=date(2024, 5, 5),
        title="10. Sitzung",
    )
    storage.upsert_protocol(metadata_new)
    storage.replace_speeches(
        metadata_new.identifier,
        [
            Speech(protocol_id=metadata_new.identifier, sequence_number=1, speaker_name="B", text="Test"),
            Speech(protocol_id=metadata_new.identifier, sequence_number=2, speaker_name="C", text="Noch ein Test"),
        ],
    )

    overview = storage.list_protocols()
    assert overview[0].identifier == metadata_new.identifier
    assert overview[0].speech_count == 2
    assert overview[1].identifier == metadata_old.identifier
    assert overview[1].speech_count == 1
