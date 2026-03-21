"""URL configuration for administrators app."""

from django.urls import path

from apps.administrators import views

app_name = "administrators"

urlpatterns = [
    # Auth
    path("login/", views.admin_login_view, name="login"),
    path("logout/", views.admin_logout_view, name="logout"),
    # Dashboard
    path("", views.dashboard_view, name="dashboard"),
    # HTMX KPI fragments
    path("hero-readmission/", views.hero_readmission_fragment, name="hero_readmission"),
    path("census/", views.census_fragment, name="census"),
    path("alerts/", views.alerts_fragment, name="alerts"),
    path("discharge-to-community/", views.discharge_to_community_fragment, name="discharge_to_community"),
    path("functional-improvement/", views.functional_improvement_fragment, name="functional_improvement"),
    path("followup-completion/", views.followup_completion_fragment, name="followup_completion"),
    path("engagement/", views.engagement_fragment, name="engagement"),
    path("message-volume/", views.message_volume_fragment, name="message_volume"),
    path("checkin-completion/", views.checkin_completion_fragment, name="checkin_completion"),
    path("escalation-response/", views.escalation_response_fragment, name="escalation_response"),
    path("pathway-performance/", views.pathway_performance_fragment, name="pathway_performance"),
    # CSV Export
    path("export/csv/", views.export_csv_view, name="export_csv"),
    # Pathway administration
    path("pathways/", views.pathway_list_view, name="pathway_list"),
    path("pathways/<int:pathway_id>/", views.pathway_detail_view, name="pathway_detail"),
    path("pathways/<int:pathway_id>/toggle/", views.pathway_toggle_active_view, name="pathway_toggle"),
    path("pathways/<int:pathway_id>/edit/", views.pathway_edit_view, name="pathway_edit"),
    path("milestones/<int:milestone_id>/edit/", views.milestone_edit_view, name="milestone_edit"),
]
