"""Synthetic tests for the local read-only web API.

All records are generated here; no real account, database or network is used.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from mi_fitness_mcp.models import (
    DailyActivity,
    GpsPoint,
    HeartRateSample,
    SleepSession,
    SleepStage,
    Workout,
    WorkoutSample,
)
from mi_fitness_mcp.storage import Database
from mi_fitness_mcp.web.app import create_app
from mi_fitness_mcp.web.dependencies import get_sync_coordinator
from mi_fitness_mcp.web.schemas import SyncStatus, SyncStatusItem

USER_ID = "synthetic-web-user"
DATE = "2026-11-12"


def _base(user_id: str = USER_ID) -> dict[str, str]:
    return {
        "provider": "mi_fitness",
        "source_type": "cloud_session",
        "user_id": user_id,
    }


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "mi_fitness.db"
    db = Database(path)
    base = _base()

    db.insert_daily_activity(
        DailyActivity(
            id="activity-1",
            date=DATE,
            steps=8000,
            distance_m=6000.0,
            active_kcal=300.0,
            **base,
        )
    )
    db.insert_sleep_session(
        SleepSession(
            id="sleep-1",
            sleep_id="sleep-1",
            start_at=datetime(2026, 11, 11, 23, 20),
            end_at=datetime(2026, 11, 12, 7, 5),
            duration_minutes=465,
            time_asleep_minutes=441,
            time_awake_minutes=24,
            sleep_score=86,
            is_nap=False,
            stages=[
                SleepStage(stage="deep", minutes=82),
                SleepStage(stage="light", minutes=271),
                SleepStage(stage="rem", minutes=88),
                SleepStage(stage="awake", minutes=24),
            ],
            sleep_score_source="sleep_record",
            **base,
        )
    )
    db.insert_workout(
        Workout(
            id="workout-1",
            workout_id="workout-1",
            activity_type="outdoor_running",
            start_at=datetime(2026, 11, 12, 7, 0),
            end_at=datetime(2026, 11, 12, 7, 47),
            duration_minutes=47,
            distance_m=9650.0,
            calories_kcal=513.0,
            avg_heart_rate_bpm=151,
            max_heart_rate_bpm=167,
            avg_pace_sec_per_km=292.0,
            avg_speed_mps=3.42,
            avg_cadence=169,
            avg_stride=108,
            **base,
        )
    )
    db.insert_workout_detail_samples(
        [
            WorkoutSample(
                id="sample-1",
                workout_id="workout-1",
                offset_seconds=0,
                timestamp=datetime(2026, 11, 12, 7, 0),
                heart_rate_bpm=130,
                cadence=168,
                pace_sec_per_km=300.0,
                speed_mps=3.33,
                altitude_m=40.0,
                distance_m=0.0,
                **base,
            ),
            WorkoutSample(
                id="sample-2",
                workout_id="workout-1",
                offset_seconds=1,
                timestamp=datetime(2026, 11, 12, 7, 0, 1),
                heart_rate_bpm=131,
                cadence=169,
                pace_sec_per_km=299.0,
                speed_mps=3.34,
                altitude_m=41.0,
                distance_m=3.3,
                **base,
            ),
        ]
    )
    db.insert_workout_gps_points(
        [
            GpsPoint(
                id="gps-1",
                workout_id="workout-1",
                offset_seconds=0,
                timestamp=datetime(2026, 11, 12, 7, 0),
                latitude=31.2304,
                longitude=121.4737,
                altitude_m=40.0,
                speed_mps=3.33,
                **base,
            )
        ]
    )
    db.insert_heart_rate_samples(
        [
            HeartRateSample(
                id="hr-1",
                timestamp=datetime(2026, 11, 12, 6, 0),
                bpm=60,
                sample_type="resting",
                **base,
            ),
            HeartRateSample(
                id="hr-2",
                timestamp=datetime(2026, 11, 12, 12, 0),
                bpm=80,
                sample_type="passive",
                **base,
            ),
        ]
    )
    return path


@pytest.fixture
def client(db_path):
    app = create_app(db_path=db_path)
    with TestClient(app) as test_client:
        yield test_client


def _assert_json(response):
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers.get("x-request-id")


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    _assert_json(response)
    assert response.json() == {"status": "ok", "database": "ok"}


def test_home_uses_camel_case_and_real_shapes(client):
    response = client.get("/api/home", params={"date": DATE})
    assert response.status_code == 200
    _assert_json(response)
    data = response.json()

    assert data["date"] == DATE
    assert data["activity"]["steps"] == 8000
    assert data["activity"]["totalKcal"] is None
    assert data["sleep"]["sleepScore"] == 86
    assert data["sleep"]["scoreSource"] == "sleep_record"
    assert data["sleep"]["isNap"] is False
    assert len(data["sleep"]["stages"]) == 4
    assert data["restingHeartRate"] == 60
    assert data["latestHeartRate"] == 80
    assert len(data["hrSamples"]) == 2
    assert data["hrSamples"][0]["sampleType"] == "resting"
    assert len(data["weeklyActivity"]) == 7
    assert data["weeklyActivity"][-1]["date"] == DATE
    assert data["recentWorkouts"][0]["workoutId"] == "workout-1"
    assert data["recentWorkouts"][0]["avgStride"] == 108


def test_workouts_list_and_detail(client):
    response = client.get("/api/workouts", params={"limit": 1})
    assert response.status_code == 200
    _assert_json(response)
    workouts = response.json()
    assert len(workouts) == 1
    assert workouts[0]["workoutId"] == "workout-1"
    assert workouts[0]["activityType"] == "outdoor_running"

    response = client.get("/api/workouts/workout-1")
    assert response.status_code == 200
    data = response.json()
    assert data["workout"]["workoutId"] == "workout-1"
    assert len(data["samples"]) == 2
    assert data["samples"][0]["heartRateBpm"] == 130
    assert data["samples"][0]["offsetSeconds"] == 0
    assert len(data["gps"]) == 1
    assert data["gps"][0]["latitude"] == pytest.approx(31.2304)


def test_workout_summary(client):
    response = client.get(
        "/api/workouts/summary",
        params={"range": "month", "anchor": DATE},
    )
    assert response.status_code == 200
    _assert_json(response)
    data = response.json()

    assert data["range"] == "month"
    assert data["anchor"] == DATE
    assert data["totals"]["workouts"] == 1
    assert data["totals"]["durationMinutes"] == 47
    assert data["totals"]["distanceM"] == pytest.approx(9650.0)
    assert data["totals"]["avgHeartRateBpm"] == 151
    assert len(data["buckets"]) == 30
    assert data["buckets"][11]["workouts"] == 1
    assert data["byType"][0]["type"] == "running"
    assert len(data["workouts"]) == 1


def test_goals_is_empty_but_valid(client):
    response = client.get("/api/goals")
    assert response.status_code == 200
    _assert_json(response)
    assert response.json() == []


def test_workout_not_found_uses_error_envelope(client):
    response = client.get("/api/workouts/missing-workout")
    assert response.status_code == 404
    _assert_json(response)
    payload = response.json()
    assert payload["error"]["code"] == "WORKOUT_NOT_FOUND"
    assert payload["error"]["message"]
    assert payload["error"]["requestId"]
    assert payload["error"]["requestId"] == response.headers["x-request-id"]


def test_invalid_date_returns_422(client):
    response = client.get("/api/home", params={"date": "2026-13-01"})
    assert response.status_code == 422
    _assert_json(response)
    payload = response.json()
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert payload["error"]["details"]
    assert "日期格式" in payload["error"]["details"][0]["message"]


def test_only_get_and_post_are_exposed(client):
    response = client.post("/api/home")
    assert response.status_code == 405
    _assert_json(response)
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"

    openapi = client.get("/openapi.json").json()
    http_methods = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
    methods = {
        method
        for path in openapi["paths"].values()
        for method in path
        if method in http_methods
    }
    assert methods <= {"get", "post"}
    assert "post" in openapi["paths"]["/api/sync"]
    assert "/api/home" in openapi["paths"]


def test_cors_preflight_for_local_frontend(client):
    response = client.options(
        "/api/home",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"]
        == "http://127.0.0.1:5173"
    )


def test_missing_database_returns_503(tmp_path):
    app = create_app(db_path=tmp_path / "missing.db")
    with TestClient(app) as client:
        response = client.get("/api/home")
        health = client.get("/api/health")
        goals = client.get("/api/goals")
    assert response.status_code == 503
    _assert_json(response)
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert health.status_code == 503
    assert goals.status_code == 200
    assert goals.json() == []


def test_ambiguous_users_can_be_resolved_with_environment(db_path, monkeypatch):
    db = Database(db_path)
    db.insert_daily_activity(
        DailyActivity(
            id="activity-2",
            date=DATE,
            steps=1000,
            distance_m=800.0,
            active_kcal=50.0,
            **_base("other-user"),
        )
    )

    app = create_app(db_path=db_path)
    with TestClient(app) as client:
        response = client.get("/api/home", params={"date": DATE})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "AMBIGUOUS_USER"

    monkeypatch.setenv("MI_FITNESS_WEB_USER_ID", USER_ID)
    app = create_app(db_path=db_path)
    with TestClient(app) as client:
        response = client.get("/api/home", params={"date": DATE})
    assert response.status_code == 200
    assert response.json()["activity"]["steps"] == 8000


def test_read_only_database_does_not_allow_writes(db_path):
    read_only = Database(db_path, read_only=True)
    rows = read_only.query_daily_activity(USER_ID, DATE, DATE)
    assert rows[0]["steps"] == 8000

    with pytest.raises(sqlite3.OperationalError):
        read_only.insert_daily_activity(
            DailyActivity(
                id="activity-3",
                date="2026-11-13",
                steps=1,
                distance_m=1.0,
                active_kcal=1.0,
                **_base(),
            )
        )


def test_read_only_database_missing_file(tmp_path):
    read_only = Database(tmp_path / "missing.db", read_only=True)
    with pytest.raises(FileNotFoundError):
        read_only.ping()


def test_sync_status_lists_all_types_as_never_before_first_sync(client):
    response = client.get("/api/sync/status")
    assert response.status_code == 200
    _assert_json(response)
    data = response.json()
    assert data["active"] is False
    assert len(data["items"]) == 9
    assert {item["lastStatus"] for item in data["items"]} == {"never"}
    assert all(item["lastSyncedAt"] is None for item in data["items"])


def test_sync_status_reads_latest_sync_run(db_path):
    db = Database(db_path)
    run_id = db.start_sync_run(
        sync_id="synthetic-sync",
        data_type="sleep",
        source="cli",
        incremental=True,
    )
    db.finish_sync_run(
        run_id,
        "ok",
        added=5,
        updated=1,
        skipped=2,
    )

    app = create_app(db_path=db_path)
    with TestClient(app) as client:
        response = client.get("/api/sync/status")
    assert response.status_code == 200
    items = {item["dataType"]: item for item in response.json()["items"]}
    item = items["sleep"]
    assert item["lastStatus"] == "ok"
    assert item["recordsAdded"] == 5
    assert item["recordsUpdated"] == 1
    assert item["recordsSkipped"] == 2
    assert item["source"] == "cli"
    assert item["incremental"] is True
    assert item["lastSyncedAt"]


def test_sync_status_falls_back_to_legacy_watermark(db_path):
    db = Database(db_path)
    db.update_sync_state("sleep")

    app = create_app(db_path=db_path)
    with TestClient(app) as client:
        response = client.get("/api/sync/status")
    assert response.status_code == 200
    items = {item["dataType"]: item for item in response.json()["items"]}
    assert items["sleep"]["lastStatus"] == "unknown"
    assert items["sleep"]["source"] == "legacy"
    assert items["sleep"]["lastSyncedAt"]


def test_sync_requires_confirmation_header(client):
    response = client.post("/api/sync", json={"full": False})
    assert response.status_code == 403
    _assert_json(response)
    assert response.json()["error"]["code"] == "SYNC_CONFIRMATION_REQUIRED"


def test_sync_rejects_unknown_data_types(client):
    response = client.post(
        "/api/sync",
        headers={"X-Mi-Fitness-Confirm": "sync"},
        json={"dataTypes": ["invented"]},
    )
    assert response.status_code == 422
    _assert_json(response)
    assert response.json()["error"]["code"] == "INVALID_DATA_TYPES"


def test_sync_rejects_empty_data_types(client):
    response = client.post(
        "/api/sync",
        headers={"X-Mi-Fitness-Confirm": "sync"},
        json={"dataTypes": []},
    )
    assert response.status_code == 422
    _assert_json(response)
    assert response.json()["error"]["code"] == "INVALID_DATA_TYPES"


def test_sync_rejects_credentials_in_body(client):
    response = client.post(
        "/api/sync",
        headers={"X-Mi-Fitness-Confirm": "sync"},
        json={"passToken": "must-not-be-accepted"},
    )
    assert response.status_code == 422
    _assert_json(response)
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_sync_missing_keyring_credentials(client, monkeypatch):
    monkeypatch.setattr(
        "mi_fitness_mcp.web.sync.load_mi_fitness_token", lambda: (None, None)
    )
    response = client.post(
        "/api/sync",
        headers={"X-Mi-Fitness-Confirm": "sync"},
        json={"full": False},
    )
    assert response.status_code == 409
    _assert_json(response)
    assert response.json()["error"]["code"] == "CREDENTIALS_MISSING"


class _FakeCoordinator:
    def __init__(self):
        self.started = []

    async def start(self, data_types=None, *, full=False):
        self.started.append((data_types, full))
        return "synthetic-sync-id"

    def status(self):
        return SyncStatus(
            active=False,
            sync_id="synthetic-sync-id",
            state="completed",
            items=[
                SyncStatusItem(
                    data_type="sleep",
                    last_status="ok",
                    source="web",
                    incremental=True,
                )
            ],
        )


def test_sync_start_and_status_with_fake_coordinator(db_path):
    app = create_app(db_path=db_path)
    fake = _FakeCoordinator()
    app.dependency_overrides[get_sync_coordinator] = lambda: fake
    with TestClient(app) as client:
        response = client.post(
            "/api/sync",
            headers={"X-Mi-Fitness-Confirm": "sync"},
            json={"dataTypes": ["sleep"], "full": True},
        )
        status = client.get("/api/sync/status")
    assert response.status_code == 202
    assert response.json()["syncId"] == "synthetic-sync-id"
    assert response.json()["status"] == "accepted"
    assert fake.started == [(["sleep"], True)]
    assert status.status_code == 200
    assert status.json()["items"][0]["lastStatus"] == "ok"
