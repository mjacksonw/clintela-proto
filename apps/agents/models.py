"""AI Agents app - Multi-agent care coordination system."""

import uuid

from django.db import models


class AgentConversation(models.Model):
    """Enhanced conversation tracking for agent-patient interactions."""

    AGENT_TYPES = [
        ("supervisor", "Supervisor"),
        ("care_coordinator", "Care Coordinator"),
        ("nurse_triage", "Nurse Triage"),
        ("documentation", "Documentation"),
        ("specialist_cardiology", "Cardiology Specialist"),
        ("specialist_social_work", "Social Work Specialist"),
        ("specialist_nutrition", "Nutrition Specialist"),
        ("specialist_pt_rehab", "PT/Rehab Specialist"),
        ("specialist_palliative", "Palliative Care Specialist"),
        ("specialist_pharmacy", "Pharmacy Specialist"),
    ]

    STATUS_CHOICES = [
        ("active", "Active"),
        ("paused", "Paused"),
        ("completed", "Completed"),
        ("escalated", "Escalated"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="agent_conversations",
    )
    agent_type = models.CharField(max_length=30, choices=AGENT_TYPES, default="supervisor")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    # JSONB fields for flexible agent state
    context = models.JSONField(default=dict, blank=True)
    tool_invocations = models.JSONField(default=list, blank=True)
    escalation_reason = models.TextField(blank=True)

    # LLM metadata
    llm_metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "agents_conversation"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["patient", "status"], name="idx_agent_conv_patient_status"),
            models.Index(fields=["created_at"], name="idx_agent_conv_created"),
        ]

    def __str__(self):
        return f"{self.agent_type} - {self.patient} - {self.status}"


class AgentMessage(models.Model):
    """Individual messages within an agent conversation."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        AgentConversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )

    # Message content
    role = models.CharField(max_length=20, choices=[("user", "User"), ("assistant", "Assistant")])
    content = models.TextField()

    # Agent metadata
    agent_type = models.CharField(max_length=30, choices=AgentConversation.AGENT_TYPES, blank=True)
    routing_decision = models.CharField(max_length=50, blank=True)
    confidence_score = models.FloatField(null=True, blank=True)

    # Escalation tracking
    escalation_triggered = models.BooleanField(default=False)
    escalation_reason = models.TextField(blank=True)

    # Additional metadata
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agents_message"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "created_at"], name="idx_agent_msg_conv_created"),
        ]

    def __str__(self):
        return f"{self.role} - {self.created_at}"


class ConversationState(models.Model):
    """Cache for active conversation context (ephemeral, not critical)."""

    conversation = models.OneToOneField(
        AgentConversation,
        on_delete=models.CASCADE,
        related_name="state",
    )

    # Cached context
    patient_summary = models.TextField(blank=True)
    recent_symptoms = models.JSONField(default=list, blank=True)
    medications = models.JSONField(default=list, blank=True)
    recovery_phase = models.CharField(max_length=20, blank=True)
    tools_invoked = models.JSONField(default=list, blank=True)
    escalation_history = models.JSONField(default=list, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "agents_conversation_state"

    def __str__(self):
        return f"State for {self.conversation.id}"


class AgentAuditLog(models.Model):
    """HIPAA-compliant audit trail for all agent decisions."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="agent_audit_logs",
    )
    conversation = models.ForeignKey(
        AgentConversation,
        on_delete=models.CASCADE,
        related_name="audit_logs",
        null=True,
        blank=True,
    )

    action = models.CharField(max_length=100)
    agent_type = models.CharField(max_length=30, blank=True)
    details = models.JSONField(default=dict, blank=True)

    # Request metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agents_audit_log"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["patient", "created_at"], name="idx_audit_patient_created"),
            models.Index(fields=["created_at"], name="idx_audit_created"),
        ]

    def __str__(self):
        return f"{self.action} - {self.patient} - {self.created_at}"


class Escalation(models.Model):
    """Track escalations from AI to human clinicians."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("acknowledged", "Acknowledged"),
        ("resolved", "Resolved"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="escalations",
    )
    conversation = models.ForeignKey(
        AgentConversation,
        on_delete=models.CASCADE,
        related_name="escalations",
        null=True,
        blank=True,
    )

    reason = models.TextField()
    severity = models.CharField(
        max_length=20,
        choices=[
            ("critical", "Critical"),
            ("urgent", "Urgent"),
            ("routine", "Routine"),
        ]
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Context for clinician
    conversation_summary = models.TextField(blank=True)
    patient_context = models.JSONField(default=dict, blank=True)

    # Assignment
    assigned_to = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_escalations",
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "agents_escalation"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "severity"], name="idx_escalation_status_severity"),
            models.Index(fields=["patient", "created_at"], name="idx_escalation_patient_created"),
        ]

    def __str__(self):
        return f"{self.severity} - {self.patient} - {self.status}"
