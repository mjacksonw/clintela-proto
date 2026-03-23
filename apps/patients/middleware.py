"""Patient middleware — language preference activation."""

from django.conf import settings
from django.utils import translation

# LANGUAGE_SESSION_KEY was removed in Django 5.0; use a local constant.
LANGUAGE_SESSION_KEY = "_language"


class PatientLanguageMiddleware:
    """Activate the patient's preferred language from their PatientPreferences.

    On each request for an authenticated patient, loads their preferred_language
    from PatientPreferences and activates it via Django's translation system.
    This persists the language choice in the session so Django's LocaleMiddleware
    picks it up on subsequent requests.

    Must be placed AFTER SessionMiddleware and AuthenticationMiddleware.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only activate for authenticated patients (session-based auth)
        patient_id = request.session.get("patient_id")
        authenticated = request.session.get("authenticated")

        if patient_id and authenticated:
            # Check if language is already set in session
            session_lang = request.session.get(LANGUAGE_SESSION_KEY)

            if not session_lang:
                # Load from PatientPreferences
                try:
                    from apps.patients.models import PatientPreferences

                    prefs = PatientPreferences.objects.filter(patient_id=patient_id).first()
                    if prefs and prefs.preferred_language:
                        lang = prefs.preferred_language
                        # Validate it's a supported language
                        supported = [code for code, _name in settings.LANGUAGES]
                        if lang in supported:
                            translation.activate(lang)
                            request.session[LANGUAGE_SESSION_KEY] = lang
                except Exception:  # noqa: S110
                    pass  # Graceful degradation — English fallback  # nosec B110

        response = self.get_response(request)
        return response
