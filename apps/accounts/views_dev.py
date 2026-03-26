"""Dev-only views for demo authentication — DEBUG only."""

from django.conf import settings
from django.contrib.auth import login, logout
from django.http import Http404, HttpResponse
from django.shortcuts import redirect

ROLE_DASHBOARDS = {
    "patient": "patients:dashboard",
    "clinician": "clinicians:dashboard",
    "admin": "administrators:dashboard",
}


def _login_as_patient(request, user_id):
    """Authenticate as a patient via session keys."""
    from apps.patients.models import Patient

    try:
        if user_id:
            patient = Patient.objects.get(id=user_id)
        else:
            patient = Patient.objects.order_by("id").first()
            if not patient:
                return None
    except Patient.DoesNotExist:
        return None

    request.session["patient_id"] = str(patient.id)
    request.session["authenticated"] = True
    return redirect(ROLE_DASHBOARDS["patient"])


def _login_as_django_user(request, user_id, role):
    """Authenticate as a clinician or admin via Django login."""
    from apps.accounts.models import User

    try:
        if user_id:
            user = User.objects.get(id=user_id, role=role)
        else:
            user = User.objects.filter(role=role).order_by("id").first()
            if not user:
                return None
    except User.DoesNotExist:
        return None

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return redirect(ROLE_DASHBOARDS[role])


def demo_login_view(request):
    """One-click demo login — switches role without knowing credentials.

    POST params:
        role: "patient" | "clinician" | "admin"
        user_id: optional specific user/patient ID
    """
    if not settings.DEBUG:
        raise Http404

    if request.method != "POST":
        return HttpResponse(status=405)

    role = request.POST.get("role", "")
    user_id = request.POST.get("user_id")

    # Clear any existing auth (flushes both Django auth and session keys)
    logout(request)

    # Authenticate as new role
    if role == "patient":
        response = _login_as_patient(request, user_id)
    elif role in ("clinician", "admin"):
        response = _login_as_django_user(request, user_id, role)
    else:
        response = None

    return response or redirect("/")
