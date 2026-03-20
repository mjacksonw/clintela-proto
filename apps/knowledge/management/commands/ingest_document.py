"""Management command for ingesting documents into the knowledge base.

Usage:
    python manage.py ingest_document --file path/to/doc.pdf --source "Source Name" --type hospital_protocol
    python manage.py ingest_document --file guidelines.md --source "ACC CABG 2024" --type acc_guideline
    python manage.py ingest_document --file protocol.pdf \
        --source "St. Mary's Cardiac" --type hospital_protocol --hospital HOSP001
"""

import logging

from django.core.management.base import BaseCommand, CommandError

from apps.knowledge.ingestion import IngestionPipeline
from apps.knowledge.models import KnowledgeSource
from apps.patients.models import Hospital

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Ingest a document into the clinical knowledge base"

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, help="Path to the document file")
        parser.add_argument("--source", required=True, help="Knowledge source name")
        parser.add_argument(
            "--type",
            required=True,
            choices=["acc_guideline", "clinical_research", "hospital_protocol"],
            help="Source type",
        )
        parser.add_argument("--hospital", help="Hospital code (for tenant-scoped documents)")
        parser.add_argument("--version", default="", help="Document version")
        parser.add_argument("--url", default="", help="Source URL")

    def handle(self, *args, **options):
        file_path = options["file"]
        source_name = options["source"]
        source_type = options["type"]

        hospital = None
        if options.get("hospital"):
            try:
                hospital = Hospital.objects.get(code=options["hospital"])
            except Hospital.DoesNotExist as err:
                raise CommandError(f"Hospital not found: {options['hospital']}") from err

        # Get or create the source
        source, created = KnowledgeSource.objects.get_or_create(
            name=source_name,
            source_type=source_type,
            hospital=hospital,
            defaults={
                "version": options.get("version", ""),
                "url": options.get("url", ""),
            },
        )

        action = "Created" if created else "Using existing"
        self.stdout.write(f"{action} source: {source}")

        # Run ingestion
        pipeline = IngestionPipeline(source)
        stats = pipeline.ingest_file(file_path)

        self.stdout.write(
            self.style.SUCCESS(
                f"Ingestion complete: "
                f"{stats['sections_parsed']} sections parsed, "
                f"{stats['chunks_created']} chunks created, "
                f"{stats['chunks_deduplicated']} deduplicated, "
                f"{stats['sanitization_events']} sanitization events, "
                f"{stats['errors']} errors"
            )
        )
