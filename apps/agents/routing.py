"""WebSocket routing for agents and notifications."""

from django.urls import re_path

from apps.agents.consumers import (
    AgentChatConsumer,
    ClinicianDashboardConsumer,
    SupportGroupConsumer,
)
from apps.notifications.consumers import (
    ClinicianNotificationConsumer,
    NotificationConsumer,
)

websocket_urlpatterns = [
    re_path(r"ws/chat/(?P<patient_id>[0-9a-f-]+)/$", AgentChatConsumer.as_asgi()),
    re_path(r"ws/support-group/(?P<patient_id>[0-9a-f-]+)/$", SupportGroupConsumer.as_asgi()),
    re_path(r"ws/dashboard/(?P<hospital_id>\d+)/$", ClinicianDashboardConsumer.as_asgi()),
    re_path(
        r"ws/notifications/patient/(?P<patient_id>[0-9a-f-]+)/$",
        NotificationConsumer.as_asgi(),
    ),
    re_path(
        r"ws/notifications/clinician/(?P<clinician_id>\d+)/$",
        ClinicianNotificationConsumer.as_asgi(),
    ),
]
