"""Modernisierte Pipeline für Bundestagsprotokolle."""
from __future__ import annotations

from .clients import DIPClient, DIPClientError
from .config import AppConfig, DIPConfig, GeminiConfig, StorageConfig, load_config
from .core import ProtocolDocument, ProtocolMetadata, Speech
from .database import Base, Protocol, SpeechModel, Storage, create_storage
from .parsing import parse_speeches
from .pipeline import ImportPipeline
from .summarization import GeminiSummarizer

__all__ = [
    "AppConfig",
    "Base",
    "DIPClient",
    "DIPClientError",
    "DIPConfig",
    "GeminiConfig",
    "GeminiSummarizer",
    "ImportPipeline",
    "Protocol",
    "ProtocolDocument",
    "ProtocolMetadata",
    "Speech",
    "SpeechModel",
    "Storage",
    "StorageConfig",
    "create_storage",
    "load_config",
    "parse_speeches",
]
