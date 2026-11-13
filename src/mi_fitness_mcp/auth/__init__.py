"""Authentication helpers for Mi Fitness cloud API."""

import logging

import keyring

logger = logging.getLogger(__name__)


SERVICE_NAME = "mi-fitness-mcp"
ACCOUNT_NAME = "mi_fitness_auth"
COACH_LLM_ACCOUNTS = {
    "anthropic": "coach_llm_api_key_anthropic",
    "openai_compatible": "coach_llm_api_key_openai_compatible",
}

# Module/class name fragments of keyring backends that store secrets weakly
# or not at all (fail, null, keyrings.alt plaintext/file backends).
_WEAK_BACKEND_MARKERS = ("fail", "null", "plaintext", "keyrings.alt")


def keyring_backend_warning() -> str | None:
    """Return a warning when the active keyring backend is weak, else None.

    Detection is heuristic and never raises: a backend we cannot inspect is
    reported as unknown rather than crashing setup/doctor.
    """
    try:
        backend = keyring.get_keyring()
    except Exception as exc:
        return f"无法确定 keyring 后端（{exc}）；凭据可能不会被安全存储"
    name = f"{type(backend).__module__}.{type(backend).__name__}"
    if any(marker in name.lower() for marker in _WEAK_BACKEND_MARKERS):
        return (
            f"当前 keyring 后端 {name} 不安全（明文存储或不可用）；"
            "passToken 可能以明文落盘，请配置系统钥匙串后重试"
        )
    return None


def save_mi_fitness_token(user_id: str, pass_token: str) -> None:
    try:
        keyring.set_password(SERVICE_NAME, f"{ACCOUNT_NAME}_user_id", user_id)
        keyring.set_password(SERVICE_NAME, f"{ACCOUNT_NAME}_pass_token", pass_token)
    except Exception as exc:
        logger.error("Failed to save Mi Fitness credentials: %s", exc)
        raise


def load_mi_fitness_token() -> tuple[str | None, str | None]:
    try:
        user_id = keyring.get_password(SERVICE_NAME, f"{ACCOUNT_NAME}_user_id")
        pass_token = keyring.get_password(SERVICE_NAME, f"{ACCOUNT_NAME}_pass_token")
        return user_id, pass_token
    except Exception as exc:
        logger.error("Failed to load Mi Fitness credentials: %s", exc)
        return None, None


def mask_account_id(value: str | None) -> str | None:
    """统一的账号标识掩码：固定 6 个星号，只保留末 2 位。

    长度 ≤2 的输入全掩码（不保留任何字符）；空值/None 返回 None。
    server 与 CLI 必须使用同一个掩码格式，避免两处输出不一致泄露长度信息。
    """
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    if len(value) <= 2:
        return "*" * 6
    return f"{'*' * 6}{value[-2:]}"


def delete_mi_fitness_token() -> None:
    try:
        keyring.delete_password(SERVICE_NAME, f"{ACCOUNT_NAME}_user_id")
    except keyring.errors.PasswordDeleteError:
        pass
    except Exception as exc:
        logger.error("Failed to delete Mi Fitness user_id: %s", exc)
    try:
        keyring.delete_password(SERVICE_NAME, f"{ACCOUNT_NAME}_pass_token")
    except keyring.errors.PasswordDeleteError:
        pass
    except Exception as exc:
        logger.error("Failed to delete Mi Fitness passToken: %s", exc)


def _coach_llm_account(provider: str) -> str:
    try:
        return COACH_LLM_ACCOUNTS[provider]
    except KeyError as exc:
        raise ValueError(f"Unsupported coach LLM provider: {provider}") from exc


def save_coach_llm_api_key(provider: str, api_key: str) -> None:
    """Store an optional coach provider key in the OS keyring.

    The key is never written to config.json, CLI arguments, MCP arguments,
    HTTP responses, logs, or environment-variable fallbacks.
    """
    account = _coach_llm_account(provider)
    keyring.set_password(SERVICE_NAME, account, api_key)


def load_coach_llm_api_key(provider: str) -> str | None:
    account = _coach_llm_account(provider)
    try:
        return keyring.get_password(SERVICE_NAME, account)
    except Exception as exc:
        # Never include the secret value; the provider name is enough for diagnosis.
        logger.error("Failed to load coach LLM key for %s: %s", provider, exc)
        return None


def coach_llm_key_configured(provider: str) -> bool:
    return bool(load_coach_llm_api_key(provider))


def delete_coach_llm_api_key(provider: str) -> None:
    account = _coach_llm_account(provider)
    try:
        keyring.delete_password(SERVICE_NAME, account)
    except keyring.errors.PasswordDeleteError:
        pass
    except Exception as exc:
        logger.error("Failed to delete coach LLM key for %s: %s", provider, exc)
