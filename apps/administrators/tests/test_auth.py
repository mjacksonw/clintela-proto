"""Tests for administrator authentication."""

from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from apps.accounts.models import User
from apps.administrators.auth import admin_required, get_authenticated_admin


class GetAuthenticatedAdminTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_unauthenticated_user(self):
        from django.contrib.auth.models import AnonymousUser

        request = self.factory.get("/")
        request.user = AnonymousUser()
        assert get_authenticated_admin(request) is None

    def test_non_admin_role_patient(self):
        user = User.objects.create_user(
            username="patient_user",
            password="pass",  # pragma: allowlist secret
            role="patient",
        )
        request = self.factory.get("/")
        request.user = user
        assert get_authenticated_admin(request) is None

    def test_non_admin_role_clinician(self):
        user = User.objects.create_user(
            username="clinician_user",
            password="pass",  # pragma: allowlist secret
            role="clinician",
        )
        request = self.factory.get("/")
        request.user = user
        assert get_authenticated_admin(request) is None

    def test_admin_role_returns_user(self):
        user = User.objects.create_user(
            username="admin_user",
            password="pass",  # pragma: allowlist secret
            role="admin",
        )
        request = self.factory.get("/")
        request.user = user
        result = get_authenticated_admin(request)
        assert result == user


class AdminRequiredDecoratorTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _dummy_view(self, request):
        return HttpResponse("OK")

    def test_unauthenticated_redirects_to_login(self):
        from django.contrib.auth.models import AnonymousUser

        request = self.factory.get("/")
        request.user = AnonymousUser()
        response = admin_required(self._dummy_view)(request)
        assert response.status_code == 302
        assert "login" in response.url

    def test_non_admin_returns_403(self):
        user = User.objects.create_user(
            username="clinician",
            password="pass",  # pragma: allowlist secret
            role="clinician",
        )
        request = self.factory.get("/")
        request.user = user
        response = admin_required(self._dummy_view)(request)
        assert response.status_code == 403

    def test_admin_passes_through(self):
        user = User.objects.create_user(
            username="admin",
            password="pass",  # pragma: allowlist secret
            role="admin",
        )
        request = self.factory.get("/")
        request.user = user
        response = admin_required(self._dummy_view)(request)
        assert response.status_code == 200
        assert hasattr(request, "admin_user")
        assert request.admin_user == user
