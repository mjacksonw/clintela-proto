"""Patient views."""

from django.shortcuts import redirect, render


def patient_dashboard_view(request):
    """Patient dashboard - placeholder for Phase 2."""
    # Check if patient is authenticated via session
    patient_id = request.session.get("patient_id")
    authenticated = request.session.get("authenticated")

    if not patient_id or not authenticated:
        return redirect("accounts:start")

    from .models import Patient

    try:
        patient = Patient.objects.get(id=patient_id)
    except Patient.DoesNotExist:
        return redirect("accounts:start")

    return render(
        request,
        "patients/dashboard.html",
        {
            "patient": patient,
        },
    )
