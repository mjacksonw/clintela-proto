from django.urls import path

from apps.checkins import views

app_name = "checkins"

urlpatterns = [
    # REST API
    path(
        "api/widgets/respond/<uuid:session_id>/<str:question_code>/",
        views.widget_respond_api,
        name="widget_respond_api",
    ),
    # HTMX wrapper
    path(
        "checkins/respond/<uuid:session_id>/<str:question_code>/",
        views.widget_respond_htmx,
        name="widget_respond_htmx",
    ),
]
