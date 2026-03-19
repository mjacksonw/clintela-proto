"""Tests for patient authentication tokens."""

import pytest

from apps.accounts.models import User
from apps.accounts.tokens import ShortCodeTokenGenerator, short_code_token_generator
from apps.patients.models import Hospital, Patient


@pytest.mark.django_db
def test_token_generator_creates_valid_token():
    """Test that token generator creates valid tokens with short codes."""
    user = User.objects.create_user(username="testuser", password="testpass")
    hospital = Hospital.objects.create(name="Test Hospital", code="TEST001")
    patient = Patient.objects.create(user=user, hospital=hospital, date_of_birth="1990-01-15", leaflet_code="A3B9K2")

    generator = ShortCodeTokenGenerator()
    full_token = generator.make_token(patient)
    short_code = generator.get_short_code(full_token)

    # Short code should be 6 characters
    assert len(short_code) == 6
    assert short_code.isalnum()

    # Token should be valid
    assert generator.check_token(patient, full_token) is True


@pytest.mark.django_db
def test_token_generator_short_code_is_deterministic():
    """Test that short code is deterministic for same token."""
    user = User.objects.create_user(username="testuser2", password="testpass")
    hospital = Hospital.objects.create(name="Test Hospital 2", code="TEST002")
    patient = Patient.objects.create(user=user, hospital=hospital, date_of_birth="1990-01-15", leaflet_code="B4C0D1")

    generator = ShortCodeTokenGenerator()
    full_token = generator.make_token(patient)

    # Should always produce same short code
    short_code_1 = generator.get_short_code(full_token)
    short_code_2 = generator.get_short_code(full_token)
    assert short_code_1 == short_code_2


@pytest.mark.django_db
def test_generate_short_code_random():
    """Test that generate_short_code produces random codes."""
    generator = ShortCodeTokenGenerator()

    # Generate multiple codes
    codes = [generator.generate_short_code() for _ in range(10)]

    # All codes should be 6 characters
    for code in codes:
        assert len(code) == 6
        assert code.isalnum()

    # Should have some variety (not all identical)
    assert len(set(codes)) > 1


@pytest.mark.django_db
def test_short_code_singleton():
    """Test that singleton instance works correctly."""
    user = User.objects.create_user(username="testuser3", password="testpass")
    hospital = Hospital.objects.create(name="Test Hospital 3", code="TEST003")
    patient = Patient.objects.create(user=user, hospital=hospital, date_of_birth="1990-01-15", leaflet_code="C5D1E2")

    # Use singleton
    full_token = short_code_token_generator.make_token(patient)
    short_code = short_code_token_generator.get_short_code(full_token)

    assert len(short_code) == 6
    assert short_code_token_generator.check_token(patient, full_token) is True
