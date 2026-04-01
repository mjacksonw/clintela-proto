"""Tests for routing.py URL patterns and context_processors.py."""

from unittest.mock import patch

from django.test import RequestFactory

from apps.agents.context_processors import support_group_flags


class TestWebSocketRouting:
    """Verify websocket_urlpatterns loads and contains expected routes."""

    def test_routing_imports(self):
        """routing.py can be imported and has URL patterns."""
        from apps.agents.routing import websocket_urlpatterns

        assert len(websocket_urlpatterns) >= 3
        # Verify support group route exists
        pattern_strs = [p.pattern.regex.pattern for p in websocket_urlpatterns]
        assert any("support-group" in s for s in pattern_strs)

    def test_routing_has_chat_pattern(self):
        """Chat WebSocket pattern is present."""
        from apps.agents.routing import websocket_urlpatterns

        pattern_strs = [p.pattern.regex.pattern for p in websocket_urlpatterns]
        assert any("chat" in s for s in pattern_strs)

    def test_routing_has_dashboard_pattern(self):
        """Dashboard WebSocket pattern is present."""
        from apps.agents.routing import websocket_urlpatterns

        pattern_strs = [p.pattern.regex.pattern for p in websocket_urlpatterns]
        assert any("dashboard" in s for s in pattern_strs)


class TestSupportGroupContextProcessor:
    """Tests for support_group_flags context processor."""

    def test_enabled(self):
        """When ENABLE_SUPPORT_GROUP is True, returns flag + persona JSON."""
        factory = RequestFactory()
        request = factory.get("/")

        with patch("apps.agents.context_processors.ENABLE_SUPPORT_GROUP", True):
            ctx = support_group_flags(request)

        assert ctx["ENABLE_SUPPORT_GROUP"] is True
        assert "sg_personas_json" in ctx
        assert "maria" in ctx["sg_personas_json"]

    def test_disabled(self):
        """When ENABLE_SUPPORT_GROUP is False, no persona JSON."""
        factory = RequestFactory()
        request = factory.get("/")

        with patch("apps.agents.context_processors.ENABLE_SUPPORT_GROUP", False):
            ctx = support_group_flags(request)

        assert ctx["ENABLE_SUPPORT_GROUP"] is False
        assert "sg_personas_json" not in ctx
