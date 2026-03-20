"""Celery tasks for messages_app."""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def cleanup_expired_voice_files():
    """Periodic task: delete voice memo files past retention period.

    Runs hourly via Celery Beat. Calls the cleanup_voice_memos
    management command.
    """
    from django.core.management import call_command

    call_command("cleanup_voice_memos")
