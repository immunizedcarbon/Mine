"""Utilities for parsing plenary protocol texts into speeches."""
from __future__ import annotations

from typing import List, Tuple
import logging
import re

from ..core.types import Speech

LOGGER = logging.getLogger(__name__)

_SPEAKER_PATTERN = re.compile(
    r"^\s*(?P<header>[A-ZÄÖÜß][^\n:]{2,}?)(?::|\s+:)",
    re.MULTILINE,
)
_PARTY_PATTERN = re.compile(r"\((?P<party>[^)]+)\)")
_ROLE_KEYWORDS = (
    r"Präsident(?:in)?",
    r"Vizepräsident(?:in)?",
    r"Bundesminister(?:in)?",
    r"Bundeskanzler(?:in)?",
    r"Staatssekretär(?:in)?",
    r"Staatsminister(?:in)?",
    r"Parlamentarische(?:r)?\s+Staatssekretär(?:in)?",
)
_STAGE_DIRECTIONS = re.compile(
    r"\((?:[^()]*?(?:Beifall|Zuruf|Heiterkeit|Lachen|Unruhe|Beifallsrufe)[^()]*)\)",
    re.IGNORECASE,
)
_MULTISPACE = re.compile(r"\s{2,}")
_INTERJECTION_PATTERN = re.compile(r"^Zuruf von [^\n:]+:.*$", re.MULTILINE)


def _extract_party(header: str) -> Tuple[str, str | None]:
    match = _PARTY_PATTERN.search(header)
    if not match:
        return header.strip(), None
    party = match.group("party").strip()
    cleaned = _PARTY_PATTERN.sub("", header).strip()
    return cleaned, party


def _split_role(name: str) -> Tuple[str, str | None]:
    for keyword in _ROLE_KEYWORDS:
        pattern = re.compile(rf"^(?P<role>{keyword}\b[^:]*?)\s+(?P<name>.+)$", re.IGNORECASE)
        match = pattern.match(name)
        if match:
            return match.group("name").strip(), match.group("role").strip()
    return name.strip(), None


def parse_speeches(protocol_text: str, protocol_id: str) -> List[Speech]:
    """Parse the speech segments contained in ``protocol_text``."""

    cleaned_text = _INTERJECTION_PATTERN.sub("", protocol_text)
    matches = list(_SPEAKER_PATTERN.finditer(cleaned_text))
    speeches: List[Speech] = []
    if not matches:
        LOGGER.warning("No speeches detected for protocol %s", protocol_id)
        return speeches

    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(cleaned_text)
        raw_header = match.group("header").strip()
        raw_text = cleaned_text[start:end].strip()
        raw_text = _STAGE_DIRECTIONS.sub("", raw_text)
        raw_text = _MULTISPACE.sub(" ", raw_text)
        header_without_party, party = _extract_party(raw_header)
        speaker_name, role = _split_role(header_without_party)
        speech_text = raw_text.strip()
        if not speech_text:
            continue
        speeches.append(
            Speech(
                protocol_id=protocol_id,
                sequence_number=index + 1,
                speaker_name=speaker_name,
                party=party,
                role=role,
                text=speech_text,
            )
        )
    return speeches


__all__ = ["parse_speeches"]
