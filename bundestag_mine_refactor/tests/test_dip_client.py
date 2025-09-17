from datetime import date
from datetime import date

import pytest

from bundestag_mine_refactor.dip_client import DIPClient


class DummyClient(DIPClient):
    def __init__(self):
        super().__init__(base_url="https://example.invalid", api_key=None)


def test_parse_protocol_metadata_handles_multiple_field_names():
    client = DummyClient()
    raw = {
        "id": "BT-PL-20-10",
        "wahlperiode": "20",
        "nummer": "10",
        "datum": "2024-05-05",
        "titel": "20. Sitzung",
    }

    metadata = client._parse_protocol_metadata(raw)
    assert metadata.identifier == "BT-PL-20-10"
    assert metadata.legislative_period == 20
    assert metadata.session_number == 10
    assert metadata.date == date(2024, 5, 5)
    assert metadata.title == "20. Sitzung"


def test_parse_protocol_metadata_requires_identifier():
    client = DummyClient()
    with pytest.raises(Exception):
        client._parse_protocol_metadata({})
