"""URL configuration for messages_app (SMS webhooks)."""

from django.urls import path

from . import views

app_name = "messages"

urlpatterns = [
    path("sms/webhook/", views.twilio_inbound_webhook, name="sms_inbound"),
    path("sms/status/", views.twilio_status_webhook, name="sms_status"),
]
