"""Typed domain objects for the refactored pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, Optional


@dataclass(slots=True)
class ProtocolMetadata:
    """Metadata describing a Bundestag plenary protocol."""

    identifier: str
    legislative_period: Optional[int]
    session_number: Optional[int]
    date: Optional[date]
    title: Optional[str]
    source: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ProtocolDocument:
    """A protocol document including the full text."""

    metadata: ProtocolMetadata
    full_text: str


@dataclass(slots=True)
class Speech:
    """A single speech contribution within a protocol."""

    protocol_id: str
    sequence_number: int
    speaker_name: str
    text: str
    party: Optional[str] = None
    role: Optional[str] = None
    topics: Optional[str] = None
    summary: Optional[str] = None
    sentiment: Optional[str] = None


__all__ = ["ProtocolMetadata", "ProtocolDocument", "Speech"]
