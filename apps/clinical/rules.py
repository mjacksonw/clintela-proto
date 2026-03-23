"""Clinical Rules Engine — deterministic, auditable, FDA-aligned.

Rule registry pattern: each rule is a function registered in RULE_REGISTRY.
Rules return a list of RuleResult objects (or empty list if no alert needed).

Architecture:
  ingest_observation() ──► rules_engine.check() ──► [RuleResult, ...]
                                                         │
                                                    ClinicalAlert created
                                                    with rule_rationale

Each rule receives the patient and returns results with:
  - alert_type, severity, title, description
  - rule_rationale (FDA 2026 CDS transparency requirement)
  - trigger_data (the observations that fired the rule)
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta

from django.utils import timezone

from apps.clinical.constants import (
    ALERT_TYPE_COMBINATION,
    ALERT_TYPE_MISSING_DATA,
    ALERT_TYPE_THRESHOLD,
    ALERT_TYPE_TREND,
    CONCEPT_BODY_WEIGHT,
    CONCEPT_DAILY_STEPS,
    CONCEPT_HEART_RATE,
    CONCEPT_SPO2,
    CONCEPT_SYSTOLIC_BP,
    CONCEPT_TEMPERATURE,
    SEVERITY_INFO,
    SEVERITY_ORANGE,
    SEVERITY_RED,
    SEVERITY_YELLOW,
)

logger = logging.getLogger(__name__)


@dataclass
class RuleResult:
    rule_name: str
    alert_type: str
    severity: str
    title: str
    description: str
    rule_rationale: str
    trigger_data: dict = field(default_factory=dict)


# Type for rule functions: (patient) -> list[RuleResult]
RuleFunction = Callable[..., list[RuleResult]]

# ──────────────────────────────────────────────────────────────────────
# Rule Registry
# ──────────────────────────────────────────────────────────────────────

RULE_REGISTRY: dict[str, RuleFunction] = {}


def register_rule(name: str):
    """Decorator to register a rule function."""

    def decorator(func: RuleFunction) -> RuleFunction:
        RULE_REGISTRY[name] = func
        return func

    return decorator


def check_all_rules(patient) -> list[RuleResult]:
    """Run all registered rules for a patient. Returns list of RuleResults."""
    results = []
    for rule_name, rule_func in RULE_REGISTRY.items():
        try:
            rule_results = rule_func(patient)
            results.extend(rule_results)
        except Exception:
            logger.exception("Rule '%s' failed for patient %s", rule_name, patient.pk)
    return results


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def _get_latest_observation(patient, concept_id):
    """Get the most recent observation for a concept."""
    from apps.clinical.models import ClinicalObservation

    return ClinicalObservation.objects.filter(patient=patient, concept_id=concept_id).order_by("-observed_at").first()


def _get_observations_in_window(patient, concept_id, days):
    """Get observations for a concept within a time window."""
    from apps.clinical.models import ClinicalObservation

    since = timezone.now() - timedelta(days=days)
    return list(
        ClinicalObservation.objects.filter(
            patient=patient,
            concept_id=concept_id,
            observed_at__gte=since,
            value_numeric__isnull=False,
        )
        .order_by("observed_at")
        .values_list("value_numeric", "observed_at")
    )


def _compute_slope(observations):
    """Compute slope of values over time. Returns change per day.

    Uses simple linear regression with Python's built-in statistics module.
    Returns None if insufficient data (< 2 points).
    """
    if len(observations) < 2:
        return None

    # Convert to (days_from_start, value) pairs
    t0 = observations[0][1]
    points = []
    for value, timestamp in observations:
        days = (timestamp - t0).total_seconds() / 86400
        points.append((days, float(value)))

    n = len(points)
    if n < 2:
        return None

    sum_x = sum(p[0] for p in points)
    sum_y = sum(p[1] for p in points)
    sum_xy = sum(p[0] * p[1] for p in points)
    sum_x2 = sum(p[0] ** 2 for p in points)

    denom = n * sum_x2 - sum_x**2
    if abs(denom) < 1e-10:
        return 0.0

    return (n * sum_xy - sum_x * sum_y) / denom


# ──────────────────────────────────────────────────────────────────────
# Threshold Rules
# ──────────────────────────────────────────────────────────────────────


@register_rule("hr_critical")
def rule_hr_critical(patient) -> list[RuleResult]:
    obs = _get_latest_observation(patient, CONCEPT_HEART_RATE)
    if not obs or obs.value_numeric is None:
        return []
    hr = float(obs.value_numeric)
    if hr > 120:
        return [
            RuleResult(
                rule_name="hr_critical",
                alert_type=ALERT_TYPE_THRESHOLD,
                severity=SEVERITY_RED,
                title="Critical Heart Rate — Elevated",
                description=f"Heart rate of {hr:.0f} bpm exceeds critical threshold of 120 bpm.",
                rule_rationale=(
                    f"Heart rate measured at {hr:.0f} bpm (threshold: >120 bpm). "
                    "Sustained tachycardia after cardiac surgery may indicate "
                    "hemodynamic instability, infection, or arrhythmia. "
                    "Immediate clinical review recommended."
                ),
                trigger_data={"concept_id": CONCEPT_HEART_RATE, "value": hr, "threshold": 120, "direction": "above"},
            )
        ]
    if hr < 50:
        return [
            RuleResult(
                rule_name="hr_critical",
                alert_type=ALERT_TYPE_THRESHOLD,
                severity=SEVERITY_RED,
                title="Critical Heart Rate — Low",
                description=f"Heart rate of {hr:.0f} bpm below critical threshold of 50 bpm.",
                rule_rationale=(
                    f"Heart rate measured at {hr:.0f} bpm (threshold: <50 bpm). "
                    "Significant bradycardia after cardiac surgery may indicate "
                    "conduction system damage or medication effects. "
                    "Immediate clinical review recommended."
                ),
                trigger_data={"concept_id": CONCEPT_HEART_RATE, "value": hr, "threshold": 50, "direction": "below"},
            )
        ]
    return []


@register_rule("hr_warning")
def rule_hr_warning(patient) -> list[RuleResult]:
    obs = _get_latest_observation(patient, CONCEPT_HEART_RATE)
    if not obs or obs.value_numeric is None:
        return []
    hr = float(obs.value_numeric)
    if hr > 100 and hr <= 120:
        return [
            RuleResult(
                rule_name="hr_warning",
                alert_type=ALERT_TYPE_THRESHOLD,
                severity=SEVERITY_ORANGE,
                title="Elevated Heart Rate",
                description=f"Heart rate of {hr:.0f} bpm exceeds warning threshold of 100 bpm.",
                rule_rationale=(
                    f"Heart rate measured at {hr:.0f} bpm (threshold: >100 bpm). "
                    "Mild tachycardia in the post-surgical period warrants monitoring. "
                    "May be related to pain, anxiety, dehydration, or early infection."
                ),
                trigger_data={"concept_id": CONCEPT_HEART_RATE, "value": hr, "threshold": 100, "direction": "above"},
            )
        ]
    if hr < 55 and hr >= 50:
        return [
            RuleResult(
                rule_name="hr_warning",
                alert_type=ALERT_TYPE_THRESHOLD,
                severity=SEVERITY_ORANGE,
                title="Low Heart Rate",
                description=f"Heart rate of {hr:.0f} bpm below warning threshold of 55 bpm.",
                rule_rationale=(
                    f"Heart rate measured at {hr:.0f} bpm (threshold: <55 bpm). "
                    "Mild bradycardia may be medication-related (beta-blockers) "
                    "or indicate conduction changes. Monitor for symptoms."
                ),
                trigger_data={"concept_id": CONCEPT_HEART_RATE, "value": hr, "threshold": 55, "direction": "below"},
            )
        ]
    return []


@register_rule("bp_critical")
def rule_bp_critical(patient) -> list[RuleResult]:
    obs = _get_latest_observation(patient, CONCEPT_SYSTOLIC_BP)
    if not obs or obs.value_numeric is None:
        return []
    sbp = float(obs.value_numeric)
    if sbp > 180:
        return [
            RuleResult(
                rule_name="bp_critical",
                alert_type=ALERT_TYPE_THRESHOLD,
                severity=SEVERITY_RED,
                title="Critical Blood Pressure — Hypertensive",
                description=f"Systolic BP of {sbp:.0f} mmHg exceeds critical threshold of 180 mmHg.",
                rule_rationale=(
                    f"Systolic blood pressure measured at {sbp:.0f} mmHg (threshold: >180 mmHg). "
                    "Hypertensive urgency after cardiac surgery increases risk of "
                    "surgical site bleeding and stroke. Immediate intervention needed."
                ),
                trigger_data={
                    "concept_id": CONCEPT_SYSTOLIC_BP,
                    "value": sbp,
                    "threshold": 180,
                    "direction": "above",
                },
            )
        ]
    if sbp < 90:
        return [
            RuleResult(
                rule_name="bp_critical",
                alert_type=ALERT_TYPE_THRESHOLD,
                severity=SEVERITY_RED,
                title="Critical Blood Pressure — Hypotensive",
                description=f"Systolic BP of {sbp:.0f} mmHg below critical threshold of 90 mmHg.",
                rule_rationale=(
                    f"Systolic blood pressure measured at {sbp:.0f} mmHg (threshold: <90 mmHg). "
                    "Hypotension after cardiac surgery may indicate bleeding, "
                    "dehydration, or cardiac dysfunction. Immediate assessment needed."
                ),
                trigger_data={
                    "concept_id": CONCEPT_SYSTOLIC_BP,
                    "value": sbp,
                    "threshold": 90,
                    "direction": "below",
                },
            )
        ]
    return []


@register_rule("spo2_critical")
def rule_spo2_critical(patient) -> list[RuleResult]:
    obs = _get_latest_observation(patient, CONCEPT_SPO2)
    if not obs or obs.value_numeric is None:
        return []
    spo2 = float(obs.value_numeric)
    if spo2 < 92:
        return [
            RuleResult(
                rule_name="spo2_critical",
                alert_type=ALERT_TYPE_THRESHOLD,
                severity=SEVERITY_RED,
                title="Critical Oxygen Saturation",
                description=f"SpO2 of {spo2:.0f}% below critical threshold of 92%.",
                rule_rationale=(
                    f"Oxygen saturation measured at {spo2:.0f}% (threshold: <92%). "
                    "Significant hypoxemia after cardiac surgery may indicate "
                    "pulmonary complications, fluid overload, or cardiac dysfunction. "
                    "Immediate clinical review recommended."
                ),
                trigger_data={"concept_id": CONCEPT_SPO2, "value": spo2, "threshold": 92, "direction": "below"},
            )
        ]
    return []


@register_rule("spo2_warning")
def rule_spo2_warning(patient) -> list[RuleResult]:
    obs = _get_latest_observation(patient, CONCEPT_SPO2)
    if not obs or obs.value_numeric is None:
        return []
    spo2 = float(obs.value_numeric)
    if spo2 < 95 and spo2 >= 92:
        return [
            RuleResult(
                rule_name="spo2_warning",
                alert_type=ALERT_TYPE_THRESHOLD,
                severity=SEVERITY_ORANGE,
                title="Low Oxygen Saturation",
                description=f"SpO2 of {spo2:.0f}% below warning threshold of 95%.",
                rule_rationale=(
                    f"Oxygen saturation measured at {spo2:.0f}% (threshold: <95%). "
                    "Mild hypoxemia may indicate atelectasis or early fluid retention. "
                    "Monitor trend and encourage deep breathing exercises."
                ),
                trigger_data={"concept_id": CONCEPT_SPO2, "value": spo2, "threshold": 95, "direction": "below"},
            )
        ]
    return []


@register_rule("temp_critical")
def rule_temp_critical(patient) -> list[RuleResult]:
    obs = _get_latest_observation(patient, CONCEPT_TEMPERATURE)
    if not obs or obs.value_numeric is None:
        return []
    temp = float(obs.value_numeric)
    if temp > 103:
        return [
            RuleResult(
                rule_name="temp_critical",
                alert_type=ALERT_TYPE_THRESHOLD,
                severity=SEVERITY_RED,
                title="Critical Fever",
                description=f"Temperature of {temp:.1f}°F exceeds critical threshold of 103°F.",
                rule_rationale=(
                    f"Temperature measured at {temp:.1f}°F (threshold: >103°F). "
                    "High fever after cardiac surgery strongly suggests infection "
                    "(surgical site, pneumonia, or endocarditis). "
                    "Immediate clinical evaluation and cultures recommended."
                ),
                trigger_data={
                    "concept_id": CONCEPT_TEMPERATURE,
                    "value": temp,
                    "threshold": 103,
                    "direction": "above",
                },
            )
        ]
    return []


@register_rule("temp_warning")
def rule_temp_warning(patient) -> list[RuleResult]:
    obs = _get_latest_observation(patient, CONCEPT_TEMPERATURE)
    if not obs or obs.value_numeric is None:
        return []
    temp = float(obs.value_numeric)
    if temp > 101.5 and temp <= 103:
        return [
            RuleResult(
                rule_name="temp_warning",
                alert_type=ALERT_TYPE_THRESHOLD,
                severity=SEVERITY_ORANGE,
                title="Elevated Temperature",
                description=f"Temperature of {temp:.1f}°F exceeds warning threshold of 101.5°F.",
                rule_rationale=(
                    f"Temperature measured at {temp:.1f}°F (threshold: >101.5°F). "
                    "Low-grade fever in the early post-surgical period is common, "
                    "but persistent elevation warrants assessment for wound infection, "
                    "urinary tract infection, or pneumonia."
                ),
                trigger_data={
                    "concept_id": CONCEPT_TEMPERATURE,
                    "value": temp,
                    "threshold": 101.5,
                    "direction": "above",
                },
            )
        ]
    return []


# ──────────────────────────────────────────────────────────────────────
# Trend Rules
# ──────────────────────────────────────────────────────────────────────


@register_rule("weight_gain_3day")
def rule_weight_gain_3day(patient) -> list[RuleResult]:
    """Weight gain > 3 lbs in 3 days — fluid retention signal for CHF."""
    observations = _get_observations_in_window(patient, CONCEPT_BODY_WEIGHT, days=3)
    if len(observations) < 2:
        return []

    first_value = float(observations[0][0])
    last_value = float(observations[-1][0])
    gain = last_value - first_value

    if gain > 5:
        return [
            RuleResult(
                rule_name="weight_gain_3day",
                alert_type=ALERT_TYPE_TREND,
                severity=SEVERITY_RED,
                title="Significant Weight Gain",
                description=f"Weight increased {gain:.1f} lbs over 3 days.",
                rule_rationale=(
                    f"Body weight increased {gain:.1f} lbs over the past 3 days "
                    f"(from {first_value:.1f} to {last_value:.1f} lbs, threshold: >5 lbs). "
                    "Rapid weight gain is a hallmark sign of fluid retention and "
                    "possible heart failure decompensation. Immediate clinical review "
                    "and potential diuretic adjustment recommended."
                ),
                trigger_data={
                    "concept_id": CONCEPT_BODY_WEIGHT,
                    "first_value": first_value,
                    "last_value": last_value,
                    "gain": gain,
                    "days": 3,
                    "threshold": 5,
                },
            )
        ]
    if gain > 3:
        return [
            RuleResult(
                rule_name="weight_gain_3day",
                alert_type=ALERT_TYPE_TREND,
                severity=SEVERITY_ORANGE,
                title="Weight Trending Up",
                description=f"Weight increased {gain:.1f} lbs over 3 days.",
                rule_rationale=(
                    f"Body weight increased {gain:.1f} lbs over the past 3 days "
                    f"(from {first_value:.1f} to {last_value:.1f} lbs, threshold: >3 lbs). "
                    "This pattern can indicate fluid retention, a common early sign "
                    "of heart failure decompensation. Close monitoring and daily "
                    "weight checks recommended."
                ),
                trigger_data={
                    "concept_id": CONCEPT_BODY_WEIGHT,
                    "first_value": first_value,
                    "last_value": last_value,
                    "gain": gain,
                    "days": 3,
                    "threshold": 3,
                },
            )
        ]
    return []


@register_rule("hr_trend_3day")
def rule_hr_trend_3day(patient) -> list[RuleResult]:
    """HR trending upward > 10% over 3 days."""
    observations = _get_observations_in_window(patient, CONCEPT_HEART_RATE, days=3)
    if len(observations) < 4:
        return []

    first_value = float(observations[0][0])
    last_value = float(observations[-1][0])
    if first_value == 0:
        return []

    pct_change = ((last_value - first_value) / first_value) * 100
    if pct_change > 10:
        return [
            RuleResult(
                rule_name="hr_trend_3day",
                alert_type=ALERT_TYPE_TREND,
                severity=SEVERITY_YELLOW,
                title="Heart Rate Trending Up",
                description=f"Heart rate increased {pct_change:.0f}% over 3 days.",
                rule_rationale=(
                    f"Heart rate trending upward by {pct_change:.0f}% over the past 3 days "
                    f"(from {first_value:.0f} to {last_value:.0f} bpm, threshold: >10%). "
                    "Progressive tachycardia may indicate developing infection, "
                    "dehydration, pain, or cardiac stress. Monitor closely."
                ),
                trigger_data={
                    "concept_id": CONCEPT_HEART_RATE,
                    "first_value": first_value,
                    "last_value": last_value,
                    "pct_change": pct_change,
                    "threshold_pct": 10,
                },
            )
        ]
    return []


@register_rule("bp_trend_3day")
def rule_bp_trend_3day(patient) -> list[RuleResult]:
    """BP trending upward > 15% over 3 days."""
    observations = _get_observations_in_window(patient, CONCEPT_SYSTOLIC_BP, days=3)
    if len(observations) < 4:
        return []

    first_value = float(observations[0][0])
    last_value = float(observations[-1][0])
    if first_value == 0:
        return []

    pct_change = ((last_value - first_value) / first_value) * 100
    if pct_change > 15:
        return [
            RuleResult(
                rule_name="bp_trend_3day",
                alert_type=ALERT_TYPE_TREND,
                severity=SEVERITY_YELLOW,
                title="Blood Pressure Trending Up",
                description=f"Systolic BP increased {pct_change:.0f}% over 3 days.",
                rule_rationale=(
                    f"Systolic blood pressure trending upward by {pct_change:.0f}% over the past 3 days "
                    f"(from {first_value:.0f} to {last_value:.0f} mmHg, threshold: >15%). "
                    "Progressive hypertension may indicate pain, medication non-adherence, "
                    "or renal complications. Review medication plan."
                ),
                trigger_data={
                    "concept_id": CONCEPT_SYSTOLIC_BP,
                    "first_value": first_value,
                    "last_value": last_value,
                    "pct_change": pct_change,
                    "threshold_pct": 15,
                },
            )
        ]
    return []


@register_rule("steps_declining_7day")
def rule_steps_declining_7day(patient) -> list[RuleResult]:
    """Step count declining > 30% over 7 days."""
    observations = _get_observations_in_window(patient, CONCEPT_DAILY_STEPS, days=7)
    if len(observations) < 4:
        return []

    # Compare first 2 days avg to last 2 days avg
    early = [float(v) for v, _ in observations[: len(observations) // 3]]
    late = [float(v) for v, _ in observations[-(len(observations) // 3) :]]
    if not early or not late:
        return []

    early_avg = sum(early) / len(early)
    late_avg = sum(late) / len(late)
    if early_avg == 0:
        return []

    pct_decline = ((early_avg - late_avg) / early_avg) * 100
    if pct_decline > 30:
        return [
            RuleResult(
                rule_name="steps_declining_7day",
                alert_type=ALERT_TYPE_TREND,
                severity=SEVERITY_YELLOW,
                title="Declining Activity Level",
                description=f"Daily step count declined {pct_decline:.0f}% over 7 days.",
                rule_rationale=(
                    f"Daily step count declined approximately {pct_decline:.0f}% over the past week "
                    f"(from ~{early_avg:.0f} to ~{late_avg:.0f} steps/day, threshold: >30% decline). "
                    "Declining mobility after surgery may indicate increasing pain, "
                    "fatigue, depression, or functional decline. Consider outreach."
                ),
                trigger_data={
                    "concept_id": CONCEPT_DAILY_STEPS,
                    "early_avg": early_avg,
                    "late_avg": late_avg,
                    "pct_decline": pct_decline,
                    "threshold_pct": 30,
                },
            )
        ]
    return []


# ──────────────────────────────────────────────────────────────────────
# Missing Data Rules
# ──────────────────────────────────────────────────────────────────────


@register_rule("missing_weight")
def rule_missing_weight(patient) -> list[RuleResult]:
    """No weight reading in 48 hours."""
    obs = _get_latest_observation(patient, CONCEPT_BODY_WEIGHT)
    if obs is None:
        return []  # Never had a weight reading — not a missing data issue
    hours_since = (timezone.now() - obs.observed_at).total_seconds() / 3600
    if hours_since > 48:
        return [
            RuleResult(
                rule_name="missing_weight",
                alert_type=ALERT_TYPE_MISSING_DATA,
                severity=SEVERITY_YELLOW,
                title="Missing Weight Data",
                description=f"No weight reading in {hours_since:.0f} hours.",
                rule_rationale=(
                    f"Last weight measurement was {hours_since:.0f} hours ago (threshold: 48 hours). "
                    "Daily weight monitoring is critical for detecting fluid retention "
                    "in post-cardiac surgery patients. Missing data reduces our ability "
                    "to detect early signs of heart failure decompensation."
                ),
                trigger_data={
                    "concept_id": CONCEPT_BODY_WEIGHT,
                    "hours_since": hours_since,
                    "threshold_hours": 48,
                },
            )
        ]
    return []


@register_rule("missing_hr")
def rule_missing_hr(patient) -> list[RuleResult]:
    """No heart rate data in 24 hours."""
    obs = _get_latest_observation(patient, CONCEPT_HEART_RATE)
    if obs is None:
        return []
    hours_since = (timezone.now() - obs.observed_at).total_seconds() / 3600
    if hours_since > 24:
        return [
            RuleResult(
                rule_name="missing_hr",
                alert_type=ALERT_TYPE_MISSING_DATA,
                severity=SEVERITY_INFO,
                title="Missing Heart Rate Data",
                description=f"No heart rate reading in {hours_since:.0f} hours.",
                rule_rationale=(
                    f"Last heart rate measurement was {hours_since:.0f} hours ago (threshold: 24 hours). "
                    "The wearable device may be off, uncharged, or removed. "
                    "Consider a gentle reminder to the patient."
                ),
                trigger_data={
                    "concept_id": CONCEPT_HEART_RATE,
                    "hours_since": hours_since,
                    "threshold_hours": 24,
                },
            )
        ]
    return []


# ──────────────────────────────────────────────────────────────────────
# Combination Rules
# ──────────────────────────────────────────────────────────────────────


@register_rule("chf_decompensation")
def rule_chf_decompensation(patient) -> list[RuleResult]:
    """Weight gain + elevated HR + declining activity = CHF decompensation signal."""
    # Check weight gain
    weight_obs = _get_observations_in_window(patient, CONCEPT_BODY_WEIGHT, days=3)
    if len(weight_obs) < 2:
        return []
    weight_gain = float(weight_obs[-1][0]) - float(weight_obs[0][0])

    # Check HR elevation
    hr_obs = _get_latest_observation(patient, CONCEPT_HEART_RATE)
    hr_elevated = hr_obs and hr_obs.value_numeric and float(hr_obs.value_numeric) > 90

    # Check activity decline
    steps_obs = _get_observations_in_window(patient, CONCEPT_DAILY_STEPS, days=7)
    activity_declining = False
    if len(steps_obs) >= 4:
        early = [float(v) for v, _ in steps_obs[: len(steps_obs) // 2]]
        late = [float(v) for v, _ in steps_obs[len(steps_obs) // 2 :]]
        if early and late:
            early_avg = sum(early) / len(early)
            late_avg = sum(late) / len(late)
            activity_declining = early_avg > 0 and ((early_avg - late_avg) / early_avg) > 0.2

    if weight_gain > 2 and hr_elevated and activity_declining:
        return [
            RuleResult(
                rule_name="chf_decompensation",
                alert_type=ALERT_TYPE_COMBINATION,
                severity=SEVERITY_RED,
                title="CHF Decompensation Pattern Detected",
                description="Multiple indicators suggest possible heart failure decompensation.",
                rule_rationale=(
                    "Three concurrent signals detected: "
                    f"(1) Weight gain of {weight_gain:.1f} lbs over 3 days, "
                    f"(2) Elevated heart rate at {float(hr_obs.value_numeric):.0f} bpm, "
                    f"(3) Declining daily activity. "
                    "This combination pattern is a classic early indicator of "
                    "heart failure decompensation. The convergence of fluid retention "
                    "(weight), compensatory tachycardia (HR), and functional decline "
                    "(activity) warrants urgent clinical assessment and possible "
                    "diuretic adjustment."
                ),
                trigger_data={
                    "weight_gain": weight_gain,
                    "hr": float(hr_obs.value_numeric),
                    "activity_declining": True,
                },
            )
        ]
    return []


@register_rule("infection_signal")
def rule_infection_signal(patient) -> list[RuleResult]:
    """Elevated temperature + elevated HR = possible infection."""
    temp_obs = _get_latest_observation(patient, CONCEPT_TEMPERATURE)
    hr_obs = _get_latest_observation(patient, CONCEPT_HEART_RATE)

    if not temp_obs or not hr_obs:
        return []
    if temp_obs.value_numeric is None or hr_obs.value_numeric is None:
        return []

    temp = float(temp_obs.value_numeric)
    hr = float(hr_obs.value_numeric)

    if temp > 100.4 and hr > 90:
        return [
            RuleResult(
                rule_name="infection_signal",
                alert_type=ALERT_TYPE_COMBINATION,
                severity=SEVERITY_ORANGE,
                title="Possible Infection Pattern",
                description=f"Elevated temperature ({temp:.1f}°F) with elevated heart rate ({hr:.0f} bpm).",
                rule_rationale=(
                    f"Temperature of {temp:.1f}°F combined with heart rate of {hr:.0f} bpm. "
                    "The combination of fever and tachycardia after cardiac surgery "
                    "raises concern for infection (wound site, pneumonia, or urinary). "
                    "Clinical assessment, blood cultures, and wound inspection recommended."
                ),
                trigger_data={
                    "temp": temp,
                    "hr": hr,
                },
            )
        ]
    return []


# ──────────────────────────────────────────────────────────────────────
# ePRO Correlation Rule (CEO cherry-pick)
# ──────────────────────────────────────────────────────────────────────


@register_rule("epro_activity_correlation")
def rule_epro_activity_correlation(patient) -> list[RuleResult]:
    """PHQ-2 score increase + step count decline = cross-domain signal."""
    # Check for recent PHQ-2 survey completion
    try:
        from apps.surveys.models import SurveyInstance

        recent_surveys = list(
            SurveyInstance.objects.filter(
                patient=patient,
                instrument__code="PHQ2",
                status="completed",
            ).order_by("-completed_at")[:2]
        )
    except Exception:
        return []  # surveys app not available

    if len(recent_surveys) < 2:
        return []

    # Compare most recent to previous
    current_score = recent_surveys[0].total_score or 0
    previous_score = recent_surveys[1].total_score or 0

    if current_score <= previous_score:
        return []

    # Check activity decline
    steps_obs = _get_observations_in_window(patient, CONCEPT_DAILY_STEPS, days=7)
    if len(steps_obs) < 4:
        return []

    early = [float(v) for v, _ in steps_obs[: len(steps_obs) // 2]]
    late = [float(v) for v, _ in steps_obs[len(steps_obs) // 2 :]]
    if not early or not late:
        return []

    early_avg = sum(early) / len(early)
    late_avg = sum(late) / len(late)
    if early_avg == 0:
        return []

    pct_decline = ((early_avg - late_avg) / early_avg) * 100
    if pct_decline > 30:
        return [
            RuleResult(
                rule_name="epro_activity_correlation",
                alert_type=ALERT_TYPE_COMBINATION,
                severity=SEVERITY_ORANGE,
                title="Depression + Activity Decline Pattern",
                description=(
                    f"Depression screening score increased ({previous_score}→{current_score}) "
                    f"while activity declined {pct_decline:.0f}%."
                ),
                rule_rationale=(
                    f"Depression screening score (PHQ-2) increased from {previous_score} to "
                    f"{current_score} while daily step count declined approximately {pct_decline:.0f}% "
                    f"over the past week (from ~{early_avg:.0f} to ~{late_avg:.0f} steps/day). "
                    "This combination pattern — worsening mood with declining physical activity — "
                    "warrants clinical review. Post-surgical depression is associated with "
                    "worse recovery outcomes and higher readmission rates."
                ),
                trigger_data={
                    "phq2_previous": previous_score,
                    "phq2_current": current_score,
                    "steps_early_avg": early_avg,
                    "steps_late_avg": late_avg,
                    "steps_decline_pct": pct_decline,
                },
            )
        ]
    return []
