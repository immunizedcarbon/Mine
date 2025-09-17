"""HTTP client for the Bundestag Data Service (DIP) API."""
from __future__ import annotations

from datetime import date, datetime
from typing import Dict, Iterator, Optional
import logging

import httpx

from .types import ProtocolDocument, ProtocolMetadata

LOGGER = logging.getLogger(__name__)


class DIPClientError(RuntimeError):
    """Raised when the Bundestag DIP API responds with an error."""


class DIPClient:
    """Minimal client for fetching plenary protocols from DIP."""

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str],
        *,
        timeout: float = 30.0,
        max_retries: int = 3,
        page_size: int = 100,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._max_retries = max(1, max_retries)
        self._page_size = page_size
        self._client = httpx.Client(timeout=timeout)

    # --- public API -----------------------------------------------------
    def iter_protocols(self, *, updated_since: Optional[str] = None) -> Iterator[ProtocolMetadata]:
        """Iterate over protocol metadata entries."""

        page = 0
        while True:
            params: Dict[str, str] = {"offset": str(page * self._page_size), "limit": str(self._page_size)}
            if updated_since:
                params["f.aktualisiertStart"] = updated_since
            response_json = self._request("GET", "/plenarprotokoll", params=params)
            documents = response_json.get("documents") or response_json.get("dokuments") or []
            if not documents:
                break
            for entry in documents:
                yield self._parse_protocol_metadata(entry)
            if len(documents) < self._page_size:
                break
            page += 1

    def fetch_protocol_text(self, identifier: str) -> ProtocolDocument:
        """Download a plenary protocol including the full text."""

        endpoint = f"/plenarprotokoll-text/{identifier}"
        data = self._request("GET", endpoint)
        metadata = self._parse_protocol_metadata(data)
        full_text = data.get("text") or data.get("inhalt")
        if not full_text:
            raise DIPClientError(f"Protocol {identifier} does not contain text data")
        return ProtocolDocument(metadata=metadata, full_text=full_text)

    # --- helpers --------------------------------------------------------
    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"ApiKey {self._api_key}"
        return headers

    def _request(self, method: str, path: str, params: Optional[Dict[str, str]] = None) -> Dict[str, any]:
        url = f"{self._base_url}{path}"
        last_exc: Optional[Exception] = None
        for attempt in range(1, self._max_retries + 1):
            try:
                response = self._client.request(method, url, headers=self._headers(), params=params)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:  # pragma: no cover - network errors are rare in tests
                last_exc = exc
                LOGGER.warning("DIP API returned status %s for %s %s", exc.response.status_code, method, url)
            except httpx.HTTPError as exc:  # pragma: no cover - network errors are rare in tests
                last_exc = exc
                LOGGER.warning("HTTP error while requesting %s %s: %s", method, url, exc)
        raise DIPClientError(f"Failed to request {url}") from last_exc

    @staticmethod
    def _parse_protocol_metadata(data: Dict[str, any]) -> ProtocolMetadata:
        raw_identifier = data.get("id") or data.get("vorgangId") or data.get("dipId") or data.get("plenarprotokollId")
        if not raw_identifier:
            raise DIPClientError("Protocol metadata did not contain an identifier")
        identifier = str(raw_identifier)

        def _parse_int(candidate: Optional[str]) -> Optional[int]:
            if candidate is None:
                return None
            try:
                return int(candidate)
            except (TypeError, ValueError):
                return None

        def _parse_date(value: Optional[str]) -> Optional[date]:
            if not value:
                return None
            try:
                return datetime.fromisoformat(value).date()
            except ValueError:
                try:
                    return datetime.strptime(value, "%d.%m.%Y").date()
                except ValueError:
                    return None

        legislative_period = _parse_int(data.get("wahlperiode") or data.get("wahlperiodeNummer"))
        session_number = _parse_int(data.get("sitzungsnummer") or data.get("nummer"))
        date_value = _parse_date(data.get("datum") or data.get("sitzungsdatum"))
        title = data.get("titel") or data.get("sitzungstitel")

        return ProtocolMetadata(
            identifier=identifier,
            legislative_period=legislative_period,
            session_number=session_number,
            date=date_value,
            title=title,
            source=data,
        )


__all__ = ["DIPClient", "DIPClientError"]
