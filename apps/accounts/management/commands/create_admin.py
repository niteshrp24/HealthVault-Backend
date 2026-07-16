from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password
from apps.accounts.models import Admin


class Command(BaseCommand):
    help = 'Create the initial admin account for the HealthVault admin portal.'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, required=True)
        parser.add_argument('--email', type=str, required=True)
        parser.add_argument('--password', type=str, required=True)

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options['password']

        if Admin.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f'Admin "{username}" already exists.'))
            return

        Admin.objects.create(
            username=username,
            email=email,
            password_hash=make_password(password),
        )
        self.stdout.write(self.style.SUCCESS(f'Admin "{username}" created successfully.'))
