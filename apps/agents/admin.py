"""Agents admin configuration (read-only, for inspection)."""

from django.contrib import admin

from .models import AgentConversation, AgentMessage, Escalation


@admin.register(AgentConversation)
class AgentConversationAdmin(admin.ModelAdmin):
    """Admin for AgentConversation model."""

    list_display = ("get_patient_name", "status", "agent_type", "created_at")
    list_filter = ("status", "agent_type")
    search_fields = ("patient__user__first_name", "patient__user__last_name")
    readonly_fields = (
        "id",
        "patient",
        "agent_type",
        "status",
        "context",
        "tool_invocations",
        "escalation_reason",
        "llm_metadata",
        "created_at",
        "updated_at",
    )

    @admin.display(description="Patient")
    def get_patient_name(self, obj):
        return obj.patient.user.get_full_name()

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AgentMessage)
class AgentMessageAdmin(admin.ModelAdmin):
    """Admin for AgentMessage model."""

    list_display = ("conversation", "role", "agent_type", "confidence_score", "created_at")
    list_filter = ("role", "agent_type", "escalation_triggered")
    search_fields = ("content",)
    readonly_fields = (
        "id",
        "conversation",
        "role",
        "content",
        "agent_type",
        "routing_decision",
        "confidence_score",
        "escalation_triggered",
        "escalation_reason",
        "metadata",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Escalation)
class EscalationAdmin(admin.ModelAdmin):
    """Admin for Escalation model."""

    list_display = ("get_patient_name", "severity", "status", "created_at")
    list_filter = ("severity", "status")
    search_fields = ("patient__user__first_name", "patient__user__last_name", "reason")
    readonly_fields = (
        "id",
        "patient",
        "conversation",
        "reason",
        "severity",
        "status",
        "conversation_summary",
        "patient_context",
        "assigned_to",
        "acknowledged_at",
        "resolved_at",
        "created_at",
        "updated_at",
    )

    @admin.display(description="Patient")
    def get_patient_name(self, obj):
        return obj.patient.user.get_full_name()

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
