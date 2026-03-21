"""Views for the surveys app — patient-facing and clinician-facing."""

from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from apps.clinicians.auth import clinician_required
from apps.surveys.models import SurveyAssignment, SurveyInstance, SurveyInstrument
from apps.surveys.services import SurveyService


def _get_authenticated_patient(request):
    """Return the authenticated Patient or None (mirrors patients app pattern)."""
    patient_id = request.session.get("patient_id")
    authenticated = request.session.get("authenticated")
    if not patient_id or not authenticated:
        return None
    from apps.patients.models import Patient

    try:
        return Patient.objects.select_related("user", "hospital").get(id=patient_id)
    except Patient.DoesNotExist:
        return None


# =============================================================================
# Patient-facing views
# =============================================================================


@require_GET
def available_surveys(request):
    """HTMX fragment: pending survey cards for patient dashboard."""
    patient = _get_authenticated_patient(request)
    if not patient:
        return HttpResponse(status=403)
    from datetime import date

    instances = SurveyService.get_available_surveys(patient)
    next_date = SurveyService.get_next_survey_date(patient)

    return render(
        request,
        "surveys/_survey_card.html",
        {
            "instances": instances,
            "next_date": next_date,
            "today": date.today(),
        },
    )


@require_POST
def start_survey(request, instance_id):
    """Start a survey — returns the wizard modal content."""
    patient = _get_authenticated_patient(request)
    if not patient:
        return HttpResponse(status=403)
    instance = get_object_or_404(
        SurveyInstance,
        id=instance_id,
        patient=patient,
        status__in=["available", "in_progress"],
    )

    if instance.status == "available":
        SurveyService.start_instance(instance)

    questions = list(
        instance.instrument.questions.order_by("order").values(
            "id",
            "code",
            "domain",
            "order",
            "text",
            "question_type",
            "options",
            "min_value",
            "max_value",
            "min_label",
            "max_label",
            "required",
            "help_text",
        )
    )

    # Get existing answers for resume
    existing_answers = {a.question.code: a.value for a in instance.answers.select_related("question").all()}

    # Get display config from instrument registry
    from apps.surveys.instruments import registry

    inst_cls = registry.get(instance.instrument.code)
    display_config = inst_cls().get_display_config() if inst_cls else {"mode": "single_page"}

    import json

    return render(
        request,
        "surveys/_survey_modal.html",
        {
            "instance": instance,
            "questions": questions,
            "questions_json": json.dumps(questions),
            "existing_answers_json": json.dumps(existing_answers),
            "display_config": display_config,
        },
    )


@require_POST
def submit_answers(request, instance_id):
    """Save partial answers (called on each "Next" step)."""
    patient = _get_authenticated_patient(request)
    if not patient:
        return HttpResponse(status=403)
    instance = get_object_or_404(
        SurveyInstance,
        id=instance_id,
        patient=patient,
        status="in_progress",
    )

    # Parse answers from POST data
    answers = {}
    for key, value in request.POST.items():
        if key.startswith("q_"):
            code = key[2:]  # Strip "q_" prefix
            # Try to parse as int/float for numeric values
            try:
                answers[code] = int(value)
            except (ValueError, TypeError):
                answers[code] = value

    SurveyService.save_answers(instance, answers)
    return HttpResponse(status=204)


@require_POST
def complete_survey(request, instance_id):
    """Complete survey and show post-completion screen."""
    patient = _get_authenticated_patient(request)
    if not patient:
        return HttpResponse(status=403)
    instance = get_object_or_404(
        SurveyInstance,
        id=instance_id,
        patient=patient,
        status="in_progress",
    )

    # Save any final answers
    answers = {}
    for key, value in request.POST.items():
        if key.startswith("q_"):
            code = key[2:]
            try:
                answers[code] = int(value)
            except (ValueError, TypeError):
                answers[code] = value

    if answers:
        SurveyService.save_answers(instance, answers)

    # Complete and score
    instance = SurveyService.complete_instance(instance)

    # Get interpretation for display
    interpretation = ""
    if not instance.scoring_error:
        from apps.surveys.instruments import registry

        inst_cls = registry.get(instance.instrument.code)
        if inst_cls and instance.raw_scores:
            try:
                result = inst_cls().score(instance.raw_scores)
                interpretation = result.interpretation
            except Exception:  # noqa: S110  # nosec B110
                pass

    return render(
        request,
        "surveys/_survey_completion.html",
        {
            "instance": instance,
            "interpretation": interpretation,
        },
    )


@require_GET
def score_history(request):
    """HTMX fragment: patient score history with CSS bars."""
    patient = _get_authenticated_patient(request)
    if not patient:
        return HttpResponse(status=403)
    history = SurveyService.get_score_history(patient)

    # Annotate each instance with max_score and percentage for bar rendering
    history_with_pct = []
    for instance in history:
        max_score = SurveyService._get_max_score(instance.instrument.code) or 100
        pct = round((instance.total_score / max_score) * 100) if max_score else 0
        history_with_pct.append(
            {
                "instance": instance,
                "max_score": max_score,
                "pct": min(pct, 100),
            }
        )

    return render(
        request,
        "surveys/_score_history.html",
        {"history": history_with_pct},
    )


# =============================================================================
# Clinician-facing views
# =============================================================================


@clinician_required
@require_GET
def clinician_surveys_tab(request, patient_id):
    """HTMX fragment: clinician Surveys tab content."""
    from apps.patients.models import Patient

    patient = get_object_or_404(Patient, id=patient_id)

    # Score history (recent completions)
    recent = (
        SurveyInstance.objects.filter(
            patient=patient,
            status="completed",
            total_score__isnull=False,
        )
        .select_related("instrument")
        .order_by("-completed_at")[:20]
    )

    # Active assignments
    assignments = (
        SurveyAssignment.objects.filter(patient=patient, is_active=True)
        .select_related("instrument")
        .order_by("instrument__name")
    )

    # Available instruments for assignment
    assigned_codes = set(assignments.values_list("instrument__code", flat=True))
    available_instruments = SurveyInstrument.objects.filter(
        is_active=True,
    ).exclude(code__in=assigned_codes)

    # Score trends per instrument (last 5 per instrument)
    trends = {}
    for assignment in assignments:
        scores = list(
            SurveyInstance.objects.filter(
                patient=patient,
                instrument=assignment.instrument,
                status="completed",
                total_score__isnull=False,
            )
            .order_by("-completed_at")[:5]
            .values_list("total_score", flat=True)
        )
        if scores:
            trends[assignment.instrument.code] = {
                "scores": list(reversed(scores)),
                "latest": scores[0],
                "delta": scores[0] - scores[1] if len(scores) > 1 else None,
            }

    return render(
        request,
        "surveys/_tab_surveys.html",
        {
            "patient": patient,
            "recent": recent,
            "assignments": assignments,
            "available_instruments": available_instruments,
            "trends": trends,
        },
    )


@clinician_required
@require_POST
def assign_survey(request, patient_id):
    """Assign a survey to a patient."""
    from apps.patients.models import Patient

    patient = get_object_or_404(Patient, id=patient_id)
    instrument_code = request.POST.get("instrument_code")
    schedule_type = request.POST.get("schedule_type", "weekly")

    try:
        SurveyService.create_assignment(
            patient=patient,
            instrument_code=instrument_code,
            schedule_type=schedule_type,
            assigned_by=request.user,
        )
        return HttpResponse(
            '<div class="text-sm" style="color: #059669;">Survey assigned successfully</div>',
            status=200,
        )
    except Exception as e:
        return HttpResponse(
            f'<div class="text-sm" style="color: #DC2626;">Failed to assign: {e}</div>',
            status=400,
        )


@clinician_required
@require_POST
def deactivate_assignment(request, assignment_id):
    """Deactivate a survey assignment."""
    assignment = get_object_or_404(
        SurveyAssignment,
        id=assignment_id,
        is_active=True,
    )
    assignment.is_active = False
    assignment.save(update_fields=["is_active", "updated_at"])

    return HttpResponse(
        '<div class="text-sm" style="color: var(--color-text-secondary);">Assignment deactivated</div>',
        status=200,
    )


@clinician_required
@require_GET
def survey_results(request, instance_id):
    """Detailed survey results view."""
    instance = get_object_or_404(
        SurveyInstance.objects.select_related("instrument", "patient").prefetch_related("answers__question"),
        id=instance_id,
        status="completed",
    )

    # Get previous scores for trend
    previous_scores = list(
        SurveyInstance.objects.filter(
            patient=instance.patient,
            instrument=instance.instrument,
            status="completed",
            total_score__isnull=False,
        )
        .order_by("-completed_at")[:10]
        .values_list("total_score", "completed_at")
    )

    # Get interpretation
    interpretation = ""
    from apps.surveys.instruments import registry

    inst_cls = registry.get(instance.instrument.code)
    if inst_cls and instance.raw_scores:
        try:
            result = inst_cls().score(instance.raw_scores)
            interpretation = result.interpretation
        except Exception:  # noqa: S110  # nosec B110
            pass

    return render(
        request,
        "surveys/_survey_results.html",
        {
            "instance": instance,
            "interpretation": interpretation,
            "previous_scores": list(reversed(previous_scores)),
            "answers": instance.answers.select_related("question").order_by("question__order"),
        },
    )
