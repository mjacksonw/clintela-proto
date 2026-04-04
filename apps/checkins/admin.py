from django.contrib import admin

from apps.checkins.models import (
    CheckinQuestion,
    CheckinResponse,
    CheckinSession,
    PathwayCheckinConfig,
)


@admin.register(CheckinQuestion)
class CheckinQuestionAdmin(admin.ModelAdmin):
    list_display = ["code", "category", "response_type", "priority", "is_active"]
    list_filter = ["category", "response_type", "is_active"]
    search_fields = ["code", "text"]
    ordering = ["category", "priority"]


@admin.register(PathwayCheckinConfig)
class PathwayCheckinConfigAdmin(admin.ModelAdmin):
    list_display = ["pathway", "category", "relevance_phase", "max_gap_days"]
    list_filter = ["category", "relevance_phase"]
    raw_id_fields = ["pathway"]


class CheckinResponseInline(admin.TabularInline):
    model = CheckinResponse
    extra = 0
    readonly_fields = ["question", "value", "follow_up_triggered", "escalation_triggered", "created_at"]


@admin.register(CheckinSession)
class CheckinSessionAdmin(admin.ModelAdmin):
    list_display = ["patient", "date", "status", "pathway_day", "phase", "created_at"]
    list_filter = ["status", "phase"]
    search_fields = ["patient__user__first_name", "patient__user__last_name"]
    raw_id_fields = ["patient", "conversation"]
    inlines = [CheckinResponseInline]
    readonly_fields = ["questions_selected", "selection_rationale"]


@admin.register(CheckinResponse)
class CheckinResponseAdmin(admin.ModelAdmin):
    list_display = ["session", "question", "value", "follow_up_triggered", "escalation_triggered"]
    list_filter = ["follow_up_triggered", "escalation_triggered"]
    raw_id_fields = ["session", "question", "agent_message"]
