"""Context processors for the accounts app."""

from django.conf import settings


def demo_bar_context(request):
    """Inject demo bar data into all templates when DEBUG=True."""
    if not settings.DEBUG:
        return {}

    from apps.accounts.models import User
    from apps.clinicians.models import Clinician
    from apps.patients.models import Patient

    return {
        "demo_patients": Patient.objects.select_related("user").order_by("user__last_name", "user__first_name"),
        "demo_clinicians": Clinician.objects.select_related("user").filter(is_active=True).order_by("user__last_name"),
        "demo_admins": User.objects.filter(role="admin", is_active=True).order_by("last_name"),
        "current_patient_id": request.session.get("patient_id"),
    }
