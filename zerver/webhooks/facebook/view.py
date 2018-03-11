from typing import Any, Dict, Optional, Text

from django.http import HttpRequest, HttpResponse, QueryDict
from django.utils.translation import ugettext as _

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.actions import check_send_stream_message, create_stream_if_needed
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success, json_error
from zerver.models import UserProfile
import json

class UnknownEventType(Exception):
    pass

def user_event(payload: Dict[Text, Any]) -> Text:
    field = payload['entry'][0]['changes'][0]['field']
    message = "Changed **{field}**".format(field=field)
    if field == "email":
        if payload['entry'][0]['changes'][0]['value'] is not None:
            message = message + '\nTo: *{email}*'.format(
                email=payload['entry'][0]['changes'][0]['value']
            )
    return message

def page_event(payload: Dict[Text, Any]) -> Text:
    field = payload['entry'][0]['changes'][0]['field']
    message = ''
    if field == 'conversations':
        message = message + 'Updated **conversations**'
        message = message + '\n[Open conversations...](https://www.facebook.com/'\
                            '{page_id}/{thread_id})'.format(
                                page_id=payload['entry'][0]['changes'][0]['value']['page_id'],
                                thread_id=payload['entry'][0]['changes'][0]['value']['thread_id']
                            )
    elif field == 'website':
        message = message + 'Changed **website**'
    return message

def permissions_event(payload: Dict[Text, Any]) -> Text:
    field = payload['entry'][0]['changes'][0]['field']
    message = '**{field} permission** changed'.format(field=field)
    if field == 'ads_management':
        message = message + '\n* {verb}'.format(
            verb=payload['entry'][0]['changes'][0]['value']['verb']
        )
        for id in payload['entry'][0]['changes'][0]['value']['target_ids']:
            message = message + '\n  * {id}'.format(id=id)
    elif field == 'manage_pages':
        message = message + '\n* {verb}'.format(
            verb=payload['entry'][0]['changes'][0]['value']['verb']
        )
        for id in payload['entry'][0]['changes'][0]['value']['target_ids']:
            message = message + '\n  * {id}'.format(id=id)
    return message

def application_event(payload: Dict[Text, Any]) -> Text:
    field = payload['entry'][0]['changes'][0]['field']
    message = '**{field}** received'.format(field=field)
    if field == 'plugin_comment':
        message = message + '\n**{msg_user}:**\n```quote\n{message}\n```'.format(
            msg_user=payload['entry'][0]['changes'][0]['value']['from']['name'],
            message=payload['entry'][0]['changes'][0]['value']['message']
        )
    if field == 'plugin_comment_reply':
        message = message + '\n**{prt_msg_user}:** (Parent)\n'\
            '```quote\n{prt_message}\n```'.format(
                prt_msg_user=payload['entry'][0]['changes'][0]['value']['parent']['from']['name'],
                prt_message=payload['entry'][0]['changes'][0]['value']['parent']['message']
            )
        message = message + '\n**{cld_msg_user}:**\n```quote\n'\
            '```quote\n{cld_message}\n```\n```'.format(
                cld_msg_user=payload['entry'][0]['changes'][0]['value']['from']['name'],
                cld_message=payload['entry'][0]['changes'][0]['value']['message']
            )
    return message

@api_key_only_webhook_view("Facebook")
@has_request_variables
def api_facebook_webhook(request: HttpRequest, user_profile: UserProfile,
                         stream: Text=REQ(default='Facebook'), token: Text=REQ()) -> HttpResponse:

    if request.method == 'GET':  # facebook webhook verify
        if request.GET.get("hub.mode") == 'subscribe':
            if request.GET.get('hub.verify_token') == token:
                return HttpResponse(request.GET.get('hub.challenge'))
            else:
                return json_error(_('Error: Token is wrong'))
        return json_error(_('Error: Unsupported method'))

    payload = json.loads(request.body.decode("UTF-8"))
    event = get_event(payload)
    if event is not None:
        body = get_body_based_on_event(event)(payload)
        subject = event + " notification"
        check_send_stream_message(user_profile, request.client,
                                  stream, subject, body)
    return json_success()

# This integration doesn't support instant_workflow, instagram
# and certificate_transparency event.
EVENTS_FUNCTION_MAPPER = {
    'user': user_event,
    'page': page_event,
    'permissions': permissions_event,
    'application': application_event
}

def get_event(payload: Dict[Text, Any]) -> Optional[Text]:
    event = payload['object']
    if event in EVENTS_FUNCTION_MAPPER:
        return event
    raise UnknownEventType(u"OEvent '{}' is unknown and cannot be handled".format(event))  # nocoverage

def get_body_based_on_event(event: Text) -> Any:
    return EVENTS_FUNCTION_MAPPER[event]
