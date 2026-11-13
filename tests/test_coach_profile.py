"""Training profile contracts: synthetic data only, no network or real keys."""

from __future__ import annotations

import json
import re

from mi_fitness_mcp.coach.profile import (
    BANNED_PAYLOAD_KEYS,
    TrainingProfileBuilder,
    assert_minimized,
)
from mi_fitness_mcp.services.query_service import QueryService
from mi_fitness_mcp.storage import Database
from tests.coach_fixtures import seed_coach_db, seed_minimal_coach_history


def _builder(tmp_path):
    db_path, user_id, today = seed_coach_db(tmp_path)
    db = Database(db_path)
    query = QueryService(db, user_id)
    return TrainingProfileBuilder(query, timezone="Asia/Shanghai", today=today)


def test_profile_aggregates_recent_training_without_zero_filling(tmp_path):
    builder = _builder(tmp_path)
    profile = builder.build(weeks=12)
    assert profile.window.weeks == 12
    assert profile.window.weeks_without_records == 2
    assert len(profile.weekly) == 10
    assert all(bucket.sessions > 0 for bucket in profile.weekly)
    assert profile.observed_frequency.active_weeks == 10
    assert profile.observed_frequency.mean_per_week > 0
    assert profile.longest_session.duration_minutes is not None
    assert profile.best_5k_proxy.estimated_5k_seconds is not None
    assert profile.best_5k_proxy.estimated_5k_seconds < 1800
    assert profile.sleep.nights >= 3
    assert profile.body is not None
    assert profile.data_quality.status == "ok"
    assert profile.data_quality.workout_days > 0


def test_llm_payload_is_minimized(tmp_path):
    builder = _builder(tmp_path)
    profile = builder.build(weeks=12)
    payload = builder.build_llm_payload(profile, language="zh-CN")
    serialized = json.dumps(payload, ensure_ascii=False)
    for banned in BANNED_PAYLOAD_KEYS:
        assert banned not in serialized
    assert not re.search(r"\d{4}-\d{2}-\d{2}", serialized)
    assert payload["schema_version"] == "coach-payload-v1"
    assert "weeks" in payload
    assert payload["schema_version"] != ""


def test_llm_payload_excludes_body_unless_requested(tmp_path):
    builder = _builder(tmp_path)
    profile = builder.build(weeks=12)
    payload = builder.build_llm_payload(profile)
    assert "body" not in payload
    with_body = builder.build_llm_payload(profile, include_body_context=True)
    assert "body" in with_body


def test_assert_minimized_rejects_identifiers_and_dates():
    try:
        assert_minimized({"user_id": "x"})
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("user_id should be rejected")
    try:
        assert_minimized({"week": "2026-01-05"})
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("exact date should be rejected")


def test_minimal_history_is_insufficient(tmp_path):
    db_path, user_id, today = seed_minimal_coach_history(tmp_path / "minimal.db")
    db = Database(db_path)
    builder = TrainingProfileBuilder(
        QueryService(db, user_id), timezone="Asia/Shanghai", today=today
    )
    profile = builder.build(weeks=12)
    assert profile.data_quality.status == "insufficient"
    assert profile.best_5k_proxy.estimated_5k_seconds is None
    assert profile.body is None
    payload = builder.build_llm_payload(profile)
    assert payload["data_quality"]["status"] == "insufficient"
