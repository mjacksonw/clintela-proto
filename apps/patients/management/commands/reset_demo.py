"""Reset the database and seed all demo data with a single command."""

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Flush the database and seed all demo data for presentation."

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Flushing database..."))
        call_command("flush", "--no-input", verbosity=0)
        self.stdout.write("")

        # Required steps — failure here is fatal
        steps = [
            ("seed_pathways", "Seeding clinical pathways..."),
            ("seed_cardiac_pathways", "Seeding cardiac pathways..."),
            ("seed_instruments", "Seeding survey instruments..."),
            ("create_test_clinician", "Creating test clinician..."),
            ("create_test_admin", "Creating test admin..."),
            ("create_cardiology_service", "Creating cardiology service (45 patients)..."),
            ("seed_demo_data", "Seeding hand-crafted demo fixtures..."),
        ]

        for cmd, msg in steps:
            self.stdout.write(msg)
            call_command(cmd, verbosity=0)

        # Optional step — requires DEBUG=True (production guard)
        try:
            self.stdout.write("Seeding clinical vitals & alerts (4 cardiac scenarios)...")
            call_command("seed_clinical_data", verbosity=0)
        except CommandError:
            self.stdout.write(self.style.WARNING("  Skipped (requires DEBUG=True)"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Demo environment ready!"))
        self.stdout.write("")
        self.stdout.write("  Clinician login:  /clinician/login/  (dr_smith / testpass123)")
        self.stdout.write("  Admin login:      /admin-dashboard/  (admin_test / testpass123)")
        self.stdout.write("  Patient:          use dev toolbar to switch patients")
