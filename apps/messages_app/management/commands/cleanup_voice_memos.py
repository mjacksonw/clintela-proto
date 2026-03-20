"""Management command to clean up expired voice memo files."""

import logging
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Delete voice memo files older than VOICE_MEMO_RETENTION_HOURS"

    def handle(self, *args, **options):
        voice_dir = Path(settings.MEDIA_ROOT) / "voice_memos"
        if not voice_dir.exists():
            self.stdout.write("No voice_memos directory found")
            return

        retention_hours = getattr(settings, "VOICE_MEMO_RETENTION_HOURS", 24)
        cutoff = time.time() - (retention_hours * 3600)

        deleted = 0
        for audio_file in voice_dir.rglob("*"):
            if audio_file.is_file() and audio_file.stat().st_mtime < cutoff:
                audio_file.unlink()
                deleted += 1

        # Clean up empty patient directories
        for patient_dir in voice_dir.iterdir():
            if patient_dir.is_dir() and not any(patient_dir.iterdir()):
                patient_dir.rmdir()

        self.stdout.write(f"Deleted {deleted} expired voice file(s)")
        logger.info("Voice memo cleanup: deleted %d files", deleted)
