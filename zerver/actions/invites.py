import logging
from datetime import datetime, timedelta
from typing import Any, Collection, Dict, List, Optional, Sequence, Set, Tuple

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q, QuerySet, Sum
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from zxcvbn import zxcvbn

from analytics.lib.counts import COUNT_STATS, do_increment_logging_stat
from analytics.models import RealmCount
from confirmation import settings as confirmation_settings
from confirmation.models import (
    Confirmation,
    confirmation_url_for,
    create_confirmation_link,
    create_confirmation_object,
)
from zerver.context_processors import common_context
from zerver.lib.email_validation import (
    get_existing_user_errors,
    get_realm_email_validator,
    validate_email_is_valid,
)
from zerver.lib.exceptions import InvitationError
from zerver.lib.invites import notify_invites_changed
from zerver.lib.queue import queue_event_on_commit
from zerver.lib.send_email import FromAddress, clear_scheduled_invitation_emails, send_future_email
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.utils import assert_is_not_none
from zerver.models import Message, MultiuseInvite, PreregistrationUser, Realm, Stream, UserProfile
from zerver.models.prereg_users import filter_to_valid_prereg_users


def estimate_recent_invites(realms: Collection[Realm] | QuerySet[Realm], *, days: int) -> int:
    """An upper bound on the number of invites sent in the last `days` days"""
    recent_invites = RealmCount.objects.filter(
        realm__in=realms,
        property="invites_sent::day",
        end_time__gte=timezone_now() - timedelta(days=days),
    ).aggregate(Sum("value"))["value__sum"]
    if recent_invites is None:
        return 0
    return recent_invites


def too_many_recent_realm_invites(realm: Realm, num_invitees: int) -> bool:
    # Basic check that we're blow the realm-set limit
    recent_invites = estimate_recent_invites([realm], days=1)
    if num_invitees + recent_invites > realm.max_invites:
        return True

    if realm.plan_type != Realm.PLAN_TYPE_LIMITED:
        return False
    if realm.max_invites != settings.INVITES_DEFAULT_REALM_DAILY_MAX:
        return False

    # If they're a non-paid plan with default invitation limits,
    # we further limit how many invitations can be sent in a day
    # as a function of how many current users they have. The
    # allowed ratio has some heuristics to lock down likely-spammy
    # realms.  This ratio likely only matters for the first
    # handful of invites; if those users accept, then the realm is
    # unlikely to hit these limits.  If a real realm hits them,
    # the resulting message suggests that they contact support if
    # they have a real use case.
    warning_flags = []
    if zxcvbn(realm.string_id)["score"] == 4:
        # Very high entropy realm names are suspicious
        warning_flags.append("random-realm-name")

    if not realm.description:
        warning_flags.append("no-realm-description")

    if realm.icon_source == Realm.ICON_FROM_GRAVATAR:
        warning_flags.append("no-realm-icon")

    if realm.date_created >= timezone_now() - timedelta(hours=1):
        warning_flags.append("realm-created-in-last-hour")

    current_user_count = UserProfile.objects.filter(
        realm=realm, is_bot=False, is_active=True
    ).count()
    if current_user_count == 1:
        warning_flags.append("only-one-user")

    estimated_sent = RealmCount.objects.filter(
        realm=realm, property="messages_sent:message_type:day"
    ).aggregate(messages=Sum("value"))
    if (
        not estimated_sent["messages"]
        # Only after we've done the rough-estimate check, take the
        # time to do the exact check:
        and not Message.objects.filter(
            # Uses index: zerver_message_realm_sender_recipient (prefix)
            realm=realm,
            sender__is_bot=False,
        ).exists()
    ):
        warning_flags.append("no-messages-sent")

    if len(warning_flags) == 6:
        permitted_ratio = 2
    elif len(warning_flags) >= 3:
        permitted_ratio = 3
    else:
        permitted_ratio = 5

    ratio = (num_invitees + recent_invites) / current_user_count
    logging.log(
        logging.WARNING if ratio > permitted_ratio else logging.INFO,
        "%s (!: %s) inviting %d more, have %d recent, but only %d current users.  Ratio %.1f, %d allowed",
        realm.string_id,
        ",".join(warning_flags),
        num_invitees,
        recent_invites,
        current_user_count,
        ratio,
        permitted_ratio,
    )
    return ratio > permitted_ratio


def check_invite_limit(realm: Realm, num_invitees: int) -> None:
    """Discourage using invitation emails as a vector for carrying spam."""
    msg = _(
        "To protect users, Zulip limits the number of invitations you can send in one day. Because you have reached the limit, no invitations were sent."
    )
    if not settings.OPEN_REALM_CREATION:
        return

    if too_many_recent_realm_invites(realm, num_invitees):
        raise InvitationError(
            msg,
            [],
            sent_invitations=False,
            daily_limit_reached=True,
        )

    default_max = settings.INVITES_DEFAULT_REALM_DAILY_MAX
    newrealm_age = timedelta(days=settings.INVITES_NEW_REALM_DAYS)
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


@transaction.atomic
def do_invite_users(
    user_profile: UserProfile,
    invitee_emails: Collection[str],
    streams: Collection[Stream],
    *,
    invite_expires_in_minutes: Optional[int],
    invite_as: int = PreregistrationUser.INVITE_AS["MEMBER"],
) -> List[Tuple[str, str, bool]]:
    num_invites = len(invitee_emails)

    # Lock the realm, since we need to not race with other invitations
    realm = Realm.objects.select_for_update().get(id=user_profile.realm_id)
    check_invite_limit(realm, num_invites)

    if settings.BILLING_ENABLED:
        from corporate.lib.registration import check_spare_licenses_available_for_inviting_new_users

        if invite_as == PreregistrationUser.INVITE_AS["GUEST_USER"]:
            check_spare_licenses_available_for_inviting_new_users(
                realm, extra_guests_count=num_invites
            )
        else:
            check_spare_licenses_available_for_inviting_new_users(
                realm, extra_non_guests_count=num_invites
            )

    if not realm.invite_required:
        # Inhibit joining an open realm to send spam invitations.
        min_age = timedelta(days=settings.INVITES_MIN_USER_AGE_DAYS)
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
    validate_email_allowed_in_realm = get_realm_email_validator(realm)
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
    error_dict = get_existing_user_errors(realm, good_emails)

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

    # Now that we are past all the possible errors, we actually create
    # the PreregistrationUser objects and trigger the email invitations.
    for email in validated_emails:
        # The logged in user is the referrer.
        prereg_user = PreregistrationUser(
            email=email, referred_by=user_profile, invited_as=invite_as, realm=realm
        )
        prereg_user.save()
        stream_ids = [stream.id for stream in streams]
        prereg_user.streams.set(stream_ids)

        confirmation = create_confirmation_object(
            prereg_user, Confirmation.INVITATION, validity_in_minutes=invite_expires_in_minutes
        )
        do_send_user_invite_email(
            prereg_user,
            confirmation=confirmation,
            invite_expires_in_minutes=invite_expires_in_minutes,
        )

    notify_invites_changed(realm, changed_invite_referrer=user_profile)

    return skipped


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

    if user_profile.is_realm_admin:
        multiuse_confirmation_objs = Confirmation.objects.filter(
            realm=user_profile.realm, type=Confirmation.MULTIUSE_INVITE
        ).filter(Q(expiry_date__gte=timezone_now()) | Q(expiry_date=None))
    else:
        multiuse_invite_ids = MultiuseInvite.objects.filter(referred_by=user_profile).values_list(
            "id", flat=True
        )
        multiuse_confirmation_objs = Confirmation.objects.filter(
            type=Confirmation.MULTIUSE_INVITE,
            object_id__in=multiuse_invite_ids,
        ).filter(Q(expiry_date__gte=timezone_now()) | Q(expiry_date=None))

    for confirmation_obj in multiuse_confirmation_objs:
        invite = confirmation_obj.content_object
        assert invite is not None

        # This should be impossible, because revoking a multiuse invite
        # deletes the Confirmation object, so it couldn't have been fetched above.
        assert invite.status != confirmation_settings.STATUS_REVOKED
        invites.append(
            dict(
                invited_by_user_id=invite.referred_by.id,
                invited=datetime_to_timestamp(confirmation_obj.date_sent),
                expiry_date=get_invitation_expiry_date(confirmation_obj),
                id=invite.id,
                link_url=confirmation_url_for(confirmation_obj),
                invited_as=invite.invited_as,
                is_multiuse=True,
            )
        )
    return invites


@transaction.atomic
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
    notify_invites_changed(referred_by.realm, changed_invite_referrer=referred_by)
    return create_confirmation_link(
        invite, Confirmation.MULTIUSE_INVITE, validity_in_minutes=invite_expires_in_minutes
    )


@transaction.atomic
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
    notify_invites_changed(realm, changed_invite_referrer=prereg_user.referred_by)


@transaction.atomic
def do_revoke_multi_use_invite(multiuse_invite: MultiuseInvite) -> None:
    realm = multiuse_invite.referred_by.realm

    content_type = ContentType.objects.get_for_model(MultiuseInvite)
    Confirmation.objects.filter(content_type=content_type, object_id=multiuse_invite.id).delete()
    multiuse_invite.status = confirmation_settings.STATUS_REVOKED
    multiuse_invite.save(update_fields=["status"])
    notify_invites_changed(realm, changed_invite_referrer=multiuse_invite.referred_by)


@transaction.atomic
def do_send_user_invite_email(
    prereg_user: PreregistrationUser,
    *,
    confirmation: Optional[Confirmation] = None,
    event_time: Optional[datetime] = None,
    invite_expires_in_minutes: Optional[float] = None,
) -> None:
    # Take a lock on the realm, so we can check for invitation limits without races
    realm_id = assert_is_not_none(prereg_user.realm_id)
    realm = Realm.objects.select_for_update().get(id=realm_id)
    check_invite_limit(realm, 1)
    referrer = assert_is_not_none(prereg_user.referred_by)

    if event_time is None:
        event_time = prereg_user.invited_at
    do_increment_logging_stat(realm, COUNT_STATS["invites_sent::day"], None, event_time)

    if confirmation is None:
        confirmation = prereg_user.confirmation.get()

    event = {
        "template_prefix": "zerver/emails/invitation",
        "to_emails": [prereg_user.email],
        "from_address": FromAddress.tokenized_no_reply_address(),
        "language": realm.default_language,
        "context": {
            "referrer_full_name": referrer.full_name,
            "referrer_email": referrer.delivery_email,
            "activate_url": confirmation_url_for(confirmation),
            "referrer_realm_name": realm.name,
            "corporate_enabled": settings.CORPORATE_ENABLED,
        },
        "realm_id": realm.id,
    }
    queue_event_on_commit("email_senders", event)

    clear_scheduled_invitation_emails(prereg_user.email)
    if invite_expires_in_minutes is None and confirmation.expiry_date is not None:
        # Pull the remaining time from the confirmation object
        invite_expires_in_minutes = (confirmation.expiry_date - event_time).total_seconds() / 60

    if invite_expires_in_minutes is None or invite_expires_in_minutes < 4 * 24 * 60:
        # We do not queue reminder email for never expiring
        # invitations. This is probably a low importance bug; it
        # would likely be more natural to send a reminder after 7
        # days.
        return

    context = common_context(referrer)
    context.update(
        activate_url=confirmation_url_for(confirmation),
        referrer_name=referrer.full_name,
        referrer_email=referrer.delivery_email,
        referrer_realm_name=realm.name,
    )
    send_future_email(
        "zerver/emails/invitation_reminder",
        realm,
        to_emails=[prereg_user.email],
        from_address=FromAddress.tokenized_no_reply_placeholder,
        language=realm.default_language,
        context=context,
        delay=timedelta(minutes=invite_expires_in_minutes - (2 * 24 * 60)),
    )
