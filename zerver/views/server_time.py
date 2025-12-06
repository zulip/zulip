"""
Server time endpoint.

This module was created to fix a broken import in zproject/urls.py
that referenced a non-existent server_time module.
"""

import time

from django.http import HttpRequest, HttpResponse

from zerver.lib.response import json_success


def server_time(request: HttpRequest) -> HttpResponse:
    """Return the current server timestamp."""
    return json_success(request, data={"server_timestamp": time.time()})
