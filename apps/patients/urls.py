"""URL patterns for patients app."""

from django.urls import path

from . import views

app_name = "patients"

urlpatterns = [
    path("dashboard/", views.patient_dashboard_view, name="dashboard"),
    path("chat/send/", views.patient_chat_send_view, name="chat_send"),
    path("dev/", views.patient_dev_actions_view, name="dev_actions"),
]
