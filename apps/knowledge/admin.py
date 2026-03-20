"""Knowledge app admin configuration."""

from django.contrib import admin
from django.db.models import Count
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
