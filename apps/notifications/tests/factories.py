"""Factory Boy factories for notification models."""

import factory

from apps.agents.tests.factories import PatientFactory
from apps.notifications.models import (
    DeviceToken,
    Notification,
    NotificationDelivery,
    NotificationPreference,
)


class DeviceTokenFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DeviceToken

    patient = factory.SubFactory(PatientFactory)
    platform = "ios"
    token = factory.Sequence(lambda n: f"fcm_token_{n:06d}")
    device_name = "iPhone 15"
    is_active = True


class NotificationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Notification

    patient = factory.SubFactory(PatientFactory)
    clinician = None
    notification_type = "alert"
    severity = "info"
    title = factory.Sequence(lambda n: f"Test Notification {n}")
    message = factory.Faker("sentence")


class NotificationDeliveryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = NotificationDelivery

    notification = factory.SubFactory(NotificationFactory)
    channel = "in_app"
    status = "pending"


class NotificationPreferenceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = NotificationPreference

    patient = factory.SubFactory(PatientFactory)
    channel = "in_app"
    notification_type = "alert"
    enabled = True
    quiet_hours_start = None
    quiet_hours_end = None
