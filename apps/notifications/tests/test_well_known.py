"""Tests for .well-known endpoints (deep linking).

Covers:
  - /.well-known/apple-app-site-association — iOS Universal Links
  - /.well-known/assetlinks.json — Android App Links
"""

import pytest
from django.test import Client


@pytest.mark.django_db
class TestWellKnownEndpoints:
    def test_apple_app_site_association(self, settings):
        """iOS Universal Links config is served correctly."""
        settings.APPLE_APP_ID = "TEAMID.com.clintela.app"

        client = Client()
        response = client.get("/.well-known/apple-app-site-association")

        assert response.status_code == 200
        assert response["Content-Type"] == "application/json"

        data = response.json()
        assert "applinks" in data
        details = data["applinks"]["details"]
        assert len(details) == 1
        assert details[0]["appID"] == "TEAMID.com.clintela.app"
        assert "/patient/*" in details[0]["paths"]
        assert "/api/v1/*" in details[0]["paths"]

        # webcredentials for autofill
        assert "webcredentials" in data
        assert settings.APPLE_APP_ID in data["webcredentials"]["apps"]

    def test_android_asset_links(self, settings):
        """Android App Links config is served correctly."""
        settings.ANDROID_PACKAGE_NAME = "com.clintela.app"
        settings.ANDROID_CERT_FINGERPRINTS = ["AA:BB:CC"]

        client = Client()
        response = client.get("/.well-known/assetlinks.json")

        assert response.status_code == 200
        assert response["Content-Type"] == "application/json"

        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1

        entry = data[0]
        assert entry["relation"] == ["delegate_permission/common.handle_all_urls"]
        assert entry["target"]["namespace"] == "android_app"
        assert entry["target"]["package_name"] == "com.clintela.app"
        assert entry["target"]["sha256_cert_fingerprints"] == ["AA:BB:CC"]
