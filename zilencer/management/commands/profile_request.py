import cProfile
import logging
from typing import Any, Dict

from django.core.management.base import CommandParser
from django.http import HttpRequest, HttpResponse

from zerver.lib.management import ZulipBaseCommand
from zerver.middleware import LogRequests
from zerver.models import UserMessage, UserProfile
from zerver.views.messages import get_messages_backend

request_logger = LogRequests()

class MockSession:
    def __init__(self) -> None:
        self.modified = False

class MockRequest(HttpRequest):
    def __init__(self, user: UserProfile) -> None:
        self.user = user
        self.path = '/'
        self.method = "POST"
        self.META = {"REMOTE_ADDR": "127.0.0.1"}
        anchor = UserMessage.objects.filter(user_profile=self.user).order_by("-message")[200].message_id
        self.REQUEST = {
            "anchor": anchor,
            "num_before": 1200,
            "num_after": 200
        }
        self.GET = {}  # type: Dict[Any, Any]
        self.session = MockSession()

    def get_full_path(self) -> str:
        return self.path

def profile_request(request: HttpRequest) -> HttpResponse:
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
    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("email", metavar="<email>", type=str, help="Email address of the user")
        self.add_realm_args(parser)

    def handle(self, *args: Any, **options: Any) -> None:
        realm = self.get_realm(options)
        user = self.get_user(options["email"], realm)
        profile_request(MockRequest(user))
