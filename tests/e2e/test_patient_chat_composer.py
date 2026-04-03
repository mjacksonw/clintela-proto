"""E2E: care team chat composer must hydrate (Alpine + voice-recorder.js load order).

Regression: voice-recorder.js was embedded in _chat_input.html. When the sidebar is
mounted via Alpine ``template x-if``, injected <script> tags do not execute, so
``patientChatComposer`` was undefined, ``x-data`` failed silently, and the textarea
stayed ``display: none`` (x-show) with a disabled appearance.

Scripts are loaded from ``base_patient.html`` ``extra_js`` so they run before Alpine.
"""

import pytest
from playwright.sync_api import Page, expect

DASHBOARD_PATH = "/patient/dashboard/"


@pytest.mark.django_db(transaction=True)
class TestCareTeamComposerVisible:
    @pytest.fixture(autouse=True)
    def _desktop(self, authenticated_page: Page):
        authenticated_page.set_viewport_size({"width": 1400, "height": 900})

    def test_chat_textarea_visible_and_enabled_on_load(self, authenticated_page: Page, live_server, test_patient):
        authenticated_page.goto(f"{live_server.url}{DASHBOARD_PATH}", wait_until="domcontentloaded")
        authenticated_page.wait_for_timeout(1500)

        ta = authenticated_page.locator("[role='complementary'] #chat-textarea")
        expect(ta).to_be_visible(timeout=15_000)

        authenticated_page.wait_for_function(
            """
            () => {
                const form = document.querySelector("[role='complementary'] #chat-form");
                if (!form || !window.Alpine) return false;
                const d = Alpine.$data(form);
                return d && typeof d.recording === 'boolean' && d.recording === false;
            }
            """,
            timeout=15_000,
        )

        info = authenticated_page.evaluate(
            """
            () => {
                const el = document.querySelector("[role='complementary'] #chat-textarea");
                const form = document.querySelector("[role='complementary'] #chat-form");
                const d = form && window.Alpine ? Alpine.$data(form) : null;
                return {
                    display: el ? getComputedStyle(el).display : null,
                    disabled: el ? el.disabled : null,
                    recording: d ? d.recording : null,
                    inflight: d ? d.inflight : null,
                };
            }
            """
        )
        assert info["display"] != "none", info
        assert info["disabled"] is False, info
        assert info["recording"] is False, info
        assert info["inflight"] is False, info
