"""Tests for config/settings.py."""

import os

import yaml

from ai_assisted_automation.config.settings import LLMConfig, Settings, load_settings


def test_defaults_when_no_file_or_env(monkeypatch, tmp_path):
    """Default settings when no config file or env vars exist."""
    # Point to nonexistent config file
    monkeypatch.setenv("AAA_CONFIG_FILE", str(tmp_path / "nonexistent.yaml"))
    # Clear any LLM env vars
    for key in ("AAA_LLM_PROVIDER", "AAA_LLM_MODEL", "AAA_LLM_API_KEY", "AAA_LLM_HOST_URL"):
        monkeypatch.delenv(key, raising=False)

    settings = load_settings(config_path=str(tmp_path / "nonexistent.yaml"))
    assert settings.llm.provider == "anthropic"
    assert settings.llm.model == "claude-opus-4-5-20251101"
    assert settings.llm.api_key == ""
    assert settings.llm.host_url is None
    assert settings.llm.max_tokens == 16384
    assert settings.llm.thinking_budget == 8000


def test_yaml_file_overrides_defaults(tmp_path, monkeypatch):
    """YAML config file values override Pydantic defaults."""
    for key in ("AAA_LLM_PROVIDER", "AAA_LLM_MODEL", "AAA_LLM_API_KEY"):
        monkeypatch.delenv(key, raising=False)

    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump({
        "llm": {
            "provider": "openai",
            "model": "gpt-5.2",
            "api_key": "sk-from-yaml",
            "max_tokens": 8192,
        }
    }))

    settings = load_settings(config_path=str(config_file))
    assert settings.llm.provider == "openai"
    assert settings.llm.model == "gpt-5.2"
    assert settings.llm.api_key == "sk-from-yaml"
    assert settings.llm.max_tokens == 8192
    # Unset fields keep defaults
    assert settings.llm.thinking_budget == 8000


def test_env_vars_override_yaml(tmp_path, monkeypatch):
    """Env vars take priority over YAML file values."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump({
        "llm": {
            "provider": "openai",
            "model": "gpt-5.2",
            "api_key": "sk-from-yaml",
        }
    }))

    monkeypatch.setenv("AAA_LLM_API_KEY", "sk-from-env")
    monkeypatch.setenv("AAA_LLM_MODEL", "gpt-5.2-turbo")

    settings = load_settings(config_path=str(config_file))
    # Env vars win
    assert settings.llm.api_key == "sk-from-env"
    assert settings.llm.model == "gpt-5.2-turbo"
    # YAML still applies where env not set
    assert settings.llm.provider == "openai"


def test_env_var_config_file_path(tmp_path, monkeypatch):
    """AAA_CONFIG_FILE env var points to config file."""
    config_file = tmp_path / "custom.yaml"
    config_file.write_text(yaml.dump({"llm": {"model": "custom-model"}}))
    monkeypatch.setenv("AAA_CONFIG_FILE", str(config_file))
    for key in ("AAA_LLM_PROVIDER", "AAA_LLM_MODEL", "AAA_LLM_API_KEY"):
        monkeypatch.delenv(key, raising=False)

    settings = load_settings()
    assert settings.llm.model == "custom-model"
