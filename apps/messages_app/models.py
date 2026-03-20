"""Messages app - SMS, web chat, and voice communication."""

from django.db import models


class Message(models.Model):
    """Communication message (SMS, chat, voice)."""

    CHANNEL_CHOICES = [
        ("sms", "SMS"),
        ("chat", "Web Chat"),
        ("voice", "Voice"),
        ("email", "Email"),
    ]

    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="messages",
    )
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES)
    direction = models.CharField(
        max_length=10,
        choices=[("inbound", "Inbound"), ("outbound", "Outbound")],
    )
    content = models.TextField()
    external_id = models.CharField(  # Twilio message SID, etc.
        max_length=255,
        blank=True,
        db_index=True,
    )
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "messages_message"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["external_id"],
                condition=~models.Q(external_id=""),
                name="uniq_message_external_id",
            ),
        ]

    def __str__(self):
        return f"{self.channel} {self.direction} - {self.created_at}"
