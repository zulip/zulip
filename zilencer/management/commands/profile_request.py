from __future__ import absolute_import
from typing import Any, Dict

from django.http import HttpRequest, HttpResponse
from optparse import make_option
from django.core.management.base import BaseCommand, CommandParser
from zerver.models import get_user_profile_by_email, UserMessage
from zerver.views.messages import get_messages_backend
import cProfile
import logging
from zerver.middleware import LogRequests

request_logger = LogRequests()

class MockSession(object):
    def __init__(self):
        # type: () -> None
        self.modified = False

class MockRequest(HttpRequest):
    def __init__(self, email):
        # type: (str) -> None
        self.user = get_user_profile_by_email(email)
        self.path = '/'
        self.method = "POST"
        self.META = {"REMOTE_ADDR": "127.0.0.1"}
        self.REQUEST = {
            "anchor": UserMessage.objects.filter(user_profile=self.user).order_by("-message")[200].message_id,
            "num_before": 1200,
            "num_after": 200
        }
        self.GET = {} # type: Dict[Any, Any]
        self.session = MockSession()

    def get_full_path(self):
        # type: () -> str
        return self.path

def profile_request(request):
    # type: (HttpRequest) -> HttpResponse
    request_logger.process_request(request)
    prof = cProfile.Profile()
    prof.enable()
    ret = get_messages_backend(request, request.user,
                               apply_markdown=True)
    prof.disable()
    prof.dump_stats("/tmp/profile.data")
    request_logger.process_response(request, ret)
    logging.info("Profiling data written to /tmp/profile.data")
    return ret

class Command(BaseCommand):
    def add_arguments(self, parser):
        # type: (CommandParser) -> None
        parser.add_argument('--email', action='store')

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        profile_request(MockRequest(options["email"]))
