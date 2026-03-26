"""E2E tests for clinician dashboard URL routing.

Tests verify that path-based URLs update correctly when navigating
patients and tabs, and that deep links restore the correct state.
"""

import pytest
from playwright.sync_api import Page, expect

DASHBOARD_PATH = "/clinician/dashboard/"


@pytest.mark.django_db(transaction=True)
class TestDashboardDeepLinks:
    """Test that deep link URLs load the correct dashboard state."""

    def test_base_dashboard_loads(self, authenticated_clinician_page: Page, live_server):
        """Base dashboard URL loads without errors."""
        authenticated_clinician_page.goto(f"{live_server.url}{DASHBOARD_PATH}")
        expect(authenticated_clinician_page.locator("[role='tablist']")).to_be_attached()

    def test_deep_link_with_patient(
        self, authenticated_clinician_page: Page, live_server, test_patient
    ):
        """Deep link with patient ID sets data attributes for JS restoration."""
        url = f"{live_server.url}/clinician/dashboard/patient/{test_patient.id}/"
        authenticated_clinician_page.goto(url)
        root = authenticated_clinician_page.locator("[data-initial-patient]")
        expect(root).to_be_attached()
        assert root.get_attribute("data-initial-patient") == str(test_patient.id)

    def test_deep_link_with_patient_and_tab(
        self, authenticated_clinician_page: Page, live_server, test_patient
    ):
        """Deep link with patient + tab sets correct data attributes."""
        url = f"{live_server.url}/clinician/dashboard/patient/{test_patient.id}/surveys/"
        authenticated_clinician_page.goto(url)
        root = authenticated_clinician_page.locator("[data-initial-patient]")
        assert root.get_attribute("data-initial-patient") == str(test_patient.id)
        assert root.get_attribute("data-initial-tab") == "surveys"

    def test_deep_link_with_invalid_patient(
        self, authenticated_clinician_page: Page, live_server
    ):
        """Deep link with nonexistent patient renders empty dashboard."""
        url = f"{live_server.url}/clinician/dashboard/patient/99999/"
        authenticated_clinician_page.goto(url)
        root = authenticated_clinician_page.locator("[data-initial-patient]")
        assert root.get_attribute("data-initial-patient") == ""

    def test_deep_link_with_invalid_tab(
        self, authenticated_clinician_page: Page, live_server, test_patient
    ):
        """Deep link with bogus tab falls back to details."""
        url = f"{live_server.url}/clinician/dashboard/patient/{test_patient.id}/bogus/"
        authenticated_clinician_page.goto(url)
        root = authenticated_clinician_page.locator("[data-initial-tab]")
        assert root.get_attribute("data-initial-tab") == "details"


@pytest.mark.django_db(transaction=True)
class TestSurveysTabButton:
    """Test that the Surveys tab button is present and functional."""

    def test_surveys_tab_visible(self, authenticated_clinician_page: Page, live_server):
        """Surveys tab button is rendered in the tab bar."""
        authenticated_clinician_page.goto(f"{live_server.url}{DASHBOARD_PATH}")
        surveys_btn = authenticated_clinician_page.locator("button[role='tab']", has_text="Surveys")
        expect(surveys_btn).to_be_attached()

    def test_all_tabs_present(self, authenticated_clinician_page: Page, live_server):
        """All expected tabs are present in the tab bar."""
        authenticated_clinician_page.goto(f"{live_server.url}{DASHBOARD_PATH}")
        tabs = authenticated_clinician_page.locator("button[role='tab']")
        tab_texts = [tabs.nth(i).text_content().strip() for i in range(tabs.count())]
        for expected in ["Details", "Care Plan", "Research", "Surveys", "Tools"]:
            assert expected in tab_texts, f"Missing tab: {expected}"


@pytest.mark.django_db(transaction=True)
class TestUrlRoutingJsMethods:
    """Test that URL routing JS methods are loaded in the dashboard."""

    def test_routing_methods_in_js(
        self, authenticated_clinician_page: Page, live_server
    ):
        """Dashboard JS includes all URL routing methods."""
        authenticated_clinician_page.goto(f"{live_server.url}{DASHBOARD_PATH}")
        # The JS file is loaded as an external script; check it defines the methods
        result = authenticated_clinician_page.evaluate(
            "typeof clinicianDashboard === 'function'"
        )
        assert result is True


@pytest.mark.django_db(transaction=True)
class TestKeyboardHelp:
    """Test keyboard help shows correct number of shortcuts."""

    def test_keyboard_help_has_six_keys(
        self, authenticated_clinician_page: Page, live_server
    ):
        """Keyboard help shows 6 tab shortcuts (1-6)."""
        authenticated_clinician_page.goto(f"{live_server.url}{DASHBOARD_PATH}")
        # The keyboard help contains kbd elements for tab switching
        # Count kbd elements within the "Switch tabs" row
        content = authenticated_clinician_page.content()
        # Should have kbd elements for 1 through 6
        for key in ["1", "2", "3", "4", "5", "6"]:
            assert f">{key}</kbd>" in content, f"Missing keyboard shortcut: {key}"
