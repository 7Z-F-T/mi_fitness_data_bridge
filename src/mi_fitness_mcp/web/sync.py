"""Local sync action for the web dashboard.

The query API is read-only. This coordinator is the one deliberate exception:
when the user clicks "同步" in the local UI, it loads credentials from the OS
keyring, contacts Xiaomi, and writes the local cache with the existing sync
service. It never accepts credentials over HTTP.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from mi_fitness_mcp.adapters.mi_fitness_cloud import MiFitnessCloudAdapter
from mi_fitness_mcp.auth import load_mi_fitness_token
from mi_fitness_mcp.config import load_config
from mi_fitness_mcp.services.sync_service import SyncService
from mi_fitness_mcp.storage import Database
from mi_fitness_mcp.web.exceptions import (
    CredentialsMissingError,
    InvalidDataTypesError,
    SyncInProgressError,
)
from mi_fitness_mcp.web.schemas import (
    SyncState,
    SyncStatus,
    SyncStatusItem,
    SyncStatusValue,
)

logger = logging.getLogger(__name__)

SUPPORTED_DATA_TYPES = (
    "daily_activity",
    "heart_rate",
    "body_measurements",
    "sleep",
    "workouts",
    "workout_detail",
    "spo2",
    "stress",
    "abnormal_heart_beat",
)

_VALID_RUN_STATUSES = {"ok", "partial", "error", "running", "cancelled"}


def _legacy_utc(value: Any) -> str | None:
    """Interpret legacy ``CURRENT_TIMESTAMP`` text (UTC, no offset) correctly."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return str(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.isoformat()


class SyncCoordinator:
    """Run at most one background sync from the local web API."""

    def __init__(
        self,
        db_path: Path | str,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self._on_complete = on_complete
        self._task: asyncio.Task[None] | None = None
        self._sync_id: str | None = None
        self._state: SyncState = "idle"
        self._last_error_code: str | None = None
        self._last_error_message: str | None = None

    @property
    def is_active(self) -> bool:
        return bool(self._task and not self._task.done())

    async def start(
        self,
        data_types: list[str] | None = None,
        *,
        full: bool = False,
    ) -> str:
        if self.is_active:
            raise SyncInProgressError()
        if data_types is not None and not data_types:
            raise InvalidDataTypesError("dataTypes 不能为空。")

        requested = list(dict.fromkeys(data_types or SUPPORTED_DATA_TYPES))
        unknown = [item for item in requested if item not in SUPPORTED_DATA_TYPES]
        if unknown:
            raise InvalidDataTypesError(details={"dataTypes": unknown})

        user_id, pass_token = load_mi_fitness_token()
        if not user_id or not pass_token:
            raise CredentialsMissingError()

        sync_id = uuid.uuid4().hex
        self._sync_id = sync_id
        self._state = "running"
        self._last_error_code = None
        self._last_error_message = None
        self._task = asyncio.create_task(
            self._run(sync_id, requested, full, user_id, pass_token)
        )
        return sync_id

    async def _run(
        self,
        sync_id: str,
        data_types: list[str],
        full: bool,
        user_id: str,
        pass_token: str,
    ) -> None:
        adapter: MiFitnessCloudAdapter | None = None
        try:
            config = load_config()
            adapter = MiFitnessCloudAdapter(
                user_id=user_id,
                pass_token=pass_token,
                region=config.region,
            )
            adapter.http_timeout = config.http_timeout_seconds
            adapter.request_retries = config.request_retries
            adapter.max_pages = config.max_pages

            if not await adapter.connect():
                # Do not persist the provider's raw error (it may contain URLs).
                logger.warning("Web sync connect failed: %s", adapter.last_error)
                self._state = "error"
                self._last_error_code = "ADAPTER_CONNECT_FAILED"
                self._last_error_message = (
                    "无法连接小米云，请检查网络、账户地区或重新运行 setup。"
                )
                return

            database = Database(self.db_path)
            sync_service = SyncService(
                adapter,
                database,
                default_lookback_days=config.default_lookback_days,
                chunk_days=config.sync_chunk_days,
            )

            successes = 0
            failures = 0
            for data_type in data_types:
                try:
                    result = await sync_service.sync_data_type(
                        data_type,
                        force_full=full,
                        sync_id=sync_id,
                        source="web",
                    )
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("Web sync failed for %s", data_type)
                    failures += 1
                    continue

                status = result.get("status", "ok")
                if status in {"ok", "partial"}:
                    successes += 1
                if status == "error":
                    failures += 1

            if failures and not successes:
                self._state = "error"
                self._last_error_code = "SYNC_FAILED"
                self._last_error_message = "同步未成功，请查看各数据类型的同步状态。"
            else:
                self._state = "completed"
                self._last_error_code = None
                self._last_error_message = None
        except asyncio.CancelledError:
            self._state = "idle"
            raise
        except Exception:
            logger.exception("Web sync coordinator failed")
            self._state = "error"
            self._last_error_code = "SYNC_INTERNAL_ERROR"
            self._last_error_message = "同步过程中发生错误，请查看同步状态或终端日志。"
        finally:
            if adapter is not None:
                try:
                    await adapter.close()
                except Exception:
                    logger.debug("Failed to close web sync adapter", exc_info=True)
            if self._on_complete is not None:
                try:
                    self._on_complete()
                except Exception:
                    logger.warning(
                        "Failed to invalidate read service after sync", exc_info=True
                    )

    def status(self) -> SyncStatus:
        active = self.is_active
        state: SyncState = "running" if active else self._state
        return SyncStatus(
            active=active,
            sync_id=self._sync_id,
            state=state,
            last_error_code=self._last_error_code,
            last_error_message=self._last_error_message,
            items=self._status_items(),
        )

    def _status_items(self) -> list[SyncStatusItem]:
        runs: dict[str, dict[str, Any]] = {}
        legacy: dict[str, dict[str, Any]] = {}

        path = self.db_path.expanduser()
        if path.is_file():
            try:
                database = Database(path, read_only=True)
            except (FileNotFoundError, sqlite3.OperationalError):
                database = None
            if database is not None:
                try:
                    runs = {
                        row["data_type"]: row
                        for row in database.latest_sync_runs()
                    }
                except sqlite3.OperationalError:
                    runs = {}
                try:
                    legacy = {
                        row["data_type"]: row for row in database.get_sync_states()
                    }
                except sqlite3.OperationalError:
                    legacy = {}

        items: list[SyncStatusItem] = []
        for data_type in SUPPORTED_DATA_TYPES:
            run = runs.get(data_type)
            if run:
                status = str(run.get("status") or "unknown")
                if status not in _VALID_RUN_STATUSES:
                    status = "unknown"
                items.append(
                    SyncStatusItem(
                        data_type=data_type,
                        last_status=cast(SyncStatusValue, status),
                        last_synced_at=run.get("finished_at") or run.get("started_at"),
                        records_added=int(run.get("records_added") or 0),
                        records_updated=int(run.get("records_updated") or 0),
                        records_skipped=int(run.get("records_skipped") or 0),
                        error_code=run.get("error_code"),
                        source=str(run.get("source") or "unknown"),
                        incremental=bool(run.get("incremental")),
                        requested_start_date=run.get("requested_start_date"),
                        requested_end_date=run.get("requested_end_date"),
                    )
                )
                continue

            state = legacy.get(data_type)
            if state and state.get("last_sync_at"):
                items.append(
                    SyncStatusItem(
                        data_type=data_type,
                        last_status="unknown",
                        last_synced_at=_legacy_utc(state.get("last_sync_at")),
                        source="legacy",
                        incremental=True,
                    )
                )
            else:
                items.append(
                    SyncStatusItem(
                        data_type=data_type,
                        last_status="never",
                        source="never",
                        incremental=True,
                    )
                )
        return items

    async def shutdown(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
        self._task = None
        if self._state == "running":
            self._state = "idle"
