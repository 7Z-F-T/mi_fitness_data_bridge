"""Synthetic lifecycle tests for the local web sync coordinator (no network)."""

from __future__ import annotations

import asyncio

import mi_fitness_mcp.web.sync as sync_module
from mi_fitness_mcp.web.sync import SyncCoordinator


class FakeAdapter:
    last_error = None

    def __init__(self, *args, **kwargs):
        pass

    async def connect(self):
        return True

    async def close(self):
        return None


class FakeSyncService:
    calls: list[tuple[str, bool, str]] = []

    def __init__(self, *args, **kwargs):
        pass

    async def sync_data_type(
        self, data_type, force_full=False, *, sync_id=None, source="cli"
    ):
        self.calls.append((data_type, force_full, source))
        return {"status": "ok", "added": 1, "updated": 0, "skipped": 0}


def test_sync_coordinator_runs_background_task_and_invalidates(tmp_path, monkeypatch):
    monkeypatch.setattr(
        sync_module, "load_mi_fitness_token", lambda: ("synthetic-user", "token")
    )
    monkeypatch.setattr(sync_module, "MiFitnessCloudAdapter", FakeAdapter)
    monkeypatch.setattr(sync_module, "SyncService", FakeSyncService)
    FakeSyncService.calls = []

    invalidated: list[bool] = []
    coordinator = SyncCoordinator(
        tmp_path / "sync.db", on_complete=lambda: invalidated.append(True)
    )

    async def run():
        sync_id = await coordinator.start(["sleep"], full=False)
        assert coordinator.is_active is True
        assert coordinator._task is not None
        await coordinator._task
        return sync_id, coordinator.status()

    sync_id, status = asyncio.run(run())

    assert sync_id
    assert status.active is False
    assert status.state == "completed"
    assert status.sync_id == sync_id
    assert FakeSyncService.calls == [("sleep", False, "web")]
    assert invalidated == [True]


def test_sync_coordinator_rejects_missing_credentials(tmp_path, monkeypatch):
    from mi_fitness_mcp.web.exceptions import CredentialsMissingError

    monkeypatch.setattr(sync_module, "load_mi_fitness_token", lambda: (None, None))
    coordinator = SyncCoordinator(tmp_path / "sync-missing.db")

    async def run():
        await coordinator.start()

    try:
        asyncio.run(run())
    except CredentialsMissingError:
        pass
    else:  # pragma: no cover - assertion helper
        raise AssertionError("expected CredentialsMissingError")
