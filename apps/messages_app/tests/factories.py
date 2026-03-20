"""Factory Boy factories for messages_app."""

import factory

from apps.agents.tests.factories import PatientFactory
from apps.messages_app.models import Message


class MessageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Message

    patient = factory.SubFactory(PatientFactory)
    channel = "chat"
    direction = "inbound"
    content = factory.Faker("sentence")
    external_id = ""
