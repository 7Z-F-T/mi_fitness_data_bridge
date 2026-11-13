"""Configuration management for Mi Fitness MCP."""

import ipaddress
import json
import os
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from platformdirs import user_config_dir, user_data_dir, user_log_dir
from pydantic import BaseModel, ConfigDict, Field, field_validator

ENV_DB_PATH = "MI_FITNESS_DB_PATH"


def _default_database_path() -> Path:
    return Path(user_data_dir("mi-fitness-mcp")) / "mi_fitness.db"


def _default_logs_path() -> Path:
    return Path(user_log_dir("mi-fitness-mcp")) / "mi_fitness.log"


def _is_loopback_host(host: str | None) -> bool:
    if not host:
        return False
    normalized = host.strip().lower()
    if normalized == "localhost" or normalized.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


class CoachLLMConfig(BaseModel):
    """Non-secret coach LLM settings.

    API keys live in the OS keyring, never in this model or config.json.
    Remote consent is recorded here only by the interactive ``coach setup``
    command; the web API never writes it.
    """

    provider: Literal["anthropic", "openai_compatible"] = "anthropic"
    model: str = Field(default="claude-opus-5-5", min_length=1, max_length=200)
    base_url: str | None = None
    timeout_seconds: float = Field(default=180.0, gt=0, le=600)
    max_output_tokens: int = Field(default=16000, ge=256, le=64000)
    max_retries: int = Field(default=1, ge=0, le=5)
    temperature: float = Field(default=0.3, ge=0, le=2)
    remote_consent_at: str | None = None
    remote_consent_provider: str | None = None
    remote_consent_host: str | None = None
    remote_consent_fingerprint: str | None = None
    anthropic_fallback_models: list[str] = Field(default_factory=list)

    @field_validator("base_url")
    @classmethod
    def _validate_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().rstrip("/")
        if not value:
            return None
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("base_url must use http or https")
        if not parsed.hostname:
            raise ValueError("base_url must include a host")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("base_url must not include credentials")
        if parsed.query or parsed.fragment:
            raise ValueError("base_url must not include a query or fragment")
        if not _is_loopback_host(parsed.hostname) and parsed.scheme != "https":
            raise ValueError("non-local base_url must use https")
        return value


class CoachConfig(BaseModel):
    enabled: bool = False
    language: Literal["zh-CN", "en"] = "zh-CN"
    profile_weeks: int = Field(default=8, ge=4, le=52)
    default_plan_weeks: int = Field(default=8, ge=4, le=24)
    allow_deterministic_fallback: bool = True
    llm: CoachLLMConfig = Field(default_factory=CoachLLMConfig)


class Config(BaseModel):
    mode: Literal["mi_fitness_cloud", "not_configured"] = "not_configured"
    region: str = "cn"
    timezone: str = Field(default="UTC")
    database_path: Path = Field(default_factory=_default_database_path)
    logs_path: Path = Field(default_factory=_default_logs_path)
    auto_sync_on_start: bool = True
    stale_after_minutes: int = 60
    default_lookback_days: int = Field(default=30, ge=1, le=3650)
    sync_chunk_days: int = Field(default=7, ge=1, le=90)
    http_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    request_retries: int = Field(default=3, ge=1, le=10)
    health_check_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    sync_type_timeout_seconds: float = Field(default=180.0, gt=0, le=3600)
    max_pages: int = Field(default=200, ge=1, le=5000)
    coach: CoachConfig = Field(default_factory=CoachConfig)

    model_config = ConfigDict(arbitrary_types_allowed=True)


def get_config_dir() -> Path:
    # No mkdir here: reading configuration must not write to the user profile.
    # save_config() creates the directory when the user explicitly runs setup.
    return Path(user_config_dir("mi-fitness-mcp"))


def get_config_path() -> Path:
    return get_config_dir() / "config.json"


def resolve_database_path(cli_path: str | Path | None = None) -> Path | None:
    """Resolve a database path override: CLI option beats the environment variable.

    Returns None when neither is set, meaning the configured/default path applies.
    """
    if cli_path:
        return Path(cli_path)
    env_value = os.environ.get(ENV_DB_PATH)
    if env_value:
        return Path(env_value)
    return None


def load_config() -> Config:
    config_path = get_config_path()
    if not config_path.exists():
        # Do not persist anything implicitly; interactive setup commands are
        # the only writers.
        return Config()

    with open(config_path, encoding="utf-8") as f:
        data = json.load(f)

    if "database_path" in data and isinstance(data["database_path"], str):
        data["database_path"] = Path(data["database_path"])
    if "logs_path" in data and isinstance(data["logs_path"], str):
        data["logs_path"] = Path(data["logs_path"])

    return Config(**data)


def save_config(config: Config) -> None:
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    data = config.model_dump()
    data["database_path"] = str(data["database_path"])
    data["logs_path"] = str(data["logs_path"])

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
