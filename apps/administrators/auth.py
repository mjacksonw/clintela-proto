"""Administrator authentication utilities.

Mirrors the clinician auth pattern from apps/clinicians/auth.py.
Admin role enforced via @admin_required decorator — single enforcement point.
No IDOR prevention needed (admin sees aggregate data, never individual patients).
"""

import functools
import logging

from django.http import HttpRequest, HttpResponseForbidden
from django.shortcuts import redirect

logger = logging.getLogger(__name__)


def get_authenticated_admin(request: HttpRequest):
    """Return the User if they are an authenticated admin, else None."""
    user = request.user
    if not user.is_authenticated:
        return None
    if user.role != "admin":
        return None
    return user


def admin_required(view_func):
    """Decorator enforcing admin authentication.

    Sets request.admin_user for use in views.
    Redirects unauthenticated users to administrators:login.
    Returns 403 for authenticated non-admins.
    """

    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        admin_user = get_authenticated_admin(request)

        if admin_user is None:
            if not request.user.is_authenticated:
                return redirect("administrators:login")
            return HttpResponseForbidden("Administrator access required.")

        request.admin_user = admin_user
        return view_func(request, *args, **kwargs)

    return wrapper
