"""Application configuration helpers for the Mine pipeline."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path
import types
from typing import Any, Dict, Optional, Type, TypeVar, Union, get_args, get_origin, get_type_hints


_DEFAULT_CONFIG_LOCATIONS = (
    Path("mine.json"),
    Path.home() / ".config" / "mine" / "config.json",
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
    enable_safety_settings: bool = False


@dataclass(slots=True)
class StorageConfig:
    """Configuration for the local SQLite database."""

    database_url: str = "sqlite:///mine.db"
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


T = TypeVar("T")


def _coerce_value(value: Any, annotation: Any) -> Any:
    """Best-effort conversion of ``value`` to match ``annotation``."""

    if value is None:
        return None

    origin = get_origin(annotation)
    if origin in (Union, types.UnionType):
        args = [arg for arg in get_args(annotation) if arg is not type(None)]  # noqa: E721 - allow Optional
        if not args:
            return None
        last_error: Exception | None = None
        for candidate in args:
            try:
                return _coerce_value(value, candidate)
            except (TypeError, ValueError) as exc:
                last_error = exc
        raise ValueError(f"Cannot convert {value!r} to {annotation}") from last_error

    target_type = origin or annotation

    if target_type in {Any, object}:
        return value

    if target_type is bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "y", "on"}:
                return True
            if normalized in {"false", "0", "no", "n", "off"}:
                return False
        if isinstance(value, (int, float)):
            return bool(value)
        raise ValueError(f"Cannot convert {value!r} to bool")

    if target_type is int:
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        if isinstance(value, (float, str)):
            return int(float(value))
        raise ValueError(f"Cannot convert {value!r} to int")

    if target_type is float:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            return float(value)
        raise ValueError(f"Cannot convert {value!r} to float")

    if target_type is str:
        if isinstance(value, str):
            return value
        return str(value)

    return value


def _dataclass_from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
    """Create dataclass ``cls`` while coercing ``data`` to the proper types."""

    kwargs: Dict[str, Any] = {}
    type_hints = get_type_hints(cls)
    for field in fields(cls):
        if field.name not in data:
            continue
        try:
            annotation = type_hints.get(field.name, field.type)
            kwargs[field.name] = _coerce_value(data[field.name], annotation)
        except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
            raise ValueError(
                f"Invalid value for {cls.__name__}.{field.name}: {data[field.name]!r}"
            ) from exc
    return cls(**kwargs)


def resolve_config_path(explicit_path: Optional[Path] = None) -> Path:
    """Return the effective configuration file path.

    If ``explicit_path`` is provided it is returned verbatim. Otherwise the
    function checks the default locations in order. The first existing file is
    used; if none are present the function falls back to the last default path
    (``~/.config/mine/config.json``).
    """

    if explicit_path:
        return explicit_path

    for candidate in _DEFAULT_CONFIG_LOCATIONS:
        if candidate.exists():
            return candidate

    # Prefer the XDG-style location for newly created configuration files.
    return _DEFAULT_CONFIG_LOCATIONS[-1]


def load_config(explicit_path: Optional[Path] = None) -> AppConfig:
    """Create the application configuration.

    The function combines default values, optional configuration files and
    environment variables (``MINE_*``) into a single :class:`AppConfig` instance.
    Environment variable names are expected to use the format
    ``MINE_SECTION_FIELD`` (e.g. ``MINE_DIP_API_KEY``).
    """

    base = {
        "dip": asdict(DIPConfig()),
        "gemini": asdict(GeminiConfig()),
        "storage": asdict(StorageConfig()),
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

    dip_data = _merge_dict(merged.get("dip", {}), _load_from_env("MINE_DIP_"))
    gemini_data = _merge_dict(merged.get("gemini", {}), _load_from_env("MINE_GEMINI_"))
    storage_data = _merge_dict(merged.get("storage", {}), _load_from_env("MINE_STORAGE_"))

    return AppConfig(
        dip=_dataclass_from_dict(DIPConfig, dip_data),
        gemini=_dataclass_from_dict(GeminiConfig, gemini_data),
        storage=_dataclass_from_dict(StorageConfig, storage_data),
    )


def save_config(config: AppConfig, path: Optional[Path] = None) -> Path:
    """Persist ``config`` as JSON and return the target path."""

    target = resolve_config_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "dip": asdict(config.dip),
        "gemini": asdict(config.gemini),
        "storage": asdict(config.storage),
    }
    with target.open("w", encoding="utf8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    return target


__all__ = [
    "AppConfig",
    "DIPConfig",
    "GeminiConfig",
    "StorageConfig",
    "load_config",
    "resolve_config_path",
    "save_config",
]
