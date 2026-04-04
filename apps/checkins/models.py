import uuid

from django.db import models


class CheckinQuestion(models.Model):
    """Curated question bank for daily check-ins."""

    CATEGORY_CHOICES = [
        ("pain", "Pain"),
        ("sleep", "Sleep"),
        ("bowel", "Bowel Function"),
        ("energy", "Energy"),
        ("medication", "Medication"),
        ("mood", "Mood"),
        ("mobility", "Mobility"),
        ("wound", "Wound Care"),
    ]

    RESPONSE_TYPE_CHOICES = [
        ("yes_no", "Yes / No"),
        ("scale_1_5", "Scale 1-5"),
        ("scale_1_10", "Scale 1-10"),
        ("multiple_choice", "Multiple Choice"),
        ("free_text", "Free Text"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=80, unique=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    text = models.TextField(help_text="Question text shown to the patient")
    response_type = models.CharField(max_length=20, choices=RESPONSE_TYPE_CHOICES)
    options = models.JSONField(
        default=list,
        blank=True,
        help_text="For multiple_choice: list of {value, label} dicts",
    )
    follow_up_rules = models.JSONField(
        default=list,
        blank=True,
        help_text="Rules that trigger follow-up. Each: {operator, value, message}",
    )
    priority = models.IntegerField(
        default=5,
        help_text="1=highest priority for selection (asked first when tied)",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "checkins_question"
        ordering = ["category", "priority"]

    def __str__(self):
        return f"[{self.category}] {self.code}"


class PathwayCheckinConfig(models.Model):
    """Links question categories to pathways with frequency floors."""

    PHASE_CHOICES = [
        ("early", "Early (days 1-7)"),
        ("middle", "Middle (days 8-30)"),
        ("late", "Late (days 31+)"),
        ("all", "All phases"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pathway = models.ForeignKey(
        "pathways.ClinicalPathway",
        on_delete=models.CASCADE,
        related_name="checkin_configs",
    )
    category = models.CharField(max_length=20, choices=CheckinQuestion.CATEGORY_CHOICES)
    min_frequency = models.JSONField(
        default=list,
        blank=True,
        help_text='Frequency floors by phase. E.g. [{"phase":"early","every_n_days":1}]',
    )
    relevance_phase = models.CharField(
        max_length=10,
        choices=PHASE_CHOICES,
        default="all",
    )
    max_gap_days = models.IntegerField(
        default=7,
        help_text="Max days between asks for this category before floor forces it",
    )

    class Meta:
        db_table = "checkins_pathway_config"
        unique_together = [("pathway", "category")]

    def __str__(self):
        return f"{self.pathway.name} / {self.category}"


class CheckinSession(models.Model):
    """One check-in session per patient per day."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("missed", "Missed"),
        ("skipped", "Skipped"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="checkin_sessions",
    )
    date = models.DateField(help_text="The calendar date this check-in covers")
    pathway_day = models.IntegerField(
        null=True,
        blank=True,
        help_text="Days post-op when this session was created",
    )
    phase = models.CharField(max_length=10, blank=True, default="")
    questions_selected = models.JSONField(
        default=list,
        blank=True,
        help_text="List of question codes selected for this session",
    )
    selection_rationale = models.TextField(
        blank=True,
        default="",
        help_text="LLM reasoning for question selection",
    )
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="pending")
    conversation = models.ForeignKey(
        "agents.AgentConversation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checkin_sessions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "checkins_session"
        unique_together = [("patient", "date")]
        ordering = ["-date"]
        indexes = [
            models.Index(
                fields=["patient", "-date"],
                name="idx_checkin_sess_pt_date",
            ),
        ]

    def __str__(self):
        return f"{self.patient} / {self.date} ({self.status})"

    @property
    def total_questions(self):
        return len(self.questions_selected)

    @property
    def answered_count(self):
        return self.responses.count()

    @property
    def is_complete(self):
        return self.total_questions > 0 and self.answered_count >= self.total_questions


class CheckinResponse(models.Model):
    """One response per question per session."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        CheckinSession,
        on_delete=models.CASCADE,
        related_name="responses",
    )
    question = models.ForeignKey(
        CheckinQuestion,
        on_delete=models.CASCADE,
        related_name="responses",
    )
    value = models.JSONField(
        help_text="The response value (string, int, or structured data)",
    )
    raw_text = models.TextField(
        blank=True,
        default="",
        help_text="Raw text input for free_text responses",
    )
    agent_message = models.ForeignKey(
        "agents.AgentMessage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checkin_responses",
        help_text="The widget message this response was submitted through",
    )
    follow_up_triggered = models.BooleanField(default=False)
    follow_up_response = models.TextField(
        blank=True,
        default="",
        help_text="Agent follow-up message content, if triggered",
    )
    escalation_triggered = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "checkins_response"
        unique_together = [("session", "question")]
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.session.date} / {self.question.code}: {self.value}"
