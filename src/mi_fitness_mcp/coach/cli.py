"""CLI commands for the optional coach extension."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import hashlib
import ipaddress
import json
import sys
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import urlsplit

from mi_fitness_mcp.auth import (
    delete_coach_llm_api_key,
    load_mi_fitness_token,
    save_coach_llm_api_key,
)
from mi_fitness_mcp.coach.llm.base import LLMProviderError
from mi_fitness_mcp.coach.models import GoalCreate, GoalUpdate
from mi_fitness_mcp.coach.service import (
    CoachDisabledError,
    CoachLLMUnavailableError,
    CoachService,
)
from mi_fitness_mcp.config import (
    CoachLLMConfig,
    Config,
    load_config,
    resolve_database_path,
    save_config,
)
from mi_fitness_mcp.services.query_service import QueryService
from mi_fitness_mcp.storage import Database
from mi_fitness_mcp.storage.coach import CoachStore

PROGRAM_NAME = "mi-fitness-bridge"


def register_coach_parser(subparsers: Any, db_help: str) -> None:
    coach_parser = subparsers.add_parser(
        "coach",
        help="可选本地教练：目标、训练档案与 AI 训练计划",
    )
    coach_sub = coach_parser.add_subparsers(dest="coach_command", required=True)

    status_parser = coach_sub.add_parser("status", help="查看 coach 配置与数据状态")
    status_parser.add_argument("--json", action="store_true")
    status_parser.add_argument("--db", help=db_help)

    setup_parser = coach_sub.add_parser("setup", help="交互式配置 AI 供应商（可选）")
    setup_parser.add_argument("--db", help=db_help)

    profile_parser = coach_sub.add_parser("profile", help="查看近期训练档案")
    profile_parser.add_argument("--weeks", type=int, default=None)
    profile_parser.add_argument("--goal", help="目标 ID（用于 payload 裁剪）")
    profile_parser.add_argument("--llm-payload", action="store_true")
    profile_parser.add_argument("--json", action="store_true")
    profile_parser.add_argument("--db", help=db_help)

    recommend_parser = coach_sub.add_parser("recommend", help="生成目标建议")
    recommend_parser.add_argument("--weeks", type=int, default=None)
    recommend_parser.add_argument("--llm", action="store_true", help="调用已配置的 LLM")
    recommend_parser.add_argument(
        "--fallback", action="store_true", help="强制使用本地规则建议"
    )
    recommend_parser.add_argument("--save", action="store_true", help="把建议保存为目标")
    recommend_parser.add_argument("--json", action="store_true")
    recommend_parser.add_argument("--db", help=db_help)

    goals_parser = coach_sub.add_parser("goals", help="管理运动目标")
    goals_sub = goals_parser.add_subparsers(dest="goals_command", required=True)
    goals_list = goals_sub.add_parser("list", help="列出目标")
    goals_list.add_argument(
        "--status", choices=["active", "achieved", "archived"], default="active"
    )
    goals_list.add_argument("--json", action="store_true")
    goals_list.add_argument("--db", help=db_help)
    goals_show = goals_sub.add_parser("show", help="查看目标与进度")
    goals_show.add_argument("goal_id")
    goals_show.add_argument("--json", action="store_true")
    goals_show.add_argument("--db", help=db_help)
    goals_add = goals_sub.add_parser("add", help="手动创建目标")
    _add_goal_fields(goals_add)
    goals_add.add_argument("--json", action="store_true")
    goals_add.add_argument("--db", help=db_help)
    goals_update = goals_sub.add_parser("update", help="更新目标")
    goals_update.add_argument("goal_id")
    _add_goal_fields(goals_update, required=False)
    goals_update.add_argument("--json", action="store_true")
    goals_update.add_argument("--db", help=db_help)
    goals_archive = goals_sub.add_parser("archive", help="归档目标")
    goals_archive.add_argument("goal_id")
    goals_archive.add_argument("--db", help=db_help)
    goals_evaluate = goals_sub.add_parser("evaluate", help="重新计算目标进度")
    goals_evaluate.add_argument("goal_id")
    goals_evaluate.add_argument("--json", action="store_true")
    goals_evaluate.add_argument("--db", help=db_help)

    plan_parser = coach_sub.add_parser("plan", help="查看或生成训练计划")
    plan_parser.add_argument("--goal", help="目标 ID")
    plan_parser.add_argument("--generate", action="store_true")
    plan_parser.add_argument("--weeks", type=int, default=None)
    plan_parser.add_argument("--fallback", action="store_true")
    plan_parser.add_argument("--llm", action="store_true")
    plan_parser.add_argument("--activate", action="store_true")
    plan_parser.add_argument("--json", action="store_true")
    plan_parser.add_argument("--db", help=db_help)


def _add_goal_fields(parser: argparse.ArgumentParser, *, required: bool = True) -> None:
    parser.add_argument(
        "--type",
        dest="goal_type",
        choices=[
            "weekly_frequency",
            "weekly_duration",
            "race",
            "distance",
            "body_composition",
        ],
        required=required,
        help="目标类型",
    )
    parser.add_argument("--title")
    parser.add_argument(
        "--sport",
        choices=["any", "running", "cycling", "walking", "strength", "swimming", "other"],
    )
    parser.add_argument("--target", type=float)
    parser.add_argument(
        "--unit",
        choices=[
            "sessions_per_week",
            "minutes_per_week",
            "meters",
            "kg",
            "percent",
            "seconds",
        ],
    )
    parser.add_argument("--mode", choices=["target", "trend"])
    parser.add_argument(
        "--period",
        choices=["week", "month", "target_date", "rolling_28d"],
    )
    parser.add_argument("--start-date", help="YYYY-MM-DD，默认今天")
    parser.add_argument("--date", dest="target_date", help="目标日期 YYYY-MM-DD")
    parser.add_argument("--race-distance", choices=["5k", "10k", "half", "full"])
    parser.add_argument("--target-time", help="MM:SS 或 H:MM:SS")
    parser.add_argument("--available-days", type=int)
    parser.add_argument("--max-sessions", type=int, dest="max_sessions_per_week")
    parser.add_argument("--notes")


def run_coach(args: argparse.Namespace) -> None:
    command = args.coach_command
    if command == "setup":
        config = _load_coach_config(args)
        interactive_coach_setup(config)
        return
    config = _load_coach_config(args)
    db = Database(config.database_path)
    user_id = _resolve_user_id(db)
    query = QueryService(db, user_id)
    store = CoachStore(db)
    service = CoachService(
        store,
        query,
        config.coach,
        timezone=config.timezone,
        user_id="local",
    )
    try:
        if command == "status":
            _print_status(service, as_json=args.json)
        elif command == "profile":
            _print_profile(service, args)
        elif command == "recommend":
            _print_recommendations(service, args)
        elif command == "goals":
            _run_goals(service, args)
        elif command == "plan":
            _run_plan(service, args)
        else:  # pragma: no cover - argparse enforces choices
            raise SystemExit(f"Unknown coach command: {command}")
    except (
        ValueError,
        KeyError,
        CoachDisabledError,
        CoachLLMUnavailableError,
        LLMProviderError,
    ) as exc:
        print(f"❌ {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def _load_coach_config(args: argparse.Namespace) -> Config:
    config = load_config()
    override = resolve_database_path(getattr(args, "db", None))
    if override is not None:
        config.database_path = override
    return config


def _resolve_user_id(db: Database) -> str:
    user_id, _ = load_mi_fitness_token()
    if user_id:
        return user_id
    with db._get_connection() as conn:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        for table in (
            "workouts",
            "daily_activity",
            "sleep_sessions",
            "body_measurements",
        ):
            if table not in tables:
                continue
            row = conn.execute(
                f"SELECT user_id, COUNT(*) AS n FROM {table} "
                "WHERE user_id IS NOT NULL GROUP BY user_id "
                "ORDER BY n DESC LIMIT 1"
            ).fetchone()
            if row is not None and row["user_id"]:
                return str(row["user_id"])
    return "local"


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def _print_status(service: CoachService, *, as_json: bool) -> None:
    status = service.status()
    if as_json:
        _print_json(status)
        return
    print("Coach 状态")
    print("=" * 40)
    print(f"AI 已启用： {'是' if status['enabled'] else '否'}")
    print(f"供应商： {status['provider']} / {status['model']}")
    if status.get("base_url"):
        print(f"端点： {status['base_url']}")
    print(f"API Key 已配置： {'是' if status['key_configured'] else '否'}")
    print(
        "Anthropic SDK： "
        f"{'已安装' if status.get('anthropic_extra_available') else '未安装'}"
    )
    print(f"远程同意： {status.get('remote_consent_at') or '未记录'}")
    print(f"目标数： {status['goal_count']}，计划数： {status['plan_count']}")


def _print_profile(service: CoachService, args: argparse.Namespace) -> None:
    if args.llm_payload:
        payload = service.llm_payload(weeks=args.weeks, goal_id=args.goal)
        _print_json(payload)
        return
    profile = service.profile(args.weeks)
    if args.json:
        _print_json(profile.model_dump(mode="json"))
        return
    print("近期训练档案")
    print("=" * 40)
    print(
        f"窗口： {profile.window.start_date} 至 {profile.window.end_date}"
        f"（{profile.window.weeks} 周）"
    )
    print(
        f"训练： {profile.observed_frequency.mean_per_week:.1f} 次/周，"
        f"活跃周 {profile.observed_frequency.active_weeks}，"
        f"缺失周 {profile.window.weeks_without_records}"
    )
    if profile.best_5k_proxy.estimated_5k_seconds:
        print(
            "5K 代理值： "
            f"{profile.best_5k_proxy.estimated_5k_seconds // 60}:"
            f"{profile.best_5k_proxy.estimated_5k_seconds % 60:02d}"
            "（非正式 PB）"
        )
    print(f"数据质量： {profile.data_quality.status}")
    for caveat in profile.data_quality.caveats:
        print(f"- {caveat}")


def _confirm_ai_call(service: CoachService) -> bool:
    config = service.config.llm
    host = (
        "api.anthropic.com"
        if config.provider == "anthropic"
        else (urlsplit(config.base_url or "").hostname or "")
    )
    print(f"将调用： {config.provider} / {config.model} / {host}")
    print("只发送最小化周聚合；不含账号、设备、GPS、原始样本、精确日期或备注。")
    answer = input("确认发送？输入 yes： ").strip().lower()
    return answer == "yes"


def _print_recommendations(service: CoachService, args: argparse.Namespace) -> None:
    use_llm = bool(args.llm and not args.fallback)
    if use_llm:
        if not _confirm_ai_call(service):
            print("已取消 AI 调用。")
            return
        recommendations = asyncio.run(
            service.recommend_goals_ai(weeks=args.weeks, consent=True)
        )
    else:
        recommendations = service.recommend_goals(weeks=args.weeks)
    if args.save:
        created = []
        for recommendation in recommendations:
            payload = recommendation.model_dump()
            payload.pop("rationale", None)
            payload.pop("evidence", None)
            payload.pop("confidence", None)
            payload.pop("data_gaps", None)
            payload.pop("source", None)
            created.append(
                service.create_goal(GoalCreate.model_validate(payload)).model_dump(mode="json")
            )
        recommendations = recommendations[:0]
        if args.json:
            _print_json(created)
        else:
            for item in created:
                print(f"已创建目标： {item['title']} ({item['id']})")
        return
    if args.json:
        _print_json([item.model_dump(mode="json") for item in recommendations])
        return
    if not recommendations:
        print("当前数据不足，暂时没有可靠的目标建议。")
        return
    for index, item in enumerate(recommendations, start=1):
        print(f"{index}. {item.title}")
        print(f"   类型： {item.goal_type}，目标值： {item.target_value} {item.target_unit}")
        print(f"   理由： {item.rationale}")
        if item.data_gaps:
            print(f"   数据缺口： {'；'.join(item.data_gaps)}")


def _run_goals(service: CoachService, args: argparse.Namespace) -> None:
    if args.goals_command == "list":
        items = service.list_goals(args.status)
        if args.json:
            _print_json([item.model_dump(mode="json") for item in items])
            return
        if not items:
            print("没有目标。")
            return
        for item in items:
            progress = item.progress
            print(
                f"{item.goal.title} ({item.goal.id})："
                f"{progress.status}，当前 {progress.current_value} / {progress.target_value}"
                f" {item.goal.target_unit}"
            )
    elif args.goals_command == "show":
        item = service.get_goal(args.goal_id)
        if args.json:
            _print_json(item.model_dump(mode="json"))
        else:
            print(f"{item.goal.title} ({item.goal.id})")
            print(f"进度： {item.progress.model_dump_json(indent=2)}")
    elif args.goals_command == "add":
        goal = service.create_goal(_goal_create_from_args(args))
        print(f"已创建目标： {goal.title} ({goal.id})")
    elif args.goals_command == "update":
        changes = _goal_update_from_args(args)
        goal = service.update_goal(args.goal_id, changes)
        print(f"已更新目标： {goal.title} ({goal.id})")
    elif args.goals_command == "archive":
        goal = service.archive_goal(args.goal_id)
        print(f"已归档目标： {goal.title} ({goal.id})")
    elif args.goals_command == "evaluate":
        item = service.get_goal(args.goal_id)
        if args.json:
            _print_json(item.model_dump(mode="json"))
        else:
            print(f"{item.goal.title}： {item.progress.status}")
    else:  # pragma: no cover
        raise SystemExit(f"Unknown goals command: {args.goals_command}")


def _run_plan(service: CoachService, args: argparse.Namespace) -> None:
    if args.generate:
        if not args.goal:
            raise SystemExit("生成计划需要 --goal <goal_id>")
        use_llm = bool(args.llm and not args.fallback)
        if use_llm:
            if not _confirm_ai_call(service):
                print("已取消 AI 调用。")
                return
            plan = asyncio.run(
                service.generate_plan_ai(
                    args.goal,
                    weeks=args.weeks,
                    consent=True,
                    activate=args.activate,
                )
            )
        else:
            plan = service.generate_plan(
                args.goal,
                weeks=args.weeks,
                activate=args.activate,
            )
        if args.json:
            _print_json(plan.model_dump(mode="json"))
            return
        print(f"已生成计划： {plan.title} ({plan.id})，{plan.weeks} 周")
        print(f"状态： {plan.status}，来源： {plan.generated_by}")
        if plan.validation_warnings:
            print("校验警告：")
            for warning in plan.validation_warnings:
                print(f"- {warning}")
        if plan.plan.weeks:
            first_week = plan.plan.weeks[0]
            print(f"第一周（{first_week.start_date}）：")
            for session in first_week.sessions:
                print(
                    f"- {session.date} {session.session_type} "
                    f"{session.duration_minutes} 分钟： {session.description}"
                )
        return
    plans = service.list_plans(goal_id=args.goal)
    if args.json:
        _print_json(plans)
        return
    if not plans:
        print("没有训练计划。")
        return
    for plan in plans:
        print(f"{plan['title']} ({plan['id']})： {plan['status']}，{plan['weeks']} 周")


def _goal_create_from_args(args: argparse.Namespace) -> GoalCreate:
    payload = _goal_payload_from_args(args)
    return GoalCreate.model_validate(payload)


def _goal_update_from_args(args: argparse.Namespace) -> GoalUpdate:
    return GoalUpdate.model_validate(_goal_payload_from_args(args, include_none=False))


def _goal_payload_from_args(
    args: argparse.Namespace, *, include_none: bool = True
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "goal_type": getattr(args, "goal_type", None),
        "sport": getattr(args, "sport", None),
        "title": getattr(args, "title", None),
        "mode": getattr(args, "mode", None),
        "target_value": getattr(args, "target", None),
        "target_unit": getattr(args, "unit", None),
        "period": getattr(args, "period", None),
        "start_date": getattr(args, "start_date", None),
        "target_date": getattr(args, "target_date", None),
        "race_distance": getattr(args, "race_distance", None),
        "target_time_seconds": _parse_target_time(getattr(args, "target_time", None)),
        "available_days": getattr(args, "available_days", None),
        "max_sessions_per_week": getattr(args, "max_sessions_per_week", None),
        "notes": getattr(args, "notes", None),
    }
    if include_none:
        goal_type = payload["goal_type"]
        if payload["start_date"] is None:
            payload["start_date"] = date.today().isoformat()
        if payload["sport"] is None:
            payload["sport"] = "running" if goal_type == "race" else "any"
        if payload["mode"] is None:
            payload["mode"] = "target"
        if payload["target_unit"] is None:
            payload["target_unit"] = _default_unit(goal_type)
        if payload["period"] is None:
            payload["period"] = (
                "rolling_28d"
                if goal_type == "body_composition" and payload["mode"] == "trend"
                else _default_period(goal_type)
            )
        if not payload["title"]:
            payload["title"] = _default_title(payload)
        return payload
    return {key: value for key, value in payload.items() if value is not None}


def _default_unit(goal_type: str | None) -> str:
    return {
        "weekly_frequency": "sessions_per_week",
        "weekly_duration": "minutes_per_week",
        "race": "seconds",
        "distance": "meters",
        "body_composition": "kg",
    }.get(goal_type or "", "sessions_per_week")


def _default_period(goal_type: str | None) -> str:
    return {
        "weekly_frequency": "week",
        "weekly_duration": "week",
        "race": "target_date",
        "distance": "week",
        "body_composition": "target_date",
    }.get(goal_type or "", "week")


def _default_title(payload: dict[str, Any]) -> str:
    goal_type = payload.get("goal_type")
    target = payload.get("target_value")
    if goal_type == "weekly_frequency" and target:
        return f"每周训练 {target:g} 次"
    if goal_type == "weekly_duration" and target:
        return f"每周训练 {target:g} 分钟"
    if goal_type == "distance" and target:
        return f"每周 {target / 1000:g} 公里"
    if goal_type == "race" and payload.get("target_time_seconds"):
        seconds = payload["target_time_seconds"]
        return f"比赛目标 {seconds // 60}:{seconds % 60:02d}"
    if goal_type == "body_composition":
        return "体重趋势" if payload.get("mode") == "trend" else "体重/体脂目标"
    return "运动目标"


def _parse_target_time(value: str | None) -> int | None:
    if not value:
        return None
    if value.isdigit():
        return int(value)
    parts = [int(part) for part in value.split(":")]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    raise SystemExit("目标时间格式应为 MM:SS 或 H:MM:SS")


def interactive_coach_setup(config: Config) -> None:
    """Interactive provider/key setup; the only writer of remote consent."""
    print("Coach AI 配置（可选）")
    print("=" * 40)
    print("核心桥接和本地目标不需要 AI；只有显式生成建议/计划时才会调用模型。")
    provider = input("供应商 [anthropic/openai_compatible]（默认 anthropic）： ").strip()
    provider = provider or "anthropic"
    if provider not in {"anthropic", "openai_compatible"}:
        raise SystemExit("未知供应商")
    default_model = (
        "claude-opus-5-5"
        if provider == "anthropic"
        else config.coach.llm.model
    )
    model = input(f"模型（默认 {default_model}）： ").strip()
    model = model or default_model
    base_url = None
    if provider == "openai_compatible":
        base_url = input(
            "Base URL（例如 https://api.deepseek.com/v1 或 http://127.0.0.1:11434/v1）： "
        ).strip()
        if not base_url:
            raise SystemExit("openai_compatible 必须提供 base_url")
    language = input("输出语言 [zh-CN/en]（默认 zh-CN）： ").strip() or "zh-CN"
    profile_weeks_raw = input("训练档案周数（默认 8）： ").strip()
    try:
        profile_weeks = int(profile_weeks_raw) if profile_weeks_raw else 8
    except ValueError as exc:
        raise SystemExit("周数必须是整数") from exc
    try:
        llm_data = config.coach.llm.model_dump()
        llm_data.update({"provider": provider, "model": model, "base_url": base_url})
        llm = CoachLLMConfig.model_validate(llm_data)
    except ValueError as exc:
        raise SystemExit(f"配置不合法： {exc}") from exc
    is_local = _is_local_base_url(base_url) if base_url else False
    if not is_local:
        print()
        print("将要发送的内容：最近训练周聚合（训练次数、时长、距离、心率负荷代理、")
        print("睡眠均值、目标约束）。不会发送 user_id、device_id、GPS、原始样本、")
        print("精确时间戳或备注。你可以先运行 `mi-fitness-bridge coach profile --llm-payload`")
        print("查看精确 payload。")
        consent = input("同意向该远程端点发送健康摘要？输入 yes： ").strip().lower()
        if consent != "yes":
            raise SystemExit("未授予远程同意，未启用 AI。")
    api_key = ""
    if provider == "anthropic" or not is_local:
        api_key = getpass.getpass("API Key（输入不回显，将保存到系统钥匙串）： ").strip()
        if not api_key:
            raise SystemExit("该供应商需要 API Key")
    else:
        api_key = getpass.getpass("API Key（本地端点可留空）： ").strip()
    if api_key:
        save_coach_llm_api_key(provider, api_key)
    host = _host_for_consent(provider, base_url)
    config.coach.enabled = True
    config.coach.language = language if language in {"zh-CN", "en"} else "zh-CN"
    config.coach.profile_weeks = max(4, min(52, profile_weeks))
    config.coach.llm = llm
    if is_local:
        config.coach.llm.remote_consent_at = None
        config.coach.llm.remote_consent_provider = None
        config.coach.llm.remote_consent_host = None
        config.coach.llm.remote_consent_fingerprint = None
    else:
        config.coach.llm.remote_consent_at = datetime.now(UTC).isoformat()
        config.coach.llm.remote_consent_provider = provider
        config.coach.llm.remote_consent_host = host
        config.coach.llm.remote_consent_fingerprint = hashlib.sha256(
            f"{provider}|{host}|{model}".encode()
        ).hexdigest()[:16]
    save_config(config)
    print("✅ Coach AI 配置已保存。")
    print("   运行 `mi-fitness-bridge coach status` 查看状态。")


def _is_local_base_url(base_url: str | None) -> bool:
    if not base_url:
        return False
    host = (urlsplit(base_url).hostname or "").lower()
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _host_for_consent(provider: str, base_url: str | None) -> str:
    if provider == "anthropic":
        return "api.anthropic.com"
    return (urlsplit(base_url or "").hostname or "").lower()


def revoke_coach_consent(config: Config, provider: str | None = None) -> None:
    target = provider or config.coach.llm.provider
    delete_coach_llm_api_key(target)
    config.coach.llm.remote_consent_at = None
    config.coach.llm.remote_consent_provider = None
    config.coach.llm.remote_consent_host = None
    config.coach.llm.remote_consent_fingerprint = None
    save_config(config)
    print("已撤销 coach LLM 密钥与远程同意。")
