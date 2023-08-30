import datetime
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from django.conf import settings
from django.db import transaction
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from django.utils.translation import override as override_language

from analytics.lib.counts import COUNT_STATS, do_increment_logging_stat
from confirmation import settings as confirmation_settings
from zerver.actions.invites import notify_invites_changed
from zerver.actions.message_send import internal_send_private_message, internal_send_stream_message
from zerver.actions.streams import bulk_add_subscriptions, send_peer_subscriber_events
from zerver.actions.user_groups import do_send_user_group_members_update_event
from zerver.actions.users import change_user_is_active, get_service_dicts_for_bot
from zerver.lib.avatar import avatar_url
from zerver.lib.create_user import create_user
from zerver.lib.default_streams import get_slim_realm_default_streams
from zerver.lib.email_notifications import enqueue_welcome_emails, send_account_registered_email
from zerver.lib.mention import silent_mention_syntax_for_user
from zerver.lib.send_email import clear_scheduled_invitation_emails
from zerver.lib.stream_subscription import bulk_get_subscriber_peer_info
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
    PreregistrationRealm,
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
    get_system_bot,
)
from zerver.tornado.django_api import send_event_on_commit

if settings.BILLING_ENABLED:
    from corporate.lib.stripe import update_license_ledger_if_needed


MAX_NUM_ONBOARDING_MESSAGES = 1000
MAX_NUM_ONBOARDING_UNREAD_MESSAGES = 20

# We don't want to mark years-old messages as unread, since that might
# feel like Zulip is buggy, but in low-traffic or bursty-traffic
# organizations, it's reasonable for the most recent 20 messages to be
# several weeks old and still be a good place to start.
ONBOARDING_RECENT_TIMEDELTA = datetime.timedelta(weeks=12)

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


def set_up_streams_for_new_human_user(
    *,
    user_profile: UserProfile,
    prereg_user: Optional[PreregistrationUser] = None,
    default_stream_groups: Sequence[DefaultStreamGroup] = [],
) -> None:
    realm = user_profile.realm

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

    # If the Preregistration object didn't explicitly list some streams (it
    # happens when user directly signs up without any invitation), we add the
    # default streams for the realm. Note that we are fine with "slim" Stream
    # objects for calling bulk_add_subscriptions and add_new_user_history,
    # which we verify in StreamSetupTest tests that check query counts.
    if len(streams) == 0 and not user_was_invited:
        streams = get_slim_realm_default_streams(realm.id)

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


def add_new_user_history(user_profile: UserProfile, streams: Iterable[Stream]) -> None:
    """
    Give the user some messages in their feed, so that they can learn how to
    use the home view in a realistic way after finishing the tutorial.

    Mark the very most recent messages as unread.
    """

    # Find recipient ids for the user's streams that were passed to us.
    # (Only look at public streams.)
    recipient_ids = [stream.recipient_id for stream in streams if not stream.invite_only]

    # Start by finding recent messages matching those recipients.
    cutoff_date = timezone_now() - ONBOARDING_RECENT_TIMEDELTA
    recent_message_ids = set(
        Message.objects.filter(
            # Uses index: zerver_message_realm_recipient_id
            realm_id=user_profile.realm_id,
            recipient_id__in=recipient_ids,
            date_sent__gt=cutoff_date,
        )
        .order_by("-id")
        .values_list("id", flat=True)[0:MAX_NUM_ONBOARDING_MESSAGES]
    )

    if len(recent_message_ids) > 0:
        # Handle the race condition where a message arrives between
        # bulk_add_subscriptions above and the Message query just above
        already_used_ids = set(
            UserMessage.objects.filter(
                message_id__in=recent_message_ids, user_profile=user_profile
            ).values_list("message_id", flat=True)
        )

        # Exclude the already-used ids and sort them.
        backfill_message_ids = sorted(recent_message_ids - already_used_ids)

        # Find which message ids we should mark as read.
        # (We don't want too many unread messages.)
        older_message_ids = set(backfill_message_ids[:-MAX_NUM_ONBOARDING_UNREAD_MESSAGES])

        # Create UserMessage rows for the backfill.
        ums_to_create = []
        for message_id in backfill_message_ids:
            um = UserMessage(user_profile=user_profile, message_id=message_id)
            if message_id in older_message_ids:
                um.flags = UserMessage.flags.read
            ums_to_create.append(um)

        UserMessage.objects.bulk_create(ums_to_create)


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
    # subscribe to default/invitation streams and
    # fill in some recent historical messages
    set_up_streams_for_new_human_user(
        user_profile=user_profile,
        prereg_user=prereg_user,
        default_stream_groups=default_stream_groups,
    )

    realm = user_profile.realm
    mit_beta_user = realm.is_zephyr_mirror_realm

    # mit_beta_users don't have a referred_by field
    if (
        not mit_beta_user
        and prereg_user is not None
        and prereg_user.referred_by is not None
        and prereg_user.referred_by.is_active
    ):
        # This is a cross-realm direct message.
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
        notify_invites_changed(user_profile.realm, changed_invite_referrer=prereg_user.referred_by)

    notify_new_user(user_profile)
    # Clear any scheduled invitation emails to prevent them
    # from being sent after the user is created.
    clear_scheduled_invitation_emails(user_profile.delivery_email)
    if realm.send_welcome_emails:
        enqueue_welcome_emails(user_profile, realm_creation)

    # Schedule an initial email with the user's
    # new account details and log-in information.
    send_account_registered_email(user_profile, realm_creation)

    # We have an import loop here; it's intentional, because we want
    # to keep all the onboarding code in zerver/lib/onboarding.py.
    from zerver.lib.onboarding import send_initial_direct_message

    send_initial_direct_message(user_profile)


def notify_created_user(user_profile: UserProfile) -> None:
    user_row = user_profile_to_user_row(user_profile)

    format_user_row_kwargs: Dict[str, Any] = {
        "realm_id": user_profile.realm_id,
        "row": user_row,
        # Since we don't know what the client
        # supports at this point in the code, we
        # just assume client_gravatar and
        # user_avatar_url_field_optional = False :(
        "client_gravatar": False,
        "user_avatar_url_field_optional": False,
        # We assume there's no custom profile
        # field data for a new user; initial
        # values are expected to be added in a
        # later event.
        "custom_profile_field_data": {},
    }

    active_users = user_profile.realm.get_active_users()
    user_ids_with_real_email_access = []
    user_ids_without_real_email_access = []

    person_for_real_email_access_users = None
    person_for_without_real_email_access_users = None
    for recipient_user in active_users:
        if can_access_delivery_email(
            recipient_user, user_profile.id, user_row["email_address_visibility"]
        ):
            user_ids_with_real_email_access.append(recipient_user.id)
            if person_for_real_email_access_users is None:
                # This caller assumes that "format_user_row" only depends on
                # specific value of "acting_user" among users in a realm in
                # email_address_visibility.
                person_for_real_email_access_users = format_user_row(
                    **format_user_row_kwargs,
                    acting_user=recipient_user,
                )
        else:
            user_ids_without_real_email_access.append(recipient_user.id)
            if person_for_without_real_email_access_users is None:
                person_for_without_real_email_access_users = format_user_row(
                    **format_user_row_kwargs,
                    acting_user=recipient_user,
                )

    if user_ids_with_real_email_access:
        assert person_for_real_email_access_users is not None
        event: Dict[str, Any] = dict(
            type="realm_user", op="add", person=person_for_real_email_access_users
        )
        send_event_on_commit(user_profile.realm, event, user_ids_with_real_email_access)

    if user_ids_without_real_email_access:
        assert person_for_without_real_email_access_users is not None
        event = dict(type="realm_user", op="add", person=person_for_without_real_email_access_users)
        send_event_on_commit(user_profile.realm, event, user_ids_without_real_email_access)


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
    if user_profile.bot_owner_id is not None:
        bot["owner_id"] = user_profile.bot_owner_id

    return dict(type="realm_bot", op="add", bot=bot)


def notify_created_bot(user_profile: UserProfile) -> None:
    event = created_bot_event(user_profile)
    send_event_on_commit(user_profile.realm, event, bot_owner_user_ids(user_profile))


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
    prereg_realm: Optional[PreregistrationRealm] = None,
    default_stream_groups: Sequence[DefaultStreamGroup] = [],
    source_profile: Optional[UserProfile] = None,
    realm_creation: bool = False,
    *,
    acting_user: Optional[UserProfile],
    enable_marketing_emails: bool = True,
    email_address_visibility: Optional[int] = None,
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
            email_address_visibility=email_address_visibility,
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
            extra_data={
                RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(user_profile.realm),
            },
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
        RealmAuditLog.objects.create(
            realm=user_profile.realm,
            modified_user=user_profile,
            modified_user_group=system_user_group,
            event_type=RealmAuditLog.USER_GROUP_DIRECT_USER_MEMBERSHIP_ADDED,
            event_time=event_time,
            acting_user=acting_user,
        )

        if user_profile.role == UserProfile.ROLE_MEMBER and not user_profile.is_provisional_member:
            full_members_system_group = UserGroup.objects.get(
                name=UserGroup.FULL_MEMBERS_GROUP_NAME,
                realm=user_profile.realm,
                is_system_group=True,
            )
            UserGroupMembership.objects.create(
                user_profile=user_profile, user_group=full_members_system_group
            )
            RealmAuditLog.objects.create(
                realm=user_profile.realm,
                modified_user=user_profile,
                modified_user_group=full_members_system_group,
                event_type=RealmAuditLog.USER_GROUP_DIRECT_USER_MEMBERSHIP_ADDED,
                event_time=event_time,
                acting_user=acting_user,
            )

    # Note that for bots, the caller will send an additional event
    # with bot-specific info like services.
    notify_created_user(user_profile)

    do_send_user_group_members_update_event("add_members", system_user_group, [user_profile.id])
    if user_profile.role == UserProfile.ROLE_MEMBER and not user_profile.is_provisional_member:
        do_send_user_group_members_update_event(
            "add_members", full_members_system_group, [user_profile.id]
        )

    if prereg_realm is not None:
        prereg_realm.created_user = user_profile
        prereg_realm.save(update_fields=["created_user"])

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
            extra_data={
                RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(user_profile.realm),
            },
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


@transaction.atomic(savepoint=False)
def do_reactivate_user(user_profile: UserProfile, *, acting_user: Optional[UserProfile]) -> None:
    """Reactivate a user that had previously been deactivated"""
    change_user_is_active(user_profile, True)

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=user_profile.realm,
        modified_user=user_profile,
        acting_user=acting_user,
        event_type=RealmAuditLog.USER_REACTIVATED,
        event_time=event_time,
        extra_data={
            RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(user_profile.realm),
        },
    )

    bot_owner_changed = False
    if (
        user_profile.is_bot
        and user_profile.bot_owner is not None
        and not user_profile.bot_owner.is_active
        and acting_user is not None
    ):
        previous_owner = user_profile.bot_owner
        user_profile.bot_owner = acting_user
        user_profile.save()  # Can't use update_fields because of how the foreign key works.
        RealmAuditLog.objects.create(
            realm=user_profile.realm,
            acting_user=acting_user,
            modified_user=user_profile,
            event_type=RealmAuditLog.USER_BOT_OWNER_CHANGED,
            event_time=event_time,
        )
        bot_owner_changed = True

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

        if bot_owner_changed:
            from zerver.actions.bots import send_bot_owner_update_events

            assert acting_user is not None
            send_bot_owner_update_events(user_profile, acting_user, previous_owner)

    if bot_owner_changed:
        from zerver.actions.bots import remove_bot_from_inaccessible_private_streams

        remove_bot_from_inaccessible_private_streams(user_profile, acting_user=acting_user)

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
