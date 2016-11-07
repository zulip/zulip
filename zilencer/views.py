from __future__ import absolute_import

from django.utils.translation import ugettext as _
from django.utils.timezone import now
from django.http import HttpResponse, HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.views import login as django_login_page
from django.http import HttpResponseRedirect

from zilencer.models import Deployment, RemotePushDeviceToken, RemoteZulipServer

from zerver.decorator import has_request_variables, REQ
from zerver.lib.actions import internal_send_message
from zerver.lib.redis_utils import get_redis_client
from zerver.lib.response import json_success, json_error, json_response
from zerver.lib.validator import check_dict
from zerver.models import get_realm, get_user_profile_by_email, \
    get_realm_by_email_domain, UserProfile, Realm
from .error_notify import notify_server_error, notify_browser_error

import time

from typing import Dict, Optional, Any, Text

client = get_redis_client()

def has_enough_time_expired_since_last_message(sender_email, min_delay):
    # type: (Text, float) -> bool
    # This function returns a boolean, but it also has the side effect
    # of noting that a new message was received.
    key = 'zilencer:feedback:%s' % (sender_email,)
    t = int(time.time())
    last_time = client.getset(key, t)
    if last_time is None:
        return True
    delay = t - int(last_time)
    return delay > min_delay

def get_ticket_number():
    # type: () -> int
    fn = '/var/tmp/.feedback-bot-ticket-number'
    try:
        ticket_number = int(open(fn).read()) + 1
    except:
        ticket_number = 1
    open(fn, 'w').write('%d' % (ticket_number,))
    return ticket_number

@has_request_variables
def remote_server_register_push(request, entity_profile, server_uuid=REQ(), user_id=REQ(), token=REQ(), token_kind=REQ(), ios_app_id=None):
    # type: (HttpRequest, text_type, int, text_type, int, text_type) -> HttpResponse
    if token == '' or len(token) > 4096:
        return json_error(_("Empty or invalid length token"))

    server_ids = RemoteZulipServer.objects.filter(uuid=server_uuid)
    if len(server_ids) == 0:
        # No server found for that uuid
        return json_error(_("Server not registered. UUID:" + server_uuid))


    # If a user logged out on a device and failed to unregister,
    # we should delete any other user associations for this token
    # & RemoteServer pair
    RemotePushDeviceToken.objects.filter(token=token,kind=token_kind,server_id__in=server_ids).exclude(user_id=user_id).delete()

    # Save or update
    remote_token, created = RemotePushDeviceToken.objects.get_or_create(user_id=user_id,
                                              server=server_ids[0],
                                              kind=token_kind,
                                              token=token,
                                              ios_app_id=ios_app_id,
                                              last_updated=now())

    return json_success()

@has_request_variables
def remote_server_unregister_push(request, entity_profile, server_uuid=REQ(), token=REQ(), token_kind=REQ(), ios_app_id=None):
    # type: (HttpRequest, text_type, text_type, int, text_type) -> HttpResponse
    if token == '' or len(token) > 4096:
        return json_error(_("Empty or invalid length token"))

    # Note that this doesn't filter by user_id;
    # any token unregistration should remove that device for that
    # server completely (it's impossible to have multiple users
    # logged in to the same app on a single device)
    server_ids = RemoteZulipServer.objects.filter(uuid=server_uuid)

    if len(server_ids) == 0:
        # No server found for that uuid
        return json_error(_("Server not registered. UUID:" + server_uuid))

    RemotePushDeviceToken.objects.filter(token=token,kind=token_kind,server_id__in=server_ids).delete()

    return json_success()

@has_request_variables
def remote_server_push_message(request):
    # type: (HttpRequest) -> HttpResponse
    # stub. todo: write this method
    return json_success()

@has_request_variables
def update_remote_server(request):
    # type: (HttpRequest) -> HttpResponse
    # stub. todo: write this method (either update or save a new remote server object)
    return json_success()

@has_request_variables
def submit_feedback(request, deployment, message=REQ(validator=check_dict([]))):
    # type: (HttpRequest, Deployment, Dict[str, Text]) -> HttpResponse
    domainish = message["sender_domain"]
    if get_realm("zulip") not in deployment.realms.all():
        domainish += u" via " + deployment.name
    subject = "%s" % (message["sender_email"],)

    if len(subject) > 60:
        subject = subject[:57].rstrip() + "..."

    content = u''
    sender_email = message['sender_email']

    # We generate ticket numbers if it's been more than a few minutes
    # since their last message.  This avoids some noise when people use
    # enter-send.
    need_ticket = has_enough_time_expired_since_last_message(sender_email, 180)

    if need_ticket:
        ticket_number = get_ticket_number()
        content += '\n~~~'
        content += '\nticket Z%03d (@support please ack)' % (ticket_number,)
        content += '\nsender: %s' % (message['sender_full_name'],)
        content += '\nemail: %s' % (sender_email,)
        if 'sender_domain' in message:
            content += '\nrealm: %s' % (message['sender_domain'],)
        content += '\n~~~'
        content += '\n\n'

    content += message['content']

    internal_send_message("feedback@zulip.com", "stream", "support", subject, content)

    return HttpResponse(message['sender_email'])

@has_request_variables
def report_error(request, deployment, type=REQ(), report=REQ(validator=check_dict([]))):
    # type: (HttpRequest, Deployment, Text, Dict[str, Any]) -> HttpResponse
    return do_report_error(deployment.name, type, report)

def do_report_error(deployment_name, type, report):
    # type: (Text, Text, Dict[str, Any]) -> HttpResponse
    report['deployment'] = deployment_name
    if type == 'browser':
        notify_browser_error(report)
    elif type == 'server':
        notify_server_error(report)
    else:
        return json_error(_("Invalid type parameter"))
    return json_success()

def realm_for_email(email):
    # type: (str) -> Optional[Realm]
    try:
        user = get_user_profile_by_email(email)
        return user.realm
    except UserProfile.DoesNotExist:
        pass

    return get_realm_by_email_domain(email)

# Requests made to this endpoint are UNAUTHENTICATED
@csrf_exempt
@has_request_variables
def lookup_endpoints_for_user(request, email=REQ()):
    # type: (HttpRequest, str) -> HttpResponse
    try:
        return json_response(realm_for_email(email).deployment.endpoints)
    except AttributeError:
        return json_error(_("Cannot determine endpoint for user."), status=404)

def account_deployment_dispatch(request, **kwargs):
    # type: (HttpRequest, **Any) -> HttpResponse
    sso_unknown_email = False
    if request.method == 'POST':
        email = request.POST['username']
        realm = realm_for_email(email)
        try:
            return HttpResponseRedirect(realm.deployment.base_site_url)
        except AttributeError:
            # No deployment found for this user/email
            sso_unknown_email = True

    template_response = django_login_page(request, **kwargs)
    template_response.context_data['desktop_sso_dispatch'] = True
    template_response.context_data['desktop_sso_unknown_email'] = sso_unknown_email
    return template_response
