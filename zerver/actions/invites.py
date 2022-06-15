import datetime
from typing import Any, Collection, Dict, List, Optional, Sequence, Set, Tuple, Union

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q, Sum
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from analytics.lib.counts import COUNT_STATS, do_increment_logging_stat
from analytics.models import RealmCount
from confirmation.models import Confirmation, confirmation_url, create_confirmation_link
from zerver.lib.email_validation import (
    get_existing_user_errors,
    get_realm_email_validator,
    validate_email_is_valid,
)
from zerver.lib.exceptions import InvitationError
from zerver.lib.queue import queue_json_publish
from zerver.lib.send_email import FromAddress, clear_scheduled_invitation_emails, send_email
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.types import UnspecifiedValue
from zerver.models import (
    MultiuseInvite,
    PreregistrationUser,
    Realm,
    Stream,
    UserProfile,
    filter_to_valid_prereg_users,
)
from zerver.tornado.django_api import send_event


def notify_invites_changed(realm: Realm) -> None:
    event = dict(type="invites_changed")
    admin_ids = [user.id for user in realm.get_admin_users_and_bots()]
    send_event(realm, event, admin_ids)


def do_send_confirmation_email(
    invitee: PreregistrationUser,
    referrer: UserProfile,
    email_language: str,
    invite_expires_in_minutes: Union[Optional[int], UnspecifiedValue] = UnspecifiedValue(),
) -> str:
    """
    Send the confirmation/welcome e-mail to an invited user.
    """
    activation_url = create_confirmation_link(
        invitee, Confirmation.INVITATION, validity_in_minutes=invite_expires_in_minutes
    )
    context = {
        "referrer_full_name": referrer.full_name,
        "referrer_email": referrer.delivery_email,
        "activate_url": activation_url,
        "referrer_realm_name": referrer.realm.name,
    }
    send_email(
        "zerver/emails/invitation",
        to_emails=[invitee.email],
        from_address=FromAddress.tokenized_no_reply_address(),
        language=email_language,
        context=context,
        realm=referrer.realm,
    )
    return activation_url


def estimate_recent_invites(realms: Collection[Realm], *, days: int) -> int:
    """An upper bound on the number of invites sent in the last `days` days"""
    recent_invites = RealmCount.objects.filter(
        realm__in=realms,
        property="invites_sent::day",
        end_time__gte=timezone_now() - datetime.timedelta(days=days),
    ).aggregate(Sum("value"))["value__sum"]
    if recent_invites is None:
        return 0
    return recent_invites


def check_invite_limit(realm: Realm, num_invitees: int) -> None:
    """Discourage using invitation emails as a vector for carrying spam."""
    msg = _(
        "To protect users, Zulip limits the number of invitations you can send in one day. Because you have reached the limit, no invitations were sent."
    )
    if not settings.OPEN_REALM_CREATION:
        return

    recent_invites = estimate_recent_invites([realm], days=1)
    if num_invitees + recent_invites > realm.max_invites:
        raise InvitationError(
            msg,
            [],
            sent_invitations=False,
            daily_limit_reached=True,
        )

    default_max = settings.INVITES_DEFAULT_REALM_DAILY_MAX
    newrealm_age = datetime.timedelta(days=settings.INVITES_NEW_REALM_DAYS)
    if realm.date_created <= timezone_now() - newrealm_age:
        # If this isn't a "newly-created" realm, we're done. The
        # remaining code applies an aggregate limit across all
        # "new" realms, to address sudden bursts of spam realms.
        return

    if realm.max_invites > default_max:
        # If a user is on a realm where we've bumped up
        # max_invites, then we exempt them from invite limits.
        return

    new_realms = Realm.objects.filter(
        date_created__gte=timezone_now() - newrealm_age,
        _max_invites__lte=default_max,
    ).all()

    for days, count in settings.INVITES_NEW_REALM_LIMIT_DAYS:
        recent_invites = estimate_recent_invites(new_realms, days=days)
        if num_invitees + recent_invites > count:
            raise InvitationError(
                msg,
                [],
                sent_invitations=False,
                daily_limit_reached=True,
            )


def do_invite_users(
    user_profile: UserProfile,
    invitee_emails: Collection[str],
    streams: Collection[Stream],
    *,
    invite_expires_in_minutes: Optional[int],
    invite_as: int = PreregistrationUser.INVITE_AS["MEMBER"],
) -> None:
    num_invites = len(invitee_emails)

    check_invite_limit(user_profile.realm, num_invites)
    if settings.BILLING_ENABLED:
        from corporate.lib.registration import check_spare_licenses_available_for_inviting_new_users

        check_spare_licenses_available_for_inviting_new_users(user_profile.realm, num_invites)

    realm = user_profile.realm
    if not realm.invite_required:
        # Inhibit joining an open realm to send spam invitations.
        min_age = datetime.timedelta(days=settings.INVITES_MIN_USER_AGE_DAYS)
        if user_profile.date_joined > timezone_now() - min_age and not user_profile.is_realm_admin:
            raise InvitationError(
                _(
                    "Your account is too new to send invites for this organization. "
                    "Ask an organization admin, or a more experienced user."
                ),
                [],
                sent_invitations=False,
            )

    good_emails: Set[str] = set()
    errors: List[Tuple[str, str, bool]] = []
    validate_email_allowed_in_realm = get_realm_email_validator(user_profile.realm)
    for email in invitee_emails:
        if email == "":
            continue
        email_error = validate_email_is_valid(
            email,
            validate_email_allowed_in_realm,
        )

        if email_error:
            errors.append((email, email_error, False))
        else:
            good_emails.add(email)

    """
    good_emails are emails that look ok so far,
    but we still need to make sure they're not
    gonna conflict with existing users
    """
    error_dict = get_existing_user_errors(user_profile.realm, good_emails)

    skipped: List[Tuple[str, str, bool]] = []
    for email in error_dict:
        msg, deactivated = error_dict[email]
        skipped.append((email, msg, deactivated))
        good_emails.remove(email)

    validated_emails = list(good_emails)

    if errors:
        raise InvitationError(
            _("Some emails did not validate, so we didn't send any invitations."),
            errors + skipped,
            sent_invitations=False,
        )

    if skipped and len(skipped) == len(invitee_emails):
        # All e-mails were skipped, so we didn't actually invite anyone.
        raise InvitationError(
            _("We weren't able to invite anyone."), skipped, sent_invitations=False
        )

    # We do this here rather than in the invite queue processor since this
    # is used for rate limiting invitations, rather than keeping track of
    # when exactly invitations were sent
    do_increment_logging_stat(
        user_profile.realm,
        COUNT_STATS["invites_sent::day"],
        None,
        timezone_now(),
        increment=len(validated_emails),
    )

    # Now that we are past all the possible errors, we actually create
    # the PreregistrationUser objects and trigger the email invitations.
    for email in validated_emails:
        # The logged in user is the referrer.
        prereg_user = PreregistrationUser(
            email=email, referred_by=user_profile, invited_as=invite_as, realm=user_profile.realm
        )
        prereg_user.save()
        stream_ids = [stream.id for stream in streams]
        prereg_user.streams.set(stream_ids)

        event = {
            "prereg_id": prereg_user.id,
            "referrer_id": user_profile.id,
            "email_language": user_profile.realm.default_language,
            "invite_expires_in_minutes": invite_expires_in_minutes,
        }
        queue_json_publish("invites", event)

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
    notify_invites_changed(user_profile.realm)


def get_invitation_expiry_date(confirmation_obj: Confirmation) -> Optional[int]:
    expiry_date = confirmation_obj.expiry_date
    if expiry_date is None:
        return expiry_date
    return datetime_to_timestamp(expiry_date)


def do_get_invites_controlled_by_user(user_profile: UserProfile) -> List[Dict[str, Any]]:
    """
    Returns a list of dicts representing invitations that can be controlled by user_profile.
    This isn't necessarily the same as all the invitations generated by the user, as administrators
    can control also invitations that they did not themselves create.
    """
    if user_profile.is_realm_admin:
        prereg_users = filter_to_valid_prereg_users(
            PreregistrationUser.objects.filter(referred_by__realm=user_profile.realm)
        )
    else:
        prereg_users = filter_to_valid_prereg_users(
            PreregistrationUser.objects.filter(referred_by=user_profile)
        )

    invites = []

    for invitee in prereg_users:
        assert invitee.referred_by is not None
        invites.append(
            dict(
                email=invitee.email,
                invited_by_user_id=invitee.referred_by.id,
                invited=datetime_to_timestamp(invitee.invited_at),
                expiry_date=get_invitation_expiry_date(invitee.confirmation.get()),
                id=invitee.id,
                invited_as=invitee.invited_as,
                is_multiuse=False,
            )
        )

    if not user_profile.is_realm_admin:
        # We do not return multiuse invites to non-admin users.
        return invites

    multiuse_confirmation_objs = Confirmation.objects.filter(
        realm=user_profile.realm, type=Confirmation.MULTIUSE_INVITE
    ).filter(Q(expiry_date__gte=timezone_now()) | Q(expiry_date=None))
    for confirmation_obj in multiuse_confirmation_objs:
        invite = confirmation_obj.content_object
        assert invite is not None
        invites.append(
            dict(
                invited_by_user_id=invite.referred_by.id,
                invited=datetime_to_timestamp(confirmation_obj.date_sent),
                expiry_date=get_invitation_expiry_date(confirmation_obj),
                id=invite.id,
                link_url=confirmation_url(
                    confirmation_obj.confirmation_key,
                    user_profile.realm,
                    Confirmation.MULTIUSE_INVITE,
                ),
                invited_as=invite.invited_as,
                is_multiuse=True,
            )
        )
    return invites


def get_valid_invite_confirmations_generated_by_user(
    user_profile: UserProfile,
) -> List[Confirmation]:
    prereg_user_ids = filter_to_valid_prereg_users(
        PreregistrationUser.objects.filter(referred_by=user_profile)
    ).values_list("id", flat=True)
    confirmations = list(
        Confirmation.objects.filter(type=Confirmation.INVITATION, object_id__in=prereg_user_ids)
    )

    multiuse_invite_ids = MultiuseInvite.objects.filter(referred_by=user_profile).values_list(
        "id", flat=True
    )
    confirmations += list(
        Confirmation.objects.filter(
            type=Confirmation.MULTIUSE_INVITE,
            object_id__in=multiuse_invite_ids,
        ).filter(Q(expiry_date__gte=timezone_now()) | Q(expiry_date=None))
    )

    return confirmations


def revoke_invites_generated_by_user(user_profile: UserProfile) -> None:
    confirmations_to_revoke = get_valid_invite_confirmations_generated_by_user(user_profile)
    now = timezone_now()
    for confirmation in confirmations_to_revoke:
        confirmation.expiry_date = now

    Confirmation.objects.bulk_update(confirmations_to_revoke, ["expiry_date"])
    if len(confirmations_to_revoke):
        notify_invites_changed(realm=user_profile.realm)


def do_create_multiuse_invite_link(
    referred_by: UserProfile,
    invited_as: int,
    invite_expires_in_minutes: Optional[int],
    streams: Sequence[Stream] = [],
) -> str:
    realm = referred_by.realm
    invite = MultiuseInvite.objects.create(realm=realm, referred_by=referred_by)
    if streams:
        invite.streams.set(streams)
    invite.invited_as = invited_as
    invite.save()
    notify_invites_changed(referred_by.realm)
    return create_confirmation_link(
        invite, Confirmation.MULTIUSE_INVITE, validity_in_minutes=invite_expires_in_minutes
    )


def do_revoke_user_invite(prereg_user: PreregistrationUser) -> None:
    email = prereg_user.email
    realm = prereg_user.realm
    assert realm is not None

    # Delete both the confirmation objects and the prereg_user object.
    # TODO: Probably we actually want to set the confirmation objects
    # to a "revoked" status so that we can give the invited user a better
    # error message.
    content_type = ContentType.objects.get_for_model(PreregistrationUser)
    Confirmation.objects.filter(content_type=content_type, object_id=prereg_user.id).delete()
    prereg_user.delete()
    clear_scheduled_invitation_emails(email)
    notify_invites_changed(realm)


def do_revoke_multi_use_invite(multiuse_invite: MultiuseInvite) -> None:
    realm = multiuse_invite.referred_by.realm

    content_type = ContentType.objects.get_for_model(MultiuseInvite)
    Confirmation.objects.filter(content_type=content_type, object_id=multiuse_invite.id).delete()
    multiuse_invite.delete()
    notify_invites_changed(realm)


def do_resend_user_invite_email(prereg_user: PreregistrationUser) -> int:
    # These are two structurally for the caller's code path.
    assert prereg_user.referred_by is not None
    assert prereg_user.realm is not None

    check_invite_limit(prereg_user.referred_by.realm, 1)

    prereg_user.invited_at = timezone_now()
    prereg_user.save()

    expiry_date = prereg_user.confirmation.get().expiry_date
    if expiry_date is None:
        invite_expires_in_minutes = None
    else:
        # The resent invitation is reset to expire as long after the
        # reminder is sent as it lasted originally.
        invite_expires_in_minutes = (expiry_date - prereg_user.invited_at).total_seconds() / 60
    prereg_user.confirmation.clear()

    do_increment_logging_stat(
        prereg_user.realm, COUNT_STATS["invites_sent::day"], None, prereg_user.invited_at
    )

    clear_scheduled_invitation_emails(prereg_user.email)
    # We don't store the custom email body, so just set it to None
    event = {
        "prereg_id": prereg_user.id,
        "referrer_id": prereg_user.referred_by.id,
        "email_language": prereg_user.referred_by.realm.default_language,
        "invite_expires_in_minutes": invite_expires_in_minutes,
    }
    queue_json_publish("invites", event)

    return datetime_to_timestamp(prereg_user.invited_at)
