"""Domain exceptions for the local read-only web API.

Each exception carries a stable machine-readable code, a friendly user message
and an HTTP status. The app translates them into a consistent JSON envelope.
"""

from __future__ import annotations

from typing import Any


class ApiError(Exception):
    """Base class for expected API failures."""

    status_code: int = 500
    code: str = "INTERNAL_ERROR"
    message: str = "服务器内部错误，请稍后重试。"

    def __init__(
        self,
        message: str | None = None,
        *,
        details: Any | None = None,
        code: str | None = None,
        status_code: int | None = None,
    ) -> None:
        if message:
            self.message = message
        if code:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.details = details
        super().__init__(self.message)


class WorkoutNotFoundError(ApiError):
    status_code = 404
    code = "WORKOUT_NOT_FOUND"
    message = "没有找到这场运动，可能尚未同步或已被删除。"


class NoDataError(ApiError):
    status_code = 404
    code = "NO_DATA"
    message = "数据库还没有可展示的健康数据，请先运行 `mi-fitness-bridge sync`。"


class AmbiguousUserError(ApiError):
    status_code = 409
    code = "AMBIGUOUS_USER"
    message = (
        "数据库包含多个账号的数据，无法确定要展示哪一个。"
        "请设置环境变量 MI_FITNESS_WEB_USER_ID 指定账号后重试。"
    )


class DatabaseUnavailableError(ApiError):
    status_code = 503
    code = "DATABASE_UNAVAILABLE"
    message = (
        "本地数据库不存在或无法打开。"
        "请先运行 `mi-fitness-bridge sync` 同步数据，并确认数据库路径正确。"
    )


class DatabaseLockedError(ApiError):
    status_code = 503
    code = "DATABASE_LOCKED"
    message = "数据库正被同步进程占用，请稍后重试。"


class QueryError(ApiError):
    status_code = 500
    code = "QUERY_ERROR"
    message = "读取本地数据时发生错误，请稍后重试。"


class SyncConfirmationError(ApiError):
    status_code = 403
    code = "SYNC_CONFIRMATION_REQUIRED"
    message = "缺少同步确认头，请从本地数据台发起同步。"


class SyncInProgressError(ApiError):
    status_code = 409
    code = "SYNC_IN_PROGRESS"
    message = "已有同步任务正在进行，请等待完成后再试。"


class CredentialsMissingError(ApiError):
    status_code = 409
    code = "CREDENTIALS_MISSING"
    message = "未找到小米账户凭证，请先在终端运行 `mi-fitness-bridge setup`。"


class InvalidDataTypesError(ApiError):
    status_code = 422
    code = "INVALID_DATA_TYPES"
    message = "包含不支持的数据类型，请检查后重试。"
