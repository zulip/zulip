from __future__ import absolute_import

from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _
from typing import List, Optional, Set, Text

from zerver.decorator import authenticated_json_post_view
from zerver.lib.actions import do_invite_users, do_refer_friend, \
    get_default_subs, internal_send_message
from zerver.lib.request import REQ, has_request_variables, JsonableError
from zerver.lib.response import json_success, json_error
from zerver.lib.streams import access_stream_by_name
from zerver.lib.validator import check_string, check_list
from zerver.models import PreregistrationUser, Stream, UserProfile

import re

@authenticated_json_post_view
@has_request_variables
def json_invite_users(request, user_profile,
                      invitee_emails_raw=REQ("invitee_emails"),
                      body=REQ("custom_body", default=None)):
    # type: (HttpRequest, UserProfile, str, Optional[str]) -> HttpResponse
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

    streams = [] # type: List[Stream]
    for stream_name in stream_names:
        try:
            (stream, recipient, sub) = access_stream_by_name(user_profile, stream_name)
        except JsonableError:
            return json_error(_("Stream does not exist: %s. No invites were sent.") % (stream_name,))
        streams.append(stream)

    ret_error, error_data = do_invite_users(user_profile, invitee_emails, streams, body)

    if ret_error is not None:
        return json_error(data=error_data, msg=ret_error)
    else:
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

@has_request_variables
def bulk_invite_users(request, user_profile,
                      invitee_emails_list=REQ('invitee_emails',
                                              validator=check_list(check_string))):
    # type: (HttpRequest, UserProfile, List[str]) -> HttpResponse
    invitee_emails = set(invitee_emails_list)
    streams = get_default_subs(user_profile)

    ret_error, error_data = do_invite_users(user_profile, invitee_emails, streams)

    if ret_error is not None:
        return json_error(data=error_data, msg=ret_error)
    else:
        # Report bulk invites to internal Zulip.
        invited = PreregistrationUser.objects.filter(referred_by=user_profile)
        internal_message = "%s <`%s`> invited %d people to Zulip." % (
            user_profile.full_name, user_profile.email, invited.count())
        internal_send_message(user_profile.realm, settings.NEW_USER_BOT, "stream",
                              "signups", user_profile.realm.string_id, internal_message)
        return json_success()

@authenticated_json_post_view
@has_request_variables
def json_refer_friend(request, user_profile, email=REQ()):
    # type: (HttpRequest, UserProfile, str) -> HttpResponse
    if not email:
        return json_error(_("No email address specified"))
    if user_profile.invites_granted - user_profile.invites_used <= 0:
        return json_error(_("Insufficient invites"))

    do_refer_friend(user_profile, email)

    return json_success()
