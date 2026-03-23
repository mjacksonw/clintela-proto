from django.contrib import admin

from apps.clinical.models import ClinicalAlert, ClinicalObservation, PatientClinicalSnapshot


@admin.register(ClinicalObservation)
class ClinicalObservationAdmin(admin.ModelAdmin):
    list_display = ("concept_name", "patient", "value_numeric", "unit", "source", "observed_at")
    list_filter = ("concept_id", "source", "quality", "is_anomalous")
    search_fields = ("patient__user__first_name", "patient__user__last_name", "concept_name")
    readonly_fields = ("id", "created_at")
    date_hierarchy = "observed_at"


@admin.register(PatientClinicalSnapshot)
class PatientClinicalSnapshotAdmin(admin.ModelAdmin):
    list_display = ("patient", "trajectory", "risk_score", "active_alerts_count", "data_completeness", "computed_at")
    list_filter = ("trajectory",)
    readonly_fields = ("computed_at",)


@admin.register(ClinicalAlert)
class ClinicalAlertAdmin(admin.ModelAdmin):
    list_display = ("title", "patient", "severity", "alert_type", "rule_name", "status", "created_at")
    list_filter = ("severity", "alert_type", "status")
    search_fields = ("title", "patient__user__first_name", "patient__user__last_name", "rule_name")
    readonly_fields = ("id", "created_at")
    date_hierarchy = "created_at"
