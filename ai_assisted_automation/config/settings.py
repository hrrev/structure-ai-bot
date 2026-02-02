"""Configuration loading: YAML file -> env vars -> Pydantic defaults."""

import os
from pathlib import Path

import yaml
from pydantic import BaseModel


class LLMConfig(BaseModel):
    provider: str = "anthropic"
    model: str = "claude-opus-4-5-20251101"
    api_key: str = ""
    host_url: str | None = None
    max_tokens: int = 16384
    thinking_budget: int = 8000

    # # OpenAI configuration:
    # provider: str = "openai"
    # model: str = "gpt-5.2"
    # host_url: str | None = "https://api.openai.com/v1"


class Settings(BaseModel):
    llm: LLMConfig = LLMConfig()


_ENV_MAP: dict[str, tuple[str, type]] = {
    "AAA_LLM_PROVIDER": ("provider", str),
    "AAA_LLM_MODEL": ("model", str),
    "AAA_LLM_API_KEY": ("api_key", str),
    "AAA_LLM_HOST_URL": ("host_url", str),
    "AAA_LLM_MAX_TOKENS": ("max_tokens", int),
    "AAA_LLM_THINKING_BUDGET": ("thinking_budget", int),
}


def load_settings(config_path: str | None = None) -> Settings:
    """Load settings: YAML file -> env var overrides -> Pydantic defaults."""
    yaml_data: dict = {}

    # 1. Resolve config file path
    path = _resolve_config_path(config_path)
    if path and path.is_file():
        with open(path) as f:
            yaml_data = yaml.safe_load(f) or {}

    # 2. Build settings from YAML (or defaults)
    settings = Settings.model_validate(yaml_data) if yaml_data else Settings()

    # 3. Override with env vars
    llm_overrides: dict = {}
    for env_key, (field_name, field_type) in _ENV_MAP.items():
        val = os.environ.get(env_key)
        if val is not None:
            llm_overrides[field_name] = field_type(val)

    if llm_overrides:
        merged = settings.llm.model_dump()
        merged.update(llm_overrides)
        settings.llm = LLMConfig.model_validate(merged)

    return settings


def _resolve_config_path(explicit_path: str | None) -> Path | None:
    if explicit_path:
        return Path(explicit_path)

    env_path = os.environ.get("AAA_CONFIG_FILE")
    if env_path:
        return Path(env_path)

    # Default: config/config.yaml relative to package
    pkg_dir = Path(__file__).parent
    default = pkg_dir / "config.yaml"
    if default.is_file():
        return default

    return None
