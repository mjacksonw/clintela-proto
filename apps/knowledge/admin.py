"""Knowledge app admin configuration with health dashboard."""

import contextlib

from django.contrib import admin
from django.db.models import Count, Max
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone

from .models import KnowledgeDocument, KnowledgeGap, KnowledgeSource


@admin.register(KnowledgeSource)
class KnowledgeSourceAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "source_type",
        "hospital",
        "version",
        "is_active",
        "chunk_count",
        "freshness_indicator",
        "last_ingested_at",
        "created_by",
    ]
    list_filter = ["source_type", "is_active", "hospital"]
    search_fields = ["name", "version"]
    readonly_fields = ["created_at", "updated_at"]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                _chunk_count=Count("documents", distinct=True),
            )
        )

    @admin.display(description="Chunks", ordering="_chunk_count")
    def chunk_count(self, obj):
        return obj._chunk_count

    @admin.display(description="Freshness")
    def freshness_indicator(self, obj):
        if not obj.last_ingested_at:
            return "-- Never ingested"
        days = (timezone.now() - obj.last_ingested_at).days
        if days < 30:
            return f"Fresh ({days}d)"
        if days < 90:
            return f"Aging ({days}d)"
        return f"Stale ({days}d)"


@admin.register(KnowledgeDocument)
class KnowledgeDocumentAdmin(admin.ModelAdmin):
    list_display = ["title", "source", "chunk_index", "token_count", "is_active", "created_at"]
    list_filter = ["source", "is_active"]
    search_fields = ["title", "content"]
    readonly_fields = ["content_hash", "created_at"]


@admin.register(KnowledgeGap)
class KnowledgeGapAdmin(admin.ModelAdmin):
    list_display = ["query_truncated", "hospital", "agent_type", "max_similarity", "created_at"]
    list_filter = ["hospital", "agent_type"]
    search_fields = ["query"]
    date_hierarchy = "created_at"

    @admin.display(description="Query")
    def query_truncated(self, obj):
        return obj.query[:100] + "..." if len(obj.query) > 100 else obj.query


class KnowledgeDashboardAdmin(admin.ModelAdmin):
    """Proxy admin to host the Knowledge Health Dashboard."""

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "dashboard/",
                self.admin_site.admin_view(self.dashboard_view),
                name="knowledge_dashboard",
            ),
        ]
        return custom + urls

    def dashboard_view(self, request):
        """Knowledge Health Dashboard view."""
        now = timezone.now()

        # Summary stats
        source_count = KnowledgeSource.objects.filter(is_active=True).count()
        chunk_count = KnowledgeDocument.objects.filter(is_active=True).count()
        gap_count = KnowledgeGap.objects.count()

        # Average source age (compute in Python since AVG doesn't work on timestamps)
        avg_age_days = None
        ingested_sources = KnowledgeSource.objects.filter(is_active=True, last_ingested_at__isnull=False).values_list(
            "last_ingested_at", flat=True
        )
        if ingested_sources:
            ages = [(now - ts).days for ts in ingested_sources]
            avg_age_days = sum(ages) // len(ages)

        # Source freshness table
        sources = (
            KnowledgeSource.objects.filter(is_active=True)
            .annotate(doc_count=Count("documents"))
            .order_by("-last_ingested_at")
        )
        source_rows = []
        for src in sources:
            if src.last_ingested_at:
                days = (now - src.last_ingested_at).days
                if days < 30:
                    freshness = "fresh"
                elif days < 90:
                    freshness = "aging"
                else:
                    freshness = "stale"
            else:
                days = None
                freshness = "stale"
            source_rows.append(
                {
                    "name": src.name,
                    "chunks": src.doc_count,
                    "days": days,
                    "freshness": freshness,
                }
            )

        # Top knowledge gaps (most frequent unanswered questions)
        top_gaps = KnowledgeGap.objects.values("query").annotate(count=Count("id")).order_by("-count")[:10]

        # Most cited documents (from MessageCitation)
        most_cited = []
        with contextlib.suppress(Exception):
            most_cited = list(
                KnowledgeDocument.objects.filter(is_active=True)
                .annotate(
                    citation_count=Count("citations"),
                    last_cited=Max("citations__retrieved_at"),
                )
                .filter(citation_count__gt=0)
                .order_by("-citation_count")[:10]
                .values("title", "source__name", "citation_count")
            )

        context = {
            **self.admin_site.each_context(request),
            "title": "Knowledge Health Dashboard",
            "source_count": source_count,
            "chunk_count": chunk_count,
            "gap_count": gap_count,
            "avg_age_days": avg_age_days,
            "source_rows": source_rows,
            "top_gaps": top_gaps,
            "most_cited": most_cited,
        }
        return TemplateResponse(
            request,
            "admin/knowledge/dashboard.html",
            context,
        )


# Register a proxy model for the dashboard URL
class KnowledgeDashboardProxy(KnowledgeSource):
    class Meta:
        proxy = True
        verbose_name = "Knowledge Dashboard"
        verbose_name_plural = "Knowledge Dashboard"


admin.site.register(KnowledgeDashboardProxy, KnowledgeDashboardAdmin)
