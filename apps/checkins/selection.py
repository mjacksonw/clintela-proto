"""
Question selection engine for daily check-ins.

Three layers:
1. PathwayFloor — enforces minimum frequency from pathway config
2. RelevanceFilter — filters by recovery phase and procedure
3. select_daily_questions — LLM selects from eligible pool, merged with floors
"""

import json
import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)


class PathwayFloor:
    """Enforces minimum frequency rules from PathwayCheckinConfig."""

    @staticmethod
    def get_required_questions(patient, date):
        """Return question codes that MUST be asked today per frequency floors.

        Checks each category's min_frequency config against recent responses.
        If max_gap_days exceeded for a category, that category's highest-priority
        active question is required.
        """
        from apps.checkins.models import CheckinQuestion, CheckinResponse, PathwayCheckinConfig

        patient_pathway = _get_active_pathway(patient)
        if not patient_pathway:
            return []

        phase = _derive_phase(patient)
        configs = PathwayCheckinConfig.objects.filter(
            pathway=patient_pathway.pathway,
        ).filter(
            relevance_phase_q(phase),
        )

        required_codes = []

        for config in configs:
            # Check when this category was last asked
            last_response = (
                CheckinResponse.objects.filter(
                    session__patient=patient,
                    question__category=config.category,
                )
                .order_by("-created_at")
                .first()
            )

            days_since = None
            if last_response:
                days_since = (date - last_response.created_at.date()).days

            # Get the frequency floor for this phase
            every_n_days = _get_frequency_for_phase(config.min_frequency, phase)

            should_ask = False
            if days_since is None:
                # Never asked, always ask
                should_ask = True
            elif every_n_days and days_since >= every_n_days or days_since >= config.max_gap_days:
                should_ask = True

            if should_ask:
                # Pick the highest priority active question in this category
                question = (
                    CheckinQuestion.objects.filter(
                        category=config.category,
                        is_active=True,
                    )
                    .order_by("priority")
                    .first()
                )
                if question:
                    required_codes.append(question.code)

        return required_codes


class RelevanceFilter:
    """Filters questions by recovery phase and active status."""

    @staticmethod
    def get_eligible_questions(patient):
        """Return CheckinQuestion queryset eligible for this patient.

        Filters by:
        - is_active=True
        - Category has a PathwayCheckinConfig for the patient's pathway
          that matches the current phase
        """
        from apps.checkins.models import CheckinQuestion, PathwayCheckinConfig

        patient_pathway = _get_active_pathway(patient)
        if not patient_pathway:
            return CheckinQuestion.objects.none()

        phase = _derive_phase(patient)

        # Get categories configured for this pathway + phase
        eligible_categories = (
            PathwayCheckinConfig.objects.filter(
                pathway=patient_pathway.pathway,
            )
            .filter(
                relevance_phase_q(phase),
            )
            .values_list("category", flat=True)
        )

        return CheckinQuestion.objects.filter(
            is_active=True,
            category__in=eligible_categories,
        )


def select_daily_questions(patient, max_questions=5):
    """Select today's check-in questions for a patient.

    Flow:
    1. Get floor-required questions (must-ask)
    2. Get eligible pool
    3. Ask LLM to select from eligible pool (excluding floors already chosen)
    4. Merge floors + LLM selections, cap at max_questions
    5. Fallback: if LLM fails, use floor-required only

    Returns:
        tuple: (list of question codes, rationale string)
    """

    today = _patient_today(patient)

    # 1. Floor requirements
    floor_codes = PathwayFloor.get_required_questions(patient, today)

    # 2. Eligible pool
    eligible_qs = RelevanceFilter.get_eligible_questions(patient)
    if not eligible_qs.exists():
        logger.info("No eligible questions for patient %s", patient.id)
        return [], "No eligible questions for patient's pathway/phase"

    eligible_codes = list(eligible_qs.values_list("code", flat=True))

    # 3. Try LLM selection
    remaining_slots = max(0, max_questions - len(floor_codes))
    llm_codes = []
    rationale = ""

    if remaining_slots > 0:
        pool_for_llm = [c for c in eligible_codes if c not in floor_codes]
        if pool_for_llm:
            try:
                llm_codes, rationale = _llm_select(patient, pool_for_llm, remaining_slots)
            except Exception:
                logger.exception("LLM selection failed for patient %s, using floor only", patient.id)
                rationale = "LLM selection failed, using floor requirements only"

    # 4. Merge and cap
    selected = list(dict.fromkeys(floor_codes + llm_codes))[:max_questions]

    if not rationale:
        rationale = f"Floor requirements: {floor_codes}" if floor_codes else "LLM selection"

    return selected, rationale


def evaluate_follow_up_rules(question, response_value):
    """Evaluate follow-up rules for a question against a response value.

    Handles type coercion: int for scales, string for yes/no and multiple choice.

    Returns:
        str or None: Follow-up message if a rule matches, None otherwise.
    """
    for rule in question.follow_up_rules:
        operator = rule.get("operator")
        rule_value = rule.get("value")
        message = rule.get("message", "")

        # Type coercion
        coerced_response = _coerce_value(response_value, question.response_type)

        try:
            if (
                operator == "eq"
                and coerced_response == rule_value
                or operator == "gte"
                and coerced_response >= rule_value
                or operator == "lte"
                and coerced_response <= rule_value
                or operator == "in"
                and coerced_response in rule_value
            ):
                return message
        except (TypeError, ValueError):
            logger.warning(
                "Follow-up rule evaluation failed: question=%s, operator=%s, value=%s, response=%s",
                question.code,
                operator,
                rule_value,
                response_value,
            )
            continue

    return None


# --- Private helpers ---


def _coerce_value(value, response_type):
    """Coerce a response value to the appropriate type for comparison."""
    if response_type in ("scale_1_5", "scale_1_10"):
        try:
            return int(value)
        except (TypeError, ValueError):
            return value
    # yes_no and multiple_choice stay as strings
    if isinstance(value, str):
        return value
    return str(value) if value is not None else value


def _get_active_pathway(patient):
    """Get the patient's active PatientPathway, or None."""
    from apps.pathways.models import PatientPathway

    return PatientPathway.objects.filter(patient=patient, status="active").select_related("pathway").first()


def _derive_phase(patient):
    """Derive recovery phase from days post-op."""
    days = patient.days_post_op()
    if days is None:
        return "early"
    if days <= 7:
        return "early"
    elif days <= 30:
        return "middle"
    else:
        return "late"


def _patient_today(patient):
    """Get today's date in the patient's timezone."""
    from datetime import date

    try:
        import zoneinfo

        from apps.notifications.models import NotificationPreference

        pref = NotificationPreference.objects.filter(patient=patient).first()
        if pref and pref.timezone:
            tz = zoneinfo.ZoneInfo(pref.timezone)
            return timezone.now().astimezone(tz).date()
    except Exception:
        logger.debug("Timezone lookup failed for patient %s, using server date", patient.id)
    return date.today()


def _get_frequency_for_phase(min_frequency, phase):
    """Extract the every_n_days value for a given phase from min_frequency JSON.

    min_frequency is a list like [{"phase": "early", "every_n_days": 1}, ...]
    """
    if not min_frequency:
        return None
    for entry in min_frequency:
        if entry.get("phase") == phase or entry.get("phase") == "all":
            return entry.get("every_n_days")
    return None


def relevance_phase_q(phase):
    """Build a Q filter for relevance_phase matching the given phase or 'all'."""
    from django.db.models import Q

    return Q(relevance_phase=phase) | Q(relevance_phase="all")


def _llm_select(patient, pool_codes, max_count):
    """Use LLM to select questions from the eligible pool.

    Returns:
        tuple: (list of selected codes, rationale string)
    """
    from apps.checkins.models import CheckinQuestion, CheckinResponse
    from apps.clinical.models import PatientClinicalSnapshot
    from apps.patients.models import PatientPreferences

    # Gather context for LLM
    context_parts = []

    # Patient preferences
    try:
        prefs = PatientPreferences.objects.get(patient=patient)
        if prefs.recovery_goals:
            context_parts.append(f"Recovery goals: {prefs.recovery_goals}")
        if prefs.concerns:
            context_parts.append(f"Concerns: {prefs.concerns}")
    except PatientPreferences.DoesNotExist:
        pass

    # Recent responses (last 7 days)
    recent = (
        CheckinResponse.objects.filter(
            session__patient=patient,
            created_at__gte=timezone.now() - timedelta(days=7),
        )
        .select_related("question")
        .order_by("-created_at")[:20]
    )
    if recent:
        recent_summary = "; ".join(f"{r.question.code}={r.value} ({r.created_at.date()})" for r in recent)
        context_parts.append(f"Recent check-in responses: {recent_summary}")

    # Clinical snapshot
    try:
        snapshot = PatientClinicalSnapshot.objects.filter(patient=patient).latest("computed_at")
        if snapshot.summary:
            context_parts.append(f"Clinical summary: {snapshot.summary}")
    except PatientClinicalSnapshot.DoesNotExist:
        pass

    # Build pool descriptions
    pool_questions = CheckinQuestion.objects.filter(code__in=pool_codes)
    pool_desc = "\n".join(f"- {q.code}: {q.text} ({q.category})" for q in pool_questions)

    phase = _derive_phase(patient)
    days = patient.days_post_op() or "unknown"

    prompt = f"""You are selecting daily check-in questions for a cardiac surgery recovery patient.

Patient context:
- Day {days} post-op, phase: {phase}
{chr(10).join(f"- {c}" for c in context_parts)}

Available questions (select 0 to {max_count}):
{pool_desc}

Rules:
- Select 0 questions if the patient is doing well and doesn't need checking today
- Prioritize questions about areas where the patient reported problems recently
- Don't repeat questions that were asked yesterday unless the answer was concerning
- Select fewer questions on days the patient is stable

Return a JSON object with:
- "selected": list of question codes (can be empty)
- "rationale": one sentence explaining your selection
"""

    try:
        from apps.agents.services import get_llm

        llm = get_llm()
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)

        # Parse JSON from response
        result = _parse_llm_response(content)
        selected = [c for c in result.get("selected", []) if c in pool_codes]
        rationale = result.get("rationale", "LLM selection")

        return selected[:max_count], rationale

    except Exception:
        logger.exception("LLM invocation failed for question selection")
        raise


def _parse_llm_response(content):
    """Parse JSON from LLM response, handling markdown code blocks."""
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        # Remove first and last line (code block markers)
        json_lines = [line for line in lines[1:] if not line.startswith("```")]
        content = "\n".join(json_lines)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM response as JSON: %s", content[:200])
        return {"selected": [], "rationale": "Failed to parse LLM response"}
