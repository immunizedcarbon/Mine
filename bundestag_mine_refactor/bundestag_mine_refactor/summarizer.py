"""Integration with the Gemini 2.5 Pro API."""
from __future__ import annotations

from typing import Optional
import logging

import httpx

LOGGER = logging.getLogger(__name__)

_PROMPT_TEMPLATE = (
    "Fasse die folgende Rede aus dem Deutschen Bundestag sachlich, kompakt "
    "und in höchstens fünf Sätzen zusammen. Konzentriere dich auf zentrale "
    "Argumente, Beschlüsse und Forderungen. Rede:\n\n{speech}"
)


class GeminiSummarizer:
    """Client for the Gemini 2.5 Pro text summarisation endpoint."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://generativelanguage.googleapis.com",
        model: str = "gemini-2.5-pro",
        timeout: float = 120.0,
        max_retries: int = 3,
    ) -> None:
        if not api_key:
            raise ValueError("A Gemini API key must be provided")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._max_retries = max(1, max_retries)

    def summarize(self, speech_text: str) -> str:
        """Generate a Gemini powered summary for ``speech_text``."""

        prompt = _PROMPT_TEMPLATE.format(speech=speech_text.strip())
        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": prompt}]}
            ],
            "generationConfig": {
                "temperature": 0.2,
                "topK": 32,
                "topP": 0.95,
                "maxOutputTokens": 512,
            },
        }
        endpoint = f"{self._base_url}/v1beta/models/{self._model}:generateContent?key={self._api_key}"
        last_exc: Optional[Exception] = None
        for attempt in range(1, self._max_retries + 1):
            try:
                response = httpx.post(endpoint, json=payload, timeout=self._timeout)
                response.raise_for_status()
                data = response.json()
                return self._extract_text(data)
            except httpx.HTTPError as exc:  # pragma: no cover - network errors are rare in tests
                last_exc = exc
                LOGGER.warning("Gemini request failed (attempt %s/%s): %s", attempt, self._max_retries, exc)
        raise RuntimeError("Failed to generate summary via Gemini") from last_exc

    @staticmethod
    def _extract_text(response_json: dict) -> str:
        candidates = response_json.get("candidates") or []
        for candidate in candidates:
            for part in candidate.get("content", {}).get("parts", []):
                text = part.get("text")
                if text:
                    return text.strip()
        raise RuntimeError("Gemini response did not contain text")


__all__ = ["GeminiSummarizer"]
