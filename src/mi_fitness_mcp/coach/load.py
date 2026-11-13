"""Transparent training-load proxy for the coach profile.

This is deliberately a simple duration × heart-rate-reserve factor, not a
Garmin EPOC or proprietary training-load claim.  When heart-rate context is
missing the result is marked uncalibrated rather than pretending to be precise.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LoadEstimate:
    load: float
    bucket: str
    calibrated: bool


def estimate_training_load(
    *,
    duration_minutes: float,
    avg_hr_bpm: float | None = None,
    observed_max_hr: float | None = None,
    resting_hr: float | None = None,
) -> LoadEstimate:
    """Return a unitless load proxy and an interpretable intensity bucket."""
    minutes = max(0.0, float(duration_minutes))
    if (
        avg_hr_bpm
        and observed_max_hr
        and resting_hr
        and observed_max_hr > resting_hr + 20
    ):
        reserve = (avg_hr_bpm - resting_hr) / (observed_max_hr - resting_hr)
        if reserve < 0.65:
            factor, bucket = 1.0, "low_aerobic"
        elif reserve < 0.78:
            factor, bucket = 1.4, "moderate_aerobic"
        else:
            factor, bucket = 1.8, "high_intensity"
        return LoadEstimate(round(minutes * factor, 2), bucket, True)
    return LoadEstimate(round(minutes * 1.2, 2), "uncalibrated", False)
