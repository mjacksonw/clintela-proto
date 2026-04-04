"""Clinical Pathways app - Recovery protocols."""

from django.db import models


class ClinicalPathway(models.Model):
    """Post-surgical recovery pathway template."""

    name = models.CharField(max_length=100)
    surgery_type = models.CharField(max_length=100)
    description = models.TextField()
    duration_days = models.IntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pathways_pathway"

    def __str__(self):
        return self.name


class PatientPathway(models.Model):
    """Assigned pathway for a specific patient."""

    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="pathways",
    )
    pathway = models.ForeignKey(
        ClinicalPathway,
        on_delete=models.CASCADE,
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("active", "Active"),
            ("completed", "Completed"),
            ("discontinued", "Discontinued"),
        ],
        default="active",
    )

    class Meta:
        db_table = "pathways_patient_pathway"
        unique_together = ["patient", "pathway"]

    def __str__(self):
        return f"{self.patient} - {self.pathway}"


class PathwayMilestone(models.Model):
    """Milestones within a clinical pathway for proactive check-ins."""

    PHASE_CHOICES = [
        ("early", "Early Recovery"),
        ("middle", "Middle Recovery"),
        ("late", "Late Recovery"),
    ]

    pathway = models.ForeignKey(
        ClinicalPathway,
        on_delete=models.CASCADE,
        related_name="milestones",
    )

    day = models.IntegerField(help_text="Day post-surgery when this milestone occurs")
    phase = models.CharField(max_length=20, choices=PHASE_CHOICES)

    # Expected symptoms and activities
    expected_symptoms = models.JSONField(default=list, blank=True)
    activities = models.JSONField(default=list, blank=True)
    red_flags = models.JSONField(default=list, blank=True)

    # Check-in questions
    check_in_questions = models.JSONField(default=list, blank=True)

    # Display
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pathways_milestone"
        ordering = ["day"]
        unique_together = ["pathway", "day"]

    def __str__(self):
        return f"{self.pathway} - Day {self.day}: {self.title}"


# PatientMilestoneCheckin has been removed.
# Replaced by apps.checkins.models.CheckinSession.
# Migration deletes the pathways_patient_milestone_checkin table.
