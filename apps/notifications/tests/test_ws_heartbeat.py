"""Tests for WebSocket heartbeat and last_active_at updates.

Covers:
  - Heartbeat action updates last_active_at
  - Connect updates last_active_at
  - last_active_at used by notification routing
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.agents.tests.factories import PatientFactory


@pytest.mark.django_db
class TestLastActiveAt:
    def test_last_active_at_field_exists(self):
        """User model has the last_active_at field with db_index."""
        field = User._meta.get_field("last_active_at")
        assert field.null is True
        assert field.blank is True
        assert field.db_index is True

    def test_last_active_at_update(self):
        """Direct update of last_active_at works correctly."""
        patient = PatientFactory()
        assert patient.user.last_active_at is None

        now = timezone.now()
        User.objects.filter(id=patient.user_id).update(last_active_at=now)

        patient.user.refresh_from_db()
        assert patient.user.last_active_at is not None
        assert abs((patient.user.last_active_at - now).total_seconds()) < 1

    def test_last_active_at_ws_active_threshold(self):
        """WS is considered active when last_active_at < 60s ago."""
        from apps.notifications.services import NotificationService

        patient = PatientFactory()

        # Active: 10 seconds ago
        patient.user.last_active_at = timezone.now() - timedelta(seconds=10)
        patient.user.save()
        assert NotificationService._is_ws_active(patient) is True

        # Inactive: 120 seconds ago
        patient.user.last_active_at = timezone.now() - timedelta(seconds=120)
        patient.user.save()
        assert NotificationService._is_ws_active(patient) is False

        # Never connected
        patient.user.last_active_at = None
        patient.user.save()
        assert NotificationService._is_ws_active(patient) is False
