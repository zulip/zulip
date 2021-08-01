import re
from typing import List, Sequence, Set

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.decorator import require_member_or_admin, require_realm_admin
from zerver.lib.actions import (
    do_create_multiuse_invite_link,
    do_get_user_invites,
    do_invite_users,
    do_resend_user_invite_email,
    do_revoke_multi_use_invite,
    do_revoke_user_invite,
)
from zerver.lib.exceptions import JsonableError, OrganizationOwnerRequired
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.streams import access_stream_by_id
from zerver.lib.validator import check_int, check_list
from zerver.models import MultiuseInvite, PreregistrationUser, Stream, UserProfile


def check_if_owner_required(invited_as: int, user_profile: UserProfile) -> None:
    if (
        invited_as == PreregistrationUser.INVITE_AS["REALM_OWNER"]
        and not user_profile.is_realm_owner
    ):
        raise OrganizationOwnerRequired()


@require_member_or_admin
@has_request_variables
def invite_users_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    invitee_emails_raw: str = REQ("invitee_emails"),
    invite_expires_in_days: int = REQ(
        json_validator=check_int, default=settings.INVITATION_LINK_VALIDITY_DAYS
    ),
    invite_as: int = REQ(json_validator=check_int, default=PreregistrationUser.INVITE_AS["MEMBER"]),
    stream_ids: List[int] = REQ(json_validator=check_list(check_int)),
) -> HttpResponse:

    if not user_profile.can_invite_others_to_realm():
        # Guest users case will not be handled here as it will
        # be handled by the decorator above.
        raise JsonableError(_("Insufficient permission"))
    if invite_as not in PreregistrationUser.INVITE_AS.values():
        raise JsonableError(_("Must be invited as an valid type of user"))
    check_if_owner_required(invite_as, user_profile)
    if (
        invite_as
        in [
            PreregistrationUser.INVITE_AS["REALM_ADMIN"],
            PreregistrationUser.INVITE_AS["MODERATOR"],
        ]
        and not user_profile.is_realm_admin
    ):
        raise JsonableError(_("Must be an organization administrator"))
    if not invitee_emails_raw:
        raise JsonableError(_("You must specify at least one email address."))
    if not stream_ids:
        raise JsonableError(_("You must specify at least one stream for invitees to join."))

    invitee_emails = get_invitee_emails_set(invitee_emails_raw)

    streams: List[Stream] = []
    for stream_id in stream_ids:
        try:
            (stream, sub) = access_stream_by_id(user_profile, stream_id)
        except JsonableError:
            raise JsonableError(
                _("Stream does not exist with id: {}. No invites were sent.").format(stream_id)
            )
        streams.append(stream)

    do_invite_users(
        user_profile,
        invitee_emails,
        streams,
        invite_expires_in_days=invite_expires_in_days,
        invite_as=invite_as,
    )
    return json_success()


def get_invitee_emails_set(invitee_emails_raw: str) -> Set[str]:
    invitee_emails_list = set(re.split(r"[,\n]", invitee_emails_raw))
    invitee_emails = set()
    for email in invitee_emails_list:
        is_email_with_name = re.search(r"<(?P<email>.*)>", email)
        if is_email_with_name:
            email = is_email_with_name.group("email")
        invitee_emails.add(email.strip())
    return invitee_emails


@require_member_or_admin
def get_user_invites(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    all_users = do_get_user_invites(user_profile)
    return json_success({"invites": all_users})


@require_member_or_admin
@has_request_variables
def revoke_user_invite(
    request: HttpRequest, user_profile: UserProfile, prereg_id: int
) -> HttpResponse:
    try:
        prereg_user = PreregistrationUser.objects.get(id=prereg_id)
    except PreregistrationUser.DoesNotExist:
        raise JsonableError(_("No such invitation"))

    if prereg_user.realm != user_profile.realm:
        raise JsonableError(_("No such invitation"))

    if prereg_user.referred_by_id != user_profile.id:
        check_if_owner_required(prereg_user.invited_as, user_profile)
        if not user_profile.is_realm_admin:
            raise JsonableError(_("Must be an organization administrator"))

    do_revoke_user_invite(prereg_user)
    return json_success()


@require_realm_admin
@has_request_variables
def revoke_multiuse_invite(
    request: HttpRequest, user_profile: UserProfile, invite_id: int
) -> HttpResponse:

    try:
        invite = MultiuseInvite.objects.get(id=invite_id)
    except MultiuseInvite.DoesNotExist:
        raise JsonableError(_("No such invitation"))

    if invite.realm != user_profile.realm:
        raise JsonableError(_("No such invitation"))

    check_if_owner_required(invite.invited_as, user_profile)

    do_revoke_multi_use_invite(invite)
    return json_success()


@require_member_or_admin
@has_request_variables
def resend_user_invite_email(
    request: HttpRequest, user_profile: UserProfile, prereg_id: int
) -> HttpResponse:
    try:
        prereg_user = PreregistrationUser.objects.get(id=prereg_id)
    except PreregistrationUser.DoesNotExist:
        raise JsonableError(_("No such invitation"))

    # Structurally, any invitation the user can actually access should
    # have a referred_by set for the user who created it.
    if prereg_user.referred_by is None or prereg_user.referred_by.realm != user_profile.realm:
        raise JsonableError(_("No such invitation"))

    if prereg_user.referred_by_id != user_profile.id:
        check_if_owner_required(prereg_user.invited_as, user_profile)
        if not user_profile.is_realm_admin:
            raise JsonableError(_("Must be an organization administrator"))

    timestamp = do_resend_user_invite_email(prereg_user)
    return json_success({"timestamp": timestamp})


@require_realm_admin
@has_request_variables
def generate_multiuse_invite_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    invite_expires_in_days: int = REQ(
        json_validator=check_int, default=settings.INVITATION_LINK_VALIDITY_DAYS
    ),
    invite_as: int = REQ(json_validator=check_int, default=PreregistrationUser.INVITE_AS["MEMBER"]),
    stream_ids: Sequence[int] = REQ(json_validator=check_list(check_int), default=[]),
) -> HttpResponse:
    check_if_owner_required(invite_as, user_profile)

    streams = []
    for stream_id in stream_ids:
        try:
            (stream, sub) = access_stream_by_id(user_profile, stream_id)
        except JsonableError:
            raise JsonableError(_("Invalid stream id {}. No invites were sent.").format(stream_id))
        streams.append(stream)

    invite_link = do_create_multiuse_invite_link(
        user_profile, invite_as, invite_expires_in_days, streams
    )
    return json_success({"invite_link": invite_link})
