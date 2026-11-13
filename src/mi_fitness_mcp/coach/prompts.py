"""Versioned prompts and prompt-safe payload projections for coach LLMs."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from mi_fitness_mcp.coach.models import Goal, GoalRecommendation

PROMPT_VERSION_GOALS = "coach-goals-v1"
PROMPT_VERSION_PLAN = "coach-plan-v1"
PAYLOAD_VERSION = "coach-payload-v1"
SCHEMA_VERSION = "coach-plan-schema-v1"
GOAL_SCHEMA_NAME = "coach_goal_recommendations"
PLAN_SCHEMA_NAME = "coach_training_plan"

_BASE_RULES = (
    "你是保守的运动训练助理，不是医生、注册营养师或持证教练。"
    "只能使用用户提供的数值和枚举；数据不足时必须明确写出 data_gaps，不得编造。"
    "不得诊断、治疗、开药、提供饮食处方、热量缺口方案、断食或极端减重建议。"
    "训练计划必须包含至少一个休息日、每周不超过 10% 的负荷增幅、停止规则和非医疗声明。"
    "输出必须严格符合给定 JSON Schema，不要输出 Markdown 或额外解释。"
)

_BASE_RULES_EN = (
    "You are a conservative training assistant, not a doctor, dietitian, or licensed coach. "
    "Use only the supplied numeric data and enums; if data is insufficient, list it in "
    "data_gaps and never invent values. Do not diagnose, treat, prescribe medication or food, "
    "or recommend calorie deficits, fasting, or extreme weight loss. Every plan must include "
    "at least one rest day, no more than 10% weekly load progression, stop rules, and a "
    "non-medical disclaimer. Output must strictly match the provided JSON Schema; no Markdown."
)


def goal_system_prompt(language: str = "zh-CN") -> str:
    if language == "en":
        return (
            f"{_BASE_RULES_EN} Recommend at most three realistic goals that fit the recent "
            "training profile. Prefer maintaining consistency over aggressive increases. "
            "For race goals use an achievable target and a 2-104 week horizon. "
            "Use the rule candidates as evidence, but you may decline a candidate if the "
            "profile does not support it. Set confidence to low when data is partial."
        )
    return (
        f"{_BASE_RULES}基于近期训练档案推荐最多 3 个现实目标；优先保持可持续性，不要激进加量。"
        "比赛目标需给出可实现的目标时间和 2-104 周的时间范围。"
        "可以参考规则候选，但若档案不支持应放弃该候选；数据不完整时 confidence 设为 low。"
    )


def plan_system_prompt(language: str = "zh-CN") -> str:
    if language == "en":
        return (
            f"{_BASE_RULES_EN} Build a week-by-week plan using week_index and "
            "day_of_week (0=Monday, 6=Sunday), never exact calendar dates. "
            "Keep the requested number of weeks and days per week, include recovery weeks, "
            "and make the final week a taper for race goals. Do not include diet advice."
        )
    return (
        f"{_BASE_RULES}按周生成训练计划，使用 week_index 和 day_of_week（0=周一，6=周日），"
        "不要输出日历日期。保持用户要求的周数和每周训练天数，安排恢复周；"
        "比赛目标最后 1-2 周必须减量。不要包含饮食建议。"
    )


def _candidate_payload(candidate: GoalRecommendation) -> dict[str, Any]:
    return {
        "goal_type": candidate.goal_type,
        "sport": candidate.sport,
        "mode": candidate.mode,
        "target_value": candidate.target_value,
        "target_unit": candidate.target_unit,
        "period": candidate.period,
        "race_distance": candidate.race_distance,
        "target_time_seconds": candidate.target_time_seconds,
        "rationale": candidate.rationale,
        "evidence": candidate.evidence,
        "confidence": candidate.confidence,
    }


def _goal_payload(goal: Goal, today: date) -> dict[str, Any]:
    weeks_until_target = None
    if goal.target_date is not None:
        weeks_until_target = max(0, (goal.target_date - today).days // 7)
    return {
        "goal_type": goal.goal_type,
        "sport": goal.sport,
        "target_value": goal.target_value,
        "target_unit": goal.target_unit,
        "race_distance": goal.race_distance,
        "target_time_seconds": goal.target_time_seconds,
        "weeks_until_target": weeks_until_target,
        "constraints": {
            "available_days": goal.available_days,
            "max_sessions_per_week": goal.max_sessions_per_week,
        },
    }


def build_goal_user_prompt(
    profile_payload: dict[str, Any],
    candidates: list[GoalRecommendation],
    language: str = "zh-CN",
) -> str:
    intro = (
        "Recommend goals using this JSON. Return only the schema object."
        if language == "en"
        else "请根据以下 JSON 推荐目标，只返回符合 schema 的 JSON。"
    )
    data = {
        "profile": profile_payload,
        "rule_candidates": [_candidate_payload(candidate) for candidate in candidates],
    }
    return f"{intro}\n{json.dumps(data, ensure_ascii=False, separators=(',', ':'))}"


def build_plan_user_prompt(
    profile_payload: dict[str, Any],
    goal: Goal,
    *,
    today: date,
    weeks: int,
    days_per_week: int,
    session_minutes: int,
    language: str = "zh-CN",
) -> str:
    intro = (
        "Build the plan using this JSON. Return only the schema object."
        if language == "en"
        else "请根据以下 JSON 生成训练计划，只返回符合 schema 的 JSON。"
    )
    data = {
        "profile": profile_payload,
        "goal": _goal_payload(goal, today),
        "constraints": {
            "weeks": weeks,
            "days_per_week": days_per_week,
            "session_minutes": session_minutes,
            "start_weekday": "Monday",
        },
    }
    return f"{intro}\n{json.dumps(data, ensure_ascii=False, separators=(',', ':'))}"


def build_repair_prompt(original: str, issues: list[str], language: str = "zh-CN") -> str:
    if language == "en":
        return (
            f"{original}\n\nThe previous output failed local validation: "
            f"{'; '.join(issues)}. Return a corrected complete JSON object only."
        )
    return (
        f"{original}\n\n上一次输出未通过本地校验： {'；'.join(issues)}。"
        "请只输出修正后的完整 JSON。"
    )
