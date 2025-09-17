"""Integration with the Gemini 2.5 Pro API via the official SDK."""
from __future__ import annotations

from typing import Optional
import logging
import math

from google import genai
from google.genai import types

LOGGER = logging.getLogger(__name__)

_PROMPT_TEMPLATE = (
    "Fasse die folgende Rede aus dem Deutschen Bundestag sachlich, kompakt "
    "und in höchstens fünf Sätzen zusammen. Konzentriere dich auf zentrale "
    "Argumente, Beschlüsse und Forderungen. Rede:\n\n{speech}"
)

_TEXTUAL_SAFETY_CATEGORIES = (
    types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
    types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
    types.HarmCategory.HARM_CATEGORY_HARASSMENT,
    types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
    types.HarmCategory.HARM_CATEGORY_CIVIC_INTEGRITY,
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
        enable_safety_settings: bool = True,
    ) -> None:
        if not api_key:
            raise ValueError("A Gemini API key must be provided")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._max_retries = max(1, max_retries)
        self._enable_safety_settings = enable_safety_settings
        http_options_kwargs: dict[str, object] = {}
        if self._base_url:
            http_options_kwargs["base_url"] = self._base_url
        timeout_seconds = math.ceil(self._timeout)
        if timeout_seconds > 0:
            http_options_kwargs["timeout"] = timeout_seconds
        http_options = types.HttpOptions(**http_options_kwargs)
        self._client = genai.Client(api_key=self._api_key, http_options=http_options)

    def summarize(self, speech_text: str) -> str:
        """Generate a Gemini powered summary for ``speech_text``."""

        prompt = _PROMPT_TEMPLATE.format(speech=speech_text.strip())
        config = self._build_generation_config()
        last_exc: Optional[Exception] = None
        for attempt in range(1, self._max_retries + 1):
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=prompt,
                    config=config,
                )
                return self._extract_text(response)
            except genai.errors.APIError as exc:  # pragma: no cover - network errors are rare in tests
                last_exc = exc
                LOGGER.warning(
                    "Gemini request failed (attempt %s/%s): %s",
                    attempt,
                    self._max_retries,
                    exc,
                )
        raise RuntimeError("Failed to generate summary via Gemini") from last_exc

    def _build_generation_config(self) -> types.GenerateContentConfig:
        config = types.GenerateContentConfig(
            temperature=0.2,
            top_k=32,
            top_p=0.95,
            max_output_tokens=512,
        )
        if not self._enable_safety_settings:
            config.safety_settings = [
                types.SafetySetting(
                    category=category,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE,
                )
                for category in _TEXTUAL_SAFETY_CATEGORIES
            ]
        return config

    @staticmethod
    def _extract_text(response: types.GenerateContentResponse) -> str:
        text = (response.text or "").strip()
        if text:
            return text
        for candidate in response.candidates or ():
            if candidate.content and candidate.content.parts:
                for part in candidate.content.parts:
                    if getattr(part, "text", None):
                        candidate_text = part.text.strip()
                        if candidate_text:
                            return candidate_text
        raise RuntimeError("Gemini response did not contain text")


__all__ = ["GeminiSummarizer"]
