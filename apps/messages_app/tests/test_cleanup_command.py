"""Tests for cleanup_voice_memos management command."""

import time
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command


@pytest.mark.django_db
class TestCleanupVoiceMemos:
    def setup_method(self):
        self.voice_dir = Path(settings.MEDIA_ROOT) / "voice_memos"
        self.voice_dir.mkdir(parents=True, exist_ok=True)

    def _create_file(self, subdir, name, age_hours=0):
        """Create a test file and optionally age it."""
        dir_path = self.voice_dir / subdir
        dir_path.mkdir(parents=True, exist_ok=True)
        file_path = dir_path / name
        file_path.write_bytes(b"\x00" * 10)

        if age_hours > 0:
            old_time = time.time() - (age_hours * 3600)
            import os

            os.utime(file_path, (old_time, old_time))

        return file_path

    def test_deletes_old_files(self):
        old_file = self._create_file("patient1", "old.webm", age_hours=25)
        assert old_file.exists()

        call_command("cleanup_voice_memos")
        assert not old_file.exists()

    def test_keeps_recent_files(self):
        new_file = self._create_file("patient1", "new.webm", age_hours=0)
        assert new_file.exists()

        call_command("cleanup_voice_memos")
        assert new_file.exists()

    def test_cleans_empty_directories(self):
        old_file = self._create_file("patient2", "expired.webm", age_hours=25)
        patient_dir = old_file.parent

        call_command("cleanup_voice_memos")
        assert not patient_dir.exists()

    def test_keeps_nonempty_directories(self):
        self._create_file("patient3", "old.webm", age_hours=25)
        new_file = self._create_file("patient3", "new.webm", age_hours=0)

        call_command("cleanup_voice_memos")
        assert new_file.exists()
        assert new_file.parent.exists()

    def test_no_voice_dir_is_noop(self):
        import shutil

        if self.voice_dir.exists():
            shutil.rmtree(self.voice_dir)

        # Should not raise
        call_command("cleanup_voice_memos")
