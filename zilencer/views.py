from __future__ import absolute_import

from django.utils.translation import ugettext as _
from django.http import HttpResponse, HttpRequest

from zilencer.models import Deployment

from zerver.decorator import has_request_variables, REQ
from zerver.lib.error_notify import do_report_error
from zerver.lib.feedback import deliver_feedback_by_zulip
from zerver.lib.validator import check_dict

from typing import Any, Dict, Text

@has_request_variables
def submit_feedback(request, deployment, message=REQ(validator=check_dict([]))):
    # type: (HttpRequest, Deployment, Dict[str, Text]) -> HttpResponse
    deliver_feedback_by_zulip(message)
    return HttpResponse(message['sender_email'])

@has_request_variables
def report_error(request, deployment, type=REQ(), report=REQ(validator=check_dict([]))):
    # type: (HttpRequest, Deployment, Text, Dict[str, Any]) -> HttpResponse
    return do_report_error(deployment.name, type, report)
