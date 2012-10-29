from django.core.management.base import NoArgsCommand
from zephyr.models import clear_database

class Command(NoArgsCommand):
    help = "Clear only tables we change: messages, accounts + sessions"

    def handle_noargs(self, **options):
        clear_database()
        self.stdout.write("Successfully cleared the database.\n")
