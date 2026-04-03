"""Caregiver push notification relay.

When a patient receives certain notifications (escalations, health alerts,
check-in reminders), their active caregivers also receive a push notification.

Caregiver push is a relay — it creates a separate Notification + push deliveries
for each caregiver, with a generic (PHI-safe) message appropriate for
a family member rather than the patient directly.

The relay checks:
  1. CaregiverRelationship.is_active (caregiver still has access)
  2. DeviceToken exists for the caregiver's user (they have the app installed)
  3. The notification type is in the relayable set (not all notifications go to caregivers)
"""

import logging

from apps.notifications.models import DeviceToken, Notification, NotificationDelivery

logger = logging.getLogger(__name__)

# Notification types that trigger caregiver relay
RELAYABLE_TYPES = {"escalation", "alert"}

# Caregiver-facing message templates (warm, not clinical, PHI-safe)
CAREGIVER_MESSAGES = {
    "escalation": (
        "Update from {patient_name}'s care team",
        "Their care team has been in touch. Everything is being taken care of.",
    ),
    "alert": (
        "Health update for {patient_name}",
        "A health reading needs attention. Their care team has been notified.",
    ),
}

DEFAULT_MESSAGE = (
    "Update about {patient_name}",
    "There's a new update about their care. Open the app for details.",
)


def relay_to_caregivers(notification: Notification) -> int:
    """Relay a patient notification to their active caregivers.

    Creates a separate Notification + push deliveries for each caregiver
    who has the app installed (has active DeviceTokens).

    Args:
        notification: The patient's Notification instance.

    Returns:
        Number of caregiver notifications created.
    """
    if notification.notification_type not in RELAYABLE_TYPES:
        return 0

    patient = notification.patient
    if not patient:
        return 0

    # Get active caregiver relationships
    from apps.caregivers.models import CaregiverRelationship

    relationships = CaregiverRelationship.objects.filter(
        patient=patient,
        is_active=True,
    ).select_related("caregiver__user")

    if not relationships.exists():
        return 0

    # Get patient name for the message (first name only, PHI-appropriate)
    patient_name = "your loved one"
    if hasattr(patient, "user") and patient.user.first_name:
        patient_name = patient.user.first_name

    title_template, message_template = CAREGIVER_MESSAGES.get(notification.notification_type, DEFAULT_MESSAGE)
    title = title_template.format(patient_name=patient_name)
    message = message_template.format(patient_name=patient_name)

    created = 0
    for rel in relationships:
        caregiver_user = rel.caregiver.user

        # Check if caregiver has active device tokens
        caregiver_tokens = DeviceToken.objects.filter(
            user=caregiver_user,
            is_active=True,
        )
        if not caregiver_tokens.exists():
            continue

        # Create caregiver notification
        caregiver_notification = Notification.objects.create(
            patient=patient,  # Still linked to patient for context
            notification_type=notification.notification_type,
            severity=notification.severity,
            title=title,
            message=message,
        )

        # Fan-out push deliveries to caregiver's devices
        for device in caregiver_tokens:
            NotificationDelivery.objects.create(
                notification=caregiver_notification,
                channel="push",
                device=device,
            )

        created += 1
        logger.info(
            "Caregiver push relay created",
            extra={
                "patient_id": patient.id,
                "caregiver_user_id": caregiver_user.id,
                "notification_type": notification.notification_type,
                "devices": caregiver_tokens.count(),
            },
        )

    return created
