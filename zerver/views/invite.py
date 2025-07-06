import re
from typing import Annotated

from django.conf import settings
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from pydantic import Json

from confirmation import settings as confirmation_settings
from zerver.actions.invites import (
    do_create_multiuse_invite_link,
    do_get_invites_controlled_by_user,
    do_invite_users,
    do_revoke_multi_use_invite,
    do_revoke_user_invite,
    do_send_user_invite_email,
)
from zerver.decorator import require_member_or_admin
from zerver.lib.exceptions import InvitationError, JsonableError, OrganizationOwnerRequiredError
from zerver.lib.response import json_success
from zerver.lib.streams import access_stream_by_id, get_streams_to_which_user_cannot_add_subscribers
from zerver.lib.typed_endpoint import ApiParamConfig, PathOnly, typed_endpoint
from zerver.lib.typed_endpoint_validators import check_int_in_validator
from zerver.lib.user_groups import UserGroupMembershipDetails, access_user_group_for_update
from zerver.models import MultiuseInvite, NamedUserGroup, PreregistrationUser, Stream, UserProfile

# Convert INVITATION_LINK_VALIDITY_DAYS into minutes.
# Because mypy fails to correctly infer the type of the validator, we want this constant
# to be Optional[int] to avoid a mypy error when using it as the default value.
# https://github.com/python/mypy/issues/13234
INVITATION_LINK_VALIDITY_MINUTES: int | None = 24 * 60 * settings.INVITATION_LINK_VALIDITY_DAYS


def check_role_based_permissions(
    invited_as: int, user_profile: UserProfile, *, require_admin: bool
) -> None:
    if (
        invited_as == PreregistrationUser.INVITE_AS["REALM_OWNER"]
        and not user_profile.is_realm_owner
    ):
        raise OrganizationOwnerRequiredError

    if require_admin and not user_profile.is_realm_admin:
        raise JsonableError(_("Must be an organization administrator"))


def access_invite_by_id(user_profile: UserProfile, invite_id: int) -> PreregistrationUser:
    try:
        prereg_user = PreregistrationUser.objects.get(id=invite_id)
    except PreregistrationUser.DoesNotExist:
        raise JsonableError(_("No such invitation"))

    # Structurally, any invitation the user can actually access should
    # have a referred_by set for the user who created it.
    if prereg_user.referred_by is None or prereg_user.referred_by.realm != user_profile.realm:
        raise JsonableError(_("No such invitation"))

    if prereg_user.referred_by_id != user_profile.id:
        check_role_based_permissions(prereg_user.invited_as, user_profile, require_admin=True)
    return prereg_user


def access_multiuse_invite_by_id(user_profile: UserProfile, invite_id: int) -> MultiuseInvite:
    try:
        invite = MultiuseInvite.objects.get(id=invite_id)
    except MultiuseInvite.DoesNotExist:
        raise JsonableError(_("No such invitation"))

    if invite.realm != user_profile.realm:
        raise JsonableError(_("No such invitation"))

    if invite.referred_by_id != user_profile.id:
        check_role_based_permissions(invite.invited_as, user_profile, require_admin=True)

    if invite.status == confirmation_settings.STATUS_REVOKED:
        raise JsonableError(_("Invitation has already been revoked"))
    return invite


def access_streams_for_invite(stream_ids: list[int], user_profile: UserProfile) -> list[Stream]:
    streams: list[Stream] = []

    for stream_id in stream_ids:
        try:
            (stream, sub) = access_stream_by_id(user_profile, stream_id)
        except JsonableError:
            raise JsonableError(
                _("Invalid channel ID {channel_id}. No invites were sent.").format(
                    channel_id=stream_id
                )
            )
        streams.append(stream)

    user_group_membership_details = UserGroupMembershipDetails(user_recursive_group_ids=None)
    streams_to_which_user_cannot_add_subscribers = get_streams_to_which_user_cannot_add_subscribers(
        streams,
        user_profile,
        allow_default_streams=True,
        user_group_membership_details=user_group_membership_details,
    )
    if len(streams_to_which_user_cannot_add_subscribers) > 0:
        raise JsonableError(_("You do not have permission to subscribe other users to channels."))

    return streams


def access_user_groups_for_invite(
    group_ids: list[int] | None, user_profile: UserProfile
) -> list[NamedUserGroup]:
    user_groups: list[NamedUserGroup] = []
    if group_ids:
        with transaction.atomic(durable=True):
            for group_id in group_ids:
                user_group = access_user_group_for_update(
                    group_id, user_profile, permission_setting="can_add_members_group"
                )
                user_groups.append(user_group)

    return user_groups


@require_member_or_admin
@typed_endpoint
def invite_users_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    group_ids: Json[list[int]] | None = None,
    include_realm_default_subscriptions: Json[bool] = False,
    invite_as: Annotated[
        Json[int],
        check_int_in_validator(list(PreregistrationUser.INVITE_AS.values())),
    ] = PreregistrationUser.INVITE_AS["MEMBER"],
    invite_expires_in_minutes: Json[int | None] = INVITATION_LINK_VALIDITY_MINUTES,
    invitee_emails_raw: Annotated[str, ApiParamConfig("invitee_emails")],
    notify_referrer_on_join: Json[bool] = True,
    stream_ids: Json[list[int]],
) -> HttpResponse:
    if not user_profile.can_invite_users_by_email():
        # Guest users case will not be handled here as it will
        # be handled by the decorator above.
        raise JsonableError(_("Insufficient permission"))

    require_admin = invite_as in [
        # Owners can only be invited by owners, checked by separate
        # logic in check_role_based_permissions.
        PreregistrationUser.INVITE_AS["REALM_OWNER"],
        PreregistrationUser.INVITE_AS["REALM_ADMIN"],
        PreregistrationUser.INVITE_AS["MODERATOR"],
    ]
    check_role_based_permissions(invite_as, user_profile, require_admin=require_admin)

    if not invitee_emails_raw:
        raise JsonableError(_("You must specify at least one email address."))

    invitee_emails = get_invitee_emails_set(invitee_emails_raw)

    streams = access_streams_for_invite(stream_ids, user_profile)
    user_groups = access_user_groups_for_invite(group_ids, user_profile)

    skipped = do_invite_users(
        user_profile,
        invitee_emails,
        streams,
        notify_referrer_on_join,
        user_groups,
        invite_expires_in_minutes=invite_expires_in_minutes,
        include_realm_default_subscriptions=include_realm_default_subscriptions,
        invite_as=invite_as,
    )

    if skipped:
        raise InvitationError(
            _(
                "Some of those addresses are already using Zulip, "
                "so we didn't send them an invitation. We did send "
                "invitations to everyone else!"
            ),
            skipped,
            sent_invitations=True,
        )

    return json_success(request)


def get_invitee_emails_set(invitee_emails_raw: str) -> set[str]:
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
    all_users = do_get_invites_controlled_by_user(user_profile)
    return json_success(request, data={"invites": all_users})


@require_member_or_admin
@typed_endpoint
def revoke_user_invite(
    request: HttpRequest, user_profile: UserProfile, *, invite_id: PathOnly[int]
) -> HttpResponse:
    prereg_user = access_invite_by_id(user_profile, invite_id)
    do_revoke_user_invite(prereg_user)
    return json_success(request)


@require_member_or_admin
@typed_endpoint
def revoke_multiuse_invite(
    request: HttpRequest, user_profile: UserProfile, *, invite_id: PathOnly[int]
) -> HttpResponse:
    invite = access_multiuse_invite_by_id(user_profile, invite_id)
    do_revoke_multi_use_invite(invite)
    return json_success(request)


@require_member_or_admin
@typed_endpoint
def resend_user_invite_email(
    request: HttpRequest, user_profile: UserProfile, *, invite_id: PathOnly[int]
) -> HttpResponse:
    prereg_user = access_invite_by_id(user_profile, invite_id)
    do_send_user_invite_email(prereg_user, event_time=timezone_now())
    return json_success(request)


@require_member_or_admin
@typed_endpoint
def generate_multiuse_invite_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    group_ids: Json[list[int]] | None = None,
    include_realm_default_subscriptions: Json[bool] = False,
    invite_as: Annotated[
        Json[int],
        check_int_in_validator(list(PreregistrationUser.INVITE_AS.values())),
    ] = PreregistrationUser.INVITE_AS["MEMBER"],
    invite_expires_in_minutes: Json[int | None] = INVITATION_LINK_VALIDITY_MINUTES,
    stream_ids: Json[list[int]] | None = None,
) -> HttpResponse:
    if stream_ids is None:
        stream_ids = []
    if not user_profile.can_create_multiuse_invite_to_realm():
        # Guest users case will not be handled here as it will
        # be handled by the decorator above.
        raise JsonableError(_("Insufficient permission"))

    require_admin = invite_as in [
        # Owners can only be invited by owners, checked by separate
        # logic in check_role_based_permissions.
        PreregistrationUser.INVITE_AS["REALM_OWNER"],
        PreregistrationUser.INVITE_AS["REALM_ADMIN"],
        PreregistrationUser.INVITE_AS["MODERATOR"],
    ]
    check_role_based_permissions(invite_as, user_profile, require_admin=require_admin)

    streams = access_streams_for_invite(stream_ids, user_profile)
    user_groups = access_user_groups_for_invite(group_ids, user_profile)

    invite_link = do_create_multiuse_invite_link(
        user_profile,
        invite_as,
        invite_expires_in_minutes,
        include_realm_default_subscriptions,
        streams,
        user_groups,
    )
    return json_success(request, data={"invite_link": invite_link})
