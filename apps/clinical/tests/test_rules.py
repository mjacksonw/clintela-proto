"""Tests for clinical rules engine — one test per rule."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.clinical.constants import (
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
from apps.clinical.models import ClinicalObservation
from apps.clinical.rules import (
    RULE_REGISTRY,
    RuleResult,
    _compute_slope,
    check_all_rules,
    rule_bp_critical,
    rule_chf_decompensation,
    rule_hr_critical,
    rule_hr_trend_3day,
    rule_hr_warning,
    rule_infection_signal,
    rule_missing_hr,
    rule_missing_weight,
    rule_spo2_critical,
    rule_spo2_warning,
    rule_steps_declining_7day,
    rule_temp_critical,
    rule_temp_warning,
    rule_weight_gain_3day,
)


@pytest.fixture
def hospital(db):
    from apps.patients.models import Hospital

    return Hospital.objects.create(name="Test Hospital", code="RULES01")


@pytest.fixture
def patient(db, hospital):
    import uuid

    from apps.accounts.models import User
    from apps.patients.models import Patient

    user = User.objects.create_user(
        username=f"rules_{uuid.uuid4().hex[:8]}",
        password="testpass123",
        first_name="Rule",
        last_name="Test",
    )
    return Patient.objects.create(
        user=user,
        hospital=hospital,
        date_of_birth="1960-01-15",
        leaflet_code=uuid.uuid4().hex[:8],
        surgery_type="CABG",
    )


def _create_obs(patient, concept_id, value, hours_ago=0, **kwargs):
    """Helper to create a clinical observation."""
    from apps.clinical.constants import CONCEPT_NAMES, CONCEPT_UNITS

    return ClinicalObservation.objects.create(
        patient=patient,
        concept_id=concept_id,
        concept_name=CONCEPT_NAMES.get(concept_id, "Test"),
        value_numeric=Decimal(str(value)),
        unit=CONCEPT_UNITS.get(concept_id, ""),
        observed_at=timezone.now() - timedelta(hours=hours_ago),
        source="wearable",
        **kwargs,
    )


class TestRuleRegistry:
    def test_all_rules_registered(self):
        expected_rules = [
            "hr_critical",
            "hr_warning",
            "bp_critical",
            "spo2_critical",
            "spo2_warning",
            "temp_critical",
            "temp_warning",
            "weight_gain_3day",
            "hr_trend_3day",
            "bp_trend_3day",
            "steps_declining_7day",
            "missing_weight",
            "missing_hr",
            "chf_decompensation",
            "infection_signal",
            "epro_activity_correlation",
        ]
        for rule_name in expected_rules:
            assert rule_name in RULE_REGISTRY, f"Rule '{rule_name}' not registered"

    def test_check_all_rules_no_data(self, patient):
        results = check_all_rules(patient)
        assert results == []

    def test_check_all_rules_catches_exceptions(self, patient):
        """Rules engine should not crash if a rule throws."""
        results = check_all_rules(patient)
        assert isinstance(results, list)


class TestThresholdRules:
    def test_hr_critical_high(self, patient):
        _create_obs(patient, CONCEPT_HEART_RATE, 125)
        results = rule_hr_critical(patient)
        assert len(results) == 1
        assert results[0].severity == SEVERITY_RED
        assert results[0].rule_name == "hr_critical"
        assert "125" in results[0].rule_rationale

    def test_hr_critical_low(self, patient):
        _create_obs(patient, CONCEPT_HEART_RATE, 45)
        results = rule_hr_critical(patient)
        assert len(results) == 1
        assert results[0].severity == SEVERITY_RED

    def test_hr_critical_normal(self, patient):
        _create_obs(patient, CONCEPT_HEART_RATE, 72)
        results = rule_hr_critical(patient)
        assert results == []

    def test_hr_warning_high(self, patient):
        _create_obs(patient, CONCEPT_HEART_RATE, 105)
        results = rule_hr_warning(patient)
        assert len(results) == 1
        assert results[0].severity == SEVERITY_ORANGE

    def test_hr_warning_low(self, patient):
        _create_obs(patient, CONCEPT_HEART_RATE, 52)
        results = rule_hr_warning(patient)
        assert len(results) == 1
        assert results[0].severity == SEVERITY_ORANGE

    def test_hr_no_data(self, patient):
        assert rule_hr_critical(patient) == []
        assert rule_hr_warning(patient) == []

    def test_bp_critical_high(self, patient):
        _create_obs(patient, CONCEPT_SYSTOLIC_BP, 185)
        results = rule_bp_critical(patient)
        assert len(results) == 1
        assert results[0].severity == SEVERITY_RED

    def test_bp_critical_low(self, patient):
        _create_obs(patient, CONCEPT_SYSTOLIC_BP, 85)
        results = rule_bp_critical(patient)
        assert len(results) == 1
        assert results[0].severity == SEVERITY_RED

    def test_bp_normal(self, patient):
        _create_obs(patient, CONCEPT_SYSTOLIC_BP, 120)
        assert rule_bp_critical(patient) == []

    def test_spo2_critical(self, patient):
        _create_obs(patient, CONCEPT_SPO2, 90)
        results = rule_spo2_critical(patient)
        assert len(results) == 1
        assert results[0].severity == SEVERITY_RED

    def test_spo2_warning(self, patient):
        _create_obs(patient, CONCEPT_SPO2, 93)
        results = rule_spo2_warning(patient)
        assert len(results) == 1
        assert results[0].severity == SEVERITY_ORANGE

    def test_spo2_normal(self, patient):
        _create_obs(patient, CONCEPT_SPO2, 97)
        assert rule_spo2_critical(patient) == []
        assert rule_spo2_warning(patient) == []

    def test_temp_critical(self, patient):
        _create_obs(patient, CONCEPT_TEMPERATURE, 104)
        results = rule_temp_critical(patient)
        assert len(results) == 1
        assert results[0].severity == SEVERITY_RED

    def test_temp_warning(self, patient):
        _create_obs(patient, CONCEPT_TEMPERATURE, 102)
        results = rule_temp_warning(patient)
        assert len(results) == 1
        assert results[0].severity == SEVERITY_ORANGE

    def test_temp_normal(self, patient):
        _create_obs(patient, CONCEPT_TEMPERATURE, 98.6)
        assert rule_temp_critical(patient) == []
        assert rule_temp_warning(patient) == []


class TestTrendRules:
    def test_weight_gain_3day_orange(self, patient):
        """3.5 lbs gain over 3 days → ORANGE."""
        _create_obs(patient, CONCEPT_BODY_WEIGHT, 185, hours_ago=70)  # Within 3-day window
        _create_obs(patient, CONCEPT_BODY_WEIGHT, 188.5, hours_ago=0)
        results = rule_weight_gain_3day(patient)
        assert len(results) == 1
        assert results[0].severity == SEVERITY_ORANGE

    def test_weight_gain_3day_red(self, patient):
        """6 lbs gain over 3 days → RED."""
        _create_obs(patient, CONCEPT_BODY_WEIGHT, 185, hours_ago=70)  # Within 3-day window
        _create_obs(patient, CONCEPT_BODY_WEIGHT, 191, hours_ago=0)
        results = rule_weight_gain_3day(patient)
        assert len(results) == 1
        assert results[0].severity == SEVERITY_RED

    def test_weight_stable(self, patient):
        _create_obs(patient, CONCEPT_BODY_WEIGHT, 185, hours_ago=70)
        _create_obs(patient, CONCEPT_BODY_WEIGHT, 185.5, hours_ago=0)
        assert rule_weight_gain_3day(patient) == []

    def test_hr_trend_3day(self, patient):
        """HR increasing > 10% over 3 days → YELLOW."""
        for i in range(8):
            _create_obs(patient, CONCEPT_HEART_RATE, 70 + (i * 2), hours_ago=72 - (i * 9))
        results = rule_hr_trend_3day(patient)
        assert len(results) == 1
        assert results[0].severity == SEVERITY_YELLOW

    def test_steps_declining_7day(self, patient):
        """Steps declining > 30% over 7 days → YELLOW."""
        for i in range(14):
            steps = 4000 - (i * 200)  # Steady decline
            _create_obs(patient, CONCEPT_DAILY_STEPS, max(200, steps), hours_ago=168 - (i * 12))
        results = rule_steps_declining_7day(patient)
        assert len(results) == 1
        assert results[0].severity == SEVERITY_YELLOW

    def test_insufficient_data(self, patient):
        """Single data point should not trigger trend rules."""
        _create_obs(patient, CONCEPT_BODY_WEIGHT, 185)
        assert rule_weight_gain_3day(patient) == []


class TestMissingDataRules:
    def test_missing_weight_48h(self, patient):
        """No weight reading in 48+ hours → YELLOW."""
        _create_obs(patient, CONCEPT_BODY_WEIGHT, 185, hours_ago=50)
        results = rule_missing_weight(patient)
        assert len(results) == 1
        assert results[0].severity == SEVERITY_YELLOW

    def test_weight_recent(self, patient):
        """Weight reading within 48 hours → no alert."""
        _create_obs(patient, CONCEPT_BODY_WEIGHT, 185, hours_ago=24)
        assert rule_missing_weight(patient) == []

    def test_missing_weight_never_had(self, patient):
        """No weight reading ever → no alert (not a missing data issue)."""
        assert rule_missing_weight(patient) == []

    def test_missing_hr_24h(self, patient):
        _create_obs(patient, CONCEPT_HEART_RATE, 72, hours_ago=26)
        results = rule_missing_hr(patient)
        assert len(results) == 1
        assert results[0].severity == SEVERITY_INFO


class TestCombinationRules:
    def test_chf_decompensation(self, patient):
        """Weight gain + elevated HR + declining activity → RED."""
        # Weight gain (within 3-day window)
        _create_obs(patient, CONCEPT_BODY_WEIGHT, 185, hours_ago=70)
        _create_obs(patient, CONCEPT_BODY_WEIGHT, 188, hours_ago=0)

        # Elevated HR
        _create_obs(patient, CONCEPT_HEART_RATE, 95, hours_ago=0)

        # Declining steps
        for i in range(10):
            steps = 3000 if i < 5 else 1000
            _create_obs(patient, CONCEPT_DAILY_STEPS, steps, hours_ago=168 - (i * 16))

        results = rule_chf_decompensation(patient)
        assert len(results) == 1
        assert results[0].severity == SEVERITY_RED
        assert "CHF" in results[0].title

    def test_infection_signal(self, patient):
        """Elevated temp + elevated HR → ORANGE."""
        _create_obs(patient, CONCEPT_TEMPERATURE, 101.5)
        _create_obs(patient, CONCEPT_HEART_RATE, 95)
        results = rule_infection_signal(patient)
        assert len(results) == 1
        assert results[0].severity == SEVERITY_ORANGE

    def test_infection_signal_no_fever(self, patient):
        _create_obs(patient, CONCEPT_TEMPERATURE, 98.6)
        _create_obs(patient, CONCEPT_HEART_RATE, 95)
        assert rule_infection_signal(patient) == []


class TestHelpers:
    def test_compute_slope_flat(self):
        now = timezone.now()
        observations = [
            (Decimal("72"), now - timedelta(hours=48)),
            (Decimal("72"), now - timedelta(hours=24)),
            (Decimal("72"), now),
        ]
        slope = _compute_slope(observations)
        assert slope is not None
        assert abs(slope) < 0.1

    def test_compute_slope_increasing(self):
        now = timezone.now()
        observations = [
            (Decimal("70"), now - timedelta(days=2)),
            (Decimal("75"), now - timedelta(days=1)),
            (Decimal("80"), now),
        ]
        slope = _compute_slope(observations)
        assert slope is not None
        assert slope > 0

    def test_compute_slope_insufficient_data(self):
        now = timezone.now()
        assert _compute_slope([(Decimal("72"), now)]) is None
        assert _compute_slope([]) is None

    def test_rule_result_dataclass(self):
        result = RuleResult(
            rule_name="test",
            alert_type="threshold",
            severity="red",
            title="Test",
            description="Desc",
            rule_rationale="Rationale",
            trigger_data={"value": 125},
        )
        assert result.rule_name == "test"
        assert result.trigger_data == {"value": 125}
