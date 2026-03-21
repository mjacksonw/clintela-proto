"""Seed survey instruments from the instrument registry into the database."""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.surveys.instruments import registry
from apps.surveys.models import SurveyInstrument, SurveyQuestion


class Command(BaseCommand):
    help = "Seed survey instruments and questions from the instrument registry"

    def handle(self, *args, **options):
        instruments = registry.all()

        if not instruments:
            self.stdout.write(self.style.WARNING("No instruments registered"))
            return

        created_count = 0
        updated_count = 0

        for code, cls in instruments.items():
            instrument_def = cls()

            with transaction.atomic():
                db_instrument, created = SurveyInstrument.objects.update_or_create(
                    code=code,
                    defaults={
                        "name": instrument_def.name,
                        "version": instrument_def.version,
                        "category": instrument_def.category,
                        "estimated_minutes": instrument_def.estimated_minutes,
                        "is_active": True,
                        "is_standard": True,
                    },
                )

                if created:
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(f"  Created: {instrument_def.name}"))
                else:
                    updated_count += 1
                    self.stdout.write(f"  Updated: {instrument_def.name}")

                # Upsert questions
                questions = instrument_def.get_questions()
                existing_codes = set()

                for q_def in questions:
                    SurveyQuestion.objects.update_or_create(
                        instrument=db_instrument,
                        code=q_def["code"],
                        defaults={
                            "domain": q_def.get("domain", ""),
                            "order": q_def["order"],
                            "text": q_def["text"],
                            "question_type": q_def["question_type"],
                            "options": q_def.get("options", []),
                            "min_value": q_def.get("min_value"),
                            "max_value": q_def.get("max_value"),
                            "min_label": q_def.get("min_label", ""),
                            "max_label": q_def.get("max_label", ""),
                            "required": q_def.get("required", True),
                            "help_text": q_def.get("help_text", ""),
                        },
                    )
                    existing_codes.add(q_def["code"])

                # Remove questions no longer in the instrument definition
                removed = db_instrument.questions.exclude(code__in=existing_codes).delete()[0]
                if removed:
                    self.stdout.write(f"    Removed {removed} obsolete question(s)")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone: {created_count} created, {updated_count} updated ({len(instruments)} total instruments)"
            )
        )
