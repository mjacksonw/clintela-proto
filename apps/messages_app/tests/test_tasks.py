"""Tests for messages_app Celery tasks."""

from unittest.mock import patch


class TestCleanupExpiredVoiceFilesTask:
    """Tests for cleanup_expired_voice_files Celery task."""

    def test_task_is_importable(self):
        from apps.messages_app.tasks import cleanup_expired_voice_files

        assert callable(cleanup_expired_voice_files)

    @patch("django.core.management.call_command")
    def test_task_calls_cleanup_command(self, mock_call_command):
        from apps.messages_app.tasks import cleanup_expired_voice_files

        cleanup_expired_voice_files()

        mock_call_command.assert_called_once_with("cleanup_voice_memos")

    @patch("django.core.management.call_command")
    def test_task_delay_calls_cleanup_command(self, mock_call_command, settings):
        """Test that task.delay() also runs eagerly in test mode."""
        settings.CELERY_TASK_ALWAYS_EAGER = True
        settings.CELERY_TASK_EAGER_PROPAGATES = True

        from apps.messages_app.tasks import cleanup_expired_voice_files

        cleanup_expired_voice_files.delay()

        mock_call_command.assert_called_once_with("cleanup_voice_memos")

    @patch("django.core.management.call_command")
    def test_task_apply_runs_synchronously(self, mock_call_command):
        """Test task.apply() runs synchronously."""
        from apps.messages_app.tasks import cleanup_expired_voice_files

        result = cleanup_expired_voice_files.apply()

        mock_call_command.assert_called_once_with("cleanup_voice_memos")
        assert result.successful()
