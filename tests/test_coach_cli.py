"""Coach CLI and setup behavior with fake keyring/config services."""

from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from mi_fitness_mcp import main as main_module
from mi_fitness_mcp.coach.cli import interactive_coach_setup, run_coach
from mi_fitness_mcp.config import CoachConfig, Config
from tests.coach_fixtures import seed_coach_history


def _common_args(**kwargs):
    return argparse.Namespace(**kwargs)


def _patch_cli(tmp_path, monkeypatch):
    today = date.today()
    current_monday = today - timedelta(days=today.weekday())
    start = current_monday - timedelta(weeks=11)
    db_path, _user_id, _fixture_today = seed_coach_history(
        tmp_path / "coach.db", start=start
    )
    config = Config(
        database_path=db_path,
        timezone="UTC",
        coach=CoachConfig(enabled=False),
    )
    monkeypatch.setattr("mi_fitness_mcp.coach.cli.load_config", lambda: config)
    monkeypatch.setattr(
        "mi_fitness_mcp.coach.cli.load_mi_fitness_token", lambda: (None, None)
    )
    monkeypatch.setattr(
        "mi_fitness_mcp.coach.service.coach_llm_key_configured",
        lambda _provider: False,
    )
    return db_path, today


def test_cli_status_profile_goal_and_plan(tmp_path, monkeypatch, capsys):
    db_path, today = _patch_cli(tmp_path, monkeypatch)
    db = str(db_path)

    run_coach(
        _common_args(
            coach_command="status",
            json=False,
            db=db,
        )
    )
    assert "Coach 状态" in capsys.readouterr().out

    run_coach(
        _common_args(
            coach_command="profile",
            weeks=12,
            goal=None,
            llm_payload=False,
            json=True,
            db=db,
        )
    )
    profile = json.loads(capsys.readouterr().out)
    assert profile["window"]["weeks"] == 12

    run_coach(
        _common_args(
            coach_command="goals",
            goals_command="add",
            goal_type="weekly_frequency",
            title="每周训练 3 次",
            target=3,
            unit="sessions_per_week",
            start_date=today.isoformat(),
            target_date=None,
            sport=None,
            mode=None,
            period=None,
            race_distance=None,
            target_time=None,
            available_days=None,
            max_sessions_per_week=None,
            notes=None,
            json=False,
            db=db,
        )
    )
    assert "已创建目标" in capsys.readouterr().out

    run_coach(
        _common_args(
            coach_command="goals",
            goals_command="list",
            status="active",
            json=True,
            db=db,
        )
    )
    goals = json.loads(capsys.readouterr().out)
    assert len(goals) == 1
    goal_id = goals[0]["goal"]["id"]

    run_coach(
        _common_args(
            coach_command="plan",
            goal=goal_id,
            generate=True,
            weeks=8,
            fallback=True,
            llm=False,
            activate=True,
            json=False,
            db=db,
        )
    )
    assert "已生成计划" in capsys.readouterr().out

    run_coach(
        _common_args(
            coach_command="recommend",
            weeks=12,
            llm=False,
            fallback=True,
            save=False,
            json=True,
            db=db,
        )
    )
    recommendations = json.loads(capsys.readouterr().out)
    assert recommendations


def test_interactive_setup_stores_key_and_no_secret_in_config(monkeypatch):
    config = Config(coach=CoachConfig(enabled=False))
    answers = iter(
        [
            "openai_compatible",
            "fake-model",
            "http://127.0.0.1:11434/v1",
            "zh-CN",
            "8",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    monkeypatch.setattr("getpass.getpass", lambda _prompt="": "synthetic-key")
    saved_keyring: list[tuple[str, str]] = []
    saved_configs: list[Config] = []
    monkeypatch.setattr(
        "mi_fitness_mcp.coach.cli.save_coach_llm_api_key",
        lambda provider, key: saved_keyring.append((provider, key)),
    )
    monkeypatch.setattr(
        "mi_fitness_mcp.coach.cli.save_config", lambda value: saved_configs.append(value)
    )

    interactive_coach_setup(config)

    assert saved_keyring == [("openai_compatible", "synthetic-key")]
    assert saved_configs
    saved = saved_configs[-1]
    assert saved.coach.enabled is True
    assert saved.coach.llm.base_url == "http://127.0.0.1:11434/v1"
    dumped = json.dumps(saved.model_dump(mode="json"), ensure_ascii=False)
    assert "synthetic-key" not in dumped
    assert "api_key" not in dumped


def test_interactive_remote_setup_requires_explicit_yes(monkeypatch):
    config = Config(coach=CoachConfig(enabled=False))
    answers = iter(["anthropic", "claude-opus-5-5", "zh-CN", "8", "no"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    with pytest.raises(SystemExit):
        interactive_coach_setup(config)


def test_cmd_setup_preserves_existing_coach_settings(monkeypatch):
    existing = Config(
        coach=CoachConfig(enabled=True, llm=CoachConfig().llm.model_copy(update={"model": "keep-me"})),
    )
    captured: list[Config] = []
    monkeypatch.setattr("mi_fitness_mcp.main.load_config", lambda: existing)
    monkeypatch.setattr(
        "mi_fitness_mcp.main.save_config", lambda value: captured.append(value)
    )
    monkeypatch.setattr("mi_fitness_mcp.main.save_mi_fitness_token", lambda *_: None)
    monkeypatch.setattr("mi_fitness_mcp.main._warn_on_weak_keyring", lambda: None)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "synthetic-user")
    monkeypatch.setattr("getpass.getpass", lambda _prompt="": "synthetic-pass")

    main_module.cmd_setup(SimpleNamespace(with_coach=False))

    assert captured
    assert captured[-1].mode == "mi_fitness_cloud"
    assert captured[-1].coach.enabled is True
    assert captured[-1].coach.llm.model == "keep-me"
