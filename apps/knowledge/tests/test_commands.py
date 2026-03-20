"""Tests for knowledge management commands."""

import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.agents.tests.factories import HospitalFactory
from apps.knowledge.models import KnowledgeSource

from .factories import KnowledgeSourceFactory

# ---------------------------------------------------------------------------
# Shared ingestion stats fixture
# ---------------------------------------------------------------------------

DEFAULT_STATS = {
    "sections_parsed": 3,
    "chunks_created": 5,
    "chunks_deduplicated": 0,
    "sanitization_events": 0,
    "errors": 0,
}


# ---------------------------------------------------------------------------
# ingest_document
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestIngestDocumentCommand:
    """Tests for the ingest_document management command."""

    def _make_temp_file(self, suffix=".md", content="# Test\nSome clinical content."):
        """Create a temporary file and return its path (caller must clean up)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as f:
            f.write(content)
            return f.name

    @patch("apps.knowledge.management.commands.ingest_document.IngestionPipeline")
    def test_basic_execution_creates_source_and_ingests(self, mock_pipeline):
        pipeline_instance = MagicMock()
        pipeline_instance.ingest_file.return_value = DEFAULT_STATS.copy()
        mock_pipeline.return_value = pipeline_instance

        tmp = self._make_temp_file()
        try:
            out = StringIO()
            call_command(
                "ingest_document",
                "--file",
                tmp,
                "--source",
                "ACC CABG 2024",
                "--type",
                "acc_guideline",
                stdout=out,
            )

            source = KnowledgeSource.objects.get(name="ACC CABG 2024")
            assert source.source_type == "acc_guideline"
            assert source.hospital is None

            mock_pipeline.assert_called_once_with(source)
            pipeline_instance.ingest_file.assert_called_once_with(tmp)

            output = out.getvalue()
            assert "Created" in output
            assert "Ingestion complete" in output
        finally:
            Path(tmp).unlink(missing_ok=True)

    @patch("apps.knowledge.management.commands.ingest_document.IngestionPipeline")
    def test_uses_existing_source_when_already_present(self, mock_pipeline):
        pipeline_instance = MagicMock()
        pipeline_instance.ingest_file.return_value = DEFAULT_STATS.copy()
        mock_pipeline.return_value = pipeline_instance

        existing = KnowledgeSourceFactory(
            name="Existing Protocol",
            source_type="hospital_protocol",
            hospital=None,
        )

        tmp = self._make_temp_file()
        try:
            out = StringIO()
            call_command(
                "ingest_document",
                "--file",
                tmp,
                "--source",
                "Existing Protocol",
                "--type",
                "hospital_protocol",
                stdout=out,
            )

            # No duplicate source created
            assert KnowledgeSource.objects.filter(name="Existing Protocol").count() == 1
            mock_pipeline.assert_called_once_with(existing)
            assert "Using existing" in out.getvalue()
        finally:
            Path(tmp).unlink(missing_ok=True)

    @patch("apps.knowledge.management.commands.ingest_document.IngestionPipeline")
    def test_hospital_scoped_document(self, mock_pipeline):
        pipeline_instance = MagicMock()
        pipeline_instance.ingest_file.return_value = DEFAULT_STATS.copy()
        mock_pipeline.return_value = pipeline_instance

        hospital = HospitalFactory()

        tmp = self._make_temp_file()
        try:
            call_command(
                "ingest_document",
                "--file",
                tmp,
                "--source",
                "St. Mary's Cardiac",
                "--type",
                "hospital_protocol",
                "--hospital",
                hospital.code,
            )

            source = KnowledgeSource.objects.get(name="St. Mary's Cardiac")
            assert source.hospital == hospital
        finally:
            Path(tmp).unlink(missing_ok=True)

    @patch("apps.knowledge.management.commands.ingest_document.IngestionPipeline")
    def test_invalid_hospital_raises_command_error(self, mock_pipeline):
        tmp = self._make_temp_file()
        try:
            with pytest.raises(CommandError, match="Hospital not found"):
                call_command(
                    "ingest_document",
                    "--file",
                    tmp,
                    "--source",
                    "Some Source",
                    "--type",
                    "hospital_protocol",
                    "--hospital",
                    "NONEXISTENT",
                )
        finally:
            Path(tmp).unlink(missing_ok=True)

    @patch("apps.knowledge.management.commands.ingest_document.IngestionPipeline")
    def test_version_and_url_stored_on_new_source(self, mock_pipeline):
        pipeline_instance = MagicMock()
        pipeline_instance.ingest_file.return_value = DEFAULT_STATS.copy()
        mock_pipeline.return_value = pipeline_instance

        tmp = self._make_temp_file()
        try:
            call_command(
                "ingest_document",
                "--file",
                tmp,
                "--source",
                "Versioned Source",
                "--type",
                "clinical_research",
                "--doc-version",
                "2025.1",
                "--url",
                "https://example.com/doc",
            )

            source = KnowledgeSource.objects.get(name="Versioned Source")
            assert source.version == "2025.1"
            assert source.url == "https://example.com/doc"
        finally:
            Path(tmp).unlink(missing_ok=True)

    @patch("apps.knowledge.management.commands.ingest_document.IngestionPipeline")
    def test_output_includes_all_stat_fields(self, mock_pipeline):
        stats = {
            "sections_parsed": 7,
            "chunks_created": 12,
            "chunks_deduplicated": 2,
            "sanitization_events": 1,
            "errors": 0,
        }
        pipeline_instance = MagicMock()
        pipeline_instance.ingest_file.return_value = stats
        mock_pipeline.return_value = pipeline_instance

        tmp = self._make_temp_file()
        try:
            out = StringIO()
            call_command(
                "ingest_document",
                "--file",
                tmp,
                "--source",
                "Stats Source",
                "--type",
                "acc_guideline",
                stdout=out,
            )

            output = out.getvalue()
            assert "7 sections parsed" in output
            assert "12 chunks created" in output
            assert "2 deduplicated" in output
            assert "1 sanitization events" in output
            assert "0 errors" in output
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_missing_required_file_argument_raises(self):
        with pytest.raises((SystemExit, CommandError)):
            call_command(
                "ingest_document",
                "--source",
                "Some Source",
                "--type",
                "acc_guideline",
            )

    def test_missing_required_source_argument_raises(self):
        with pytest.raises((SystemExit, CommandError)):
            call_command(
                "ingest_document",
                "--file",
                tempfile.gettempdir() + "/some.md",
                "--type",
                "acc_guideline",
            )

    def test_missing_required_type_argument_raises(self):
        with pytest.raises((SystemExit, CommandError)):
            call_command(
                "ingest_document",
                "--file",
                tempfile.gettempdir() + "/some.md",
                "--source",
                "Some Source",
            )

    def test_invalid_type_choice_raises(self):
        with pytest.raises((SystemExit, CommandError)):
            call_command(
                "ingest_document",
                "--file",
                tempfile.gettempdir() + "/some.md",
                "--source",
                "Some Source",
                "--type",
                "bad_type",
            )


# ---------------------------------------------------------------------------
# ingest_acc_guidelines
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestIngestAccGuidelinesCommand:
    """Tests for the ingest_acc_guidelines management command."""

    def test_missing_directory_prints_warning(self):
        out = StringIO()
        call_command(
            "ingest_acc_guidelines",
            "--dir",
            tempfile.gettempdir() + "/nonexistent_guidelines_dir_xyz",
            stdout=out,
        )
        output = out.getvalue()
        assert "not found" in output
        # No sources created
        assert KnowledgeSource.objects.count() == 0

    def test_empty_directory_prints_warning(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = StringIO()
            call_command(
                "ingest_acc_guidelines",
                "--dir",
                tmpdir,
                stdout=out,
            )
            assert "No supported files" in out.getvalue()
            assert KnowledgeSource.objects.count() == 0

    def test_unsupported_file_types_ignored(self):
        """Files with unsupported extensions (.csv, .docx) are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "report.csv").write_text("col1,col2\n")
            Path(tmpdir, "notes.docx").write_text("binary data")

            out = StringIO()
            call_command(
                "ingest_acc_guidelines",
                "--dir",
                tmpdir,
                stdout=out,
            )
            assert "No supported files" in out.getvalue()
            assert KnowledgeSource.objects.count() == 0

    @patch("apps.knowledge.management.commands.ingest_acc_guidelines.IngestionPipeline")
    def test_ingests_supported_file_types(self, mock_pipeline):
        pipeline_instance = MagicMock()
        pipeline_instance.ingest_file.return_value = {
            "chunks_created": 4,
            "chunks_deduplicated": 0,
            "errors": 0,
        }
        mock_pipeline.return_value = pipeline_instance

        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "cabg_protocol.md").write_text("# CABG Protocol\nContent here.")
            Path(tmpdir, "heart_failure.txt").write_text("Heart failure guidelines.")

            out = StringIO()
            call_command(
                "ingest_acc_guidelines",
                "--dir",
                tmpdir,
                stdout=out,
            )

            output = out.getvalue()
            assert "2 guideline files" in output
            assert "ACC guideline ingestion complete" in output
            assert KnowledgeSource.objects.count() == 2
            assert pipeline_instance.ingest_file.call_count == 2

    @patch("apps.knowledge.management.commands.ingest_acc_guidelines.IngestionPipeline")
    def test_creates_knowledge_sources_with_correct_type(self, mock_pipeline):
        pipeline_instance = MagicMock()
        pipeline_instance.ingest_file.return_value = {
            "chunks_created": 2,
            "chunks_deduplicated": 0,
            "errors": 0,
        }
        mock_pipeline.return_value = pipeline_instance

        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "cabg_2024.md").write_text("# CABG 2024\nSome content.")

            call_command(
                "ingest_acc_guidelines",
                "--dir",
                tmpdir,
            )

            source = KnowledgeSource.objects.get()
            assert source.source_type == "acc_guideline"
            assert source.hospital is None  # Global, not tenant-scoped
            assert source.version == "2024"

    @patch("apps.knowledge.management.commands.ingest_acc_guidelines.IngestionPipeline")
    def test_source_name_uses_default_prefix(self, mock_pipeline):
        pipeline_instance = MagicMock()
        pipeline_instance.ingest_file.return_value = {
            "chunks_created": 1,
            "chunks_deduplicated": 0,
            "errors": 0,
        }
        mock_pipeline.return_value = pipeline_instance

        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "cabg_post_op.md").write_text("Content.")

            call_command("ingest_acc_guidelines", "--dir", tmpdir)

            source = KnowledgeSource.objects.get()
            assert source.name.startswith("ACC ")
            assert "Cabg Post Op" in source.name

    @patch("apps.knowledge.management.commands.ingest_acc_guidelines.IngestionPipeline")
    def test_custom_source_prefix(self, mock_pipeline):
        pipeline_instance = MagicMock()
        pipeline_instance.ingest_file.return_value = {
            "chunks_created": 1,
            "chunks_deduplicated": 0,
            "errors": 0,
        }
        mock_pipeline.return_value = pipeline_instance

        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "hf_management.md").write_text("Content.")

            call_command(
                "ingest_acc_guidelines",
                "--dir",
                tmpdir,
                "--source-prefix",
                "AHA",
            )

            source = KnowledgeSource.objects.get()
            assert source.name.startswith("AHA ")

    @patch("apps.knowledge.management.commands.ingest_acc_guidelines.IngestionPipeline")
    def test_existing_source_updated_not_duplicated(self, mock_pipeline):
        pipeline_instance = MagicMock()
        pipeline_instance.ingest_file.return_value = {
            "chunks_created": 0,
            "chunks_deduplicated": 2,
            "errors": 0,
        }
        mock_pipeline.return_value = pipeline_instance

        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "cabg_protocol.md").write_text("Content.")

            # Run twice — second run should reuse the same source
            call_command("ingest_acc_guidelines", "--dir", tmpdir)
            call_command("ingest_acc_guidelines", "--dir", tmpdir)

            assert KnowledgeSource.objects.filter(source_type="acc_guideline").count() == 1
            assert pipeline_instance.ingest_file.call_count == 2

    @patch("apps.knowledge.management.commands.ingest_acc_guidelines.IngestionPipeline")
    def test_output_shows_chunk_stats(self, mock_pipeline):
        pipeline_instance = MagicMock()
        pipeline_instance.ingest_file.return_value = {
            "chunks_created": 8,
            "chunks_deduplicated": 3,
            "errors": 1,
        }
        mock_pipeline.return_value = pipeline_instance

        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "guidelines.md").write_text("Content.")

            out = StringIO()
            call_command("ingest_acc_guidelines", "--dir", tmpdir, stdout=out)

            output = out.getvalue()
            assert "8 chunks" in output
            assert "3 dedup" in output
            assert "1 errors" in output

    @patch("apps.knowledge.management.commands.ingest_acc_guidelines.IngestionPipeline")
    def test_all_supported_extensions_processed(self, mock_pipeline):
        """PDF, MD, TXT, HTML, HTM files are all ingested."""
        pipeline_instance = MagicMock()
        pipeline_instance.ingest_file.return_value = {
            "chunks_created": 1,
            "chunks_deduplicated": 0,
            "errors": 0,
        }
        mock_pipeline.return_value = pipeline_instance

        with tempfile.TemporaryDirectory() as tmpdir:
            for ext in [".pdf", ".md", ".txt", ".html", ".htm"]:
                Path(tmpdir, f"doc{ext}").write_bytes(b"content")

            out = StringIO()
            call_command("ingest_acc_guidelines", "--dir", tmpdir, stdout=out)

            assert "5 guideline files" in out.getvalue()
            assert pipeline_instance.ingest_file.call_count == 5
