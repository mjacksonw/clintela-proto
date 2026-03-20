"""SMS webhook views for Twilio integration."""

import logging

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.messages_app.services import SMSService

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def twilio_inbound_webhook(request):
    """Receive inbound SMS from Twilio.

    Always returns 200 with empty TwiML to prevent Twilio retries
    causing duplicate processing.
    """
    # Validate Twilio signature in production
    if not settings.DEBUG and not _validate_twilio_signature(request):
        logger.warning("Invalid Twilio signature on inbound webhook")
        return HttpResponse(status=403)

    from_number = request.POST.get("From", "")
    body = request.POST.get("Body", "")
    twilio_sid = request.POST.get("MessageSid", "")

    if not from_number or not body:
        return _empty_twiml()

    try:
        sms_service = SMSService()
        sms_service.handle_inbound_sms(from_number, body, twilio_sid)
    except Exception:
        logger.exception("Error processing inbound SMS", extra={"from": from_number})

    return _empty_twiml()


@csrf_exempt
@require_POST
def twilio_status_webhook(request):
    """Receive delivery status callbacks from Twilio.

    Updates NotificationDelivery status based on Twilio status.
    """
    if not settings.DEBUG and not _validate_twilio_signature(request):
        return HttpResponse(status=403)

    message_sid = request.POST.get("MessageSid", "")
    message_status = request.POST.get("MessageStatus", "")

    if not message_sid or not message_status:
        return HttpResponse(status=200)

    # Map Twilio status to our delivery status
    status_map = {
        "queued": "pending",
        "sent": "sent",
        "delivered": "delivered",
        "undelivered": "failed",
        "failed": "failed",
    }

    our_status = status_map.get(message_status)
    if not our_status:
        return HttpResponse(status=200)

    try:
        from django.utils import timezone

        from apps.notifications.models import NotificationDelivery

        deliveries = NotificationDelivery.objects.filter(external_id=message_sid)
        for delivery in deliveries:
            delivery.status = our_status
            if our_status == "delivered":
                delivery.delivered_at = timezone.now()
            if our_status == "failed":
                delivery.error_message = f"Twilio status: {message_status}"
            delivery.save()

        logger.info(
            "Twilio status update",
            extra={"sid": message_sid, "status": message_status},
        )
    except Exception:
        logger.exception("Error processing Twilio status callback")

    return HttpResponse(status=200)


def _validate_twilio_signature(request):
    """Validate the Twilio request signature."""
    try:
        from twilio.request_validator import RequestValidator

        auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", "")
        validator = RequestValidator(auth_token)

        url = request.build_absolute_uri()
        signature = request.META.get("HTTP_X_TWILIO_SIGNATURE", "")
        params = request.POST.dict()

        return validator.validate(url, params, signature)
    except ImportError:
        logger.warning("twilio package not installed, skipping signature validation")
        return True


def _empty_twiml():
    """Return an empty TwiML response."""
    return HttpResponse(
        '<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
        content_type="text/xml",
    )
