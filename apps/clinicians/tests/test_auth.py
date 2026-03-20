"""Tests for clinician authentication."""

import uuid as _uuid

from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from apps.accounts.models import User
from apps.clinicians.auth import clinician_required, get_authenticated_clinician
from apps.clinicians.models import Clinician
from apps.patients.models import Hospital, Patient

_DOB = "1960-01-15"


def _code():
    return f"TST-{_uuid.uuid4().hex[:8]}"


def _lc():
    return f"LC-{_uuid.uuid4().hex[:8]}"


class GetAuthenticatedClinicianTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.hospital = Hospital.objects.create(name="Test Hospital", code=_code())

    def test_unauthenticated_user(self):
        from django.contrib.auth.models import AnonymousUser

        request = self.factory.get("/")
        request.user = AnonymousUser()
        assert get_authenticated_clinician(request) is None

    def test_non_clinician_role(self):
        user = User.objects.create_user(
            username="patient_user",
            password="pass",  # pragma: allowlist secret
            role="patient",
        )
        request = self.factory.get("/")
        request.user = user
        assert get_authenticated_clinician(request) is None

    def test_clinician_without_profile(self):
        user = User.objects.create_user(
            username="no_profile",
            password="pass",  # pragma: allowlist secret
            role="clinician",
        )
        request = self.factory.get("/")
        request.user = user
        assert get_authenticated_clinician(request) is None

    def test_inactive_clinician(self):
        user = User.objects.create_user(
            username="inactive_dr",
            password="pass",  # pragma: allowlist secret
            role="clinician",
        )
        Clinician.objects.create(user=user, role="physician", is_active=False)
        request = self.factory.get("/")
        request.user = user
        assert get_authenticated_clinician(request) is None

    def test_valid_clinician(self):
        user = User.objects.create_user(
            username="valid_dr",
            password="pass",  # pragma: allowlist secret
            role="clinician",
        )
        clinician = Clinician.objects.create(user=user, role="physician", is_active=True)
        request = self.factory.get("/")
        request.user = user
        result = get_authenticated_clinician(request)
        assert result == clinician


class ClinicianRequiredDecoratorTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.hospital = Hospital.objects.create(name="Test Hospital", code=_code())

        self.clin_user = User.objects.create_user(
            username="dr_dec",
            password="pass",  # pragma: allowlist secret
            role="clinician",
        )
        self.clinician = Clinician.objects.create(
            user=self.clin_user,
            role="physician",
            is_active=True,
        )
        self.clinician.hospitals.add(self.hospital)

        self.pat_user = User.objects.create_user(
            username="pat_dec",
            password="pass",  # pragma: allowlist secret
            role="patient",
        )
        self.patient = Patient.objects.create(
            user=self.pat_user,
            hospital=self.hospital,
            status="green",
            date_of_birth=_DOB,
            leaflet_code=_lc(),
        )

    def _make_view(self):
        @clinician_required
        def view(request, **kwargs):
            return HttpResponse("ok")

        return view

    def test_redirects_unauthenticated(self):
        from django.contrib.auth.models import AnonymousUser

        request = self.factory.get("/")
        request.user = AnonymousUser()
        response = self._make_view()(request)
        assert response.status_code == 302  # redirect to login

    def test_403_for_non_clinician(self):
        user = User.objects.create_user(
            username="not_dr",
            password="pass",  # pragma: allowlist secret
            role="patient",
        )
        request = self.factory.get("/")
        request.user = user
        response = self._make_view()(request)
        assert response.status_code == 403

    def test_success_without_patient_id(self):
        request = self.factory.get("/")
        request.user = self.clin_user
        response = self._make_view()(request)
        assert response.status_code == 200
        assert response.content == b"ok"

    def test_idor_prevention_wrong_hospital(self):
        other_hospital = Hospital.objects.create(name="Other Hospital", code=_code())
        other_pat_user = User.objects.create_user(
            username="other_pat",
            password="pass",  # pragma: allowlist secret
            role="patient",
        )
        other_patient = Patient.objects.create(
            user=other_pat_user,
            hospital=other_hospital,
            status="green",
            date_of_birth=_DOB,
            leaflet_code=_lc(),
        )
        request = self.factory.get("/")
        request.user = self.clin_user
        response = self._make_view()(request, patient_id=other_patient.id)
        assert response.status_code == 403

    def test_idor_success_same_hospital(self):
        request = self.factory.get("/")
        request.user = self.clin_user
        response = self._make_view()(request, patient_id=self.patient.id)
        assert response.status_code == 200

    def test_patient_not_found(self):
        request = self.factory.get("/")
        request.user = self.clin_user
        response = self._make_view()(request, patient_id=999999)
        assert response.status_code == 403


class ClinicianLoginViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="login_dr",
            password="testpass",  # pragma: allowlist secret
            role="clinician",
        )
        Clinician.objects.create(user=self.user, role="physician", is_active=True)

    def test_login_page_renders(self):
        response = self.client.get("/clinician/login/")
        assert response.status_code == 200

    def test_login_success(self):
        response = self.client.post(
            "/clinician/login/",
            {
                "username": "login_dr",
                "password": "testpass",  # pragma: allowlist secret
            },
        )
        assert response.status_code == 302
        assert "/clinician/dashboard/" in response.url

    def test_login_invalid_credentials(self):
        response = self.client.post(
            "/clinician/login/",
            {
                "username": "login_dr",
                "password": "wrong",  # pragma: allowlist secret
            },
        )
        assert response.status_code == 200
        assert b"Invalid" in response.content

    def test_login_non_clinician_rejected(self):
        User.objects.create_user(
            username="patient_login",
            password="testpass",  # pragma: allowlist secret
            role="patient",
        )
        response = self.client.post(
            "/clinician/login/",
            {
                "username": "patient_login",
                "password": "testpass",  # pragma: allowlist secret
            },
        )
        assert response.status_code == 200
        assert b"Invalid" in response.content

    def test_logout(self):
        self.client.login(username="login_dr", password="testpass")  # pragma: allowlist secret
        response = self.client.get("/clinician/logout/")
        assert response.status_code == 302
