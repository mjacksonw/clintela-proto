"""Clinicians app - Healthcare provider management."""

import uuid

from django.db import models


class Clinician(models.Model):
    """Healthcare provider/clinician."""

    ROLE_CHOICES = [
        ("physician", "Physician"),
        ("nurse", "Nurse"),
        ("pa", "Physician Assistant"),
        ("np", "Nurse Practitioner"),
        ("coordinator", "Care Coordinator"),
    ]

    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="clinician_profile",
    )
    hospitals = models.ManyToManyField(
        "patients.Hospital",
        related_name="clinicians",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    specialty = models.CharField(max_length=100, blank=True)
    license_number = models.CharField(max_length=50, blank=True)
    npi_number = models.CharField(max_length=50, blank=True)
    zoom_link = models.URLField(blank=True, help_text="Personal Zoom meeting room URL")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "clinicians_clinician"

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.get_role_display()})"


class ClinicianNote(models.Model):
    """Notes written by clinicians about patients."""

    NOTE_TYPE_CHOICES = [
        ("quick_note", "Quick Note"),
        ("clinical_observation", "Clinical Observation"),
        ("follow_up", "Follow Up"),
        ("care_plan_note", "Care Plan Note"),
    ]

    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="clinician_notes",
    )
    clinician = models.ForeignKey(
        Clinician,
        on_delete=models.CASCADE,
        related_name="notes",
    )
    content = models.TextField()
    note_type = models.CharField(
        max_length=25,
        choices=NOTE_TYPE_CHOICES,
        default="quick_note",
    )
    is_pinned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "clinicians_note"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["patient", "created_at"],
                name="idx_clin_note_patient_created",
            ),
        ]

    def __str__(self):
        return f"{self.clinician} - {self.note_type} for {self.patient}"


class ClinicianAvailability(models.Model):
    """Clinician availability windows for scheduling."""

    clinician = models.ForeignKey(
        Clinician,
        on_delete=models.CASCADE,
        related_name="availability_windows",
    )
    day_of_week = models.IntegerField(
        choices=[
            (0, "Monday"),
            (1, "Tuesday"),
            (2, "Wednesday"),
            (3, "Thursday"),
            (4, "Friday"),
            (5, "Saturday"),
            (6, "Sunday"),
        ],
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_recurring = models.BooleanField(default=True)
    effective_date = models.DateField(
        null=True,
        blank=True,
        help_text="For one-off availability overrides",
    )

    class Meta:
        db_table = "clinicians_availability"
        constraints = [
            models.UniqueConstraint(
                fields=["clinician", "day_of_week", "start_time"],
                condition=models.Q(is_recurring=True),
                name="uq_clinician_recurring_avail",
            ),
        ]

    def __str__(self):
        day = self.get_day_of_week_display()
        return f"{self.clinician} - {day} {self.start_time}-{self.end_time}"


class Appointment(models.Model):
    """Scheduled appointments between clinicians and patients."""

    TYPE_CHOICES = [
        ("follow_up", "Follow Up"),
        ("virtual_visit", "Virtual Visit"),
        ("check_in", "Check In"),
        ("consultation", "Consultation"),
    ]

    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("confirmed", "Confirmed"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
        ("no_show", "No Show"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="appointments",
    )
    clinician = models.ForeignKey(
        Clinician,
        on_delete=models.CASCADE,
        related_name="appointments",
    )
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_appointments",
    )
    appointment_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="scheduled",
    )
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    notes = models.TextField(blank=True)
    virtual_visit_url = models.CharField(max_length=500, blank=True)
    reminder_24h_sent = models.BooleanField(default=False)
    reminder_1h_sent = models.BooleanField(default=False)
    ical_sent = models.BooleanField(default=False)

    class Meta:
        db_table = "clinicians_appointment"
        ordering = ["scheduled_start"]
        indexes = [
            models.Index(
                fields=["clinician", "scheduled_start"],
                name="idx_appt_clinician_start",
            ),
            models.Index(
                fields=["patient", "scheduled_start"],
                name="idx_appt_patient_start",
            ),
        ]

    def __str__(self):
        return f"{self.appointment_type} - {self.patient} with {self.clinician} at {self.scheduled_start}"


class AppointmentRequest(models.Model):
    """Patient-facing booking request triggered by milestones, escalations, or clinicians."""

    TRIGGER_TYPES = [
        ("milestone", "Pathway Milestone"),
        ("escalation", "System Escalation"),
        ("clinician", "Clinician Requested"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("booked", "Booked"),
        ("expired", "Expired"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="appointment_requests",
    )
    clinician = models.ForeignKey(
        Clinician,
        on_delete=models.CASCADE,
        related_name="appointment_requests",
    )
    trigger_type = models.CharField(max_length=20, choices=TRIGGER_TYPES)
    reason = models.TextField()
    appointment_type = models.CharField(
        max_length=20,
        choices=Appointment.TYPE_CHOICES,
        default="follow_up",
    )
    milestone = models.ForeignKey(
        "pathways.PathwayMilestone",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    escalation = models.ForeignKey(
        "agents.Escalation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    requested_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="request",
    )
    earliest_notify_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "clinicians_appointment_request"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["patient", "status"],
                name="idx_appt_req_patient_status",
            ),
            models.Index(
                fields=["earliest_notify_at", "status"],
                name="idx_appt_req_notify",
            ),
        ]

    def __str__(self):
        return f"{self.get_trigger_type_display()} request for {self.patient} - {self.status}"
