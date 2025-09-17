"""Application configuration helpers for the refactored Bundestags-Mine pipeline."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


_DEFAULT_CONFIG_LOCATIONS = (
    Path("bundestag_mine_refactor.json"),
    Path.home() / ".config" / "bundestag_mine_refactor" / "config.json",
)


@dataclass(slots=True)
class DIPConfig:
    """Configuration for the Bundestag DIP API."""

    base_url: str = "https://search.dip.bundestag.de/api/v1"
    api_key: Optional[str] = None
    timeout: float = 30.0
    max_retries: int = 3
    page_size: int = 100


@dataclass(slots=True)
class GeminiConfig:
    """Configuration for the Gemini 2.5 Pro API."""

    api_key: Optional[str] = None
    base_url: str = "https://generativelanguage.googleapis.com"
    model: str = "gemini-2.5-pro"
    timeout: float = 120.0
    max_retries: int = 3
    enable_safety_settings: bool = True


@dataclass(slots=True)
class StorageConfig:
    """Configuration for the local SQLite database."""

    database_url: str = "sqlite:///bundestag_mine.db"
    echo_sql: bool = False


@dataclass(slots=True)
class AppConfig:
    """High level application configuration."""

    dip: DIPConfig
    gemini: GeminiConfig
    storage: StorageConfig


def _load_from_env(prefix: str) -> Dict[str, Any]:
    """Load configuration entries for ``prefix`` from the environment."""

    data: Dict[str, Any] = {}
    for key, value in os.environ.items():
        if key.startswith(prefix):
            normalized_key = key.removeprefix(prefix)
            data[normalized_key.lower()] = value
    return data


def _merge_dict(target: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    merged = target.copy()
    merged.update({k: v for k, v in updates.items() if v is not None})
    return merged


def _load_config_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf8") as fh:
        return json.load(fh)


def load_config(explicit_path: Optional[Path] = None) -> AppConfig:
    """Create the application configuration.

    The function combines default values, optional configuration files and
    environment variables (``BMR_*``) into a single :class:`AppConfig` instance.
    Environment variable names are expected to use the format
    ``BMR_SECTION_FIELD`` (e.g. ``BMR_DIP_API_KEY``).
    """

    base = {
        "dip": DIPConfig().__dict__,
        "gemini": GeminiConfig().__dict__,
        "storage": StorageConfig().__dict__,
    }

    file_data: Dict[str, Any] = {}
    if explicit_path:
        file_data = _load_config_file(explicit_path)
    else:
        for candidate in _DEFAULT_CONFIG_LOCATIONS:
            file_data = _load_config_file(candidate)
            if file_data:
                break

    merged = _merge_dict(base, file_data)

    dip_data = _merge_dict(merged.get("dip", {}), _load_from_env("BMR_DIP_"))
    gemini_data = _merge_dict(merged.get("gemini", {}), _load_from_env("BMR_GEMINI_"))
    storage_data = _merge_dict(merged.get("storage", {}), _load_from_env("BMR_STORAGE_"))

    return AppConfig(
        dip=DIPConfig(**dip_data),
        gemini=GeminiConfig(**gemini_data),
        storage=StorageConfig(**storage_data),
    )


__all__ = ["AppConfig", "DIPConfig", "GeminiConfig", "StorageConfig", "load_config"]
