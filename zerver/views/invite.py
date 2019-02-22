from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _
from typing import List, Optional, Set

from zerver.decorator import require_realm_admin, require_non_guest_human_user
from zerver.lib.actions import do_invite_users, do_revoke_user_invite, \
    do_revoke_multi_use_invite, do_resend_user_invite_email, \
    do_get_user_invites, do_create_multiuse_invite_link
from zerver.lib.request import REQ, has_request_variables, JsonableError
from zerver.lib.response import json_success, json_error
from zerver.lib.streams import access_stream_by_id
from zerver.lib.validator import check_list, check_int
from zerver.models import PreregistrationUser, Stream, UserProfile, MultiuseInvite

import re

@require_non_guest_human_user
@has_request_variables
def invite_users_backend(request: HttpRequest, user_profile: UserProfile,
                         invitee_emails_raw: str=REQ("invitee_emails"),
                         invite_as: Optional[int]=REQ(
                             validator=check_int, default=PreregistrationUser.INVITE_AS['MEMBER']),
                         stream_ids: List[int]=REQ(validator=check_list(check_int)),
                         ) -> HttpResponse:

    if user_profile.realm.invite_by_admins_only and not user_profile.is_realm_admin:
        return json_error(_("Must be an organization administrator"))
    if invite_as not in PreregistrationUser.INVITE_AS.values():
        return json_error(_("Must be invited as an valid type of user"))
    if invite_as == PreregistrationUser.INVITE_AS['REALM_ADMIN'] and not user_profile.is_realm_admin:
        return json_error(_("Must be an organization administrator"))
    if not invitee_emails_raw:
        return json_error(_("You must specify at least one email address."))
    if not stream_ids:
        return json_error(_("You must specify at least one stream for invitees to join."))

    invitee_emails = get_invitee_emails_set(invitee_emails_raw)

    # We unconditionally sub you to the notifications stream if it
    # exists and is public.
    notifications_stream = user_profile.realm.notifications_stream  # type: Optional[Stream]
    if notifications_stream and not notifications_stream.invite_only:
        stream_ids.append(notifications_stream.id)

    streams = []  # type: List[Stream]
    for stream_id in stream_ids:
        try:
            (stream, recipient, sub) = access_stream_by_id(user_profile, stream_id)
        except JsonableError:
            return json_error(
                _("Stream does not exist with id: {}. No invites were sent.".format(stream_id)))
        streams.append(stream)

    do_invite_users(user_profile, invitee_emails, streams, invite_as)
    return json_success()

def get_invitee_emails_set(invitee_emails_raw: str) -> Set[str]:
    invitee_emails_list = set(re.split(r'[,\n]', invitee_emails_raw))
    invitee_emails = set()
    for email in invitee_emails_list:
        is_email_with_name = re.search(r'<(?P<email>.*)>', email)
        if is_email_with_name:
            email = is_email_with_name.group('email')
        invitee_emails.add(email.strip())
    return invitee_emails

@require_realm_admin
def get_user_invites(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    all_users = do_get_user_invites(user_profile)
    return json_success({'invites': all_users})

@require_realm_admin
@has_request_variables
def revoke_user_invite(request: HttpRequest, user_profile: UserProfile,
                       prereg_id: int) -> HttpResponse:
    try:
        prereg_user = PreregistrationUser.objects.get(id=prereg_id)
    except PreregistrationUser.DoesNotExist:
        raise JsonableError(_("No such invitation"))

    if prereg_user.referred_by.realm != user_profile.realm:
        raise JsonableError(_("No such invitation"))

    do_revoke_user_invite(prereg_user)
    return json_success()

@require_realm_admin
@has_request_variables
def revoke_multiuse_invite(request: HttpRequest, user_profile: UserProfile,
                           invite_id: int) -> HttpResponse:

    try:
        invite = MultiuseInvite.objects.get(id=invite_id)
    except MultiuseInvite.DoesNotExist:
        raise JsonableError(_("No such invitation"))

    if invite.realm != user_profile.realm:
        raise JsonableError(_("No such invitation"))

    do_revoke_multi_use_invite(invite)
    return json_success()

@require_realm_admin
@has_request_variables
def resend_user_invite_email(request: HttpRequest, user_profile: UserProfile,
                             prereg_id: int) -> HttpResponse:
    try:
        prereg_user = PreregistrationUser.objects.get(id=prereg_id)
    except PreregistrationUser.DoesNotExist:
        raise JsonableError(_("No such invitation"))

    if (prereg_user.referred_by.realm != user_profile.realm):
        raise JsonableError(_("No such invitation"))

    timestamp = do_resend_user_invite_email(prereg_user)
    return json_success({'timestamp': timestamp})

@require_realm_admin
@has_request_variables
def generate_multiuse_invite_backend(
        request: HttpRequest, user_profile: UserProfile,
        invite_as: int=REQ(validator=check_int, default=PreregistrationUser.INVITE_AS['MEMBER']),
        stream_ids: List[int]=REQ(validator=check_list(check_int), default=[])) -> HttpResponse:
    streams = []
    for stream_id in stream_ids:
        try:
            (stream, recipient, sub) = access_stream_by_id(user_profile, stream_id)
        except JsonableError:
            return json_error(_("Invalid stream id {}. No invites were sent.".format(stream_id)))
        streams.append(stream)

    invite_link = do_create_multiuse_invite_link(user_profile, invite_as, streams)
    return json_success({'invite_link': invite_link})
