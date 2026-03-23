from django.urls import path

from apps.clinical import views

app_name = "clinical"

urlpatterns = [
    # Clinician HTMX fragments (require clinician auth)
    path(
        "clinician/patient/<int:patient_id>/vitals/",
        views.vitals_tab_fragment,
        name="vitals_tab",
    ),
    # Patient HTMX fragments (require patient auth)
    path(
        "patient/health-card/",
        views.health_card_fragment,
        name="health_card",
    ),
]
