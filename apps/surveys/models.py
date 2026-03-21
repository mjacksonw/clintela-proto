import uuid

from django.db import models
from django.db.models import Q, UniqueConstraint


class SurveyInstrument(models.Model):
    """Survey template (e.g., PHQ-2, KCCQ-12)."""

    CATEGORY_CHOICES = [
        ("cardiac", "Cardiac"),
        ("mental_health", "Mental Health"),
        ("general", "General"),
        ("symptom_check", "Symptom Check"),
        ("custom", "Custom"),
    ]

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    version = models.CharField(max_length=20, default="1.0")
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    is_active = models.BooleanField(default=True)
    is_standard = models.BooleanField(default=True)
    hospital = models.ForeignKey(
        "patients.Hospital",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="custom_instruments",
    )
    estimated_minutes = models.IntegerField(default=5)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "surveys_instrument"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} (v{self.version})"


class SurveyQuestion(models.Model):
    """Individual question within an instrument."""

    TYPE_CHOICES = [
        ("likert", "Likert Scale"),
        ("numeric", "Numeric"),
        ("yes_no", "Yes/No"),
        ("multiple_choice", "Multiple Choice"),
        ("free_text", "Free Text"),
    ]

    instrument = models.ForeignKey(
        SurveyInstrument,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    code = models.CharField(max_length=50)
    domain = models.CharField(max_length=50, blank=True, default="")
    order = models.IntegerField()
    text = models.TextField()
    question_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    options = models.JSONField(default=list, blank=True)
    min_value = models.IntegerField(null=True, blank=True)
    max_value = models.IntegerField(null=True, blank=True)
    min_label = models.CharField(max_length=100, blank=True, default="")
    max_label = models.CharField(max_length=100, blank=True, default="")
    required = models.BooleanField(default=True)
    help_text = models.TextField(blank=True, default="")

    class Meta:
        db_table = "surveys_question"
        ordering = ["order"]
        constraints = [
            UniqueConstraint(
                fields=["instrument", "code"],
                name="uq_surveys_question_instrument_code",
            ),
        ]

    def __str__(self):
        return f"{self.instrument.code}.{self.code}: {self.text[:50]}"


class SurveyAssignment(models.Model):
    """Links instrument to patient with a schedule."""

    SCHEDULE_CHOICES = [
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("biweekly", "Biweekly"),
        ("monthly", "Monthly"),
        ("one_time", "One Time"),
        ("on_demand", "On Demand"),
    ]

    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="survey_assignments",
    )
    instrument = models.ForeignKey(
        SurveyInstrument,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    pathway = models.ForeignKey(
        "pathways.PatientPathway",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="survey_assignments",
    )
    assigned_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="survey_assignments_made",
    )
    schedule_type = models.CharField(max_length=20, choices=SCHEDULE_CHOICES)
    is_active = models.BooleanField(default=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    escalation_config = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "surveys_assignment"
        ordering = ["-created_at"]
        constraints = [
            UniqueConstraint(
                fields=["patient", "instrument"],
                condition=Q(is_active=True),
                name="uq_surveys_assignment_active",
            ),
        ]

    def __str__(self):
        return f"{self.patient} — {self.instrument.code} ({self.schedule_type})"


class SurveyInstance(models.Model):
    """A single survey occurrence for a patient to complete."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("available", "Available"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("expired", "Expired"),
        ("missed", "Missed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment = models.ForeignKey(
        SurveyAssignment,
        on_delete=models.CASCADE,
        related_name="instances",
    )
    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="survey_instances",
    )
    instrument = models.ForeignKey(
        SurveyInstrument,
        on_delete=models.CASCADE,
        related_name="instances",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    due_date = models.DateField()
    window_start = models.DateTimeField()
    window_end = models.DateTimeField()
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    total_score = models.FloatField(null=True, blank=True)
    domain_scores = models.JSONField(default=dict, blank=True)
    raw_scores = models.JSONField(default=dict, blank=True)
    escalation_triggered = models.BooleanField(default=False)
    escalation = models.ForeignKey(
        "agents.Escalation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="survey_instances",
    )
    scoring_error = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "surveys_instance"
        ordering = ["-created_at"]
        constraints = [
            UniqueConstraint(
                fields=["patient", "instrument"],
                condition=Q(status__in=["available", "in_progress", "pending"]),
                name="uq_surveys_instance_one_active",
            ),
        ]
        indexes = [
            models.Index(
                fields=["patient", "instrument", "status", "-completed_at"],
                name="idx_surveys_instance_history",
            ),
        ]

    def __str__(self):
        return f"{self.instrument.code} for {self.patient} ({self.status})"


class SurveyAnswer(models.Model):
    """Individual answer within a completed instance."""

    instance = models.ForeignKey(
        SurveyInstance,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    question = models.ForeignKey(
        SurveyQuestion,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    value = models.JSONField()
    raw_value = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "surveys_answer"
        constraints = [
            UniqueConstraint(
                fields=["instance", "question"],
                name="uq_surveys_answer_instance_question",
            ),
        ]

    def __str__(self):
        return f"{self.instance.instrument.code}.{self.question.code} = {self.value}"
