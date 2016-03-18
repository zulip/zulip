# Webhooks for external integrations.
from __future__ import absolute_import
from zerver.models import get_client
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import authenticated_rest_api_view


def truncate(string, length):
    if len(string) > length:
        string = string[:length-3] + '...'
    return string

@authenticated_rest_api_view
def api_zendesk_webhook(request, user_profile):
    """
    Zendesk uses trigers with message templates. This webhook uses the
    ticket_id and ticket_title to create a subject. And passes with zendesk
    user's configured message to zulip.
    """
    try:
        ticket_title = request.POST['ticket_title']
        ticket_id = request.POST['ticket_id']
        message = request.POST['message']
        stream = request.POST.get('stream', 'zendesk')
    except KeyError as e:
        return json_error('Missing post parameter %s' % (e.message,))

    subject = truncate('#%s: %s' % (ticket_id, ticket_title), 60)
    check_send_message(user_profile, get_client('ZulipZenDeskWebhook'), 'stream',
                       [stream], subject, message)
    return json_success()
