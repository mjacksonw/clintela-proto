"""E2E tests for the patient chat interface using Playwright.

Tests focus on DOM structure, accessibility attributes, and page loading.
Alpine.js/HTMX interactivity tests require CDN access (marked with @network).
"""

import pytest
from playwright.sync_api import Page, expect

# Mark for tests that need CDN scripts (Alpine.js, Tailwind, HTMX)
network = pytest.mark.skipif(
    True,  # Set to False when running with network access
    reason="Requires CDN access for Alpine.js/Tailwind/HTMX",
)

DASHBOARD_PATH = "/patient/dashboard/"


@pytest.mark.django_db(transaction=True)
class TestDashboardStructure:
    """Test that the dashboard page loads with correct DOM structure."""

    def test_page_loads_with_title(self, authenticated_page: Page, live_server, test_patient):
        """Dashboard page loads with correct title."""
        authenticated_page.goto(f"{live_server.url}{DASHBOARD_PATH}")
        assert "Clintela" in authenticated_page.title()

    def test_recovery_progress_card(self, authenticated_page: Page, live_server, test_patient):
        """Recovery Progress card is present in dashboard."""
        authenticated_page.goto(f"{live_server.url}{DASHBOARD_PATH}")
        expect(authenticated_page.locator("text=Recovery Progress").first).to_be_visible()

    def test_care_team_heading(self, authenticated_page: Page, live_server, test_patient):
        """Care Team heading is present."""
        authenticated_page.goto(f"{live_server.url}{DASHBOARD_PATH}")
        expect(authenticated_page.get_by_role("heading", name="Your Care Team")).to_be_visible()

    def test_patient_name_in_care_team(self, authenticated_page: Page, live_server, test_patient):
        """Patient name appears in care team card."""
        authenticated_page.goto(f"{live_server.url}{DASHBOARD_PATH}")
        expect(authenticated_page.get_by_text("Hi Alex —", exact=False)).to_be_visible()

    def test_hospital_name_displayed(self, authenticated_page: Page, live_server, test_patient):
        """Hospital name appears in care team card."""
        authenticated_page.goto(f"{live_server.url}{DASHBOARD_PATH}")
        expect(authenticated_page.locator("text=E2E Hospital").first).to_be_visible()


@pytest.mark.django_db(transaction=True)
class TestAccessibility:
    """Test WCAG 2.1 AA accessibility requirements."""

    def test_skip_link_exists(self, authenticated_page: Page, live_server, test_patient):
        """Skip to content link exists for keyboard users."""
        authenticated_page.goto(f"{live_server.url}{DASHBOARD_PATH}")
        skip_link = authenticated_page.locator("a[href='#main-content']")
        expect(skip_link).to_be_attached()

    def test_main_content_landmark(self, authenticated_page: Page, live_server, test_patient):
        """Main content area has role=main."""
        authenticated_page.goto(f"{live_server.url}{DASHBOARD_PATH}")
        main = authenticated_page.locator("[role='main']")
        expect(main).to_be_attached()

    def test_main_content_has_id(self, authenticated_page: Page, live_server, test_patient):
        """Main content has id for skip link."""
        authenticated_page.goto(f"{live_server.url}{DASHBOARD_PATH}")
        main = authenticated_page.locator("#main-content")
        expect(main).to_be_attached()

    def test_header_banner_role(self, authenticated_page: Page, live_server, test_patient):
        """Header has banner role."""
        authenticated_page.goto(f"{live_server.url}{DASHBOARD_PATH}")
        header = authenticated_page.locator("[role='banner']")
        expect(header).to_be_attached()

    def test_chat_sidebar_complementary_role(self, authenticated_page: Page, live_server, test_patient):
        """Chat sidebar has complementary role."""
        authenticated_page.goto(f"{live_server.url}{DASHBOARD_PATH}")
        sidebar = authenticated_page.locator("[role='complementary']")
        expect(sidebar).to_be_attached()

    def test_chat_messages_log_role(self, authenticated_page: Page, live_server, test_patient):
        """Messages area has role=log for screen readers."""
        authenticated_page.goto(f"{live_server.url}{DASHBOARD_PATH}")
        log = authenticated_page.locator("[role='log']").first
        expect(log).to_be_attached()

    def test_chat_messages_aria_live(self, authenticated_page: Page, live_server, test_patient):
        """Messages area has aria-live=polite."""
        authenticated_page.goto(f"{live_server.url}{DASHBOARD_PATH}")
        log = authenticated_page.locator("[aria-live='polite']").first
        expect(log).to_be_attached()

    def test_chat_textarea_has_label(self, authenticated_page: Page, live_server, test_patient):
        """Chat textarea has a proper label element."""
        authenticated_page.goto(f"{live_server.url}{DASHBOARD_PATH}")
        label = authenticated_page.locator("label[for='chat-textarea']").first
        expect(label).to_be_attached()

    def test_chat_textarea_exists(self, authenticated_page: Page, live_server, test_patient):
        """Chat textarea element exists."""
        authenticated_page.goto(f"{live_server.url}{DASHBOARD_PATH}")
        textarea = authenticated_page.locator("[name='message']").first
        expect(textarea).to_be_attached()

    def test_send_button_has_aria_label(self, authenticated_page: Page, live_server, test_patient):
        """Send button has aria-label."""
        authenticated_page.goto(f"{live_server.url}{DASHBOARD_PATH}")
        button = authenticated_page.locator("[aria-label='Send message']").first
        expect(button).to_be_attached()

    def test_typing_indicator_status_role(self, authenticated_page: Page, live_server, test_patient):
        """Typing indicator has role=status."""
        authenticated_page.goto(f"{live_server.url}{DASHBOARD_PATH}")
        status = authenticated_page.locator("[role='status']").first
        expect(status).to_be_attached()

    def test_offline_banner_alert_role(self, authenticated_page: Page, live_server, test_patient):
        """Offline banner has role=alert."""
        authenticated_page.goto(f"{live_server.url}{DASHBOARD_PATH}")
        alert = authenticated_page.locator("[role='alert']").first
        expect(alert).to_be_attached()

    def test_mobile_dialog_has_aria_modal(self, authenticated_page: Page, live_server, test_patient):
        """Mobile chat dialog has aria-modal=true."""
        authenticated_page.goto(f"{live_server.url}{DASHBOARD_PATH}")
        dialog = authenticated_page.locator("[role='dialog'][aria-modal='true']")
        expect(dialog).to_be_attached()

    def test_lang_attribute(self, authenticated_page: Page, live_server, test_patient):
        """HTML element has lang attribute."""
        authenticated_page.goto(f"{live_server.url}{DASHBOARD_PATH}")
        html = authenticated_page.locator("html[lang='en']")
        expect(html).to_be_attached()

    def test_focus_visible_styles(self, authenticated_page: Page, live_server, test_patient):
        """Page includes focus-visible CSS for keyboard navigation."""
        authenticated_page.goto(f"{live_server.url}{DASHBOARD_PATH}")
        content = authenticated_page.content()
        assert "focus-visible" in content

    def test_reduced_motion_styles(self, authenticated_page: Page, live_server, test_patient):
        """Page includes prefers-reduced-motion media query."""
        authenticated_page.goto(f"{live_server.url}{DASHBOARD_PATH}")
        content = authenticated_page.content()
        assert "prefers-reduced-motion" in content


@pytest.mark.django_db(transaction=True)
class TestChatSidebar:
    """Test chat sidebar DOM structure."""

    def test_suggestion_chips_in_dom(self, authenticated_page: Page, live_server, test_patient):
        """Suggestion chips are present in the DOM."""
        authenticated_page.goto(f"{live_server.url}{DASHBOARD_PATH}")
        chips = authenticated_page.locator(".suggestion-chip")
        assert chips.count() >= 3

    def test_empty_chat_welcome_in_dom(self, authenticated_page: Page, live_server, test_patient):
        """Welcome message is in the DOM for new patients."""
        authenticated_page.goto(f"{live_server.url}{DASHBOARD_PATH}")
        welcome = authenticated_page.locator("text=I'm here to help with your recovery").first
        expect(welcome).to_be_attached()

    def test_trust_signal_in_dom(self, authenticated_page: Page, live_server, test_patient):
        """Privacy/trust signal text is present."""
        authenticated_page.goto(f"{live_server.url}{DASHBOARD_PATH}")
        trust = authenticated_page.locator("text=Your conversations are private").first
        expect(trust).to_be_attached()

    def test_chat_form_exists(self, authenticated_page: Page, live_server, test_patient):
        """HTMX chat form exists with correct target."""
        authenticated_page.goto(f"{live_server.url}{DASHBOARD_PATH}")
        # Desktop sidebar form (scoped to complementary role)
        sidebar = authenticated_page.locator("[role='complementary']")
        form = sidebar.locator("form[hx-target='#messages']")
        expect(form).to_be_attached()

    def test_mobile_fab_in_dom(self, authenticated_page: Page, live_server, test_patient):
        """Mobile FAB button exists in DOM."""
        authenticated_page.goto(f"{live_server.url}{DASHBOARD_PATH}")
        fab = authenticated_page.locator("#chat-fab")
        expect(fab).to_be_attached()
        assert fab.get_attribute("aria-label") == "Open chat"

    def test_close_button_in_dom(self, authenticated_page: Page, live_server, test_patient):
        """Mobile close button exists with aria-label."""
        authenticated_page.goto(f"{live_server.url}{DASHBOARD_PATH}")
        close = authenticated_page.locator("#mobile-chat-close")
        expect(close).to_be_attached()
        assert close.get_attribute("aria-label") == "Close chat"
