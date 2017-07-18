from __future__ import absolute_import
from typing import Any, Dict

from django.http import HttpRequest, HttpResponse
from django.core.management.base import CommandParser
from zerver.lib.management import ZulipBaseCommand
from zerver.models import UserMessage, UserProfile
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
    def __init__(self, user):
        # type: (UserProfile) -> None
        self.user = user
        self.path = '/'
        self.method = "POST"
        self.META = {"REMOTE_ADDR": "127.0.0.1"}
        self.REQUEST = {
            "anchor": UserMessage.objects.filter(user_profile=self.user).order_by("-message")[200].message_id,
            "num_before": 1200,
            "num_after": 200
        }
        self.GET = {}  # type: Dict[Any, Any]
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

class Command(ZulipBaseCommand):
    def add_arguments(self, parser):
        # type: (CommandParser) -> None
        parser.add_argument("email", metavar="<email>", type=str, help="Email address of the user")
        self.add_realm_args(parser)

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        realm = self.get_realm(options)
        user = self.get_user(options["email"], realm)
        profile_request(MockRequest(user))
