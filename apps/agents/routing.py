"""WebSocket routing for agents app."""

from django.urls import re_path

from apps.agents.consumers import AgentChatConsumer, ClinicianDashboardConsumer

websocket_urlpatterns = [
    re_path(r"ws/chat/(?P<patient_id>[0-9a-f-]+)/$", AgentChatConsumer.as_asgi()),
    re_path(r"ws/dashboard/(?P<hospital_id>\d+)/$", ClinicianDashboardConsumer.as_asgi()),
]
