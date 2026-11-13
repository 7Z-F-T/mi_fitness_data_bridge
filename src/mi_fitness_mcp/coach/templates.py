"""Deterministic training-plan templates used when no LLM is available."""

from __future__ import annotations

from datetime import date, timedelta
from statistics import fmean

from mi_fitness_mcp.coach.models import (
    Goal,
    PlanGenerationConstraints,
    PlanSafety,
    PlanSession,
    PlanWeek,
    TrainingPlanContent,
    TrainingProfile,
)

RACE_DISTANCE_M = {"5k": 5000.0, "10k": 10000.0, "half": 21097.5, "full": 42195.0}
RACE_LONG_CAP_KM = {"5k": 8.0, "10k": 12.0, "half": 18.0, "full": 32.0}
PACE_MIN_PER_KM = {
    "running": 6.0,
    "cycling": 3.0,
    "walking": 12.0,
    "swimming": 20.0,
    "strength": 6.0,
    "other": 8.0,
    "any": 8.0,
}
DAY_OFFSETS = {
    2: [1, 5],
    3: [1, 3, 5],
    4: [1, 3, 5, 6],
    5: [1, 2, 3, 5, 6],
    6: [0, 1, 2, 3, 5, 6],
}


def _next_monday(value: date) -> date:
    return value + timedelta(days=(7 - value.weekday()) % 7 or 7)


def _dominant_sport(profile: TrainingProfile) -> str:
    counts: dict[str, int] = {}
    for bucket in profile.weekly:
        for sport, count in bucket.by_sport.items():
            counts[sport] = counts.get(sport, 0) + count
    if not counts:
        return "running"
    sport = max(counts, key=lambda item: (counts[item], item))
    return sport if sport in PACE_MIN_PER_KM else "running"


def _recent_weekly_duration(profile: TrainingProfile) -> float | None:
    values = [bucket.duration_minutes for bucket in profile.weekly if bucket.sessions > 0]
    return fmean(values) if values else None


def _race_weeks(start: date, target: date | None, requested: int) -> int:
    if target is None:
        return requested
    weeks = (target - start).days // 7 + 1
    return max(4, min(24, weeks))


def _safe_subject(goal: Goal) -> str:
    labels = {
        "running": "跑步",
        "cycling": "骑行",
        "walking": "步行",
        "strength": "力量",
        "swimming": "游泳",
        "other": "运动",
        "any": "运动",
    }
    return labels.get(goal.sport, "运动")


def _base_week_duration(
    goal: Goal,
    profile: TrainingProfile,
    constraints: PlanGenerationConstraints,
    sport: str,
    days: int,
) -> float:
    if goal.goal_type == "weekly_duration" and goal.target_value:
        return float(goal.target_value)
    if goal.goal_type == "weekly_frequency" and goal.target_value:
        return float(goal.target_value) * constraints.session_minutes
    recent = _recent_weekly_duration(profile)
    if recent:
        return recent
    if goal.goal_type == "distance" and goal.target_value:
        return (goal.target_value / 1000) * PACE_MIN_PER_KM.get(sport, 8.0)
    return days * constraints.session_minutes


def build_template_plan(
    goal: Goal,
    profile: TrainingProfile,
    constraints: PlanGenerationConstraints,
    *,
    today: date | None = None,
) -> TrainingPlanContent:
    """Build a conservative plan that is valid without any model call."""
    today = today or date.today()
    start = constraints.start_date or _next_monday(today)
    weeks = constraints.weeks
    if goal.goal_type == "race":
        weeks = _race_weeks(start, goal.target_date, weeks)
    days = constraints.days_per_week
    if goal.goal_type == "weekly_frequency" and goal.target_value:
        days = max(2, min(6, round(goal.target_value)))
    days = max(2, min(6, days))
    sport = goal.sport if goal.sport != "any" else _dominant_sport(profile)
    if goal.goal_type == "race":
        sport = "running"
    base_duration = _base_week_duration(goal, profile, constraints, sport, days)
    weeks_list: list[PlanWeek] = []
    planned_duration: list[float] = []
    planned_distance: list[float] = []
    race_week_index = None
    if goal.goal_type == "race" and goal.target_date is not None:
        race_offset = (goal.target_date - start).days
        if 0 <= race_offset < weeks * 7:
            race_week_index = race_offset // 7 + 1
    for week_index in range(1, weeks + 1):
        week_start = start + timedelta(weeks=week_index - 1)
        is_recovery = weeks >= 6 and week_index % 4 == 0
        if race_week_index is not None and week_index >= race_week_index - 1:
            is_recovery = True
        if is_recovery:
            factor = 0.72 if week_index < weeks else 0.55
        else:
            factor = min(1.10, 0.92 + 0.04 * week_index)
        if goal.goal_type == "weekly_frequency":
            factor = 1.0 if not is_recovery else 0.75
        week_duration = max(10.0, base_duration * factor)
        week_distance = None
        if goal.goal_type == "distance" and goal.target_value:
            week_distance = float(goal.target_value) * (factor if not is_recovery else 0.78)
        sessions = _make_sessions(
            goal=goal,
            profile=profile,
            week_start=week_start,
            week_index=week_index,
            days=days,
            sport=sport,
            week_duration=week_duration,
            week_distance=week_distance,
            is_recovery=is_recovery,
            race_week_index=race_week_index,
            session_minutes=constraints.session_minutes,
        )
        week_duration = sum(
            session.duration_minutes for session in sessions if session.session_type != "rest"
        )
        week_distance = sum(
            session.distance_m or 0 for session in sessions if session.session_type != "rest"
        )
        planned_duration.append(week_duration)
        planned_distance.append(week_distance)
        weeks_list.append(
            PlanWeek(
                week_index=week_index,
                start_date=week_start,
                focus=_week_focus(goal, week_index, weeks, is_recovery),
                is_recovery_week=is_recovery,
                target_duration_minutes=week_duration,
                target_distance_m=week_distance or None,
                sessions=sessions,
            )
        )
    end_date = start + timedelta(weeks=weeks) - timedelta(days=1)
    data_gaps = list(profile.data_quality.caveats)
    assumptions = [
        f"计划从 {start.isoformat()} 开始，共 {weeks} 周。",
        f"默认每周 {days} 次训练，每次约 {constraints.session_minutes} 分钟。",
        "没有可靠阈值测试时，强度用 RPE 和说话测试描述。",
    ]
    if (
        goal.goal_type == "race"
        and goal.target_date is not None
        and not start <= goal.target_date <= end_date
    ):
        assumptions.append(
            "比赛日期在计划周期之外；本计划覆盖前 24 周，临近比赛请重新生成。"
        )
    return TrainingPlanContent(
        title=f"{goal.title} · 训练计划",
        summary=(
            f"{_safe_subject(goal)} {weeks} 周计划，"
            f"每周 {days} 次，包含至少 1 个休息日和渐进负荷。"
        ),
        weeks=weeks_list,
        progression_rules=[
            "每周总时长/距离增幅不超过 10%。",
            "每 3-4 周安排低负荷恢复周。",
            "高强度训练之间至少间隔 48 小时。",
            "每周至少安排 1 天完全休息。",
        ],
        weekly_habits=[
            "睡眠明显不足或静息心率异常升高时，降低强度或改为休息。",
            "每次训练包含热身和放松，疼痛时停止而不是硬撑。",
            "用主观用力程度（RPE）记录训练感受。",
        ],
        safety=PlanSafety(
            stop_rules=[
                "出现胸痛、异常气短、眩晕、心悸或明显不适应立即停止。",
                "持续疼痛、发热或异常疲劳时休息，并考虑寻求医疗评估。",
                "不要在疼痛、伤病或身体不适时强行完成计划。",
            ],
            disclaimer=(
                "本计划仅供运动参考，不构成医疗建议，不替代医生或持证教练的个体化评估。"
            ),
        ),
        assumptions=assumptions,
        data_gaps=data_gaps,
    )


SESSION_WEIGHTS = {
    "tempo": 1.10,
    "interval": 1.10,
    "long": 1.60,
    "strength": 0.70,
    "recovery": 0.70,
    "easy": 1.00,
}


def _make_sessions(
    *,
    goal: Goal,
    profile: TrainingProfile,
    week_start: date,
    week_index: int,
    days: int,
    sport: str,
    week_duration: float,
    week_distance: float | None,
    is_recovery: bool,
    race_week_index: int | None,
    session_minutes: int,
) -> list[PlanSession]:
    offsets = DAY_OFFSETS.get(days, DAY_OFFSETS[3])
    max_duration = min(
        240,
        max(10, round(session_minutes * 1.5 * (0.75 if is_recovery else 1.0))),
    )
    race_date = goal.target_date
    if (
        goal.goal_type == "race"
        and race_date is not None
        and week_start <= race_date <= week_start + timedelta(days=6)
    ):
        sessions: list[PlanSession] = []
        for offset in offsets:
            session_date = week_start + timedelta(days=offset)
            if session_date < race_date and len(offsets) <= 2:
                sessions.append(
                    _easy_session(sport, session_date, 20, "赛前轻松活动")
                )
        sessions.append(_race_session(goal, race_date, sport))
        return sessions

    session_types: list[str] = []
    for index, _offset in enumerate(offsets):
        if index == 0 and not is_recovery:
            session_type = "interval" if week_index % 3 == 0 else "tempo"
        elif index == len(offsets) - 1:
            session_type = "long"
        elif days >= 4 and index == 1:
            session_type = "strength"
        elif is_recovery:
            session_type = "recovery"
        else:
            session_type = "easy"
        session_types.append(session_type)
    total_weight = sum(SESSION_WEIGHTS[session_type] for session_type in session_types)
    sessions = []
    for offset, session_type in zip(offsets, session_types, strict=True):
        session_date = week_start + timedelta(days=offset)
        share = SESSION_WEIGHTS[session_type] / total_weight
        duration = max(10, round(week_duration * share))
        distance_m = None
        if goal.goal_type == "distance" and week_distance:
            distance_m = max(1000.0, week_distance * share)
        elif goal.goal_type == "race" and session_type == "long":
            distance_m = _race_long_distance(
                goal=goal, profile=profile, week_index=week_index, is_recovery=is_recovery
            )
            duration = max(
                10,
                round((distance_m / 1000) * PACE_MIN_PER_KM.get(sport, 8.0)),
            )
        sessions.append(
            PlanSession(
                date=session_date,
                sport=sport,
                session_type=session_type,
                duration_minutes=min(max_duration, duration),
                distance_m=round(distance_m, 1) if distance_m else None,
                intensity=_intensity(session_type),
                description=_description(session_type, duration, distance_m),
                purpose=_purpose(session_type),
            )
        )
    return sessions


def _race_long_distance(
    *,
    goal: Goal,
    profile: TrainingProfile,
    week_index: int,
    is_recovery: bool,
) -> float | None:
    if goal.race_distance is None:
        return None
    cap = RACE_LONG_CAP_KM[goal.race_distance] * 1000
    existing = (profile.longest_session.distance_km or 0) * 1000
    start_long = min(cap, max(5000.0, existing or cap * 0.6))
    long_m = min(cap, start_long * (1.08 ** max(0, week_index - 1)))
    if is_recovery:
        long_m *= 0.75
    return long_m


def _race_session(goal: Goal, race_date: date, sport: str) -> PlanSession:
    distance_m = RACE_DISTANCE_M.get(goal.race_distance or "", 5000.0)
    target_seconds = goal.target_time_seconds or int(distance_m / 1000 * 360)
    return PlanSession(
        date=race_date,
        sport=sport,
        session_type="race",
        duration_minutes=max(10, min(600, round(target_seconds / 60))),
        distance_m=distance_m,
        intensity="race",
        description="按目标配速完成比赛；赛前充分热身，按计划补给。",
        purpose="完成目标比赛。",
    )


def _easy_session(sport: str, session_date: date, minutes: int, purpose: str) -> PlanSession:
    return PlanSession(
        date=session_date,
        sport=sport,
        session_type="easy",
        duration_minutes=max(10, minutes),
        intensity="RPE 3-4，可完整说话",
        description="轻松有氧活动，保持可交谈强度。",
        purpose=purpose,
    )


def _week_focus(goal: Goal, week_index: int, weeks: int, is_recovery: bool) -> str:
    if is_recovery:
        return "恢复与有氧维持"
    if goal.goal_type == "race":
        if week_index <= max(1, weeks // 2):
            return "基础耐力"
        if week_index <= max(2, weeks - 2):
            return "专项耐力"
        return "赛前调整"
    return "稳定训练"


def _intensity(session_type: str) -> str:
    return {
        "easy": "RPE 3-4，可完整说话",
        "recovery": "RPE 2-3，非常轻松",
        "long": "RPE 4-5，可短句交谈",
        "tempo": "RPE 6，呼吸加深但可说短句",
        "interval": "RPE 7-8，分组进行，组间充分恢复",
        "strength": "RPE 5-6，动作质量优先",
        "mobility": "RPE 2-3",
        "race": "比赛强度",
        "rest": "休息",
    }.get(session_type, "RPE 3-4")


def _description(session_type: str, minutes: int, distance_m: float | None) -> str:
    distance = f"，约 {distance_m / 1000:.1f} 公里" if distance_m else ""
    if session_type == "tempo":
        return f"热身 10 分钟，节奏跑 15-20 分钟，放松 5-10 分钟{distance}。"
    if session_type == "interval":
        return f"热身 10 分钟，4-6 组短间歇，组间轻松恢复，放松 5-10 分钟{distance}。"
    if session_type == "long":
        return f"轻松长距离 {minutes} 分钟{distance}，保持可短句交谈。"
    if session_type == "strength":
        return "基础力量/核心训练，动作质量优先，避免力竭。"
    if session_type == "recovery":
        return f"非常轻松的恢复活动 {minutes} 分钟，不追配速。"
    return f"轻松有氧 {minutes} 分钟{distance}，保持可完整说话。"


def _purpose(session_type: str) -> str:
    return {
        "tempo": "提高持续输出能力。",
        "interval": "提高速度储备和心肺刺激。",
        "long": "建立耐力和抗疲劳能力。",
        "strength": "补足力量与稳定性。",
        "recovery": "促进恢复，保持训练连续性。",
        "easy": "积累有氧基础。",
        "race": "完成目标比赛。",
        "rest": "恢复。",
    }.get(session_type, "积累训练量。")
