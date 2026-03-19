"""URL patterns for patients app."""

from django.urls import path

from . import views

app_name = "patients"

urlpatterns = [
    path("dashboard/", views.patient_dashboard_view, name="dashboard"),
]
