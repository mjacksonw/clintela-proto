"""Tests for ProtectedEnvironmentMiddleware and protected gate view."""

from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings

from apps.accounts.middleware import ProtectedEnvironmentMiddleware


def dummy_response(request):
    return HttpResponse("OK", status=200)


class TestProtectedEnvironmentMiddleware(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = ProtectedEnvironmentMiddleware(dummy_response)

    @override_settings(PROTECTED=False)
    def test_middleware_disabled_when_not_protected(self):
        request = self.factory.get("/any-page/")
        request.COOKIES = {}
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

    @override_settings(PROTECTED=True, PROTECTED_GATE_PATH="letmein")
    def test_middleware_blocks_without_cookie(self):
        request = self.factory.get("/any-page/")
        request.COOKIES = {}
        response = self.middleware(request)
        self.assertEqual(response.status_code, 401)

    @override_settings(PROTECTED=True, PROTECTED_GATE_PATH="letmein")
    def test_middleware_allows_with_cookie(self):
        request = self.factory.get("/any-page/")
        request.COOKIES = {"demo_access": "1"}
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

    @override_settings(PROTECTED=True, PROTECTED_GATE_PATH="letmein")
    def test_middleware_exempts_gate_url(self):
        request = self.factory.get("/auth/letmein/")
        request.COOKIES = {}
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

    @override_settings(
        PROTECTED=True,
        PROTECTED_GATE_PATH="letmein",
        STATIC_URL="/static/",
        MEDIA_URL="/media/",
    )
    def test_middleware_exempts_static_urls(self):
        for path in ["/static/css/main.css", "/media/uploads/photo.jpg"]:
            request = self.factory.get(path)
            request.COOKIES = {}
            response = self.middleware(request)
            self.assertEqual(response.status_code, 200, f"Expected 200 for {path}")

    @override_settings(PROTECTED=True, PROTECTED_GATE_PATH="letmein")
    def test_middleware_blocks_with_invalid_cookie(self):
        request = self.factory.get("/any-page/")
        request.COOKIES = {"demo_access": "wrong"}
        response = self.middleware(request)
        self.assertEqual(response.status_code, 401)


class TestProtectedGateView(TestCase):
    @override_settings(PROTECTED=True, PROTECTED_GATE_PATH="letmein")
    def test_gate_view_sets_cookie(self):
        # The gate URL is only registered when PROTECTED=True,
        # so we call the view directly.
        from apps.accounts.views_dev import protected_gate_view

        request = RequestFactory().get("/auth/letmein/")
        response = protected_gate_view(request)
        self.assertIn("demo_access", response.cookies)
        cookie = response.cookies["demo_access"]
        self.assertEqual(cookie.value, "1")
        self.assertEqual(cookie["max-age"], 2592000)
        self.assertTrue(cookie["httponly"])

    @override_settings(PROTECTED=True, PROTECTED_GATE_PATH="letmein")
    def test_gate_view_redirects_to_home(self):
        from apps.accounts.views_dev import protected_gate_view

        request = RequestFactory().get("/auth/letmein/")
        response = protected_gate_view(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")


class TestContextProcessorShowDemoBar(TestCase):
    @override_settings(DEBUG=True)
    def test_context_processor_includes_show_demo_bar(self):
        from apps.accounts.context_processors import demo_bar_context

        request = RequestFactory().get("/")
        request.session = {}
        context = demo_bar_context(request)
        self.assertTrue(context.get("show_demo_bar"))

    @override_settings(DEBUG=False)
    def test_context_processor_excludes_show_demo_bar_when_not_debug(self):
        from apps.accounts.context_processors import demo_bar_context

        request = RequestFactory().get("/")
        request.session = {}
        context = demo_bar_context(request)
        self.assertNotIn("show_demo_bar", context)
