from datetime import datetime

from django.core.management.commands.runserver import Command as DjangoCommand
from typing_extensions import Protocol


class Writable(Protocol):
    def write(self, s: str) -> None:
        ...


class FakeStdout:
    """
    Filter stdout from Django's runserver, to declutter run-dev.py
    startup output.
    """

    def __init__(self, stdout: Writable) -> None:
        self.stdout = stdout
        # Might fail to suppress the date line around midnight, but, whatever.
        self.date_prefix = datetime.now().strftime("%B %d, %Y - ")

    def write(self, s: str) -> None:
        if (
            s == "Performing system checks...\n\n"
            or s.startswith("System check identified no issues")
            or s.startswith(self.date_prefix)
        ):
            pass
        elif "Quit the server with " in s:
            self.stdout.write(
                "Django process (re)started. " + s[s.index("Quit the server with ") :]
            )
        else:
            self.stdout.write(s)


class Command(DjangoCommand):
    stdout: Writable

    def inner_run(self, *args: object, **options: object) -> None:
        self.stdout = FakeStdout(self.stdout)
        try:
            super().inner_run(*args, **options)
        finally:
            self.stdout = self.stdout.stdout
