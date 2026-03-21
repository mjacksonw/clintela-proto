"""Create a test administrator user for development."""

from django.core.management.base import BaseCommand

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Create a test administrator user."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="admin_test", help="Admin username")
        parser.add_argument("--password", default="testpass123", help="Admin password")

    def handle(self, *args, **options):
        username = options["username"]
        password = options["password"]

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "role": "admin",
                "first_name": "Admin",
                "last_name": "User",
                "email": "admin@clintela.dev",
            },
        )

        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Created admin user: {username}"))
        else:
            self.stdout.write(self.style.WARNING(f"Admin user '{username}' already exists"))

        self.stdout.write("")
        self.stdout.write("  Login URL:  http://localhost:8000/admin-dashboard/login/")
        self.stdout.write(f"  Username:   {username}")
        self.stdout.write(f"  Password:   {password}")
        self.stdout.write("")
