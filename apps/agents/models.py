"""AI Agents app - Multi-agent care coordination system."""

import uuid

from django.db import models


class AgentConversation(models.Model):
    """Enhanced conversation tracking for agent-patient interactions."""

    CONVERSATION_TYPE_CHOICES = [
        ("care_team", "Care Team"),
        ("support_group", "Support Group"),
    ]

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
        ("clinician_research", "Clinician Research"),
        ("clinician", "Clinician"),
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
    clinician = models.ForeignKey(
        "clinicians.Clinician",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="research_conversations",
        help_text="Set for clinician research conversations",
    )
    conversation_type = models.CharField(
        max_length=20,
        choices=CONVERSATION_TYPE_CHOICES,
        default="care_team",
    )
    agent_type = models.CharField(max_length=30, choices=AGENT_TYPES, default="supervisor")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    # Support group: atomic generation counter for task staleness detection.
    # Increment via queryset.update(generation_id=F('generation_id') + 1),
    # NOT .save(). Then refresh_from_db() before passing to Celery.
    generation_id = models.IntegerField(default=0)

    # JSONB fields for flexible agent state
    context = models.JSONField(default=dict, blank=True)
    tool_invocations = models.JSONField(default=list, blank=True)

    # Per-persona memory summaries for support group conversations.
    # Keyed by persona_id, each value is a compressed summary string.
    persona_memories = models.JSONField(default=dict, blank=True)

    # LLM metadata
    llm_metadata = models.JSONField(default=dict, blank=True)

    # Take-control: clinician pauses AI to respond directly
    paused_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="paused_conversations",
        help_text="Clinician who has taken control of this conversation",
    )
    paused_at = models.DateTimeField(null=True, blank=True)

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
    role = models.CharField(
        max_length=20,
        choices=[("user", "User"), ("assistant", "Assistant"), ("system", "System")],
    )
    content = models.TextField()

    # Agent metadata
    agent_type = models.CharField(max_length=30, choices=AgentConversation.AGENT_TYPES, blank=True)
    persona_id = models.CharField(max_length=20, null=True, blank=True)  # noqa: DJ001 — NULL used by UniqueConstraint condition
    generation_id = models.IntegerField(null=True, blank=True)
    routing_decision = models.CharField(max_length=50, blank=True)
    confidence_score = models.FloatField(null=True, blank=True)

    # Escalation tracking
    escalation_triggered = models.BooleanField(default=False)
    escalation_reason = models.TextField(blank=True)

    # RAG citation tracking
    cited_documents = models.ManyToManyField(
        "knowledge.KnowledgeDocument",
        through="MessageCitation",
        blank=True,
    )

    # Translation fields
    original_content = models.TextField(blank=True, default="")
    source_language = models.CharField(max_length=10, blank=True, default="")
    translated = models.BooleanField(default=False)

    # Additional metadata
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agents_message"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "created_at"], name="idx_agent_msg_conv_created"),
            models.Index(
                fields=["conversation", "persona_id", "created_at"],
                name="idx_agent_msg_persona",
            ),
        ]
        constraints = [
            # Prevent duplicate persona responses per generation cycle (idempotency guard
            # for Celery retries). Only applies to support group messages (persona_id set).
            models.UniqueConstraint(
                fields=["conversation", "persona_id", "generation_id"],
                condition=models.Q(persona_id__isnull=False),
                name="uq_agent_msg_persona_generation",
            ),
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

    ESCALATION_TYPE_CHOICES = [
        ("clinical", "Clinical"),
        ("specialist_referral", "Specialist Referral"),
        ("social_work", "Social Work"),
        ("pharmacy_consult", "Pharmacy Consult"),
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
        ],
    )
    escalation_type = models.CharField(
        max_length=30,
        choices=ESCALATION_TYPE_CHOICES,
        default="clinical",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    priority_score = models.FloatField(
        default=0.0,
        help_text="Computed from severity + wait time + patient status",
    )
    response_deadline = models.DateTimeField(
        null=True,
        blank=True,
        help_text="SLA tracking: when this escalation must be addressed",
    )

    # Context for clinician
    conversation_summary = models.TextField(blank=True)
    patient_context = models.JSONField(default=dict, blank=True)
    conversation_excerpt = models.TextField(
        blank=True,
        help_text="Verbatim triggering message + recent messages for SG escalations",
    )

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


class SupportGroupReaction(models.Model):
    """Emoji reaction from a persona on a support group message."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(
        AgentMessage,
        on_delete=models.CASCADE,
        related_name="reactions",
    )
    persona_id = models.CharField(max_length=20)
    emoji = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agents_support_group_reaction"
        constraints = [
            models.UniqueConstraint(
                fields=["message", "persona_id"],
                name="uq_reaction_message_persona",
            ),
        ]

    def __str__(self):
        return f"{self.persona_id} reacted {self.emoji} on {self.message_id}"


class MessageCitation(models.Model):
    """Through model linking AgentMessage to KnowledgeDocument.

    Tracks which knowledge chunks were retrieved and used to generate
    a given agent response, with similarity scores for analytics.
    """

    agent_message = models.ForeignKey(
        AgentMessage,
        on_delete=models.CASCADE,
        related_name="citations",
    )
    knowledge_doc = models.ForeignKey(
        "knowledge.KnowledgeDocument",
        on_delete=models.CASCADE,
        related_name="citations",
    )
    similarity_score = models.FloatField(
        help_text="Combined similarity score from hybrid search",
    )
    retrieved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agents_message_citation"
        constraints = [
            models.UniqueConstraint(
                fields=["agent_message", "knowledge_doc"],
                name="uq_citation_message_doc",
            ),
        ]
        indexes = [
            models.Index(
                fields=["knowledge_doc"],
                name="idx_citation_knowledge_doc",
            ),
        ]

    def __str__(self):
        return f"Citation: {self.knowledge_doc} (score={self.similarity_score:.2f})"
