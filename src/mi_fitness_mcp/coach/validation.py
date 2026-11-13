"""Semantic validation for generated training plans."""

from __future__ import annotations

from datetime import timedelta

from mi_fitness_mcp.coach.models import (
    Goal,
    PlanValidationIssue,
    PlanValidationResult,
    PlanWeek,
    TrainingPlanContent,
    TrainingProfile,
)

HARD_TYPES = {"tempo", "interval", "race"}
RACE_DISTANCE_CAPS_M = {
    "5k": 8000.0,
    "10k": 12000.0,
    "half": 18000.0,
    "full": 32000.0,
}
DIET_LANGUAGE = (
    "热量缺口",
    "断食",
    "节食",
    "calorie deficit",
    "fasting",
    "starvation",
)


def _volume(week: PlanWeek) -> tuple[int, float]:
    duration = 0
    distance = 0.0
    for session in week.sessions:
        if session.session_type == "rest":
            continue
        duration += session.duration_minutes
        distance += session.distance_m or 0
    return duration, distance


class PlanValidator:
    """Apply conservative, explainable safety and progression rules."""

    def validate(
        self,
        plan: TrainingPlanContent,
        goal: Goal,
        profile: TrainingProfile | None = None,
        *,
        max_session_minutes: int = 180,
    ) -> PlanValidationResult:
        issues: list[PlanValidationIssue] = []
        if not plan.weeks:
            issues.append(
                PlanValidationIssue(
                    code="PLAN_EMPTY", message="Plan has no weeks.", severity="error"
                )
            )
            return PlanValidationResult(status="failed", issues=issues)

        if not plan.safety.stop_rules or not plan.safety.disclaimer.strip():
            issues.append(
                PlanValidationIssue(
                    code="SAFETY_TEXT_MISSING",
                    message="Stop rules and a non-medical disclaimer are required.",
                    severity="error",
                )
            )

        previous_week: PlanWeek | None = None
        previous_volume: tuple[int, float] | None = None
        for index, week in enumerate(plan.weeks, start=1):
            if week.week_index != index:
                issues.append(
                    PlanValidationIssue(
                        code="WEEK_INDEX_INVALID",
                        message=f"Week index {week.week_index} should be {index}.",
                        severity="error",
                        week_index=week.week_index,
                    )
                )
            expected_start = plan.weeks[0].start_date + timedelta(weeks=index - 1)
            if week.start_date != expected_start:
                issues.append(
                    PlanValidationIssue(
                        code="WEEK_START_INVALID",
                        message="Week start dates must be contiguous 7-day blocks.",
                        severity="error",
                        week_index=week.week_index,
                    )
                )
            for session in week.sessions:
                if not week.start_date <= session.date <= week.start_date + timedelta(days=6):
                    issues.append(
                        PlanValidationIssue(
                            code="SESSION_OUTSIDE_WEEK",
                            message="Session date is outside its week.",
                            severity="error",
                            week_index=week.week_index,
                        )
                    )
                if session.session_type != "rest":
                    upper = 600 if session.session_type == "race" else 240
                    if not 10 <= session.duration_minutes <= upper:
                        issues.append(
                            PlanValidationIssue(
                                code="SESSION_DURATION_OUT_OF_BOUNDS",
                                message=f"Session duration must be 10-{upper} minutes.",
                                severity="error",
                                week_index=week.week_index,
                            )
                        )
                    if (
                        session.session_type != "race"
                        and session.duration_minutes > max_session_minutes * 1.5
                    ):
                        issues.append(
                            PlanValidationIssue(
                                code="SESSION_TOO_LONG",
                                message="Session exceeds the user's duration constraint.",
                                severity="error",
                                week_index=week.week_index,
                            )
                        )

            non_rest_dates = {
                session.date for session in week.sessions if session.session_type != "rest"
            }
            if len(non_rest_dates) >= 7:
                issues.append(
                    PlanValidationIssue(
                        code="NO_REST_DAY",
                        message="Each week needs at least one rest day.",
                        severity="error",
                        week_index=week.week_index,
                    )
                )
            hard_dates = sorted(
                session.date
                for session in week.sessions
                if session.session_type in HARD_TYPES
            )
            longest_run = 1
            current_run = 1
            for previous, current in zip(hard_dates, hard_dates[1:], strict=False):
                current_run = current_run + 1 if current == previous + timedelta(days=1) else 1
                longest_run = max(longest_run, current_run)
            if longest_run >= 3:
                issues.append(
                    PlanValidationIssue(
                        code="CONSECUTIVE_HARD_DAYS",
                        message="Avoid three consecutive hard days.",
                        severity="error",
                        week_index=week.week_index,
                    )
                )

            duration, distance = _volume(week)
            if (
                previous_week is not None
                and not previous_week.is_recovery_week
                and previous_volume is not None
                and previous_volume[0] > 0
                and not week.is_recovery_week
                and duration > previous_volume[0] * 1.10
            ):
                issues.append(
                    PlanValidationIssue(
                        code="WEEKLY_PROGRESSION_EXCEEDED",
                        message="Weekly duration increased by more than 10%.",
                        severity="error",
                        week_index=week.week_index,
                    )
                )
            if (
                previous_week is not None
                and not previous_week.is_recovery_week
                and previous_volume is not None
                and previous_volume[1] > 0
                and not week.is_recovery_week
                and distance > previous_volume[1] * 1.10
            ):
                issues.append(
                    PlanValidationIssue(
                        code="WEEKLY_PROGRESSION_EXCEEDED",
                        message="Weekly distance increased by more than 10%.",
                        severity="error",
                        week_index=week.week_index,
                    )
                )
            has_race = any(session.session_type == "race" for session in week.sessions)
            if (
                week.is_recovery_week
                and not has_race
                and previous_volume is not None
                and previous_volume[0] > 0
                and duration > previous_volume[0] * 0.80
            ):
                issues.append(
                    PlanValidationIssue(
                        code="RECOVERY_WEEK_TOO_HARD",
                        message="Recovery week should be at most 80% of the previous week.",
                        severity="error",
                        week_index=week.week_index,
                    )
                )
            previous_week = week
            previous_volume = (duration, distance)

        recovery_count = sum(1 for week in plan.weeks if week.is_recovery_week)
        if len(plan.weeks) >= 6 and recovery_count < max(1, len(plan.weeks) // 4):
            issues.append(
                PlanValidationIssue(
                    code="RECOVERY_WEEK_MISSING",
                    message="Plans of 6+ weeks need regular recovery weeks.",
                    severity="error",
                )
            )

        if goal.goal_type == "race" and goal.target_date is not None:
            self._validate_race(plan, goal, issues)
        self._validate_target(plan, goal, issues)
        self._validate_long_sessions(plan, goal, profile, issues)
        if goal.goal_type == "body_composition":
            self._validate_body_language(plan, issues)

        status = (
            "failed"
            if any(issue.severity == "error" for issue in issues)
            else "warnings"
            if issues
            else "passed"
        )
        return PlanValidationResult(status=status, issues=issues)

    def _validate_race(
        self, plan: TrainingPlanContent, goal: Goal, issues: list[PlanValidationIssue]
    ) -> None:
        assert goal.target_date is not None
        plan_start = plan.weeks[0].start_date
        plan_end = plan.weeks[-1].start_date + timedelta(days=6)
        if not plan_start <= goal.target_date <= plan_end:
            return
        race_sessions = [
            session
            for week in plan.weeks
            for session in week.sessions
            if session.date == goal.target_date and session.session_type == "race"
        ]
        if not race_sessions:
            issues.append(
                PlanValidationIssue(
                    code="RACE_DAY_MISSING",
                    message="Plan must include the race on the target date.",
                    severity="error",
                )
            )
        if any(
            session.date > goal.target_date
            for week in plan.weeks
            for session in week.sessions
            if session.session_type != "rest"
        ):
            issues.append(
                PlanValidationIssue(
                    code="SESSION_AFTER_RACE",
                    message="No sessions are allowed after the race date.",
                    severity="error",
                )
            )
        taper_start = goal.target_date - timedelta(days=7)
        if any(
            taper_start <= session.date < goal.target_date
            and session.session_type in HARD_TYPES - {"race"}
            for week in plan.weeks
            for session in week.sessions
        ):
            issues.append(
                PlanValidationIssue(
                    code="RACE_TAPER_MISSING",
                    message="Avoid hard sessions in the final 7 days before the race.",
                    severity="error",
                )
            )
        cap = RACE_DISTANCE_CAPS_M.get(goal.race_distance or "", 32000.0)
        if any(
            (session.distance_m or 0) > cap
            for week in plan.weeks
            for session in week.sessions
            if session.session_type != "race"
        ):
            issues.append(
                PlanValidationIssue(
                    code="LONG_SESSION_TOO_LONG",
                    message="A session exceeds the conservative race-distance cap.",
                    severity="error",
                )
            )

    def _validate_target(
        self, plan: TrainingPlanContent, goal: Goal, issues: list[PlanValidationIssue]
    ) -> None:
        target = goal.target_value
        if target is None or target <= 0:
            return
        if goal.goal_type == "weekly_frequency" and target > 6:
            # A safe plan supports at most six training days plus one rest day.
            issues.append(
                PlanValidationIssue(
                    code="FREQUENCY_TARGET_UNSUPPORTED",
                    message=(
                        "A safe plan supports at most six sessions per week; "
                        "the higher goal remains tracked outside the plan."
                    ),
                    severity="warning",
                )
            )
            return
        for week in plan.weeks:
            if week.is_recovery_week:
                continue
            sessions = [s for s in week.sessions if s.session_type != "rest"]
            if goal.goal_type == "weekly_frequency":
                if abs(len(sessions) - target) > 1:
                    issues.append(
                        PlanValidationIssue(
                            code="FREQUENCY_TARGET_MISMATCH",
                            message="Weekly session count is far from the goal.",
                            severity="error",
                            week_index=week.week_index,
                        )
                    )
            elif goal.goal_type == "weekly_duration":
                duration, _ = _volume(week)
                if abs(duration - target) / target > 0.25:
                    issues.append(
                        PlanValidationIssue(
                            code="DURATION_TARGET_MISMATCH",
                            message="Weekly duration is far from the goal.",
                            severity="error",
                            week_index=week.week_index,
                        )
                    )
            elif goal.goal_type == "distance":
                _, distance = _volume(week)
                if abs(distance - target) / target > 0.25:
                    issues.append(
                        PlanValidationIssue(
                            code="DISTANCE_TARGET_MISMATCH",
                            message="Weekly distance is far from the goal.",
                            severity="error",
                            week_index=week.week_index,
                        )
                    )

    def _validate_long_sessions(
        self,
        plan: TrainingPlanContent,
        goal: Goal,
        profile: TrainingProfile | None,
        issues: list[PlanValidationIssue],
    ) -> None:
        if goal.goal_type != "race" or not plan.weeks:
            return
        cap = RACE_DISTANCE_CAPS_M.get(goal.race_distance or "", 32000.0)
        longest_existing = (
            (profile.longest_session.distance_km or 0) * 1000 if profile else 0
        )
        first_week_long = max(
            (
                session.distance_m or 0
                for session in plan.weeks[0].sessions
                if session.session_type == "long"
            ),
            default=0,
        )
        if first_week_long > cap:
            issues.append(
                PlanValidationIssue(
                    code="LONG_SESSION_TOO_LONG",
                    message="First-week long session exceeds the race cap.",
                    severity="error",
                    week_index=1,
                )
            )
        if longest_existing > 0 and first_week_long > longest_existing * 1.10:
            issues.append(
                PlanValidationIssue(
                    code="LONG_SESSION_TOO_LONG",
                    message="First-week long session exceeds recent longest by >10%.",
                    severity="error",
                    week_index=1,
                )
            )

    @staticmethod
    def _validate_body_language(
        plan: TrainingPlanContent, issues: list[PlanValidationIssue]
    ) -> None:
        text = " ".join(
            [
                plan.title,
                plan.summary,
                *plan.weekly_habits,
                *(
                    f"{session.description} {session.purpose}"
                    for week in plan.weeks
                    for session in week.sessions
                ),
            ]
        ).lower()
        if any(term.lower() in text for term in DIET_LANGUAGE):
            issues.append(
                PlanValidationIssue(
                    code="BODY_COMPOSITION_DIET_LANGUAGE",
                    message="Body-composition plans must not contain diet prescriptions.",
                    severity="error",
                )
            )
