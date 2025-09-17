import pytest

from bundestag_mine_refactor.config import load_config


def test_environment_values_are_coerced(monkeypatch):
    monkeypatch.setenv("BMR_DIP_PAGE_SIZE", "25")
    monkeypatch.setenv("BMR_DIP_TIMEOUT", "15.5")
    monkeypatch.setenv("BMR_DIP_MAX_RETRIES", "4")
    monkeypatch.setenv("BMR_STORAGE_ECHO_SQL", "true")
    monkeypatch.setenv("BMR_GEMINI_ENABLE_SAFETY_SETTINGS", "false")

    config = load_config()

    assert config.dip.page_size == 25 and isinstance(config.dip.page_size, int)
    assert config.dip.timeout == pytest.approx(15.5)
    assert config.dip.max_retries == 4 and isinstance(config.dip.max_retries, int)
    assert config.storage.echo_sql is True
    assert config.gemini.enable_safety_settings is False


def test_invalid_boolean_environment_value_raises(monkeypatch):
    monkeypatch.setenv("BMR_STORAGE_ECHO_SQL", "definitely")

    with pytest.raises(ValueError):
        load_config()
