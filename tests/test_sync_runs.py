"""Synthetic tests for per-dataset sync history recording."""

from __future__ import annotations

import asyncio

import pytest

from mi_fitness_mcp.services.sync_service import SyncService
from mi_fitness_mcp.storage import Database


class ConnectedAdapter:
    def is_connected(self) -> bool:
        return True


def test_sync_runs_records_success_and_incremental_default(tmp_path):
    db = Database(tmp_path / "sync-runs.db")
    service = SyncService(ConnectedAdapter(), db)

    async def fake_sync(data_type, start_date, end_date, force_full):
        return {
            "status": "ok",
            "data_type": data_type,
            "added": 2,
            "updated": 3,
            "skipped": 1,
            "start_date": "2026-11-01",
            "end_date": "2026-11-12",
        }

    service._sync_data_type_unlocked = fake_sync

    result = asyncio.run(
        service.sync_data_type("sleep", sync_id="sync-success", source="web")
    )
    assert result["status"] == "ok"

    runs = db.latest_sync_runs()
    assert len(runs) == 1
    run = runs[0]
    assert run["sync_id"] == "sync-success"
    assert run["data_type"] == "sleep"
    assert run["source"] == "web"
    assert run["status"] == "ok"
    assert run["records_added"] == 2
    assert run["records_updated"] == 3
    assert run["records_skipped"] == 1
    assert run["incremental"] == 1
    assert run["requested_start_date"] is None
    assert run["requested_end_date"] is None
    assert run["finished_at"] is not None


def test_sync_runs_records_error_code_without_exception_text(tmp_path):
    db = Database(tmp_path / "sync-runs-error.db")
    service = SyncService(ConnectedAdapter(), db)

    async def failing_sync(data_type, start_date, end_date, force_full):
        raise RuntimeError("synthetic detail that must not be persisted")

    service._sync_data_type_unlocked = failing_sync

    with pytest.raises(RuntimeError):
        asyncio.run(
            service.sync_data_type("workouts", sync_id="sync-error", source="mcp")
        )

    run = db.query_sync_runs()[0]
    assert run["status"] == "error"
    assert run["error_code"] == "RuntimeError"
    assert run["source"] == "mcp"
    assert run["finished_at"] is not None
    assert "synthetic detail" not in str(run)


def test_sync_runs_records_explicit_range_as_non_incremental(tmp_path):
    db = Database(tmp_path / "sync-runs-range.db")
    service = SyncService(ConnectedAdapter(), db)

    async def fake_sync(data_type, start_date, end_date, force_full):
        return {"status": "ok", "added": 0, "updated": 0, "skipped": 0}

    service._sync_data_type_unlocked = fake_sync

    asyncio.run(
        service.sync_data_type(
            "daily_activity",
            start_date="2026-11-01",
            end_date="2026-11-12",
            sync_id="sync-range",
            source="cli",
        )
    )

    run = db.latest_sync_runs()[0]
    assert run["incremental"] == 0
    assert run["requested_start_date"] == "2026-11-01"
    assert run["requested_end_date"] == "2026-11-12"
    assert run["source"] == "cli"
