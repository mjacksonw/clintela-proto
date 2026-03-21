from django.urls import path

from apps.surveys import views

app_name = "surveys"

urlpatterns = [
    # Patient-facing
    path("available/", views.available_surveys, name="available"),
    path("<uuid:instance_id>/start/", views.start_survey, name="start"),
    path("<uuid:instance_id>/answer/", views.submit_answers, name="answer"),
    path("<uuid:instance_id>/complete/", views.complete_survey, name="complete"),
    path("history/", views.score_history, name="history"),
    # Clinician-facing
    path(
        "clinician/<int:patient_id>/",
        views.clinician_surveys_tab,
        name="clinician_tab",
    ),
    path(
        "clinician/<int:patient_id>/assign/",
        views.assign_survey,
        name="assign",
    ),
    path(
        "clinician/assignment/<int:assignment_id>/deactivate/",
        views.deactivate_assignment,
        name="deactivate",
    ),
    path(
        "clinician/instance/<uuid:instance_id>/results/",
        views.survey_results,
        name="results",
    ),
]
