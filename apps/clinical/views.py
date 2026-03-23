"""Clinical data HTMX fragment views."""

import json
import logging
from functools import wraps

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from apps.clinical.constants import (
    CHART_VITALS,
    CONCEPT_NAMES,
    CONCEPT_UNITS,
    NORMAL_RANGES,
    SPARKLINE_VITALS,
    TRAJECTORY_CONCERNING,
    TRAJECTORY_DETERIORATING,
    TRAJECTORY_IMPROVING,
    TRAJECTORY_STABLE,
)
from apps.clinical.models import PatientClinicalSnapshot
from apps.clinical.services import ClinicalDataService
from apps.patients.models import Patient

logger = logging.getLogger(__name__)


def _require_clinical_enabled(view_func):
    """Return empty response if clinical data feature flag is off."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not getattr(settings, "ENABLE_CLINICAL_DATA", False):
            return HttpResponse("")
        return view_func(request, *args, **kwargs)

    return wrapper


@require_GET
@_require_clinical_enabled
def vitals_tab_fragment(request, patient_id):
    """Clinician Vitals tab — HTMX fragment with Chart.js data.

    Information hierarchy:
    1. Snapshot summary bar (trajectory + risk + completeness)
    2. Active alerts list with expandable rule_rationale
    3. Vital sign trend charts (Chart.js via json_script)
    4. Lab results table
    """
    if not request.user.is_authenticated:
        return HttpResponse("", status=403)

    # IDOR protection: verify the user is a clinician with access to this patient's hospital
    if not hasattr(request.user, "clinician_profile"):
        return HttpResponse("", status=403)
    clinician = request.user.clinician_profile
    patient = get_object_or_404(Patient, pk=patient_id)
    if patient.hospital_id and patient.hospital_id not in clinician.hospitals.values_list("id", flat=True):
        return HttpResponse("", status=403)

    # Get snapshot (may not exist yet)
    try:
        snapshot = patient.clinical_snapshot
    except PatientClinicalSnapshot.DoesNotExist:
        snapshot = None

    # Get active alerts
    alerts = ClinicalDataService.get_patient_alerts(patient, status="active")

    # Build chart data for each vital
    chart_data = {}
    for concept_id in CHART_VITALS:
        name = CONCEPT_NAMES[concept_id]
        trend = ClinicalDataService.get_trend_data(patient, concept_id, days=30)
        if trend:
            normal = NORMAL_RANGES.get(concept_id)
            chart_data[name] = {
                "labels": [t["observed_at"].strftime("%m/%d") for t in trend],
                "values": [float(t["value_numeric"]) for t in trend],
                "unit": CONCEPT_UNITS[concept_id],
                "normal_low": normal[0] if normal else None,
                "normal_high": normal[1] if normal else None,
                "concept_id": concept_id,
            }

    # Lab results (BNP, troponin, etc.)
    from apps.clinical.constants import CONCEPT_BNP, CONCEPT_TROPONIN

    lab_concepts = [CONCEPT_BNP, CONCEPT_TROPONIN]
    lab_results = []
    for concept_id in lab_concepts:
        from apps.clinical.models import ClinicalObservation

        obs = (
            ClinicalObservation.objects.filter(
                patient=patient,
                concept_id=concept_id,
                value_numeric__isnull=False,
            )
            .order_by("-observed_at")
            .first()
        )
        if obs:
            normal = NORMAL_RANGES.get(concept_id)
            is_abnormal = False
            if normal and obs.value_numeric is not None:
                is_abnormal = float(obs.value_numeric) < normal[0] or float(obs.value_numeric) > normal[1]
            lab_results.append(
                {
                    "name": CONCEPT_NAMES[concept_id],
                    "value": float(obs.value_numeric),
                    "unit": CONCEPT_UNITS[concept_id],
                    "at": obs.observed_at,
                    "source": obs.get_source_display(),
                    "is_abnormal": is_abnormal,
                }
            )

    # Compute display percentage (model stores 0.0-1.0)
    data_completeness_pct = int(float(snapshot.data_completeness) * 100) if snapshot else 0

    context = {
        "patient": patient,
        "snapshot": snapshot,
        "alerts": alerts,
        "chart_data": chart_data,  # Dict — json_script template tag handles serialization
        "lab_results": lab_results,
        "has_data": bool(chart_data),
        "data_completeness_pct": data_completeness_pct,
    }
    return render(request, "clinical/vitals_tab.html", context)


@require_GET
@_require_clinical_enabled
def health_card_fragment(request):
    """Patient My Health card — HTMX fragment with sparklines.

    Shows warmly, never alarms (per design review decision).
    """
    if not request.user.is_authenticated:
        return HttpResponse("")

    try:
        patient = request.user.patient_profile
    except Exception:
        return HttpResponse("")  # Not a patient user

    try:
        snapshot = patient.clinical_snapshot
    except PatientClinicalSnapshot.DoesNotExist:
        snapshot = None

    # Build sparkline data
    sparkline_data = {}
    for concept_id in SPARKLINE_VITALS:
        name = CONCEPT_NAMES[concept_id]
        trend = ClinicalDataService.get_trend_data(patient, concept_id, days=14)
        if trend:
            sparkline_data[name] = {
                "values": [float(t["value_numeric"]) for t in trend],
                "unit": CONCEPT_UNITS[concept_id],
                "current": float(trend[-1]["value_numeric"]),
            }

    # Trajectory language (warm, never alarm)
    trajectory_messages = {
        TRAJECTORY_IMPROVING: "Your recovery is looking great! Your readings are trending in the right direction.",
        TRAJECTORY_STABLE: "Things are looking steady — keep doing what you're doing.",
        TRAJECTORY_CONCERNING: (
            "We noticed some changes in your readings this week. "
            "Your care team has been notified and is keeping a closer eye on things. "
            "You're not alone in this."
        ),
        TRAJECTORY_DETERIORATING: (
            "Your care team has noticed some changes they want to keep an eye on. "
            "They're here for you — if you have questions or concerns, just ask."
        ),
    }

    trajectory_msg = ""
    trajectory_class = ""
    if snapshot:
        trajectory_msg = trajectory_messages.get(snapshot.trajectory, "")
        trajectory_class = {
            TRAJECTORY_IMPROVING: "text-teal-600 dark:text-teal-400",
            TRAJECTORY_STABLE: "text-gray-600 dark:text-gray-400",
            TRAJECTORY_CONCERNING: "text-orange-600 dark:text-orange-400",
            TRAJECTORY_DETERIORATING: "text-orange-500 dark:text-orange-400",
        }.get(snapshot.trajectory, "")

    # Connect to patient goals if available
    goal_message = ""
    try:
        prefs = patient.preferences
        if (
            prefs
            and prefs.recovery_goals
            and snapshot
            and snapshot.trajectory in (TRAJECTORY_IMPROVING, TRAJECTORY_STABLE)
        ):
            goal_message = f"Great progress toward {prefs.recovery_goals.split('.')[0].lower().strip()}."
    except Exception:
        logger.debug("Could not load patient preferences for goal message")

    context = {
        "patient": patient,
        "snapshot": snapshot,
        "sparkline_data_json": json.dumps(sparkline_data),
        "has_data": bool(sparkline_data),
        "trajectory_msg": trajectory_msg,
        "trajectory_class": trajectory_class,
        "goal_message": goal_message,
    }
    return render(request, "clinical/health_card.html", context)
