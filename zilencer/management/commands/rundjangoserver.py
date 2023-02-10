from datetime import datetime
from functools import wraps
from typing import Callable

from dateutil.tz import tzlocal
from django.core.management.commands.runserver import Command as DjangoCommand


def output_styler(style_func: Callable[[str], str]) -> Callable[[str], str]:
    # Might fail to suppress the date line around midnight, but, whatever.
    date_prefix = datetime.now(tzlocal()).strftime("%B %d, %Y - ")

    @wraps(style_func)
    def _wrapped_style_func(message: str) -> str:
        if message == "Performing system checks...\n\n" or message.startswith(
            ("System check identified no issues", date_prefix)
        ):
            message = ""
        elif "Quit the server with " in message:
            message = (
                "Django process (re)started. " + message[message.index("Quit the server with ") :]
            )
        return style_func(message)

    return _wrapped_style_func


class Command(DjangoCommand):
    def inner_run(self, *args: object, **options: object) -> None:
        self.stdout.style_func = output_styler(self.stdout.style_func)
        super().inner_run(*args, **options)
