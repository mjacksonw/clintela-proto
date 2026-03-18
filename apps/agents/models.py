"""AI Agents app - Multi-agent care coordination system."""

from django.db import models


class AgentConversation(models.Model):
    """Log of agent-patient interactions."""

    AGENT_TYPES = [
        ("supervisor", "Supervisor"),
        ("care_coordinator", "Care Coordinator"),
        ("nurse_triage", "Nurse Triage"),
        ("documentation", "Documentation"),
        ("specialist", "Specialist"),
    ]

    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="agent_conversations",
    )
    agent_type = models.CharField(max_length=20, choices=AGENT_TYPES)
    message_text = models.TextField()
    agent_response = models.TextField()
    confidence_score = models.FloatField(null=True, blank=True)
    escalation_triggered = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agents_conversation"
        ordering = ["-created_at"]
