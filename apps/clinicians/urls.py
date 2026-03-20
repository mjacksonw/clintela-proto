"""URL configuration for clinicians app."""

from django.urls import path

from apps.clinicians import views

app_name = "clinicians"

urlpatterns = [
    # Auth
    path("login/", views.clinician_login_view, name="login"),
    path("logout/", views.clinician_logout_view, name="logout"),
    # Dashboard
    path("dashboard/", views.dashboard_view, name="dashboard"),
    # Patient list (HTMX fragment)
    path("patients/", views.patient_list_fragment, name="patient_list"),
    # Patient detail tabs (HTMX fragments)
    path(
        "patients/<int:patient_id>/detail/",
        views.patient_detail_fragment,
        name="patient_detail",
    ),
    path(
        "patients/<int:patient_id>/care-plan/",
        views.patient_care_plan_fragment,
        name="patient_care_plan",
    ),
    path(
        "patients/<int:patient_id>/research/",
        views.patient_research_fragment,
        name="patient_research",
    ),
    path(
        "patients/<int:patient_id>/research/send/",
        views.research_chat_send_view,
        name="research_chat_send",
    ),
    path(
        "patients/<int:patient_id>/tools/",
        views.patient_tools_fragment,
        name="patient_tools",
    ),
    # Patient chat (HTMX fragment)
    path(
        "patients/<int:patient_id>/chat/",
        views.patient_chat_fragment,
        name="patient_chat",
    ),
    path(
        "patients/<int:patient_id>/inject-message/",
        views.inject_chat_message_view,
        name="inject_message",
    ),
    path(
        "patients/<int:patient_id>/take-control/release/",
        views.release_take_control_view,
        name="release_take_control",
    ),
    # Notes
    path(
        "patients/<int:patient_id>/notes/add/",
        views.add_note_view,
        name="add_note",
    ),
    # Escalations
    path(
        "escalations/<uuid:escalation_id>/acknowledge/",
        views.acknowledge_escalation_view,
        name="acknowledge_escalation",
    ),
    path(
        "escalations/<uuid:escalation_id>/resolve/",
        views.resolve_escalation_view,
        name="resolve_escalation",
    ),
    path(
        "escalations/bulk-acknowledge/",
        views.bulk_acknowledge_escalations_view,
        name="bulk_acknowledge",
    ),
    # Lifecycle
    path(
        "patients/<int:patient_id>/lifecycle/",
        views.lifecycle_transition_view,
        name="lifecycle_transition",
    ),
    # Scheduling
    path("schedule/", views.schedule_view, name="schedule"),
    path(
        "schedule/availability/",
        views.save_availability_view,
        name="save_availability",
    ),
    path(
        "schedule/appointments/create/",
        views.create_appointment_view,
        name="create_appointment",
    ),
    path(
        "schedule/appointments/<uuid:appointment_id>/cancel/",
        views.cancel_appointment_view,
        name="cancel_appointment",
    ),
    # Handoff export
    path(
        "patients/<int:patient_id>/export-handoff/",
        views.export_handoff_view,
        name="export_handoff",
    ),
    # Timeline expand (HTMX fragment)
    path(
        "patients/<int:patient_id>/timeline/<str:date>/",
        views.timeline_day_fragment,
        name="timeline_day",
    ),
]
