from collections.abc import Callable
from datetime import datetime
from functools import wraps

from dateutil.tz import tzlocal
from django.core.management.commands.runserver import Command as DjangoCommand
from typing_extensions import override


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
    @override
    def inner_run(self, *args: object, **options: object) -> None:
        self.stdout.style_func = output_styler(self.stdout.style_func)
        super().inner_run(*args, **options)
