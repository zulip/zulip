from __future__ import absolute_import

from optparse import make_option
from django.core.management.base import BaseCommand
from zerver.models import get_user_profile_by_email, UserMessage
from zerver.views.messages import get_old_messages_backend
import cProfile
import logging
from zerver.middleware import LogRequests

request_logger = LogRequests()

class MockSession(object):
    def __init__(self):
        self.modified = False

class MockRequest(object):
    def __init__(self, email):
        self.user = get_user_profile_by_email(email)
        self.path = '/'
        self.method = "POST"
        self.META = {"REMOTE_ADDR": "127.0.0.1"}
        self.REQUEST = {"anchor": UserMessage.objects.filter(user_profile=self.user).order_by("-message")[200].message_id,
                        "num_before": 1200,
                        "num_after": 200}
        self.GET = {}
        self.session = MockSession()

    def get_full_path(self):
        return self.path

def profile_request(request):
    request_logger.process_request(request)
    prof = cProfile.Profile()
    prof.enable()
    ret = get_old_messages_backend(request, request.user,
                                   apply_markdown=True)
    prof.disable()
    prof.dump_stats("/tmp/profile.data")
    request_logger.process_response(request, ret)
    logging.info("Profiling data written to /tmp/profile.data")
    return ret

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--email', action='store'),
        )

    def handle(self, *args, **options):
        profile_request(MockRequest(options["email"]))
