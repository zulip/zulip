from __future__ import absolute_import

from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _
from typing import List, Optional, Set, Text

from zerver.decorator import authenticated_json_post_view
from zerver.lib.actions import do_invite_users, \
    get_default_subs, internal_send_message
from zerver.lib.request import REQ, has_request_variables, JsonableError
from zerver.lib.response import json_success, json_error
from zerver.lib.streams import access_stream_by_name
from zerver.lib.validator import check_string, check_list
from zerver.models import PreregistrationUser, Stream, UserProfile

import re

@has_request_variables
def invite_users_backend(request, user_profile,
                         invitee_emails_raw=REQ("invitee_emails"),
                         body=REQ("custom_body", default=None)):
    # type: (HttpRequest, UserProfile, str, Optional[str]) -> HttpResponse
    if user_profile.realm.invite_by_admins_only and not user_profile.is_realm_admin:
        return json_error(_("Must be a realm administrator"))
    if not invitee_emails_raw:
        return json_error(_("You must specify at least one email address."))
    if body == '':
        body = None

    invitee_emails = get_invitee_emails_set(invitee_emails_raw)

    stream_names = request.POST.getlist('stream')
    if not stream_names:
        return json_error(_("You must specify at least one stream for invitees to join."))

    # We unconditionally sub you to the notifications stream if it
    # exists and is public.
    notifications_stream = user_profile.realm.notifications_stream  # type: Optional[Stream]
    if notifications_stream and not notifications_stream.invite_only:
        stream_names.append(notifications_stream.name)

    streams = []  # type: List[Stream]
    for stream_name in stream_names:
        try:
            (stream, recipient, sub) = access_stream_by_name(user_profile, stream_name)
        except JsonableError:
            return json_error(_("Stream does not exist: %s. No invites were sent.") % (stream_name,))
        streams.append(stream)

    do_invite_users(user_profile, invitee_emails, streams, body)
    return json_success()

def get_invitee_emails_set(invitee_emails_raw):
    # type: (str) -> Set[str]
    invitee_emails_list = set(re.split(r'[,\n]', invitee_emails_raw))
    invitee_emails = set()
    for email in invitee_emails_list:
        is_email_with_name = re.search(r'<(?P<email>.*)>', email)
        if is_email_with_name:
            email = is_email_with_name.group('email')
        invitee_emails.add(email.strip())
    return invitee_emails
