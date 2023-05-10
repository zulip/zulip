import datetime
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

import orjson
from django.conf import settings
from django.db import transaction
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from django.utils.translation import override as override_language

from analytics.lib.counts import COUNT_STATS, do_increment_logging_stat
from confirmation import settings as confirmation_settings
from zerver.actions.default_streams import get_default_streams_for_realm
from zerver.actions.invites import notify_invites_changed
from zerver.actions.message_send import internal_send_private_message, internal_send_stream_message
from zerver.actions.streams import bulk_add_subscriptions, send_peer_subscriber_events
from zerver.actions.user_groups import do_send_user_group_members_update_event
from zerver.actions.users import change_user_is_active, get_service_dicts_for_bot
from zerver.lib.avatar import avatar_url
from zerver.lib.create_user import create_user
from zerver.lib.email_notifications import enqueue_welcome_emails
from zerver.lib.mention import silent_mention_syntax_for_user
from zerver.lib.send_email import clear_scheduled_invitation_emails
from zerver.lib.stream_subscription import bulk_get_subscriber_peer_info
from zerver.lib.streams import get_signups_stream
from zerver.lib.user_counts import realm_user_count, realm_user_count_by_role
from zerver.lib.user_groups import get_system_user_group_for_user
from zerver.lib.users import (
    can_access_delivery_email,
    format_user_row,
    get_api_key,
    user_profile_to_user_row,
)
from zerver.models import (
    DefaultStreamGroup,
    Message,
    PreregistrationUser,
    Realm,
    RealmAuditLog,
    Recipient,
    Stream,
    Subscription,
    UserGroup,
    UserGroupMembership,
    UserMessage,
    UserProfile,
    bot_owner_user_ids,
    get_realm,
    get_system_bot,
)
from zerver.tornado.django_api import send_event

if settings.BILLING_ENABLED:
    from corporate.lib.stripe import update_license_ledger_if_needed


ONBOARDING_TOTAL_MESSAGES = 1000
ONBOARDING_UNREAD_MESSAGES = 20
ONBOARDING_RECENT_TIMEDELTA = datetime.timedelta(weeks=1)

DEFAULT_HISTORICAL_FLAGS = UserMessage.flags.historical | UserMessage.flags.read


def create_historical_user_messages(
    *, user_id: int, message_ids: Iterable[int], flags: int = DEFAULT_HISTORICAL_FLAGS
) -> None:
    # Users can see and interact with messages sent to streams with
    # public history for which they do not have a UserMessage because
    # they were not a subscriber at the time the message was sent.
    # In order to add emoji reactions or mutate message flags for
    # those messages, we create UserMessage objects for those messages;
    # these have the special historical flag which keeps track of the
    # fact that the user did not receive the message at the time it was sent.
    UserMessage.objects.bulk_create(
        UserMessage(user_profile_id=user_id, message_id=message_id, flags=flags)
        for message_id in message_ids
    )


def send_message_to_signup_notification_stream(
    sender: UserProfile, realm: Realm, message: str
) -> None:
    signup_notifications_stream = realm.get_signup_notifications_stream()
    if signup_notifications_stream is None:
        return

    with override_language(realm.default_language):
        topic_name = _("signups")

    internal_send_stream_message(sender, signup_notifications_stream, topic_name, message)


def notify_new_user(user_profile: UserProfile) -> None:
    user_count = realm_user_count(user_profile.realm)
    sender_email = settings.NOTIFICATION_BOT
    sender = get_system_bot(sender_email, user_profile.realm_id)

    is_first_user = user_count == 1
    if not is_first_user:
        with override_language(user_profile.realm.default_language):
            message = _("{user} just signed up for Zulip. (total: {user_count})").format(
                user=silent_mention_syntax_for_user(user_profile), user_count=user_count
            )

        if settings.BILLING_ENABLED:
            from corporate.lib.registration import generate_licenses_low_warning_message_if_required

            licenses_low_warning_message = generate_licenses_low_warning_message_if_required(
                user_profile.realm
            )
            if licenses_low_warning_message is not None:
                message += "\n"
                message += licenses_low_warning_message

        send_message_to_signup_notification_stream(sender, user_profile.realm, message)

    # We also send a notification to the Zulip administrative realm
    admin_realm = get_realm(settings.SYSTEM_BOT_REALM)
    admin_realm_sender = get_system_bot(sender_email, admin_realm.id)
    try:
        # Check whether the stream exists
        signups_stream = get_signups_stream(admin_realm)
        # We intentionally use the same strings as above to avoid translation burden.
        with override_language(admin_realm.default_language):
            message = _("{user} just signed up for Zulip. (total: {user_count})").format(
                user=f"{user_profile.full_name} <`{user_profile.email}`>", user_count=user_count
            )
        internal_send_stream_message(
            admin_realm_sender, signups_stream, user_profile.realm.display_subdomain, message
        )

    except Stream.DoesNotExist:
        # If the signups stream hasn't been created in the admin
        # realm, don't auto-create it to send to it; just do nothing.
        pass


def add_new_user_history(user_profile: UserProfile, streams: Iterable[Stream]) -> None:
    """Give you the last ONBOARDING_TOTAL_MESSAGES messages on your public
    streams, so you have something to look at in your home view once
    you finish the tutorial.  The most recent ONBOARDING_UNREAD_MESSAGES
    are marked unread.
    """
    one_week_ago = timezone_now() - ONBOARDING_RECENT_TIMEDELTA

    recipient_ids = [stream.recipient_id for stream in streams if not stream.invite_only]
    recent_messages = Message.objects.filter(
        recipient_id__in=recipient_ids, date_sent__gt=one_week_ago
    ).order_by("-id")
    message_ids_to_use = list(
        reversed(recent_messages.values_list("id", flat=True)[0:ONBOARDING_TOTAL_MESSAGES])
    )
    if len(message_ids_to_use) == 0:
        return

    # Handle the race condition where a message arrives between
    # bulk_add_subscriptions above and the Message query just above
    already_ids = set(
        UserMessage.objects.filter(
            message_id__in=message_ids_to_use, user_profile=user_profile
        ).values_list("message_id", flat=True)
    )

    # Mark the newest ONBOARDING_UNREAD_MESSAGES as unread.
    marked_unread = 0
    ums_to_create = []
    for message_id in reversed(message_ids_to_use):
        if message_id in already_ids:
            continue

        um = UserMessage(user_profile=user_profile, message_id=message_id)
        if marked_unread < ONBOARDING_UNREAD_MESSAGES:
            marked_unread += 1
        else:
            um.flags = UserMessage.flags.read
        ums_to_create.append(um)

    UserMessage.objects.bulk_create(reversed(ums_to_create))


# Does the processing for a new user account:
# * Subscribes to default/invitation streams
# * Fills in some recent historical messages
# * Notifies other users in realm and Zulip about the signup
# * Deactivates PreregistrationUser objects
def process_new_human_user(
    user_profile: UserProfile,
    prereg_user: Optional[PreregistrationUser] = None,
    default_stream_groups: Sequence[DefaultStreamGroup] = [],
    realm_creation: bool = False,
) -> None:
    realm = user_profile.realm

    mit_beta_user = realm.is_zephyr_mirror_realm
    if prereg_user is not None:
        streams: List[Stream] = list(prereg_user.streams.all())
        acting_user: Optional[UserProfile] = prereg_user.referred_by

        # A PregistrationUser should not be used for another UserProfile
        assert prereg_user.created_user is None, "PregistrationUser should not be reused"
    else:
        streams = []
        acting_user = None

    user_was_invited = prereg_user is not None and (
        prereg_user.referred_by is not None or prereg_user.multiuse_invite is not None
    )
    # If the Preregistration object didn't explicitly list some streams (it happens when user
    # directly signs up without any invitation), we add the default streams
    if len(streams) == 0 and not user_was_invited:
        streams = get_default_subs(user_profile)

    for default_stream_group in default_stream_groups:
        default_stream_group_streams = default_stream_group.streams.all()
        for stream in default_stream_group_streams:
            if stream not in streams:
                streams.append(stream)

    bulk_add_subscriptions(
        realm,
        streams,
        [user_profile],
        from_user_creation=True,
        acting_user=acting_user,
    )

    add_new_user_history(user_profile, streams)

    # mit_beta_users don't have a referred_by field
    if (
        not mit_beta_user
        and prereg_user is not None
        and prereg_user.referred_by is not None
        and prereg_user.referred_by.is_active
    ):
        # This is a cross-realm private message.
        with override_language(prereg_user.referred_by.default_language):
            internal_send_private_message(
                get_system_bot(settings.NOTIFICATION_BOT, prereg_user.referred_by.realm_id),
                prereg_user.referred_by,
                _("{user} accepted your invitation to join Zulip!").format(
                    user=f"{user_profile.full_name} <`{user_profile.email}`>"
                ),
            )

    # For the sake of tracking the history of UserProfiles,
    # we want to tie the newly created user to the PreregistrationUser
    # it was created from.
    if prereg_user is not None:
        prereg_user.status = confirmation_settings.STATUS_USED
        prereg_user.created_user = user_profile
        prereg_user.save(update_fields=["status", "created_user"])

    # In the special case of realm creation, there can be no additional PreregistrationUser
    # for us to want to modify - because other realm_creation PreregistrationUsers should be
    # left usable for creating different realms.
    if not realm_creation:
        # Mark any other PreregistrationUsers in the realm that are STATUS_USED as
        # inactive so we can keep track of the PreregistrationUser we
        # actually used for analytics.
        if prereg_user is not None:
            PreregistrationUser.objects.filter(
                email__iexact=user_profile.delivery_email, realm=user_profile.realm
            ).exclude(id=prereg_user.id).update(status=confirmation_settings.STATUS_REVOKED)
        else:
            PreregistrationUser.objects.filter(
                email__iexact=user_profile.delivery_email, realm=user_profile.realm
            ).update(status=confirmation_settings.STATUS_REVOKED)

        if prereg_user is not None and prereg_user.referred_by is not None:
            notify_invites_changed(user_profile.realm)

    notify_new_user(user_profile)
    # Clear any scheduled invitation emails to prevent them
    # from being sent after the user is created.
    clear_scheduled_invitation_emails(user_profile.delivery_email)
    if realm.send_welcome_emails:
        enqueue_welcome_emails(user_profile, realm_creation)

    # We have an import loop here; it's intentional, because we want
    # to keep all the onboarding code in zerver/lib/onboarding.py.
    from zerver.lib.onboarding import send_initial_pms

    send_initial_pms(user_profile)


def notify_created_user(user_profile: UserProfile) -> None:
    user_row = user_profile_to_user_row(user_profile)
    person = format_user_row(
        user_profile.realm,
        user_profile,
        user_row,
        # Since we don't know what the client
        # supports at this point in the code, we
        # just assume client_gravatar and
        # user_avatar_url_field_optional = False :(
        client_gravatar=False,
        user_avatar_url_field_optional=False,
        # We assume there's no custom profile
        # field data for a new user; initial
        # values are expected to be added in a
        # later event.
        custom_profile_field_data={},
    )

    active_users = user_profile.realm.get_active_users()
    user_ids_with_real_email_access = []
    user_ids_without_real_email_access = []
    for user in active_users:
        if can_access_delivery_email(
            user, user_profile.id, user_profile.realm.email_address_visibility
        ):
            user_ids_with_real_email_access.append(user.id)
        else:
            user_ids_without_real_email_access.append(user.id)

    if user_ids_with_real_email_access:
        person["delivery_email"] = user_profile.delivery_email
        event: Dict[str, Any] = dict(type="realm_user", op="add", person=person)
        send_event(user_profile.realm, event, user_ids_with_real_email_access)

    if user_ids_without_real_email_access:
        del person["delivery_email"]
        event = dict(type="realm_user", op="add", person=person)
        send_event(user_profile.realm, event, user_ids_without_real_email_access)


def created_bot_event(user_profile: UserProfile) -> Dict[str, Any]:
    def stream_name(stream: Optional[Stream]) -> Optional[str]:
        if not stream:
            return None
        return stream.name

    default_sending_stream_name = stream_name(user_profile.default_sending_stream)
    default_events_register_stream_name = stream_name(user_profile.default_events_register_stream)

    bot = dict(
        email=user_profile.email,
        user_id=user_profile.id,
        full_name=user_profile.full_name,
        bot_type=user_profile.bot_type,
        is_active=user_profile.is_active,
        api_key=get_api_key(user_profile),
        default_sending_stream=default_sending_stream_name,
        default_events_register_stream=default_events_register_stream_name,
        default_all_public_streams=user_profile.default_all_public_streams,
        avatar_url=avatar_url(user_profile),
        services=get_service_dicts_for_bot(user_profile.id),
    )

    # Set the owner key only when the bot has an owner.
    # The default bots don't have an owner. So don't
    # set the owner key while reactivating them.
    if user_profile.bot_owner is not None:
        bot["owner_id"] = user_profile.bot_owner.id

    return dict(type="realm_bot", op="add", bot=bot)


def notify_created_bot(user_profile: UserProfile) -> None:
    event = created_bot_event(user_profile)
    send_event(user_profile.realm, event, bot_owner_user_ids(user_profile))


def do_create_user(
    email: str,
    password: Optional[str],
    realm: Realm,
    full_name: str,
    bot_type: Optional[int] = None,
    role: Optional[int] = None,
    bot_owner: Optional[UserProfile] = None,
    tos_version: Optional[str] = None,
    timezone: str = "",
    avatar_source: str = UserProfile.AVATAR_FROM_GRAVATAR,
    default_language: str = "en",
    default_sending_stream: Optional[Stream] = None,
    default_events_register_stream: Optional[Stream] = None,
    default_all_public_streams: Optional[bool] = None,
    prereg_user: Optional[PreregistrationUser] = None,
    default_stream_groups: Sequence[DefaultStreamGroup] = [],
    source_profile: Optional[UserProfile] = None,
    realm_creation: bool = False,
    *,
    acting_user: Optional[UserProfile],
    enable_marketing_emails: bool = True,
) -> UserProfile:
    with transaction.atomic():
        user_profile = create_user(
            email=email,
            password=password,
            realm=realm,
            full_name=full_name,
            role=role,
            bot_type=bot_type,
            bot_owner=bot_owner,
            tos_version=tos_version,
            timezone=timezone,
            avatar_source=avatar_source,
            default_language=default_language,
            default_sending_stream=default_sending_stream,
            default_events_register_stream=default_events_register_stream,
            default_all_public_streams=default_all_public_streams,
            source_profile=source_profile,
            enable_marketing_emails=enable_marketing_emails,
        )

        event_time = user_profile.date_joined
        if not acting_user:
            acting_user = user_profile
        RealmAuditLog.objects.create(
            realm=user_profile.realm,
            acting_user=acting_user,
            modified_user=user_profile,
            event_type=RealmAuditLog.USER_CREATED,
            event_time=event_time,
            extra_data=orjson.dumps(
                {
                    RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(user_profile.realm),
                }
            ).decode(),
        )

        if realm_creation:
            # If this user just created a realm, make sure they are
            # properly tagged as the creator of the realm.
            realm_creation_audit_log = (
                RealmAuditLog.objects.filter(event_type=RealmAuditLog.REALM_CREATED, realm=realm)
                .order_by("id")
                .last()
            )
            assert realm_creation_audit_log is not None
            realm_creation_audit_log.acting_user = user_profile
            realm_creation_audit_log.save(update_fields=["acting_user"])

        do_increment_logging_stat(
            user_profile.realm,
            COUNT_STATS["active_users_log:is_bot:day"],
            user_profile.is_bot,
            event_time,
        )
        if settings.BILLING_ENABLED:
            update_license_ledger_if_needed(user_profile.realm, event_time)

        system_user_group = get_system_user_group_for_user(user_profile)
        UserGroupMembership.objects.create(user_profile=user_profile, user_group=system_user_group)

        if user_profile.role == UserProfile.ROLE_MEMBER and not user_profile.is_provisional_member:
            full_members_system_group = UserGroup.objects.get(
                name=UserGroup.FULL_MEMBERS_GROUP_NAME,
                realm=user_profile.realm,
                is_system_group=True,
            )
            UserGroupMembership.objects.create(
                user_profile=user_profile, user_group=full_members_system_group
            )

    # Note that for bots, the caller will send an additional event
    # with bot-specific info like services.
    notify_created_user(user_profile)

    do_send_user_group_members_update_event("add_members", system_user_group, [user_profile.id])
    if user_profile.role == UserProfile.ROLE_MEMBER and not user_profile.is_provisional_member:
        do_send_user_group_members_update_event(
            "add_members", full_members_system_group, [user_profile.id]
        )

    if bot_type is None:
        process_new_human_user(
            user_profile,
            prereg_user=prereg_user,
            default_stream_groups=default_stream_groups,
            realm_creation=realm_creation,
        )

    if realm_creation:
        assert realm.signup_notifications_stream is not None
        bulk_add_subscriptions(
            realm, [realm.signup_notifications_stream], [user_profile], acting_user=None
        )

        from zerver.lib.onboarding import send_initial_realm_messages

        send_initial_realm_messages(realm)

    return user_profile


def do_activate_mirror_dummy_user(
    user_profile: UserProfile, *, acting_user: Optional[UserProfile]
) -> None:
    """Called to have a user "take over" a "mirror dummy" user
    (i.e. is_mirror_dummy=True) account when they sign up with the
    same email address.

    Essentially, the result should be as though we had created the
    UserProfile just now with do_create_user, except that the mirror
    dummy user may appear as the recipient or sender of messages from
    before their account was fully created.

    TODO: This function likely has bugs resulting from this being a
    parallel code path to do_create_user; e.g. it likely does not
    handle preferences or default streams properly.
    """
    with transaction.atomic():
        change_user_is_active(user_profile, True)
        user_profile.is_mirror_dummy = False
        user_profile.set_unusable_password()
        user_profile.date_joined = timezone_now()
        user_profile.tos_version = settings.TERMS_OF_SERVICE_VERSION
        user_profile.save(
            update_fields=["date_joined", "password", "is_mirror_dummy", "tos_version"]
        )

        event_time = user_profile.date_joined
        RealmAuditLog.objects.create(
            realm=user_profile.realm,
            modified_user=user_profile,
            acting_user=acting_user,
            event_type=RealmAuditLog.USER_ACTIVATED,
            event_time=event_time,
            extra_data=orjson.dumps(
                {
                    RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(user_profile.realm),
                }
            ).decode(),
        )
        do_increment_logging_stat(
            user_profile.realm,
            COUNT_STATS["active_users_log:is_bot:day"],
            user_profile.is_bot,
            event_time,
        )
        if settings.BILLING_ENABLED:
            update_license_ledger_if_needed(user_profile.realm, event_time)

    notify_created_user(user_profile)


def do_reactivate_user(user_profile: UserProfile, *, acting_user: Optional[UserProfile]) -> None:
    """Reactivate a user that had previously been deactivated"""
    with transaction.atomic():
        change_user_is_active(user_profile, True)

        event_time = timezone_now()
        RealmAuditLog.objects.create(
            realm=user_profile.realm,
            modified_user=user_profile,
            acting_user=acting_user,
            event_type=RealmAuditLog.USER_REACTIVATED,
            event_time=event_time,
            extra_data=orjson.dumps(
                {
                    RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(user_profile.realm),
                }
            ).decode(),
        )
        do_increment_logging_stat(
            user_profile.realm,
            COUNT_STATS["active_users_log:is_bot:day"],
            user_profile.is_bot,
            event_time,
        )
        if settings.BILLING_ENABLED:
            update_license_ledger_if_needed(user_profile.realm, event_time)

    notify_created_user(user_profile)

    if user_profile.is_bot:
        notify_created_bot(user_profile)

    subscribed_recipient_ids = Subscription.objects.filter(
        user_profile_id=user_profile.id, active=True, recipient__type=Recipient.STREAM
    ).values_list("recipient__type_id", flat=True)
    subscribed_streams = Stream.objects.filter(id__in=subscribed_recipient_ids, deactivated=False)
    subscriber_peer_info = bulk_get_subscriber_peer_info(
        realm=user_profile.realm,
        streams=subscribed_streams,
    )

    altered_user_dict: Dict[int, Set[int]] = defaultdict(set)
    for stream in subscribed_streams:
        altered_user_dict[stream.id] = {user_profile.id}

    stream_dict = {stream.id: stream for stream in subscribed_streams}

    send_peer_subscriber_events(
        op="peer_add",
        realm=user_profile.realm,
        altered_user_dict=altered_user_dict,
        stream_dict=stream_dict,
        private_peer_dict=subscriber_peer_info.private_peer_dict,
    )


def get_default_subs(user_profile: UserProfile) -> List[Stream]:
    # Right now default streams are realm-wide.  This wrapper gives us flexibility
    # to some day further customize how we set up default streams for new users.
    return get_default_streams_for_realm(user_profile.realm_id)
