"""Middleware for protected demo environments."""

from django.conf import settings
from django.http import HttpResponse


class ProtectedEnvironmentMiddleware:
    """Cookie-based gate for demo environments.

    When PROTECTED=True, all requests require a `demo_access` cookie.
    Without the cookie, returns 401. The cookie is set by visiting the
    gate URL (/auth/{PROTECTED_GATE_PATH}/).

    Exempt paths: the gate URL itself, static files, and media files.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not settings.PROTECTED:
            return self.get_response(request)

        path = request.path

        # Exempt the gate URL
        gate_path = f"/auth/{settings.PROTECTED_GATE_PATH}/"
        if path == gate_path:
            return self.get_response(request)

        # Exempt static and media files
        if path.startswith(settings.STATIC_URL) or path.startswith(settings.MEDIA_URL):
            return self.get_response(request)

        # Check for valid cookie
        if request.COOKIES.get("demo_access") == "1":
            return self.get_response(request)

        # Block with 401
        return HttpResponse(
            "<html><body style='font-family: sans-serif; padding: 4rem; text-align: center;'>"
            "<h1>401 — Protected Environment</h1>"
            "<p>This environment requires access. Contact the demo administrator for the access URL.</p>"
            "</body></html>",
            status=401,
            content_type="text/html; charset=utf-8",
        )
