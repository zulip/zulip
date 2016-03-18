# Webhooks for external integrations.
from __future__ import absolute_import
from zerver.models import get_client
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.lib.validator import check_dict
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view


@api_key_only_webhook_view
@has_request_variables
def api_newrelic_webhook(request, user_profile, alert=REQ(validator=check_dict([]), default=None),
                             deployment=REQ(validator=check_dict([]), default=None)):
    try:
        stream = request.GET['stream']
    except (AttributeError, KeyError):
        return json_error("Missing stream parameter.")

    if alert:
        # Use the message as the subject because it stays the same for
        # "opened", "acknowledged", and "closed" messages that should be
        # grouped.
        subject = alert['message']
        content = "%(long_description)s\n[View alert](%(alert_url)s)" % (alert)
    elif deployment:
        subject = "%s deploy" % (deployment['application_name'])
        content = """`%(revision)s` deployed by **%(deployed_by)s**
%(description)s

%(changelog)s""" % (deployment)
    else:
        return json_error("Unknown webhook request")

    check_send_message(user_profile, get_client("ZulipNewRelicWebhook"), "stream",
                       [stream], subject, content)
    return json_success()
