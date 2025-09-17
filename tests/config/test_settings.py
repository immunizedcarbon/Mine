import json

import pytest

import mine.config.settings as config_settings
from mine.config import (
    AppConfig,
    DIPConfig,
    GeminiConfig,
    StorageConfig,
    load_config,
    resolve_config_path,
    save_config,
)


def test_environment_values_are_coerced(monkeypatch):
    monkeypatch.setenv("MINE_DIP_PAGE_SIZE", "25")
    monkeypatch.setenv("MINE_DIP_TIMEOUT", "15.5")
    monkeypatch.setenv("MINE_DIP_MAX_RETRIES", "4")
    monkeypatch.setenv("MINE_STORAGE_ECHO_SQL", "true")
    monkeypatch.setenv("MINE_GEMINI_ENABLE_SAFETY_SETTINGS", "false")

    config = load_config()

    assert config.dip.page_size == 25 and isinstance(config.dip.page_size, int)
    assert config.dip.timeout == pytest.approx(15.5)
    assert config.dip.max_retries == 4 and isinstance(config.dip.max_retries, int)
    assert config.storage.echo_sql is True
    assert config.gemini.enable_safety_settings is False


def test_invalid_boolean_environment_value_raises(monkeypatch):
    monkeypatch.setenv("MINE_STORAGE_ECHO_SQL", "definitely")

    with pytest.raises(ValueError):
        load_config()


def test_resolve_config_path_prefers_existing_file(tmp_path, monkeypatch):
    first = tmp_path / "mine.json"
    second = tmp_path / "config.json"
    monkeypatch.setattr(config_settings, "_DEFAULT_CONFIG_LOCATIONS", (first, second))

    # without existing files we expect the XDG-style location (second entry)
    resolved_without_file = resolve_config_path(None)
    assert resolved_without_file == second

    second.write_text("{}", encoding="utf8")
    resolved = resolve_config_path(None)
    assert resolved == second
    explicit = resolve_config_path(first)
    assert explicit == first


def test_save_config_writes_json(tmp_path, monkeypatch):
    target = tmp_path / "settings" / "mine.json"
    monkeypatch.setattr(config_settings, "_DEFAULT_CONFIG_LOCATIONS", (target, target))

    config = AppConfig(
        dip=DIPConfig(api_key="ABC123", page_size=25),
        gemini=GeminiConfig(api_key=None, model="gemini-demo"),
        storage=StorageConfig(database_url="sqlite:///demo.db", echo_sql=True),
    )

    saved_path = save_config(config)
    assert saved_path == target
    data = json.loads(target.read_text(encoding="utf8"))
    assert data["dip"]["api_key"] == "ABC123"
    assert data["dip"]["page_size"] == 25
    assert data["gemini"]["model"] == "gemini-demo"
    assert data["storage"]["database_url"] == "sqlite:///demo.db"
    assert data["storage"]["echo_sql"] is True
