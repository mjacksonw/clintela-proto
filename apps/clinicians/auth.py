"""Clinician authentication utilities.

Designed for graduation: auth logic is isolated here behind a single decorator
(@clinician_required) and a helper (get_authenticated_clinician). Views never
need to change when auth methods are upgraded from username/password to passkeys,
TOTP MFA, magic links, or SAML/SSO.
"""

import functools
import logging

from django.http import HttpRequest, HttpResponseForbidden
from django.shortcuts import redirect

logger = logging.getLogger(__name__)


def get_authenticated_clinician(request: HttpRequest):
    """Return the Clinician profile for the current user, or None.

    Args:
        request: Django HTTP request with session auth.

    Returns:
        Clinician instance if the user is authenticated with role='clinician'
        and has an active clinician profile, else None.
    """
    user = request.user
    if not user.is_authenticated:
        return None
    if user.role != "clinician":
        return None
    try:
        clinician = user.clinician_profile
        if not clinician.is_active:
            return None
        return clinician
    except user._meta.model.clinician_profile.RelatedObjectDoesNotExist:
        return None


def clinician_required(view_func):
    """Decorator that enforces clinician authentication.

    Sets request.clinician for use in views. If a 'patient_id' kwarg is
    present in the URL, also verifies the patient belongs to one of the
    clinician's hospitals (IDOR prevention).

    Redirects unauthenticated users to clinicians:login.
    Returns 403 for authenticated non-clinicians or IDOR violations.
    """

    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        clinician = get_authenticated_clinician(request)

        if clinician is None:
            if not request.user.is_authenticated:
                return redirect("clinicians:login")
            return HttpResponseForbidden("Clinician access required.")

        # IDOR prevention: verify patient belongs to clinician's hospitals
        patient_id = kwargs.get("patient_id")
        if patient_id is not None:
            from apps.patients.models import Patient

            try:
                patient = Patient.objects.get(id=patient_id)
            except Patient.DoesNotExist:
                return HttpResponseForbidden("Patient not found.")

            clinician_hospital_ids = set(clinician.hospitals.values_list("id", flat=True))
            if patient.hospital_id not in clinician_hospital_ids:
                logger.warning(
                    "IDOR attempt: clinician=%s tried to access patient=%s",
                    clinician.id,
                    patient_id,
                )
                return HttpResponseForbidden("Access denied.")

            # Attach patient to request for convenience
            request.patient = patient

        request.clinician = clinician
        return view_func(request, *args, **kwargs)

    return wrapper
