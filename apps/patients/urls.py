"""URL patterns for patients app."""

from django.urls import path

from . import views

app_name = "patients"

urlpatterns = [
    path("dashboard/", views.patient_dashboard_view, name="dashboard"),
    path("chat/send/", views.patient_chat_send_view, name="chat_send"),
    path("voice/send/", views.patient_voice_send_view, name="voice_send"),
    path("voice/file/<uuid:file_id>/", views.patient_voice_file_view, name="voice_file"),
    path("consent/", views.patient_consent_view, name="consent"),
    path("consent/toggle/", views.patient_consent_toggle_view, name="consent_toggle"),
    path("caregivers/", views.patient_caregivers_view, name="caregivers"),
    path("caregivers/invite/", views.patient_caregiver_invite_view, name="caregiver_invite"),
    path("caregivers/revoke/", views.patient_caregiver_revoke_view, name="caregiver_revoke"),
    path("dev/", views.patient_dev_actions_view, name="dev_actions"),
]
