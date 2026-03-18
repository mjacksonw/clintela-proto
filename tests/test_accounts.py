"""Test accounts app."""

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
def test_create_user():
    """Test creating a basic user."""
    user = User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )
    assert user.username == "testuser"
    assert user.email == "test@example.com"
    assert user.role == "patient"
    assert user.is_active is True


@pytest.mark.django_db
def test_create_superuser():
    """Test creating a superuser."""
    user = User.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="adminpass123",
    )
    assert user.is_staff is True
    assert user.is_superuser is True


@pytest.mark.django_db
def test_user_str():
    """Test user string representation."""
    user = User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )
    assert str(user) == "testuser (Patient)"
