"""
Check-in views: REST API + HTMX wrappers.

REST-first design: widget response is a JSON API.
HTMX view wraps it and returns rendered HTML partial.
Mobile gets the API for free.
"""

import json
import logging

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.checkins.models import CheckinSession
from apps.checkins.services import CheckinService

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def widget_respond_api(request, session_id, question_code):
    """REST JSON API for widget responses.

    POST /api/widgets/respond/<session_id>/<question_code>/
    Body: {"value": <response_value>}

    Returns JSON: {"success": true, "updated_widget_state": {...}}

    Idempotent: if already answered, returns existing state.
    """
    session = get_object_or_404(CheckinSession, id=session_id)

    # Verify the patient owns this session
    if hasattr(request, "user") and hasattr(request.user, "patient") and session.patient_id != request.user.patient.id:
        return JsonResponse({"error": "Not authorized"}, status=403)

    try:
        body = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    value = body.get("value")
    if value is None:
        return JsonResponse({"error": "Missing 'value' field"}, status=400)

    response, was_created = CheckinService.record_response(session, question_code, value)

    # Build updated widget state
    widget_state = {
        "answered": True,
        "selected_value": response.value,
        "question_code": question_code,
        "session_id": str(session_id),
        "was_created": was_created,
        "session_complete": session.is_complete,
    }

    return JsonResponse({"success": True, "updated_widget_state": widget_state})


@require_POST
def widget_respond_htmx(request, session_id, question_code):
    """HTMX wrapper: calls API logic, returns rendered HTML partial.

    POST /checkins/respond/<session_id>/<question_code>/
    Body: value=<response_value> (form-encoded or JSON)

    Returns rendered _checkin_widget.html partial with updated state.
    Uses Django CSRF protection (HTMX includes token via X-CSRFToken header).
    """
    session = get_object_or_404(CheckinSession, id=session_id)

    # Verify the patient owns this session
    if hasattr(request, "user") and hasattr(request.user, "patient") and session.patient_id != request.user.patient.id:
        return JsonResponse({"error": "Not authorized"}, status=403)

    # Parse value from form data or JSON
    value = request.POST.get("value")
    if value is None:
        try:
            body = json.loads(request.body) if request.body else {}
            value = body.get("value")
        except json.JSONDecodeError:
            pass

    if value is None:
        return JsonResponse({"error": "Missing value"}, status=400)

    response, was_created = CheckinService.record_response(session, question_code, value)

    # Get the question for template context
    from apps.checkins.models import CheckinQuestion

    question = get_object_or_404(CheckinQuestion, code=question_code)

    # Build widget context for template
    from apps.checkins.widgets import build_widget_metadata

    widget = build_widget_metadata(
        question,
        session,
        answered=True,
        selected_value=response.value,
    )

    return render(
        request,
        "components/_checkin_widget.html",
        {
            "widget": widget,
            "session_id": str(session_id),
        },
    )
