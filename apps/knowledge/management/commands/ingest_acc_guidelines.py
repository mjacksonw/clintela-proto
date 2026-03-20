"""Management command for ingesting ACC clinical guidelines.

Usage:
    python manage.py ingest_acc_guidelines

This command is a placeholder for the ACC scraper integration.
In production, it will use the ACC scraper (apps/knowledge/scrapers/acc_scraper.py)
to fetch guidelines from acc.org and ingest them.

For now, it ingests from local files in a specified directory.
"""

import logging
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.knowledge.ingestion import IngestionPipeline
from apps.knowledge.models import KnowledgeSource

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Ingest ACC clinical guidelines into the knowledge base"

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

    def handle(self, *args, **options):
        guidelines_dir = Path(options["dir"])

        if not guidelines_dir.exists():
            self.stdout.write(
                self.style.WARNING(
                    f"Guidelines directory not found: {guidelines_dir}. "
                    "Create it and add guideline files (PDF, MD, TXT, HTML)."
                )
            )
            return

        files = list(guidelines_dir.glob("*"))
        supported = [f for f in files if f.suffix.lower() in {".pdf", ".md", ".txt", ".html", ".htm"}]

        if not supported:
            self.stdout.write(self.style.WARNING(f"No supported files found in {guidelines_dir}"))
            return

        self.stdout.write(f"Found {len(supported)} guideline files")

        for file_path in supported:
            source_name = f"{options['source_prefix']} {file_path.stem.replace('_', ' ').replace('-', ' ').title()}"

            source, created = KnowledgeSource.objects.get_or_create(
                name=source_name,
                source_type="acc_guideline",
                hospital=None,  # ACC guidelines are global
                defaults={"version": "2024"},
            )

            self.stdout.write(f"{'Creating' if created else 'Updating'}: {source_name}")

            pipeline = IngestionPipeline(source)
            stats = pipeline.ingest_file(str(file_path))

            self.stdout.write(
                f"  → {stats['chunks_created']} chunks, "
                f"{stats['chunks_deduplicated']} dedup'd, "
                f"{stats['errors']} errors"
            )

        self.stdout.write(self.style.SUCCESS("ACC guideline ingestion complete"))
