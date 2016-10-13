# Wrapper around Django's runserver to allow filtering logs.

from typing import Any

from django.core.servers.basehttp import WSGIRequestHandler
orig_log_message = WSGIRequestHandler.log_message
def log_message_monkey(self, format, *args):
    # type: (Any, str, *Any) -> None
    # Filter output for 200 or 304 responses.
    if args[1] == '200' or args[1] == '304':
        return
    orig_log_message(self, format, *args)

WSGIRequestHandler.log_message = log_message_monkey

from django.core.management.commands.runserver import Command
