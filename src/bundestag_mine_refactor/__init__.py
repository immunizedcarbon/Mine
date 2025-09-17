"""Modernisierte Pipeline für Bundestagsprotokolle."""
from __future__ import annotations

from .clients import DIPClient, DIPClientError
from .config import AppConfig, DIPConfig, GeminiConfig, StorageConfig, load_config
from .core import ProtocolDocument, ProtocolMetadata, Speech
from .database import Base, Protocol, SpeechModel, Storage, create_storage
from .parsing import parse_speeches
from .pipeline import ImportPipeline, PipelineEvent
from .runtime import PipelineResources, create_pipeline
from .ui import run_ui
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
    "PipelineEvent",
    "PipelineResources",
    "Protocol",
    "ProtocolDocument",
    "ProtocolMetadata",
    "Speech",
    "SpeechModel",
    "Storage",
    "StorageConfig",
    "create_storage",
    "create_pipeline",
    "load_config",
    "parse_speeches",
    "run_ui",
]
