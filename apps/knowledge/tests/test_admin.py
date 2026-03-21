"""Tests for knowledge admin dashboard."""

import pytest
from django.test import RequestFactory
from django.utils import timezone

from apps.agents.tests.factories import HospitalFactory, UserFactory
from apps.knowledge.admin import KnowledgeDashboardAdmin, KnowledgeDashboardProxy
from apps.knowledge.models import KnowledgeDocument, KnowledgeGap, KnowledgeSource


@pytest.fixture
def admin_user():
    return UserFactory(is_staff=True, is_superuser=True, role="admin")


@pytest.fixture
def request_factory():
    return RequestFactory()


@pytest.fixture
def dashboard_admin():
    from django.contrib.admin.sites import AdminSite

    return KnowledgeDashboardAdmin(KnowledgeDashboardProxy, AdminSite())


@pytest.mark.django_db
class TestKnowledgeDashboardView:
    def test_dashboard_renders_empty_state(self, admin_user, request_factory, dashboard_admin):
        # Clean up any leaked data from parallel test workers
        KnowledgeGap.objects.all().delete()
        KnowledgeSource.objects.all().delete()

        request = request_factory.get("/admin/knowledge/knowledgedashboardproxy/dashboard/")
        request.user = admin_user
        response = dashboard_admin.dashboard_view(request)

        assert response.status_code == 200
        assert response.context_data["source_count"] == 0
        assert response.context_data["chunk_count"] == 0
        assert response.context_data["gap_count"] == 0
        assert response.context_data["avg_age_days"] is None

    def test_dashboard_with_sources(self, admin_user, request_factory, dashboard_admin):
        hospital = HospitalFactory()
        source = KnowledgeSource.objects.create(
            name="ACC CABG Guidelines",
            source_type="acc_guideline",
            hospital=hospital,
            version="2024",
            is_active=True,
            last_ingested_at=timezone.now(),
        )
        KnowledgeDocument.objects.create(
            source=source,
            title="Post-Op Day 1-3",
            content="Recovery information",
            chunk_index=0,
            embedding=[0.0] * 768,
            token_count=50,
            content_hash="abc123",
            is_active=True,
        )

        request = request_factory.get("/admin/knowledge/knowledgedashboardproxy/dashboard/")
        request.user = admin_user
        response = dashboard_admin.dashboard_view(request)

        assert response.context_data["source_count"] == 1
        assert response.context_data["chunk_count"] == 1
        assert response.context_data["avg_age_days"] is not None
        assert len(response.context_data["source_rows"]) == 1
        assert response.context_data["source_rows"][0]["freshness"] == "fresh"

    def test_dashboard_freshness_categories(self, admin_user, request_factory, dashboard_admin):
        now = timezone.now()
        # Fresh source (< 30 days)
        KnowledgeSource.objects.create(
            name="Fresh Source",
            source_type="acc_guideline",
            version="1",
            is_active=True,
            last_ingested_at=now - timezone.timedelta(days=5),
        )
        # Aging source (30-90 days)
        KnowledgeSource.objects.create(
            name="Aging Source",
            source_type="hospital_protocol",
            version="1",
            is_active=True,
            last_ingested_at=now - timezone.timedelta(days=60),
        )
        # Stale source (> 90 days)
        KnowledgeSource.objects.create(
            name="Stale Source",
            source_type="clinical_research",
            version="1",
            is_active=True,
            last_ingested_at=now - timezone.timedelta(days=120),
        )

        request = request_factory.get("/admin/knowledge/knowledgedashboardproxy/dashboard/")
        request.user = admin_user
        response = dashboard_admin.dashboard_view(request)

        rows = response.context_data["source_rows"]
        freshness_values = {r["name"]: r["freshness"] for r in rows}
        assert freshness_values["Fresh Source"] == "fresh"
        assert freshness_values["Aging Source"] == "aging"
        assert freshness_values["Stale Source"] == "stale"

    def test_dashboard_knowledge_gaps(self, admin_user, request_factory, dashboard_admin):
        # Clean up any leaked data from parallel test workers
        KnowledgeGap.objects.all().delete()

        KnowledgeGap.objects.create(
            query="Can I take ibuprofen with warfarin?",
            max_similarity=0.45,
            agent_type="specialist_pharmacy",
        )
        KnowledgeGap.objects.create(
            query="Can I take ibuprofen with warfarin?",
            max_similarity=0.50,
            agent_type="specialist_pharmacy",
        )
        KnowledgeGap.objects.create(
            query="When can I drive after CABG?",
            max_similarity=0.30,
            agent_type="care_coordinator",
        )

        request = request_factory.get("/admin/knowledge/knowledgedashboardproxy/dashboard/")
        request.user = admin_user
        response = dashboard_admin.dashboard_view(request)

        assert response.context_data["gap_count"] == 3
        gaps = list(response.context_data["top_gaps"])
        assert len(gaps) == 2
        assert gaps[0]["count"] == 2  # ibuprofen question asked twice

    def test_dashboard_never_ingested_source(self, admin_user, request_factory, dashboard_admin):
        KnowledgeSource.objects.create(
            name="New Source",
            source_type="hospital_protocol",
            version="1",
            is_active=True,
            last_ingested_at=None,
        )

        request = request_factory.get("/admin/knowledge/knowledgedashboardproxy/dashboard/")
        request.user = admin_user
        response = dashboard_admin.dashboard_view(request)

        rows = response.context_data["source_rows"]
        assert rows[0]["days"] is None
        assert rows[0]["freshness"] == "stale"


@pytest.mark.django_db
class TestKnowledgeSourceAdmin:
    def test_freshness_indicator_fresh(self):
        source = KnowledgeSource(last_ingested_at=timezone.now() - timezone.timedelta(days=5))
        from django.contrib.admin.sites import AdminSite

        from apps.knowledge.admin import KnowledgeSourceAdmin

        admin_obj = KnowledgeSourceAdmin(KnowledgeSource, AdminSite())
        result = admin_obj.freshness_indicator(source)
        assert "Fresh" in result

    def test_freshness_indicator_aging(self):
        source = KnowledgeSource(last_ingested_at=timezone.now() - timezone.timedelta(days=60))
        from django.contrib.admin.sites import AdminSite

        from apps.knowledge.admin import KnowledgeSourceAdmin

        admin_obj = KnowledgeSourceAdmin(KnowledgeSource, AdminSite())
        result = admin_obj.freshness_indicator(source)
        assert "Aging" in result

    def test_freshness_indicator_stale(self):
        source = KnowledgeSource(last_ingested_at=timezone.now() - timezone.timedelta(days=120))
        from django.contrib.admin.sites import AdminSite

        from apps.knowledge.admin import KnowledgeSourceAdmin

        admin_obj = KnowledgeSourceAdmin(KnowledgeSource, AdminSite())
        result = admin_obj.freshness_indicator(source)
        assert "Stale" in result

    def test_freshness_indicator_never_ingested(self):
        source = KnowledgeSource(last_ingested_at=None)
        from django.contrib.admin.sites import AdminSite

        from apps.knowledge.admin import KnowledgeSourceAdmin

        admin_obj = KnowledgeSourceAdmin(KnowledgeSource, AdminSite())
        result = admin_obj.freshness_indicator(source)
        assert "Never" in result


@pytest.mark.django_db
class TestKnowledgeGapAdmin:
    def test_query_truncated_short(self):
        gap = KnowledgeGap(query="Short question?")
        from django.contrib.admin.sites import AdminSite

        from apps.knowledge.admin import KnowledgeGapAdmin

        admin_obj = KnowledgeGapAdmin(KnowledgeGap, AdminSite())
        assert admin_obj.query_truncated(gap) == "Short question?"

    def test_query_truncated_long(self):
        gap = KnowledgeGap(query="x" * 150)
        from django.contrib.admin.sites import AdminSite

        from apps.knowledge.admin import KnowledgeGapAdmin

        admin_obj = KnowledgeGapAdmin(KnowledgeGap, AdminSite())
        result = admin_obj.query_truncated(gap)
        assert result.endswith("...")
        assert len(result) == 103  # 100 chars + "..."
