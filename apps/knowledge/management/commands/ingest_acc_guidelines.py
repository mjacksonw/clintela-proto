"""Management command for batch-ingesting clinical guideline HTML files.

Usage:
    python manage.py ingest_acc_guidelines --dir data/guidelines/acc/
    python manage.py ingest_acc_guidelines --dir data/guidelines/ --dry-run
    python manage.py ingest_acc_guidelines --dir data/guidelines/acc/ --force
"""

import logging
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.knowledge.ingestion import IngestionPipeline
from apps.knowledge.models import KnowledgeDocument, KnowledgeSource

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Ingest clinical guideline files into the knowledge base"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dir",
            default="data/guidelines",
            help="Directory containing guideline files (default: data/guidelines)",
        )
        parser.add_argument(
            "--source-prefix",
            default="ACC",
            help="Prefix for source names",
        )
        parser.add_argument(
            "--type",
            default="acc_guideline",
            choices=["acc_guideline", "clinical_research", "hospital_protocol"],
            help="Source type (default: acc_guideline)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Delete existing documents for each source before re-ingesting",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse files and report stats without embedding or storing",
        )

    def handle(self, *args, **options):
        guidelines_dir = Path(options["dir"])

        if not guidelines_dir.exists():
            self.stdout.write(self.style.WARNING(f"Guidelines directory not found: {guidelines_dir}"))
            return

        files = sorted(guidelines_dir.glob("*"))
        supported = [f for f in files if f.suffix.lower() in {".pdf", ".md", ".txt", ".html", ".htm"}]

        if not supported:
            self.stdout.write(self.style.WARNING(f"No supported files found in {guidelines_dir}"))
            return

        self.stdout.write(f"Found {len(supported)} guideline files")

        if options["dry_run"]:
            self._dry_run(supported, options)
        else:
            self._ingest(supported, options)

    def _dry_run(self, files: list[Path], options: dict):
        """Parse files and report stats without storing anything."""
        from apps.knowledge.parsers import get_parser

        total_sections = 0
        total_chars = 0
        total_recs = 0

        for file_path in files:
            parser = get_parser(str(file_path))
            source_name = self._make_source_name(file_path, options["source_prefix"])

            if hasattr(parser, "parse_file"):
                sections = parser.parse_file(str(file_path), source_name)
            else:
                text = file_path.read_text(encoding="utf-8")
                sections = parser.parse(text, source_name)

            chars = sum(len(s.content) for s in sections)
            recs = sum(len(s.metadata.get("recommendations", [])) for s in sections)
            max_depth = max((s.section_path.count(">") for s in sections), default=0)

            total_sections += len(sections)
            total_chars += chars
            total_recs += recs

            self.stdout.write(
                f"  {file_path.name[:60]:60} "
                f"sections={len(sections):3} chars={chars:7,} recs={recs:3} depth={max_depth}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDry run complete: {len(files)} files, "
                f"{total_sections} sections, {total_chars:,} chars, "
                f"{total_recs} recommendations"
            )
        )

    def _ingest(self, files: list[Path], options: dict):
        """Ingest files into the knowledge base."""
        for file_path in files:
            source_name = self._make_source_name(file_path, options["source_prefix"])

            source, created = KnowledgeSource.objects.get_or_create(
                name=source_name,
                source_type=options["type"],
                hospital=None,
                defaults={"version": ""},
            )

            if options["force"] and not created:
                deleted_count, _ = KnowledgeDocument.objects.filter(source=source).delete()
                self.stdout.write(self.style.WARNING(f"  Force: deleted {deleted_count} existing documents"))

            self.stdout.write(f"{'Creating' if created else 'Updating'}: {source_name}")

            pipeline = IngestionPipeline(source)
            stats = pipeline.ingest_file(str(file_path))

            self.stdout.write(
                f"  → {stats['sections_parsed']} sections, "
                f"{stats['chunks_created']} chunks, "
                f"{stats['chunks_deduplicated']} dedup'd, "
                f"{stats['errors']} errors"
            )

        self.stdout.write(self.style.SUCCESS("Guideline ingestion complete"))

    def _make_source_name(self, file_path: Path, prefix: str) -> str:
        """Generate a human-readable source name from a file path."""
        stem = file_path.stem.replace("_", " ").replace("-", " ")
        # Truncate long names (JACC filenames can be very long)
        if len(stem) > 80:
            stem = stem[:80].rsplit(" ", 1)[0]
        return f"{prefix} {stem.title()}"
