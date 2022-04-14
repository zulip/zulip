import datetime
import logging
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

import orjson
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.utils.translation import override as override_language
from typing_extensions import TypedDict

from analytics.lib.counts import COUNT_STATS, do_increment_logging_stat
from confirmation import settings as confirmation_settings
from confirmation.models import Confirmation, create_confirmation_link, generate_key
from zerver.actions.custom_profile_fields import do_remove_realm_custom_profile_fields
from zerver.actions.default_streams import get_default_streams_for_realm
from zerver.actions.invites import notify_invites_changed
from zerver.actions.message_send import (
    filter_presence_idle_user_ids,
    get_recipient_info,
    internal_send_private_message,
    internal_send_stream_message,
    render_incoming_message,
)
from zerver.actions.streams import bulk_add_subscriptions, send_peer_subscriber_events
from zerver.actions.uploads import check_attachment_reference_change
from zerver.actions.user_groups import (
    do_send_user_group_members_update_event,
    update_users_in_full_members_system_group,
)
from zerver.actions.user_settings import do_delete_avatar_image, send_user_email_update_event
from zerver.actions.user_topics import do_mute_topic, do_unmute_topic
from zerver.actions.users import change_user_is_active, get_service_dicts_for_bot
from zerver.lib import retention as retention
from zerver.lib.avatar import avatar_url
from zerver.lib.bulk_create import create_users
from zerver.lib.cache import flush_user_profile
from zerver.lib.create_user import create_user, get_display_email_address
from zerver.lib.email_notifications import enqueue_welcome_emails
from zerver.lib.email_validation import email_reserved_for_system_bots_error
from zerver.lib.emoji import check_emoji_request, emoji_name_to_emoji_code
from zerver.lib.exceptions import JsonableError
from zerver.lib.markdown import MessageRenderingResult, topic_links
from zerver.lib.markdown import version as markdown_version
from zerver.lib.mention import MentionBackend, MentionData, silent_mention_syntax_for_user
from zerver.lib.message import (
    access_message,
    bulk_access_messages,
    format_unread_message_details,
    get_raw_unread_data,
    normalize_body,
    truncate_topic,
    update_first_visible_message_id,
    update_to_dict_cache,
    wildcard_mention_allowed,
)
from zerver.lib.queue import queue_json_publish
from zerver.lib.retention import move_messages_to_archive
from zerver.lib.send_email import (
    FromAddress,
    clear_scheduled_invitation_emails,
    send_email_to_admins,
)
from zerver.lib.server_initialization import create_internal_realm, server_initialized
from zerver.lib.sessions import delete_user_sessions
from zerver.lib.stream_subscription import (
    bulk_get_subscriber_peer_info,
    get_active_subscriptions_for_stream_id,
    subscriber_ids_with_stream_history_access,
)
from zerver.lib.stream_topic import StreamTopicTarget
from zerver.lib.streams import (
    access_stream_by_id,
    check_stream_access_based_on_stream_post_policy,
    ensure_stream,
    get_signups_stream,
)
from zerver.lib.string_validation import check_stream_topic
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.topic import (
    ORIG_TOPIC,
    RESOLVED_TOPIC_PREFIX,
    TOPIC_LINKS,
    TOPIC_NAME,
    filter_by_topic_name_via_message,
    messages_for_topic,
    save_message_for_edit_use_case,
    update_edit_history,
    update_messages_for_topic_edit,
)
from zerver.lib.types import EditHistoryEvent
from zerver.lib.user_counts import realm_user_count, realm_user_count_by_role
from zerver.lib.user_groups import (
    create_system_user_groups_for_realm,
    get_system_user_group_for_user,
)
from zerver.lib.user_message import UserMessageLite, bulk_insert_ums
from zerver.lib.user_mutes import add_user_mute, get_user_mutes
from zerver.lib.user_topics import get_users_muting_topic, remove_topic_mute
from zerver.lib.users import format_user_row, get_api_key, user_profile_to_user_row
from zerver.lib.utils import log_statsd_event
from zerver.lib.widget import is_widget_message
from zerver.models import (
    ArchivedAttachment,
    Attachment,
    DefaultStream,
    DefaultStreamGroup,
    Message,
    MutedUser,
    PreregistrationUser,
    Reaction,
    Realm,
    RealmAuditLog,
    RealmDomain,
    RealmUserDefault,
    Recipient,
    ScheduledEmail,
    Stream,
    Subscription,
    UserGroup,
    UserGroupMembership,
    UserMessage,
    UserProfile,
    active_user_ids,
    bot_owner_user_ids,
    get_realm,
    get_realm_domains,
    get_stream_by_id_in_realm,
    get_system_bot,
    is_cross_realm_bot_email,
)
from zerver.tornado.django_api import send_event

if settings.BILLING_ENABLED:
    from corporate.lib.stripe import (
        downgrade_now_without_creating_additional_invoices,
        update_license_ledger_if_needed,
    )


ONBOARDING_TOTAL_MESSAGES = 1000
ONBOARDING_UNREAD_MESSAGES = 20
ONBOARDING_RECENT_TIMEDELTA = datetime.timedelta(weeks=1)


def create_historical_user_messages(*, user_id: int, message_ids: List[int]) -> None:
    # Users can see and interact with messages sent to streams with
    # public history for which they do not have a UserMessage because
    # they were not a subscriber at the time the message was sent.
    # In order to add emoji reactions or mutate message flags for
    # those messages, we create UserMessage objects for those messages;
    # these have the special historical flag which keeps track of the
    # fact that the user did not receive the message at the time it was sent.
    for message_id in message_ids:
        UserMessage.objects.create(
            user_profile_id=user_id,
            message_id=message_id,
            flags=UserMessage.flags.historical | UserMessage.flags.read,
        )


def subscriber_info(user_id: int) -> Dict[str, Any]:
    return {"id": user_id, "flags": ["read"]}


def send_message_to_signup_notification_stream(
    sender: UserProfile, realm: Realm, message: str, topic_name: str = _("signups")
) -> None:
    signup_notifications_stream = realm.get_signup_notifications_stream()
    if signup_notifications_stream is None:
        return

    with override_language(realm.default_language):
        internal_send_stream_message(sender, signup_notifications_stream, topic_name, message)


def notify_new_user(user_profile: UserProfile) -> None:
    user_count = realm_user_count(user_profile.realm)
    sender_email = settings.NOTIFICATION_BOT
    sender = get_system_bot(sender_email, user_profile.realm_id)

    is_first_user = user_count == 1
    if not is_first_user:
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
    else:
        streams = []
        acting_user = None

    # If the user's invitation didn't explicitly list some streams, we
    # add the default streams
    if len(streams) == 0:
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

    revoke_preregistration_users(user_profile, prereg_user, realm_creation)
    if not realm_creation and prereg_user is not None and prereg_user.referred_by is not None:
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


def revoke_preregistration_users(
    created_user_profile: UserProfile,
    used_preregistration_user: Optional[PreregistrationUser],
    realm_creation: bool,
) -> None:
    if used_preregistration_user is None:
        assert not realm_creation, "realm_creation should only happen with a PreregistrationUser"

    if used_preregistration_user is not None:
        used_preregistration_user.status = confirmation_settings.STATUS_ACTIVE
        used_preregistration_user.save(update_fields=["status"])

    # In the special case of realm creation, there can be no additional PreregistrationUser
    # for us to want to modify - because other realm_creation PreregistrationUsers should be
    # left usable for creating different realms.
    if realm_creation:
        return

    # Mark any other PreregistrationUsers in the realm that are STATUS_ACTIVE as
    # inactive so we can keep track of the PreregistrationUser we
    # actually used for analytics.
    if used_preregistration_user is not None:
        PreregistrationUser.objects.filter(
            email__iexact=created_user_profile.delivery_email, realm=created_user_profile.realm
        ).exclude(id=used_preregistration_user.id).update(
            status=confirmation_settings.STATUS_REVOKED
        )
    else:
        PreregistrationUser.objects.filter(
            email__iexact=created_user_profile.delivery_email, realm=created_user_profile.realm
        ).update(status=confirmation_settings.STATUS_REVOKED)


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
    event: Dict[str, Any] = dict(type="realm_user", op="add", person=person)
    send_event(user_profile.realm, event, active_user_ids(user_profile.realm_id))


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
                name="@role:fullmembers", realm=user_profile.realm, is_system_group=True
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


def active_humans_in_realm(realm: Realm) -> Sequence[UserProfile]:
    return UserProfile.objects.filter(realm=realm, is_active=True, is_bot=False)


@transaction.atomic(savepoint=False)
def do_set_realm_property(
    realm: Realm, name: str, value: Any, *, acting_user: Optional[UserProfile]
) -> None:
    """Takes in a realm object, the name of an attribute to update, the
    value to update and and the user who initiated the update.
    """
    property_type = Realm.property_types[name]
    assert isinstance(
        value, property_type
    ), f"Cannot update {name}: {value} is not an instance of {property_type}"

    old_value = getattr(realm, name)
    setattr(realm, name, value)
    realm.save(update_fields=[name])

    event = dict(
        type="realm",
        op="update",
        property=name,
        value=value,
    )
    transaction.on_commit(lambda: send_event(realm, event, active_user_ids(realm.id)))

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=realm,
        event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
        event_time=event_time,
        acting_user=acting_user,
        extra_data=orjson.dumps(
            {
                RealmAuditLog.OLD_VALUE: old_value,
                RealmAuditLog.NEW_VALUE: value,
                "property": name,
            }
        ).decode(),
    )

    if name == "email_address_visibility":
        if Realm.EMAIL_ADDRESS_VISIBILITY_EVERYONE not in [old_value, value]:
            # We use real email addresses on UserProfile.email only if
            # EMAIL_ADDRESS_VISIBILITY_EVERYONE is configured, so
            # changes between values that will not require changing
            # that field, so we can save work and return here.
            return

        user_profiles = UserProfile.objects.filter(realm=realm, is_bot=False)
        for user_profile in user_profiles:
            user_profile.email = get_display_email_address(user_profile)
        UserProfile.objects.bulk_update(user_profiles, ["email"])

        for user_profile in user_profiles:
            transaction.on_commit(
                lambda: flush_user_profile(sender=UserProfile, instance=user_profile)
            )
            # TODO: Design a bulk event for this or force-reload all clients
            send_user_email_update_event(user_profile)

    if name == "waiting_period_threshold":
        update_users_in_full_members_system_group(realm)


def do_set_realm_authentication_methods(
    realm: Realm, authentication_methods: Dict[str, bool], *, acting_user: Optional[UserProfile]
) -> None:
    old_value = realm.authentication_methods_dict()
    with transaction.atomic():
        for key, value in list(authentication_methods.items()):
            index = getattr(realm.authentication_methods, key).number
            realm.authentication_methods.set_bit(index, int(value))
        realm.save(update_fields=["authentication_methods"])
        updated_value = realm.authentication_methods_dict()
        RealmAuditLog.objects.create(
            realm=realm,
            event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
            event_time=timezone_now(),
            acting_user=acting_user,
            extra_data=orjson.dumps(
                {
                    RealmAuditLog.OLD_VALUE: old_value,
                    RealmAuditLog.NEW_VALUE: updated_value,
                    "property": "authentication_methods",
                }
            ).decode(),
        )

    event = dict(
        type="realm",
        op="update_dict",
        property="default",
        data=dict(authentication_methods=updated_value),
    )
    send_event(realm, event, active_user_ids(realm.id))


def do_set_realm_message_editing(
    realm: Realm,
    allow_message_editing: bool,
    message_content_edit_limit_seconds: int,
    edit_topic_policy: int,
    *,
    acting_user: Optional[UserProfile],
) -> None:
    old_values = dict(
        allow_message_editing=realm.allow_message_editing,
        message_content_edit_limit_seconds=realm.message_content_edit_limit_seconds,
        edit_topic_policy=realm.edit_topic_policy,
    )

    realm.allow_message_editing = allow_message_editing
    realm.message_content_edit_limit_seconds = message_content_edit_limit_seconds
    realm.edit_topic_policy = edit_topic_policy

    event_time = timezone_now()
    updated_properties = dict(
        allow_message_editing=allow_message_editing,
        message_content_edit_limit_seconds=message_content_edit_limit_seconds,
        edit_topic_policy=edit_topic_policy,
    )

    with transaction.atomic():
        for updated_property, updated_value in updated_properties.items():
            if updated_value == old_values[updated_property]:
                continue
            RealmAuditLog.objects.create(
                realm=realm,
                event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
                event_time=event_time,
                acting_user=acting_user,
                extra_data=orjson.dumps(
                    {
                        RealmAuditLog.OLD_VALUE: old_values[updated_property],
                        RealmAuditLog.NEW_VALUE: updated_value,
                        "property": updated_property,
                    }
                ).decode(),
            )

        realm.save(update_fields=list(updated_properties.keys()))

    event = dict(
        type="realm",
        op="update_dict",
        property="default",
        data=updated_properties,
    )
    send_event(realm, event, active_user_ids(realm.id))


def do_set_realm_notifications_stream(
    realm: Realm, stream: Optional[Stream], stream_id: int, *, acting_user: Optional[UserProfile]
) -> None:
    old_value = realm.notifications_stream_id
    realm.notifications_stream = stream
    with transaction.atomic():
        realm.save(update_fields=["notifications_stream"])

        event_time = timezone_now()
        RealmAuditLog.objects.create(
            realm=realm,
            event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
            event_time=event_time,
            acting_user=acting_user,
            extra_data=orjson.dumps(
                {
                    RealmAuditLog.OLD_VALUE: old_value,
                    RealmAuditLog.NEW_VALUE: stream_id,
                    "property": "notifications_stream",
                }
            ).decode(),
        )

    event = dict(
        type="realm",
        op="update",
        property="notifications_stream_id",
        value=stream_id,
    )
    send_event(realm, event, active_user_ids(realm.id))


def do_set_realm_signup_notifications_stream(
    realm: Realm, stream: Optional[Stream], stream_id: int, *, acting_user: Optional[UserProfile]
) -> None:
    old_value = realm.signup_notifications_stream_id
    realm.signup_notifications_stream = stream
    with transaction.atomic():
        realm.save(update_fields=["signup_notifications_stream"])

        event_time = timezone_now()
        RealmAuditLog.objects.create(
            realm=realm,
            event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
            event_time=event_time,
            acting_user=acting_user,
            extra_data=orjson.dumps(
                {
                    RealmAuditLog.OLD_VALUE: old_value,
                    RealmAuditLog.NEW_VALUE: stream_id,
                    "property": "signup_notifications_stream",
                }
            ).decode(),
        )
    event = dict(
        type="realm",
        op="update",
        property="signup_notifications_stream_id",
        value=stream_id,
    )
    send_event(realm, event, active_user_ids(realm.id))


def do_set_realm_user_default_setting(
    realm_user_default: RealmUserDefault,
    name: str,
    value: Any,
    *,
    acting_user: Optional[UserProfile],
) -> None:
    old_value = getattr(realm_user_default, name)
    realm = realm_user_default.realm
    event_time = timezone_now()

    with transaction.atomic(savepoint=False):
        setattr(realm_user_default, name, value)
        realm_user_default.save(update_fields=[name])

        RealmAuditLog.objects.create(
            realm=realm,
            event_type=RealmAuditLog.REALM_DEFAULT_USER_SETTINGS_CHANGED,
            event_time=event_time,
            acting_user=acting_user,
            extra_data=orjson.dumps(
                {
                    RealmAuditLog.OLD_VALUE: old_value,
                    RealmAuditLog.NEW_VALUE: value,
                    "property": name,
                }
            ).decode(),
        )

    event = dict(
        type="realm_user_settings_defaults",
        op="update",
        property=name,
        value=value,
    )
    send_event(realm, event, active_user_ids(realm.id))


def do_deactivate_realm(realm: Realm, *, acting_user: Optional[UserProfile]) -> None:
    """
    Deactivate this realm. Do NOT deactivate the users -- we need to be able to
    tell the difference between users that were intentionally deactivated,
    e.g. by a realm admin, and users who can't currently use Zulip because their
    realm has been deactivated.
    """
    if realm.deactivated:
        return

    realm.deactivated = True
    realm.save(update_fields=["deactivated"])

    if settings.BILLING_ENABLED:
        downgrade_now_without_creating_additional_invoices(realm)

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=realm,
        event_type=RealmAuditLog.REALM_DEACTIVATED,
        event_time=event_time,
        acting_user=acting_user,
        extra_data=orjson.dumps(
            {
                RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(realm),
            }
        ).decode(),
    )

    ScheduledEmail.objects.filter(realm=realm).delete()
    for user in active_humans_in_realm(realm):
        # Don't deactivate the users, but do delete their sessions so they get
        # bumped to the login screen, where they'll get a realm deactivation
        # notice when they try to log in.
        delete_user_sessions(user)

    # This event will only ever be received by clients with an active
    # longpoll connection, because by this point clients will be
    # unable to authenticate again to their event queue (triggering an
    # immediate reload into the page explaining the realm was
    # deactivated). So the purpose of sending this is to flush all
    # active longpoll connections for the realm.
    event = dict(type="realm", op="deactivated", realm_id=realm.id)
    send_event(realm, event, active_user_ids(realm.id))


def do_reactivate_realm(realm: Realm) -> None:
    realm.deactivated = False
    with transaction.atomic():
        realm.save(update_fields=["deactivated"])

        event_time = timezone_now()
        RealmAuditLog.objects.create(
            realm=realm,
            event_type=RealmAuditLog.REALM_REACTIVATED,
            event_time=event_time,
            extra_data=orjson.dumps(
                {
                    RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(realm),
                }
            ).decode(),
        )


def do_change_realm_subdomain(
    realm: Realm, new_subdomain: str, *, acting_user: Optional[UserProfile]
) -> None:
    """Changing a realm's subdomain is a highly disruptive operation,
    because all existing clients will need to be updated to point to
    the new URL.  Further, requests to fetch data from existing event
    queues will fail with an authentication error when this change
    happens (because the old subdomain is no longer associated with
    the realm), making it hard for us to provide a graceful update
    experience for clients.
    """
    old_subdomain = realm.subdomain
    old_uri = realm.uri
    # If the realm had been a demo organization scheduled for
    # deleting, clear that state.
    realm.demo_organization_scheduled_deletion_date = None
    realm.string_id = new_subdomain
    with transaction.atomic():
        realm.save(update_fields=["string_id", "demo_organization_scheduled_deletion_date"])
        RealmAuditLog.objects.create(
            realm=realm,
            event_type=RealmAuditLog.REALM_SUBDOMAIN_CHANGED,
            event_time=timezone_now(),
            acting_user=acting_user,
            extra_data={"old_subdomain": old_subdomain, "new_subdomain": new_subdomain},
        )

        # If a realm if being renamed multiple times, we should find all the placeholder
        # realms and reset their deactivated_redirect field to point to the new realm uri
        placeholder_realms = Realm.objects.filter(deactivated_redirect=old_uri, deactivated=True)
        for placeholder_realm in placeholder_realms:
            do_add_deactivated_redirect(placeholder_realm, realm.uri)

    # The below block isn't executed in a transaction with the earlier code due to
    # the functions called below being complex and potentially sending events,
    # which we don't want to do in atomic blocks.
    # When we change a realm's subdomain the realm with old subdomain is basically
    # deactivated. We are creating a deactivated realm using old subdomain and setting
    # it's deactivated redirect to new_subdomain so that we can tell the users that
    # the realm has been moved to a new subdomain.
    placeholder_realm = do_create_realm(old_subdomain, realm.name)
    do_deactivate_realm(placeholder_realm, acting_user=None)
    do_add_deactivated_redirect(placeholder_realm, realm.uri)


def do_add_deactivated_redirect(realm: Realm, redirect_url: str) -> None:
    realm.deactivated_redirect = redirect_url
    realm.save(update_fields=["deactivated_redirect"])


def do_scrub_realm(realm: Realm, *, acting_user: Optional[UserProfile]) -> None:
    if settings.BILLING_ENABLED:
        downgrade_now_without_creating_additional_invoices(realm)

    users = UserProfile.objects.filter(realm=realm)
    for user in users:
        do_delete_messages_by_sender(user)
        do_delete_avatar_image(user, acting_user=acting_user)
        user.full_name = f"Scrubbed {generate_key()[:15]}"
        scrubbed_email = f"scrubbed-{generate_key()[:15]}@{realm.host}"
        user.email = scrubbed_email
        user.delivery_email = scrubbed_email
        user.save(update_fields=["full_name", "email", "delivery_email"])

    do_remove_realm_custom_profile_fields(realm)
    Attachment.objects.filter(realm=realm).delete()

    RealmAuditLog.objects.create(
        realm=realm,
        event_time=timezone_now(),
        acting_user=acting_user,
        event_type=RealmAuditLog.REALM_SCRUBBED,
    )


def notify_reaction_update(
    user_profile: UserProfile, message: Message, reaction: Reaction, op: str
) -> None:
    user_dict = {
        "user_id": user_profile.id,
        "email": user_profile.email,
        "full_name": user_profile.full_name,
    }

    event: Dict[str, Any] = {
        "type": "reaction",
        "op": op,
        "user_id": user_profile.id,
        # TODO: We plan to remove this redundant user_dict object once
        # clients are updated to support accessing use user_id.  See
        # https://github.com/zulip/zulip/pull/14711 for details.
        "user": user_dict,
        "message_id": message.id,
        "emoji_name": reaction.emoji_name,
        "emoji_code": reaction.emoji_code,
        "reaction_type": reaction.reaction_type,
    }

    # Update the cached message since new reaction is added.
    update_to_dict_cache([message])

    # Recipients for message update events, including reactions, are
    # everyone who got the original message, plus subscribers of
    # streams with the access to stream's full history.
    #
    # This means reactions won't live-update in preview narrows for a
    # stream the user isn't yet subscribed to; this is the right
    # performance tradeoff to avoid sending every reaction to public
    # stream messages to all users.
    #
    # To ensure that reactions do live-update for any user who has
    # actually participated in reacting to a message, we add a
    # "historical" UserMessage row for any user who reacts to message,
    # subscribing them to future notifications, even if they are not
    # subscribed to the stream.
    user_ids = set(
        UserMessage.objects.filter(message=message.id).values_list("user_profile_id", flat=True)
    )
    if message.recipient.type == Recipient.STREAM:
        stream_id = message.recipient.type_id
        stream = Stream.objects.get(id=stream_id)
        user_ids |= subscriber_ids_with_stream_history_access(stream)

    transaction.on_commit(lambda: send_event(user_profile.realm, event, list(user_ids)))


def do_add_reaction(
    user_profile: UserProfile,
    message: Message,
    emoji_name: str,
    emoji_code: str,
    reaction_type: str,
) -> None:
    """Should be called while holding a SELECT FOR UPDATE lock
    (e.g. via access_message(..., lock_message=True)) on the
    Message row, to prevent race conditions.
    """

    reaction = Reaction(
        user_profile=user_profile,
        message=message,
        emoji_name=emoji_name,
        emoji_code=emoji_code,
        reaction_type=reaction_type,
    )

    reaction.save()

    notify_reaction_update(user_profile, message, reaction, "add")


def check_add_reaction(
    user_profile: UserProfile,
    message_id: int,
    emoji_name: str,
    emoji_code: Optional[str],
    reaction_type: Optional[str],
) -> None:
    message, user_message = access_message(user_profile, message_id, lock_message=True)

    if emoji_code is None:
        # The emoji_code argument is only required for rare corner
        # cases discussed in the long block comment below.  For simple
        # API clients, we allow specifying just the name, and just
        # look up the code using the current name->code mapping.
        emoji_code = emoji_name_to_emoji_code(message.sender.realm, emoji_name)[0]

    if reaction_type is None:
        reaction_type = emoji_name_to_emoji_code(message.sender.realm, emoji_name)[1]

    if Reaction.objects.filter(
        user_profile=user_profile,
        message=message,
        emoji_code=emoji_code,
        reaction_type=reaction_type,
    ).exists():
        raise JsonableError(_("Reaction already exists."))

    query = Reaction.objects.filter(
        message=message, emoji_code=emoji_code, reaction_type=reaction_type
    )
    if query.exists():
        # If another user has already reacted to this message with
        # same emoji code, we treat the new reaction as a vote for the
        # existing reaction.  So the emoji name used by that earlier
        # reaction takes precedence over whatever was passed in this
        # request.  This is necessary to avoid a message having 2
        # "different" emoji reactions with the same emoji code (and
        # thus same image) on the same message, which looks ugly.
        #
        # In this "voting for an existing reaction" case, we shouldn't
        # check whether the emoji code and emoji name match, since
        # it's possible that the (emoji_type, emoji_name, emoji_code)
        # triple for this existing reaction may not pass validation
        # now (e.g. because it is for a realm emoji that has been
        # since deactivated).  We still want to allow users to add a
        # vote any old reaction they see in the UI even if that is a
        # deactivated custom emoji, so we just use the emoji name from
        # the existing reaction with no further validation.
        reaction = query.first()
        assert reaction is not None
        emoji_name = reaction.emoji_name
    else:
        # Otherwise, use the name provided in this request, but verify
        # it is valid in the user's realm (e.g. not a deactivated
        # realm emoji).
        check_emoji_request(user_profile.realm, emoji_name, emoji_code, reaction_type)

    if user_message is None:
        # See called function for more context.
        create_historical_user_messages(user_id=user_profile.id, message_ids=[message.id])

    do_add_reaction(user_profile, message, emoji_name, emoji_code, reaction_type)


def do_remove_reaction(
    user_profile: UserProfile, message: Message, emoji_code: str, reaction_type: str
) -> None:
    """Should be called while holding a SELECT FOR UPDATE lock
    (e.g. via access_message(..., lock_message=True)) on the
    Message row, to prevent race conditions.
    """
    reaction = Reaction.objects.filter(
        user_profile=user_profile,
        message=message,
        emoji_code=emoji_code,
        reaction_type=reaction_type,
    ).get()
    reaction.delete()

    notify_reaction_update(user_profile, message, reaction, "remove")


def validate_message_edit_payload(
    message: Message,
    stream_id: Optional[int],
    topic_name: Optional[str],
    propagate_mode: Optional[str],
    content: Optional[str],
) -> None:
    """
    Checks that the data sent is well-formed. Does not handle editability, permissions etc.
    """
    if topic_name is None and content is None and stream_id is None:
        raise JsonableError(_("Nothing to change"))

    if not message.is_stream_message():
        if stream_id is not None:
            raise JsonableError(_("Private messages cannot be moved to streams."))
        if topic_name is not None:
            raise JsonableError(_("Private messages cannot have topics."))

    if propagate_mode != "change_one" and topic_name is None and stream_id is None:
        raise JsonableError(_("Invalid propagate_mode without topic edit"))

    if topic_name is not None:
        check_stream_topic(topic_name)

    if stream_id is not None and content is not None:
        raise JsonableError(_("Cannot change message content while changing stream"))

    # Right now, we prevent users from editing widgets.
    if content is not None and is_widget_message(message):
        raise JsonableError(_("Widgets cannot be edited."))


def can_edit_content_or_topic(
    message: Message,
    user_profile: UserProfile,
    is_no_topic_msg: bool,
    content: Optional[str] = None,
    topic_name: Optional[str] = None,
) -> bool:
    # You have permission to edit the message (both content and topic) if you sent it.
    if message.sender_id == user_profile.id:
        return True

    # You cannot edit the content of message sent by someone else.
    if content is not None:
        return False

    assert topic_name is not None

    # The following cases are the various reasons a user might be
    # allowed to edit topics.

    # We allow anyone to edit (no topic) messages to help tend them.
    if is_no_topic_msg:
        return True

    # The can_edit_topic_of_any_message helper returns whether the user can edit the topic
    # or not based on edit_topic_policy setting and the user's role.
    if user_profile.can_edit_topic_of_any_message():
        return True

    return False


def check_update_message(
    user_profile: UserProfile,
    message_id: int,
    stream_id: Optional[int] = None,
    topic_name: Optional[str] = None,
    propagate_mode: str = "change_one",
    send_notification_to_old_thread: bool = True,
    send_notification_to_new_thread: bool = True,
    content: Optional[str] = None,
) -> int:
    """This will update a message given the message id and user profile.
    It checks whether the user profile has the permission to edit the message
    and raises a JsonableError if otherwise.
    It returns the number changed.
    """
    message, ignored_user_message = access_message(user_profile, message_id)

    if not user_profile.realm.allow_message_editing:
        raise JsonableError(_("Your organization has turned off message editing"))

    # The zerver/views/message_edit.py call point already strips this
    # via REQ_topic; so we can delete this line if we arrange a
    # contract where future callers in the embedded bots system strip
    # use REQ_topic as well (or otherwise are guaranteed to strip input).
    if topic_name is not None:
        topic_name = topic_name.strip()
        if topic_name == message.topic_name():
            topic_name = None

    validate_message_edit_payload(message, stream_id, topic_name, propagate_mode, content)

    is_no_topic_msg = message.topic_name() == "(no topic)"

    if content is not None or topic_name is not None:
        if not can_edit_content_or_topic(
            message, user_profile, is_no_topic_msg, content, topic_name
        ):
            raise JsonableError(_("You don't have permission to edit this message"))

    # If there is a change to the content, check that it hasn't been too long
    # Allow an extra 20 seconds since we potentially allow editing 15 seconds
    # past the limit, and in case there are network issues, etc. The 15 comes
    # from (min_seconds_to_edit + seconds_left_buffer) in message_edit.js; if
    # you change this value also change those two parameters in message_edit.js.
    edit_limit_buffer = 20
    if content is not None and user_profile.realm.message_content_edit_limit_seconds > 0:
        deadline_seconds = user_profile.realm.message_content_edit_limit_seconds + edit_limit_buffer
        if (timezone_now() - message.date_sent) > datetime.timedelta(seconds=deadline_seconds):
            raise JsonableError(_("The time limit for editing this message has passed"))

    # If there is a change to the topic, check that the user is allowed to
    # edit it and that it has not been too long. If this is not the user who
    # sent the message, they are not the admin, and the time limit for editing
    # topics is passed, raise an error.
    if (
        topic_name is not None
        and message.sender != user_profile
        and not user_profile.is_realm_admin
        and not user_profile.is_moderator
        and not is_no_topic_msg
    ):
        deadline_seconds = Realm.DEFAULT_COMMUNITY_TOPIC_EDITING_LIMIT_SECONDS + edit_limit_buffer
        if (timezone_now() - message.date_sent) > datetime.timedelta(seconds=deadline_seconds):
            raise JsonableError(_("The time limit for editing this message's topic has passed"))

    rendering_result = None
    links_for_embed: Set[str] = set()
    prior_mention_user_ids: Set[int] = set()
    mention_data: Optional[MentionData] = None
    if content is not None:
        if content.rstrip() == "":
            content = "(deleted)"
        content = normalize_body(content)

        mention_backend = MentionBackend(user_profile.realm_id)
        mention_data = MentionData(
            mention_backend=mention_backend,
            content=content,
        )
        user_info = get_user_info_for_message_updates(message.id)
        prior_mention_user_ids = user_info["mention_user_ids"]

        # We render the message using the current user's realm; since
        # the cross-realm bots never edit messages, this should be
        # always correct.
        # Note: If rendering fails, the called code will raise a JsonableError.
        rendering_result = render_incoming_message(
            message,
            content,
            user_info["message_user_ids"],
            user_profile.realm,
            mention_data=mention_data,
        )
        links_for_embed |= rendering_result.links_for_preview

        if message.is_stream_message() and rendering_result.mentions_wildcard:
            stream = access_stream_by_id(user_profile, message.recipient.type_id)[0]
            if not wildcard_mention_allowed(message.sender, stream):
                raise JsonableError(
                    _("You do not have permission to use wildcard mentions in this stream.")
                )

    new_stream = None
    number_changed = 0

    if stream_id is not None:
        assert message.is_stream_message()
        if not user_profile.can_move_messages_between_streams():
            raise JsonableError(_("You don't have permission to move this message"))
        try:
            access_stream_by_id(user_profile, message.recipient.type_id)
        except JsonableError:
            raise JsonableError(
                _(
                    "You don't have permission to move this message due to missing access to its stream"
                )
            )

        new_stream = access_stream_by_id(user_profile, stream_id, require_active=True)[0]
        check_stream_access_based_on_stream_post_policy(user_profile, new_stream)

    number_changed = do_update_message(
        user_profile,
        message,
        new_stream,
        topic_name,
        propagate_mode,
        send_notification_to_old_thread,
        send_notification_to_new_thread,
        content,
        rendering_result,
        prior_mention_user_ids,
        mention_data,
    )

    if links_for_embed:
        event_data = {
            "message_id": message.id,
            "message_content": message.content,
            # The choice of `user_profile.realm_id` rather than
            # `sender.realm_id` must match the decision made in the
            # `render_incoming_message` call earlier in this function.
            "message_realm_id": user_profile.realm_id,
            "urls": list(links_for_embed),
        }
        queue_json_publish("embed_links", event_data)

    return number_changed


@transaction.atomic(durable=True)
def do_change_bot_owner(
    user_profile: UserProfile, bot_owner: UserProfile, acting_user: UserProfile
) -> None:
    previous_owner = user_profile.bot_owner
    user_profile.bot_owner = bot_owner
    user_profile.save()  # Can't use update_fields because of how the foreign key works.
    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=user_profile.realm,
        acting_user=acting_user,
        modified_user=user_profile,
        event_type=RealmAuditLog.USER_BOT_OWNER_CHANGED,
        event_time=event_time,
    )

    update_users = bot_owner_user_ids(user_profile)

    # For admins, update event is sent instead of delete/add
    # event. bot_data of admin contains all the
    # bots and none of them should be removed/(added again).

    # Delete the bot from previous owner's bot data.
    if previous_owner and not previous_owner.is_realm_admin:
        delete_event = dict(
            type="realm_bot",
            op="delete",
            bot=dict(
                user_id=user_profile.id,
            ),
        )
        transaction.on_commit(
            lambda: send_event(
                user_profile.realm,
                delete_event,
                {previous_owner.id},
            )
        )
        # Do not send update event for previous bot owner.
        update_users = update_users - {previous_owner.id}

    # Notify the new owner that the bot has been added.
    if not bot_owner.is_realm_admin:
        add_event = created_bot_event(user_profile)
        transaction.on_commit(lambda: send_event(user_profile.realm, add_event, {bot_owner.id}))
        # Do not send update event for bot_owner.
        update_users = update_users - {bot_owner.id}

    bot_event = dict(
        type="realm_bot",
        op="update",
        bot=dict(
            user_id=user_profile.id,
            owner_id=user_profile.bot_owner.id,
        ),
    )
    transaction.on_commit(
        lambda: send_event(
            user_profile.realm,
            bot_event,
            update_users,
        )
    )

    # Since `bot_owner_id` is included in the user profile dict we need
    # to update the users dict with the new bot owner id
    event = dict(
        type="realm_user",
        op="update",
        person=dict(
            user_id=user_profile.id,
            bot_owner_id=user_profile.bot_owner.id,
        ),
    )
    transaction.on_commit(
        lambda: send_event(user_profile.realm, event, active_user_ids(user_profile.realm_id))
    )


@transaction.atomic(durable=True)
def do_change_realm_org_type(
    realm: Realm,
    org_type: int,
    acting_user: Optional[UserProfile],
) -> None:
    old_value = realm.org_type
    realm.org_type = org_type
    realm.save(update_fields=["org_type"])

    RealmAuditLog.objects.create(
        event_type=RealmAuditLog.REALM_ORG_TYPE_CHANGED,
        realm=realm,
        event_time=timezone_now(),
        acting_user=acting_user,
        extra_data={"old_value": old_value, "new_value": org_type},
    )


@transaction.atomic(savepoint=False)
def do_change_realm_plan_type(
    realm: Realm, plan_type: int, *, acting_user: Optional[UserProfile]
) -> None:
    old_value = realm.plan_type
    realm.plan_type = plan_type
    realm.save(update_fields=["plan_type"])
    RealmAuditLog.objects.create(
        event_type=RealmAuditLog.REALM_PLAN_TYPE_CHANGED,
        realm=realm,
        event_time=timezone_now(),
        acting_user=acting_user,
        extra_data={"old_value": old_value, "new_value": plan_type},
    )

    if plan_type == Realm.PLAN_TYPE_PLUS:
        realm.max_invites = Realm.INVITES_STANDARD_REALM_DAILY_MAX
        realm.message_visibility_limit = None
        realm.upload_quota_gb = Realm.UPLOAD_QUOTA_STANDARD
    elif plan_type == Realm.PLAN_TYPE_STANDARD:
        realm.max_invites = Realm.INVITES_STANDARD_REALM_DAILY_MAX
        realm.message_visibility_limit = None
        realm.upload_quota_gb = Realm.UPLOAD_QUOTA_STANDARD
    elif plan_type == Realm.PLAN_TYPE_SELF_HOSTED:
        realm.max_invites = None  # type: ignore[assignment] # Apparent mypy bug with Optional[int] setter.
        realm.message_visibility_limit = None
        realm.upload_quota_gb = None
    elif plan_type == Realm.PLAN_TYPE_STANDARD_FREE:
        realm.max_invites = Realm.INVITES_STANDARD_REALM_DAILY_MAX
        realm.message_visibility_limit = None
        realm.upload_quota_gb = Realm.UPLOAD_QUOTA_STANDARD
    elif plan_type == Realm.PLAN_TYPE_LIMITED:
        realm.max_invites = settings.INVITES_DEFAULT_REALM_DAILY_MAX
        realm.message_visibility_limit = Realm.MESSAGE_VISIBILITY_LIMITED
        realm.upload_quota_gb = Realm.UPLOAD_QUOTA_LIMITED
    else:
        raise AssertionError("Invalid plan type")

    update_first_visible_message_id(realm)

    realm.save(update_fields=["_max_invites", "message_visibility_limit", "upload_quota_gb"])

    event = {
        "type": "realm",
        "op": "update",
        "property": "plan_type",
        "value": plan_type,
        "extra_data": {"upload_quota": realm.upload_quota_bytes()},
    }
    transaction.on_commit(lambda: send_event(realm, event, active_user_ids(realm.id)))


@transaction.atomic(durable=True)
def do_change_default_sending_stream(
    user_profile: UserProfile, stream: Optional[Stream], *, acting_user: Optional[UserProfile]
) -> None:
    old_value = user_profile.default_sending_stream_id
    user_profile.default_sending_stream = stream
    user_profile.save(update_fields=["default_sending_stream"])

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=user_profile.realm,
        event_type=RealmAuditLog.USER_DEFAULT_SENDING_STREAM_CHANGED,
        event_time=event_time,
        modified_user=user_profile,
        acting_user=acting_user,
        extra_data=orjson.dumps(
            {
                RealmAuditLog.OLD_VALUE: old_value,
                RealmAuditLog.NEW_VALUE: None if stream is None else stream.id,
            }
        ).decode(),
    )

    if user_profile.is_bot:
        if stream:
            stream_name: Optional[str] = stream.name
        else:
            stream_name = None
        event = dict(
            type="realm_bot",
            op="update",
            bot=dict(
                user_id=user_profile.id,
                default_sending_stream=stream_name,
            ),
        )
        transaction.on_commit(
            lambda: send_event(
                user_profile.realm,
                event,
                bot_owner_user_ids(user_profile),
            )
        )


@transaction.atomic(durable=True)
def do_change_default_events_register_stream(
    user_profile: UserProfile, stream: Optional[Stream], *, acting_user: Optional[UserProfile]
) -> None:
    old_value = user_profile.default_events_register_stream_id
    user_profile.default_events_register_stream = stream
    user_profile.save(update_fields=["default_events_register_stream"])

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=user_profile.realm,
        event_type=RealmAuditLog.USER_DEFAULT_REGISTER_STREAM_CHANGED,
        event_time=event_time,
        modified_user=user_profile,
        acting_user=acting_user,
        extra_data=orjson.dumps(
            {
                RealmAuditLog.OLD_VALUE: old_value,
                RealmAuditLog.NEW_VALUE: None if stream is None else stream.id,
            }
        ).decode(),
    )

    if user_profile.is_bot:
        if stream:
            stream_name: Optional[str] = stream.name
        else:
            stream_name = None

        event = dict(
            type="realm_bot",
            op="update",
            bot=dict(
                user_id=user_profile.id,
                default_events_register_stream=stream_name,
            ),
        )
        transaction.on_commit(
            lambda: send_event(
                user_profile.realm,
                event,
                bot_owner_user_ids(user_profile),
            )
        )


@transaction.atomic(durable=True)
def do_change_default_all_public_streams(
    user_profile: UserProfile, value: bool, *, acting_user: Optional[UserProfile]
) -> None:
    old_value = user_profile.default_all_public_streams
    user_profile.default_all_public_streams = value
    user_profile.save(update_fields=["default_all_public_streams"])

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=user_profile.realm,
        event_type=RealmAuditLog.USER_DEFAULT_ALL_PUBLIC_STREAMS_CHANGED,
        event_time=event_time,
        modified_user=user_profile,
        acting_user=acting_user,
        extra_data=orjson.dumps(
            {
                RealmAuditLog.OLD_VALUE: old_value,
                RealmAuditLog.NEW_VALUE: value,
            }
        ).decode(),
    )

    if user_profile.is_bot:
        event = dict(
            type="realm_bot",
            op="update",
            bot=dict(
                user_id=user_profile.id,
                default_all_public_streams=user_profile.default_all_public_streams,
            ),
        )
        transaction.on_commit(
            lambda: send_event(
                user_profile.realm,
                event,
                bot_owner_user_ids(user_profile),
            )
        )


def set_realm_permissions_based_on_org_type(realm: Realm) -> None:
    """This function implements overrides for the default configuration
    for new organizations when the administrator selected specific
    organization types.

    This substantially simplifies our /help/ advice for folks setting
    up new organizations of these types.
    """

    # Custom configuration for educational organizations.  The present
    # defaults are designed for a single class, not a department or
    # larger institution, since those are more common.
    if (
        realm.org_type == Realm.ORG_TYPES["education_nonprofit"]["id"]
        or realm.org_type == Realm.ORG_TYPES["education"]["id"]
    ):
        # Limit email address visibility and user creation to administrators.
        realm.email_address_visibility = Realm.EMAIL_ADDRESS_VISIBILITY_ADMINS
        realm.invite_to_realm_policy = Realm.POLICY_ADMINS_ONLY
        # Restrict public stream creation to staff, but allow private
        # streams (useful for study groups, etc.).
        realm.create_public_stream_policy = Realm.POLICY_ADMINS_ONLY
        # Don't allow members (students) to manage user groups or
        # stream subscriptions.
        realm.user_group_edit_policy = Realm.POLICY_MODERATORS_ONLY
        realm.invite_to_stream_policy = Realm.POLICY_MODERATORS_ONLY
        # Allow moderators (TAs?) to move topics between streams.
        realm.move_messages_between_streams_policy = Realm.POLICY_MODERATORS_ONLY


def setup_realm_internal_bots(realm: Realm) -> None:
    """Create this realm's internal bots.

    This function is idempotent; it does nothing for a bot that
    already exists.
    """
    internal_bots = [
        (bot["name"], bot["email_template"] % (settings.INTERNAL_BOT_DOMAIN,))
        for bot in settings.REALM_INTERNAL_BOTS
    ]
    create_users(realm, internal_bots, bot_type=UserProfile.DEFAULT_BOT)
    bots = UserProfile.objects.filter(
        realm=realm,
        email__in=[bot_info[1] for bot_info in internal_bots],
        bot_owner__isnull=True,
    )
    for bot in bots:
        bot.bot_owner = bot
        bot.save()


def do_create_realm(
    string_id: str,
    name: str,
    *,
    emails_restricted_to_domains: Optional[bool] = None,
    email_address_visibility: Optional[int] = None,
    description: Optional[str] = None,
    invite_required: Optional[bool] = None,
    plan_type: Optional[int] = None,
    org_type: Optional[int] = None,
    date_created: Optional[datetime.datetime] = None,
    is_demo_organization: Optional[bool] = False,
    enable_spectator_access: Optional[bool] = False,
) -> Realm:
    if string_id == settings.SOCIAL_AUTH_SUBDOMAIN:
        raise AssertionError("Creating a realm on SOCIAL_AUTH_SUBDOMAIN is not allowed!")
    if Realm.objects.filter(string_id=string_id).exists():
        raise AssertionError(f"Realm {string_id} already exists!")
    if not server_initialized():
        logging.info("Server not yet initialized. Creating the internal realm first.")
        create_internal_realm()

    kwargs: Dict[str, Any] = {}
    if emails_restricted_to_domains is not None:
        kwargs["emails_restricted_to_domains"] = emails_restricted_to_domains
    if email_address_visibility is not None:
        kwargs["email_address_visibility"] = email_address_visibility
    if description is not None:
        kwargs["description"] = description
    if invite_required is not None:
        kwargs["invite_required"] = invite_required
    if plan_type is not None:
        kwargs["plan_type"] = plan_type
    if org_type is not None:
        kwargs["org_type"] = org_type
    if enable_spectator_access is not None:
        kwargs["enable_spectator_access"] = enable_spectator_access

    if date_created is not None:
        # The date_created parameter is intended only for use by test
        # suites that want to backdate the date of a realm's creation.
        assert not settings.PRODUCTION
        kwargs["date_created"] = date_created

    with transaction.atomic():
        realm = Realm(string_id=string_id, name=name, **kwargs)
        if is_demo_organization:
            realm.demo_organization_scheduled_deletion_date = (
                realm.date_created + datetime.timedelta(days=settings.DEMO_ORG_DEADLINE_DAYS)
            )

        set_realm_permissions_based_on_org_type(realm)
        realm.save()

        RealmAuditLog.objects.create(
            realm=realm, event_type=RealmAuditLog.REALM_CREATED, event_time=realm.date_created
        )

        RealmUserDefault.objects.create(realm=realm)

        create_system_user_groups_for_realm(realm)

    # Create stream once Realm object has been saved
    notifications_stream = ensure_stream(
        realm,
        Realm.DEFAULT_NOTIFICATION_STREAM_NAME,
        stream_description="Everyone is added to this stream by default. Welcome! :octopus:",
        acting_user=None,
    )
    realm.notifications_stream = notifications_stream

    # With the current initial streams situation, the only public
    # stream is the notifications_stream.
    DefaultStream.objects.create(stream=notifications_stream, realm=realm)

    signup_notifications_stream = ensure_stream(
        realm,
        Realm.INITIAL_PRIVATE_STREAM_NAME,
        invite_only=True,
        stream_description="A private stream for core team members.",
        acting_user=None,
    )
    realm.signup_notifications_stream = signup_notifications_stream

    realm.save(update_fields=["notifications_stream", "signup_notifications_stream"])

    if plan_type is None and settings.BILLING_ENABLED:
        do_change_realm_plan_type(realm, Realm.PLAN_TYPE_LIMITED, acting_user=None)

    admin_realm = get_realm(settings.SYSTEM_BOT_REALM)
    sender = get_system_bot(settings.NOTIFICATION_BOT, admin_realm.id)
    # Send a notification to the admin realm
    signup_message = _("Signups enabled")

    try:
        signups_stream = get_signups_stream(admin_realm)
        topic = realm.display_subdomain

        internal_send_stream_message(
            sender,
            signups_stream,
            topic,
            signup_message,
        )
    except Stream.DoesNotExist:  # nocoverage
        # If the signups stream hasn't been created in the admin
        # realm, don't auto-create it to send to it; just do nothing.
        pass

    setup_realm_internal_bots(realm)
    return realm


def get_default_subs(user_profile: UserProfile) -> List[Stream]:
    # Right now default streams are realm-wide.  This wrapper gives us flexibility
    # to some day further customize how we set up default streams for new users.
    return get_default_streams_for_realm(user_profile.realm_id)


@dataclass
class ReadMessagesEvent:
    messages: List[int]
    all: bool
    type: str = field(default="update_message_flags", init=False)
    op: str = field(default="add", init=False)
    operation: str = field(default="add", init=False)
    flag: str = field(default="read", init=False)


def do_mark_all_as_read(user_profile: UserProfile) -> int:
    log_statsd_event("bankruptcy")

    # First, we clear mobile push notifications.  This is safer in the
    # event that the below logic times out and we're killed.
    all_push_message_ids = (
        UserMessage.objects.filter(
            user_profile=user_profile,
        )
        .extra(
            where=[UserMessage.where_active_push_notification()],
        )
        .values_list("message_id", flat=True)[0:10000]
    )
    do_clear_mobile_push_notifications_for_ids([user_profile.id], all_push_message_ids)

    msgs = UserMessage.objects.filter(user_profile=user_profile).extra(
        where=[UserMessage.where_unread()],
    )

    count = msgs.update(
        flags=F("flags").bitor(UserMessage.flags.read),
    )

    event = asdict(
        ReadMessagesEvent(
            messages=[],  # we don't send messages, since the client reloads anyway
            all=True,
        )
    )
    event_time = timezone_now()

    send_event(user_profile.realm, event, [user_profile.id])

    do_increment_logging_stat(
        user_profile, COUNT_STATS["messages_read::hour"], None, event_time, increment=count
    )
    do_increment_logging_stat(
        user_profile,
        COUNT_STATS["messages_read_interactions::hour"],
        None,
        event_time,
        increment=min(1, count),
    )

    return count


def do_mark_stream_messages_as_read(
    user_profile: UserProfile, stream_recipient_id: int, topic_name: Optional[str] = None
) -> int:
    log_statsd_event("mark_stream_as_read")

    msgs = UserMessage.objects.filter(
        user_profile=user_profile,
    )

    msgs = msgs.filter(message__recipient_id=stream_recipient_id)

    if topic_name:
        msgs = filter_by_topic_name_via_message(
            query=msgs,
            topic_name=topic_name,
        )

    msgs = msgs.extra(
        where=[UserMessage.where_unread()],
    )

    message_ids = list(msgs.values_list("message_id", flat=True))

    count = msgs.update(
        flags=F("flags").bitor(UserMessage.flags.read),
    )

    event = asdict(
        ReadMessagesEvent(
            messages=message_ids,
            all=False,
        )
    )
    event_time = timezone_now()

    send_event(user_profile.realm, event, [user_profile.id])
    do_clear_mobile_push_notifications_for_ids([user_profile.id], message_ids)

    do_increment_logging_stat(
        user_profile, COUNT_STATS["messages_read::hour"], None, event_time, increment=count
    )
    do_increment_logging_stat(
        user_profile,
        COUNT_STATS["messages_read_interactions::hour"],
        None,
        event_time,
        increment=min(1, count),
    )
    return count


def do_mark_muted_user_messages_as_read(
    user_profile: UserProfile,
    muted_user: UserProfile,
) -> int:
    messages = UserMessage.objects.filter(
        user_profile=user_profile, message__sender=muted_user
    ).extra(where=[UserMessage.where_unread()])

    message_ids = list(messages.values_list("message_id", flat=True))

    count = messages.update(
        flags=F("flags").bitor(UserMessage.flags.read),
    )

    event = asdict(
        ReadMessagesEvent(
            messages=message_ids,
            all=False,
        )
    )
    event_time = timezone_now()

    send_event(user_profile.realm, event, [user_profile.id])
    do_clear_mobile_push_notifications_for_ids([user_profile.id], message_ids)

    do_increment_logging_stat(
        user_profile, COUNT_STATS["messages_read::hour"], None, event_time, increment=count
    )
    do_increment_logging_stat(
        user_profile,
        COUNT_STATS["messages_read_interactions::hour"],
        None,
        event_time,
        increment=min(1, count),
    )
    return count


def do_update_mobile_push_notification(
    message: Message,
    prior_mention_user_ids: Set[int],
    mentions_user_ids: Set[int],
    stream_push_user_ids: Set[int],
) -> None:
    # Called during the message edit code path to remove mobile push
    # notifications for users who are no longer mentioned following
    # the edit.  See #15428 for details.
    #
    # A perfect implementation would also support updating the message
    # in a sent notification if a message was edited to mention a
    # group rather than a user (or vice versa), though it is likely
    # not worth the effort to do such a change.
    if not message.is_stream_message():
        return

    remove_notify_users = prior_mention_user_ids - mentions_user_ids - stream_push_user_ids
    do_clear_mobile_push_notifications_for_ids(list(remove_notify_users), [message.id])


def do_clear_mobile_push_notifications_for_ids(
    user_profile_ids: List[int], message_ids: List[int]
) -> None:
    if len(message_ids) == 0:
        return

    # This function supports clearing notifications for several users
    # only for the message-edit use case where we'll have a single message_id.
    assert len(user_profile_ids) == 1 or len(message_ids) == 1

    messages_by_user = defaultdict(list)
    notifications_to_update = list(
        UserMessage.objects.filter(
            message_id__in=message_ids,
            user_profile_id__in=user_profile_ids,
        )
        .extra(
            where=[UserMessage.where_active_push_notification()],
        )
        .values_list("user_profile_id", "message_id")
    )

    for (user_id, message_id) in notifications_to_update:
        messages_by_user[user_id].append(message_id)

    for (user_profile_id, event_message_ids) in messages_by_user.items():
        queue_json_publish(
            "missedmessage_mobile_notifications",
            {
                "type": "remove",
                "user_profile_id": user_profile_id,
                "message_ids": event_message_ids,
            },
        )


def do_update_message_flags(
    user_profile: UserProfile, operation: str, flag: str, messages: List[int]
) -> int:
    valid_flags = [item for item in UserMessage.flags if item not in UserMessage.NON_API_FLAGS]
    if flag not in valid_flags:
        raise JsonableError(_("Invalid flag: '{}'").format(flag))
    if flag in UserMessage.NON_EDITABLE_FLAGS:
        raise JsonableError(_("Flag not editable: '{}'").format(flag))
    if operation not in ("add", "remove"):
        raise JsonableError(_("Invalid message flag operation: '{}'").format(operation))
    flagattr = getattr(UserMessage.flags, flag)

    msgs = UserMessage.objects.filter(user_profile=user_profile, message_id__in=messages)
    um_message_ids = {um.message_id for um in msgs}
    historical_message_ids = list(set(messages) - um_message_ids)

    # Users can mutate flags for messages that don't have a UserMessage yet.
    # First, validate that the user is even allowed to access these message_ids.
    for message_id in historical_message_ids:
        access_message(user_profile, message_id)

    # And then create historical UserMessage records.  See the called function for more context.
    create_historical_user_messages(user_id=user_profile.id, message_ids=historical_message_ids)

    if operation == "add":
        count = msgs.update(flags=F("flags").bitor(flagattr))
    elif operation == "remove":
        count = msgs.update(flags=F("flags").bitand(~flagattr))

    event = {
        "type": "update_message_flags",
        "op": operation,
        "operation": operation,
        "flag": flag,
        "messages": messages,
        "all": False,
    }

    if flag == "read" and operation == "remove":
        # When removing the read flag (i.e. marking messages as
        # unread), extend the event with an additional object with
        # details on the messages required to update the client's
        # `unread_msgs` data structure.
        raw_unread_data = get_raw_unread_data(user_profile, messages)
        event["message_details"] = format_unread_message_details(user_profile.id, raw_unread_data)

    send_event(user_profile.realm, event, [user_profile.id])

    if flag == "read" and operation == "add":
        event_time = timezone_now()
        do_clear_mobile_push_notifications_for_ids([user_profile.id], messages)

        do_increment_logging_stat(
            user_profile, COUNT_STATS["messages_read::hour"], None, event_time, increment=count
        )
        do_increment_logging_stat(
            user_profile,
            COUNT_STATS["messages_read_interactions::hour"],
            None,
            event_time,
            increment=min(1, count),
        )

    return count


class MessageUpdateUserInfoResult(TypedDict):
    message_user_ids: Set[int]
    mention_user_ids: Set[int]


def maybe_send_resolve_topic_notifications(
    *,
    user_profile: UserProfile,
    stream: Stream,
    old_topic: str,
    new_topic: str,
    changed_messages: List[Message],
) -> None:
    # Note that topics will have already been stripped in check_update_message.
    #
    # This logic is designed to treat removing a weird "✔ ✔✔ "
    # prefix as unresolving the topic.
    if old_topic.lstrip(RESOLVED_TOPIC_PREFIX) != new_topic.lstrip(RESOLVED_TOPIC_PREFIX):
        return

    topic_resolved: bool = new_topic.startswith(RESOLVED_TOPIC_PREFIX) and not old_topic.startswith(
        RESOLVED_TOPIC_PREFIX
    )
    topic_unresolved: bool = old_topic.startswith(
        RESOLVED_TOPIC_PREFIX
    ) and not new_topic.startswith(RESOLVED_TOPIC_PREFIX)

    if not topic_resolved and not topic_unresolved:
        # If there's some other weird topic that does not toggle the
        # state of "topic starts with RESOLVED_TOPIC_PREFIX", we do
        # nothing. Any other logic could result in cases where we send
        # these notifications in a non-alternating fashion.
        #
        # Note that it is still possible for an individual topic to
        # have multiple "This topic was marked as resolved"
        # notifications in a row: one can send new messages to the
        # pre-resolve topic and then resolve the topic created that
        # way to get multiple in the resolved topic. And then an
        # administrator can the messages in between. We consider this
        # to be a fundamental risk of irresponsible message deletion,
        # not a bug with the "resolve topics" feature.
        return

    # Compute the users who either sent or reacted to messages that
    # were moved via the "resolve topic' action. Only those users
    # should be eligible for this message being managed as unread.
    affected_participant_ids = {message.sender_id for message in changed_messages} | set(
        Reaction.objects.filter(message__in=changed_messages).values_list(
            "user_profile_id", flat=True
        )
    )
    sender = get_system_bot(settings.NOTIFICATION_BOT, user_profile.realm_id)
    user_mention = silent_mention_syntax_for_user(user_profile)
    with override_language(stream.realm.default_language):
        if topic_resolved:
            notification_string = _("{user} has marked this topic as resolved.")
        elif topic_unresolved:
            notification_string = _("{user} has marked this topic as unresolved.")

        internal_send_stream_message(
            sender,
            stream,
            new_topic,
            notification_string.format(
                user=user_mention,
            ),
            limit_unread_user_ids=affected_participant_ids,
        )


def send_message_moved_breadcrumbs(
    user_profile: UserProfile,
    old_stream: Stream,
    old_topic: str,
    old_thread_notification_string: Optional[str],
    new_stream: Stream,
    new_topic: Optional[str],
    new_thread_notification_string: Optional[str],
    changed_messages_count: int,
) -> None:
    # Since moving content between streams is highly disruptive,
    # it's worth adding a couple tombstone messages showing what
    # happened.
    sender = get_system_bot(settings.NOTIFICATION_BOT, old_stream.realm_id)

    if new_topic is None:
        new_topic = old_topic

    user_mention = silent_mention_syntax_for_user(user_profile)
    old_topic_link = f"#**{old_stream.name}>{old_topic}**"
    new_topic_link = f"#**{new_stream.name}>{new_topic}**"

    if new_thread_notification_string is not None:
        with override_language(new_stream.realm.default_language):
            internal_send_stream_message(
                sender,
                new_stream,
                new_topic,
                new_thread_notification_string.format(
                    old_location=old_topic_link,
                    user=user_mention,
                    changed_messages_count=changed_messages_count,
                ),
            )

    if old_thread_notification_string is not None:
        with override_language(old_stream.realm.default_language):
            # Send a notification to the old stream that the topic was moved.
            internal_send_stream_message(
                sender,
                old_stream,
                old_topic,
                old_thread_notification_string.format(
                    user=user_mention,
                    new_location=new_topic_link,
                    changed_messages_count=changed_messages_count,
                ),
            )


def get_user_info_for_message_updates(message_id: int) -> MessageUpdateUserInfoResult:

    # We exclude UserMessage.flags.historical rows since those
    # users did not receive the message originally, and thus
    # probably are not relevant for reprocessed alert_words,
    # mentions and similar rendering features.  This may be a
    # decision we change in the future.
    query = UserMessage.objects.filter(
        message=message_id,
        flags=~UserMessage.flags.historical,
    ).values("user_profile_id", "flags")
    rows = list(query)

    message_user_ids = {row["user_profile_id"] for row in rows}

    mask = UserMessage.flags.mentioned | UserMessage.flags.wildcard_mentioned

    mention_user_ids = {row["user_profile_id"] for row in rows if int(row["flags"]) & mask}

    return dict(
        message_user_ids=message_user_ids,
        mention_user_ids=mention_user_ids,
    )


def update_user_message_flags(
    rendering_result: MessageRenderingResult, ums: Iterable[UserMessage]
) -> None:
    wildcard = rendering_result.mentions_wildcard
    mentioned_ids = rendering_result.mentions_user_ids
    ids_with_alert_words = rendering_result.user_ids_with_alert_words
    changed_ums: Set[UserMessage] = set()

    def update_flag(um: UserMessage, should_set: bool, flag: int) -> None:
        if should_set:
            if not (um.flags & flag):
                um.flags |= flag
                changed_ums.add(um)
        else:
            if um.flags & flag:
                um.flags &= ~flag
                changed_ums.add(um)

    for um in ums:
        has_alert_word = um.user_profile_id in ids_with_alert_words
        update_flag(um, has_alert_word, UserMessage.flags.has_alert_word)

        mentioned = um.user_profile_id in mentioned_ids
        update_flag(um, mentioned, UserMessage.flags.mentioned)

        update_flag(um, wildcard, UserMessage.flags.wildcard_mentioned)

    for um in changed_ums:
        um.save(update_fields=["flags"])


def do_update_embedded_data(
    user_profile: UserProfile,
    message: Message,
    content: Optional[str],
    rendering_result: MessageRenderingResult,
) -> None:
    timestamp = timezone_now()
    event: Dict[str, Any] = {
        "type": "update_message",
        "user_id": None,
        "edit_timestamp": datetime_to_timestamp(timestamp),
        "message_id": message.id,
        "rendering_only": True,
    }
    changed_messages = [message]
    rendered_content: Optional[str] = None

    ums = UserMessage.objects.filter(message=message.id)

    if content is not None:
        update_user_message_flags(rendering_result, ums)
        rendered_content = rendering_result.rendered_content
        message.rendered_content = rendered_content
        message.rendered_content_version = markdown_version
        event["content"] = content
        event["rendered_content"] = rendered_content

    message.save(update_fields=["content", "rendered_content"])

    event["message_ids"] = update_to_dict_cache(changed_messages)

    def user_info(um: UserMessage) -> Dict[str, Any]:
        return {
            "id": um.user_profile_id,
            "flags": um.flags_list(),
        }

    send_event(user_profile.realm, event, list(map(user_info, ums)))


class DeleteMessagesEvent(TypedDict, total=False):
    type: str
    message_ids: List[int]
    message_type: str
    topic: str
    stream_id: int


# We use transaction.atomic to support select_for_update in the attachment codepath.
@transaction.atomic(savepoint=False)
def do_update_message(
    user_profile: UserProfile,
    target_message: Message,
    new_stream: Optional[Stream],
    topic_name: Optional[str],
    propagate_mode: str,
    send_notification_to_old_thread: bool,
    send_notification_to_new_thread: bool,
    content: Optional[str],
    rendering_result: Optional[MessageRenderingResult],
    prior_mention_user_ids: Set[int],
    mention_data: Optional[MentionData] = None,
) -> int:
    """
    The main function for message editing.  A message edit event can
    modify:
    * the message's content (in which case the caller will have
      set both content and rendered_content),
    * the topic, in which case the caller will have set topic_name
    * or both message's content and the topic
    * or stream and/or topic, in which case the caller will have set
        new_stream and/or topic_name.

    With topic edits, propagate_mode determines whether other message
    also have their topics edited.
    """
    timestamp = timezone_now()
    target_message.last_edit_time = timestamp

    event: Dict[str, Any] = {
        "type": "update_message",
        "user_id": user_profile.id,
        "edit_timestamp": datetime_to_timestamp(timestamp),
        "message_id": target_message.id,
        "rendering_only": False,
    }

    edit_history_event: EditHistoryEvent = {
        "user_id": user_profile.id,
        "timestamp": event["edit_timestamp"],
    }

    changed_messages = [target_message]

    realm = user_profile.realm

    stream_being_edited = None
    if target_message.is_stream_message():
        stream_id = target_message.recipient.type_id
        stream_being_edited = get_stream_by_id_in_realm(stream_id, realm)
        event["stream_name"] = stream_being_edited.name
        event["stream_id"] = stream_being_edited.id

    ums = UserMessage.objects.filter(message=target_message.id)

    if content is not None:
        assert rendering_result is not None

        # mention_data is required if there's a content edit.
        assert mention_data is not None

        # add data from group mentions to mentions_user_ids.
        for group_id in rendering_result.mentions_user_group_ids:
            members = mention_data.get_group_members(group_id)
            rendering_result.mentions_user_ids.update(members)

        update_user_message_flags(rendering_result, ums)

        # One could imagine checking realm.allow_edit_history here and
        # modifying the events based on that setting, but doing so
        # doesn't really make sense.  We need to send the edit event
        # to clients regardless, and a client already had access to
        # the original/pre-edit content of the message anyway.  That
        # setting must be enforced on the client side, and making a
        # change here simply complicates the logic for clients parsing
        # edit history events.
        event["orig_content"] = target_message.content
        event["orig_rendered_content"] = target_message.rendered_content
        edit_history_event["prev_content"] = target_message.content
        edit_history_event["prev_rendered_content"] = target_message.rendered_content
        edit_history_event[
            "prev_rendered_content_version"
        ] = target_message.rendered_content_version
        target_message.content = content
        target_message.rendered_content = rendering_result.rendered_content
        target_message.rendered_content_version = markdown_version
        event["content"] = content
        event["rendered_content"] = rendering_result.rendered_content
        event["prev_rendered_content_version"] = target_message.rendered_content_version
        event["is_me_message"] = Message.is_status_message(
            content, rendering_result.rendered_content
        )

        # target_message.has_image and target_message.has_link will have been
        # already updated by Markdown rendering in the caller.
        target_message.has_attachment = check_attachment_reference_change(
            target_message, rendering_result
        )

        if target_message.is_stream_message():
            if topic_name is not None:
                new_topic_name = topic_name
            else:
                new_topic_name = target_message.topic_name()

            stream_topic: Optional[StreamTopicTarget] = StreamTopicTarget(
                stream_id=stream_id,
                topic_name=new_topic_name,
            )
        else:
            stream_topic = None

        info = get_recipient_info(
            realm_id=realm.id,
            recipient=target_message.recipient,
            sender_id=target_message.sender_id,
            stream_topic=stream_topic,
            possible_wildcard_mention=mention_data.message_has_wildcards(),
        )

        event["online_push_user_ids"] = list(info["online_push_user_ids"])
        event["pm_mention_push_disabled_user_ids"] = list(info["pm_mention_push_disabled_user_ids"])
        event["pm_mention_email_disabled_user_ids"] = list(
            info["pm_mention_email_disabled_user_ids"]
        )
        event["stream_push_user_ids"] = list(info["stream_push_user_ids"])
        event["stream_email_user_ids"] = list(info["stream_email_user_ids"])
        event["muted_sender_user_ids"] = list(info["muted_sender_user_ids"])
        event["prior_mention_user_ids"] = list(prior_mention_user_ids)
        event["presence_idle_user_ids"] = filter_presence_idle_user_ids(info["active_user_ids"])
        event["all_bot_user_ids"] = list(info["all_bot_user_ids"])
        if rendering_result.mentions_wildcard:
            event["wildcard_mention_user_ids"] = list(info["wildcard_mention_user_ids"])
        else:
            event["wildcard_mention_user_ids"] = []

        do_update_mobile_push_notification(
            target_message,
            prior_mention_user_ids,
            rendering_result.mentions_user_ids,
            info["stream_push_user_ids"],
        )

    if topic_name is not None or new_stream is not None:
        orig_topic_name = target_message.topic_name()
        event["propagate_mode"] = propagate_mode

    if new_stream is not None:
        assert content is None
        assert target_message.is_stream_message()
        assert stream_being_edited is not None

        edit_history_event["prev_stream"] = stream_being_edited.id
        edit_history_event["stream"] = new_stream.id
        event[ORIG_TOPIC] = orig_topic_name
        target_message.recipient_id = new_stream.recipient_id

        event["new_stream_id"] = new_stream.id
        event["propagate_mode"] = propagate_mode

        # When messages are moved from one stream to another, some
        # users may lose access to those messages, including guest
        # users and users not subscribed to the new stream (if it is a
        # private stream).  For those users, their experience is as
        # though the messages were deleted, and we should send a
        # delete_message event to them instead.

        subs_to_old_stream = get_active_subscriptions_for_stream_id(
            stream_id, include_deactivated_users=True
        ).select_related("user_profile")
        subs_to_new_stream = list(
            get_active_subscriptions_for_stream_id(
                new_stream.id, include_deactivated_users=True
            ).select_related("user_profile")
        )

        old_stream_sub_ids = [user.user_profile_id for user in subs_to_old_stream]
        new_stream_sub_ids = [user.user_profile_id for user in subs_to_new_stream]

        # Get users who aren't subscribed to the new_stream.
        subs_losing_usermessages = [
            sub for sub in subs_to_old_stream if sub.user_profile_id not in new_stream_sub_ids
        ]
        # Users who can longer access the message without some action
        # from administrators.
        subs_losing_access = [
            sub
            for sub in subs_losing_usermessages
            if sub.user_profile.is_guest or not new_stream.is_public()
        ]
        ums = ums.exclude(
            user_profile_id__in=[sub.user_profile_id for sub in subs_losing_usermessages]
        )

        subs_gaining_usermessages = []
        if not new_stream.is_history_public_to_subscribers():
            # For private streams, with history not public to subscribers,
            # We find out users who are not present in the msgs' old stream
            # and create new UserMessage for these users so that they can
            # access this message.
            subs_gaining_usermessages += [
                user_id for user_id in new_stream_sub_ids if user_id not in old_stream_sub_ids
            ]

    if topic_name is not None:
        topic_name = truncate_topic(topic_name)
        target_message.set_topic_name(topic_name)

        # These fields have legacy field names.
        event[ORIG_TOPIC] = orig_topic_name
        event[TOPIC_NAME] = topic_name
        event[TOPIC_LINKS] = topic_links(target_message.sender.realm_id, topic_name)
        edit_history_event["prev_topic"] = orig_topic_name
        edit_history_event["topic"] = topic_name

    update_edit_history(target_message, timestamp, edit_history_event)

    delete_event_notify_user_ids: List[int] = []
    if propagate_mode in ["change_later", "change_all"]:
        assert topic_name is not None or new_stream is not None
        assert stream_being_edited is not None

        # Other messages should only get topic/stream fields in their edit history.
        topic_only_edit_history_event: EditHistoryEvent = {
            "user_id": edit_history_event["user_id"],
            "timestamp": edit_history_event["timestamp"],
        }
        if topic_name is not None:
            topic_only_edit_history_event["prev_topic"] = edit_history_event["prev_topic"]
            topic_only_edit_history_event["topic"] = edit_history_event["topic"]
        if new_stream is not None:
            topic_only_edit_history_event["prev_stream"] = edit_history_event["prev_stream"]
            topic_only_edit_history_event["stream"] = edit_history_event["stream"]

        messages_list = update_messages_for_topic_edit(
            acting_user=user_profile,
            edited_message=target_message,
            propagate_mode=propagate_mode,
            orig_topic_name=orig_topic_name,
            topic_name=topic_name,
            new_stream=new_stream,
            old_stream=stream_being_edited,
            edit_history_event=topic_only_edit_history_event,
            last_edit_time=timestamp,
        )
        changed_messages += messages_list

        if new_stream is not None:
            assert stream_being_edited is not None
            changed_message_ids = [msg.id for msg in changed_messages]

            if subs_gaining_usermessages:
                ums_to_create = []
                for message_id in changed_message_ids:
                    for user_profile_id in subs_gaining_usermessages:
                        # The fact that the user didn't have a UserMessage originally means we can infer that the user
                        # was not mentioned in the original message (even if mention syntax was present, it would not
                        # take effect for a user who was not subscribed). If we were editing the message's content, we
                        # would rerender the message and then use the new stream's data to determine whether this is
                        # a mention of a subscriber; but as we are not doing so, we choose to preserve the "was this
                        # mention syntax an actual mention" decision made during the original rendering for implementation
                        # simplicity. As a result, the only flag to consider applying here is read.
                        um = UserMessageLite(
                            user_profile_id=user_profile_id,
                            message_id=message_id,
                            flags=UserMessage.flags.read,
                        )
                        ums_to_create.append(um)
                bulk_insert_ums(ums_to_create)

            # Delete UserMessage objects for users who will no
            # longer have access to these messages.  Note: This could be
            # very expensive, since it's N guest users x M messages.
            UserMessage.objects.filter(
                user_profile_id__in=[sub.user_profile_id for sub in subs_losing_usermessages],
                message_id__in=changed_message_ids,
            ).delete()

            delete_event: DeleteMessagesEvent = {
                "type": "delete_message",
                "message_ids": changed_message_ids,
                "message_type": "stream",
                "stream_id": stream_being_edited.id,
                "topic": orig_topic_name,
            }
            delete_event_notify_user_ids = [sub.user_profile_id for sub in subs_losing_access]
            send_event(user_profile.realm, delete_event, delete_event_notify_user_ids)

            # Reset the Attachment.is_*_public caches for all messages
            # moved to another stream with different access permissions.
            if new_stream.invite_only != stream_being_edited.invite_only:
                Attachment.objects.filter(messages__in=changed_message_ids).update(
                    is_realm_public=None,
                )
                ArchivedAttachment.objects.filter(messages__in=changed_message_ids).update(
                    is_realm_public=None,
                )

            if new_stream.is_web_public != stream_being_edited.is_web_public:
                Attachment.objects.filter(messages__in=changed_message_ids).update(
                    is_web_public=None,
                )
                ArchivedAttachment.objects.filter(messages__in=changed_message_ids).update(
                    is_web_public=None,
                )

    # This does message.save(update_fields=[...])
    save_message_for_edit_use_case(message=target_message)

    realm_id: Optional[int] = None
    if stream_being_edited is not None:
        realm_id = stream_being_edited.realm_id

    event["message_ids"] = update_to_dict_cache(changed_messages, realm_id)

    def user_info(um: UserMessage) -> Dict[str, Any]:
        return {
            "id": um.user_profile_id,
            "flags": um.flags_list(),
        }

    # The following blocks arranges that users who are subscribed to a
    # stream and can see history from before they subscribed get
    # live-update when old messages are edited (e.g. if the user does
    # a topic edit themself).
    #
    # We still don't send an update event to users who are not
    # subscribed to this stream and don't have a UserMessage row. This
    # means if a non-subscriber is viewing the narrow, they won't get
    # a real-time updates. This is a balance between sending
    # message-edit notifications for every public stream to every user
    # in the organization (too expansive, and also not what we do for
    # newly sent messages anyway) and having magical live-updates
    # where possible.
    users_to_be_notified = list(map(user_info, ums))
    if stream_being_edited is not None:
        if stream_being_edited.is_history_public_to_subscribers:
            subscriptions = get_active_subscriptions_for_stream_id(
                stream_id, include_deactivated_users=False
            )
            # We exclude long-term idle users, since they by
            # definition have no active clients.
            subscriptions = subscriptions.exclude(user_profile__long_term_idle=True)
            # Remove duplicates by excluding the id of users already
            # in users_to_be_notified list.  This is the case where a
            # user both has a UserMessage row and is a current
            # Subscriber
            subscriptions = subscriptions.exclude(
                user_profile_id__in=[um.user_profile_id for um in ums]
            )

            if new_stream is not None:
                assert delete_event_notify_user_ids is not None
                subscriptions = subscriptions.exclude(
                    user_profile_id__in=delete_event_notify_user_ids
                )

            # All users that are subscribed to the stream must be
            # notified when a message is edited
            subscriber_ids = set(subscriptions.values_list("user_profile_id", flat=True))

            if new_stream is not None:
                # TODO: Guest users don't see the new moved topic
                # unless breadcrumb message for new stream is
                # enabled. Excluding these users from receiving this
                # event helps us avoid a error traceback for our
                # clients. We should figure out a way to inform the
                # guest users of this new topic if sending a 'message'
                # event for these messages is not an option.
                #
                # Don't send this event to guest subs who are not
                # subscribers of the old stream but are subscribed to
                # the new stream; clients will be confused.
                old_stream_unsubbed_guests = [
                    sub
                    for sub in subs_to_new_stream
                    if sub.user_profile.is_guest and sub.user_profile_id not in subscriber_ids
                ]
                subscriptions = subscriptions.exclude(
                    user_profile_id__in=[sub.user_profile_id for sub in old_stream_unsubbed_guests]
                )
                subscriber_ids = set(subscriptions.values_list("user_profile_id", flat=True))

            users_to_be_notified += list(map(subscriber_info, sorted(list(subscriber_ids))))

    # UserTopic updates and the content of notifications depend on
    # whether we've moved the entire topic, or just part of it. We
    # make that determination here.
    moved_all_visible_messages = False
    if topic_name is not None or new_stream is not None:
        assert stream_being_edited is not None

        if propagate_mode == "change_all":
            moved_all_visible_messages = True
        else:
            # With other propagate modes, if the user in fact moved
            # all messages in the stream, we want to explain it was a
            # full-topic move.
            #
            # For security model reasons, we don't want to allow a
            # user to take any action that would leak information
            # about older messages they cannot access (E.g. the only
            # remaining messages are in a stream without shared
            # history). The bulk_access_messages call below addresses
            # that concern.
            #
            # bulk_access_messages is inefficient for this task, since
            # we just want to do the exists() version of this
            # query. But it's nice to reuse code, and this bulk
            # operation is likely cheaper than a `GET /messages`
            # unless the topic has thousands of messages of history.
            unmoved_messages = messages_for_topic(
                stream_being_edited.recipient_id,
                orig_topic_name,
            )
            visible_unmoved_messages = bulk_access_messages(
                user_profile, unmoved_messages, stream=stream_being_edited
            )
            moved_all_visible_messages = len(visible_unmoved_messages) == 0

    # Migrate muted topic configuration in the following circumstances:
    #
    # * If propagate_mode is change_all, do so unconditionally.
    #
    # * If propagate_mode is change_later or change_one, do so when
    #   the acting user has moved the entire topic (as visible to them).
    #
    # This rule corresponds to checking moved_all_visible_messages.
    #
    # We may want more complex behavior in cases where one appears to
    # be merging topics (E.g. there are existing messages in the
    # target topic).
    if moved_all_visible_messages:
        assert stream_being_edited is not None
        assert topic_name is not None or new_stream is not None

        for muting_user in get_users_muting_topic(stream_being_edited.id, orig_topic_name):
            # TODO: Ideally, this would be a bulk update operation,
            # because we are doing database operations in a loop here.
            #
            # This loop is only acceptable in production because it is
            # rare for more than a few users to have muted an
            # individual topic that is being moved; as of this
            # writing, no individual topic in Zulip Cloud had been
            # muted by more than 100 users.

            if new_stream is not None and muting_user.id in delete_event_notify_user_ids:
                # If the messages are being moved to a stream the user
                # cannot access, then we treat this as the
                # messages/topic being deleted for this user. This is
                # important for security reasons; we don't want to
                # give users a UserTopic row in a stream they cannot
                # access.  Unmute the topic for such users.
                do_unmute_topic(muting_user, stream_being_edited, orig_topic_name)
            else:
                # Otherwise, we move the muted topic record for the user.
                # We call remove_topic_mute rather than do_unmute_topic to
                # avoid sending two events with new muted topics in
                # immediate succession; this is correct only because
                # muted_topics events always send the full set of topics.
                remove_topic_mute(muting_user, stream_being_edited.id, orig_topic_name)
                do_mute_topic(
                    muting_user,
                    new_stream if new_stream is not None else stream_being_edited,
                    topic_name if topic_name is not None else orig_topic_name,
                    ignore_duplicate=True,
                )

    send_event(user_profile.realm, event, users_to_be_notified)

    if len(changed_messages) > 0 and new_stream is not None and stream_being_edited is not None:
        # Notify users that the topic was moved.
        changed_messages_count = len(changed_messages)

        old_thread_notification_string = None
        if send_notification_to_old_thread:
            if moved_all_visible_messages:
                old_thread_notification_string = gettext_lazy(
                    "This topic was moved to {new_location} by {user}."
                )
            elif changed_messages_count == 1:
                old_thread_notification_string = gettext_lazy(
                    "A message was moved from this topic to {new_location} by {user}."
                )
            else:
                old_thread_notification_string = gettext_lazy(
                    "{changed_messages_count} messages were moved from this topic to {new_location} by {user}."
                )

        new_thread_notification_string = None
        if send_notification_to_new_thread:
            if moved_all_visible_messages:
                new_thread_notification_string = gettext_lazy(
                    "This topic was moved here from {old_location} by {user}."
                )
            elif changed_messages_count == 1:
                new_thread_notification_string = gettext_lazy(
                    "A message was moved here from {old_location} by {user}."
                )
            else:
                new_thread_notification_string = gettext_lazy(
                    "{changed_messages_count} messages were moved here from {old_location} by {user}."
                )

        send_message_moved_breadcrumbs(
            user_profile,
            stream_being_edited,
            orig_topic_name,
            old_thread_notification_string,
            new_stream,
            topic_name,
            new_thread_notification_string,
            changed_messages_count,
        )

    if (
        topic_name is not None
        and new_stream is None
        and content is None
        and len(changed_messages) > 0
    ):
        assert stream_being_edited is not None
        maybe_send_resolve_topic_notifications(
            user_profile=user_profile,
            stream=stream_being_edited,
            old_topic=orig_topic_name,
            new_topic=topic_name,
            changed_messages=changed_messages,
        )

    return len(changed_messages)


def do_delete_messages(realm: Realm, messages: Iterable[Message]) -> None:
    # messages in delete_message event belong to the same topic
    # or is a single private message, as any other behaviour is not possible with
    # the current callers to this method.
    messages = list(messages)
    message_ids = [message.id for message in messages]
    if not message_ids:
        return

    event: DeleteMessagesEvent = {
        "type": "delete_message",
        "message_ids": message_ids,
    }

    sample_message = messages[0]
    message_type = "stream"
    users_to_notify = []
    if not sample_message.is_stream_message():
        assert len(messages) == 1
        message_type = "private"
        ums = UserMessage.objects.filter(message_id__in=message_ids)
        users_to_notify = [um.user_profile_id for um in ums]
        archiving_chunk_size = retention.MESSAGE_BATCH_SIZE

    if message_type == "stream":
        stream_id = sample_message.recipient.type_id
        event["stream_id"] = stream_id
        event["topic"] = sample_message.topic_name()
        subscriptions = get_active_subscriptions_for_stream_id(
            stream_id, include_deactivated_users=False
        )
        # We exclude long-term idle users, since they by definition have no active clients.
        subscriptions = subscriptions.exclude(user_profile__long_term_idle=True)
        users_to_notify = list(subscriptions.values_list("user_profile_id", flat=True))
        archiving_chunk_size = retention.STREAM_MESSAGE_BATCH_SIZE

    move_messages_to_archive(message_ids, realm=realm, chunk_size=archiving_chunk_size)

    event["message_type"] = message_type
    transaction.on_commit(lambda: send_event(realm, event, users_to_notify))


def do_delete_messages_by_sender(user: UserProfile) -> None:
    message_ids = list(
        Message.objects.filter(sender=user).values_list("id", flat=True).order_by("id")
    )
    if message_ids:
        move_messages_to_archive(message_ids, chunk_size=retention.STREAM_MESSAGE_BATCH_SIZE)


def email_not_system_bot(email: str) -> None:
    if is_cross_realm_bot_email(email):
        msg = email_reserved_for_system_bots_error(email)
        code = msg
        raise ValidationError(
            msg,
            code=code,
            params=dict(deactivated=False),
        )


def do_mute_user(
    user_profile: UserProfile,
    muted_user: UserProfile,
    date_muted: Optional[datetime.datetime] = None,
) -> None:
    if date_muted is None:
        date_muted = timezone_now()
    add_user_mute(user_profile, muted_user, date_muted)
    do_mark_muted_user_messages_as_read(user_profile, muted_user)
    event = dict(type="muted_users", muted_users=get_user_mutes(user_profile))
    send_event(user_profile.realm, event, [user_profile.id])

    RealmAuditLog.objects.create(
        realm=user_profile.realm,
        acting_user=user_profile,
        modified_user=user_profile,
        event_type=RealmAuditLog.USER_MUTED,
        event_time=date_muted,
        extra_data=orjson.dumps({"muted_user_id": muted_user.id}).decode(),
    )


def do_unmute_user(mute_object: MutedUser) -> None:
    user_profile = mute_object.user_profile
    muted_user = mute_object.muted_user
    mute_object.delete()
    event = dict(type="muted_users", muted_users=get_user_mutes(user_profile))
    send_event(user_profile.realm, event, [user_profile.id])

    RealmAuditLog.objects.create(
        realm=user_profile.realm,
        acting_user=user_profile,
        modified_user=user_profile,
        event_type=RealmAuditLog.USER_UNMUTED,
        event_time=timezone_now(),
        extra_data=orjson.dumps({"unmuted_user_id": muted_user.id}).decode(),
    )


@transaction.atomic(durable=True)
def do_add_realm_domain(
    realm: Realm, domain: str, allow_subdomains: bool, *, acting_user: Optional[UserProfile]
) -> (RealmDomain):
    realm_domain = RealmDomain.objects.create(
        realm=realm, domain=domain, allow_subdomains=allow_subdomains
    )

    RealmAuditLog.objects.create(
        realm=realm,
        acting_user=acting_user,
        event_type=RealmAuditLog.REALM_DOMAIN_ADDED,
        event_time=timezone_now(),
        extra_data=orjson.dumps(
            {
                "realm_domains": get_realm_domains(realm),
                "added_domain": {"domain": domain, "allow_subdomains": allow_subdomains},
            }
        ).decode(),
    )

    event = dict(
        type="realm_domains",
        op="add",
        realm_domain=dict(
            domain=realm_domain.domain, allow_subdomains=realm_domain.allow_subdomains
        ),
    )
    transaction.on_commit(lambda: send_event(realm, event, active_user_ids(realm.id)))

    return realm_domain


@transaction.atomic(durable=True)
def do_change_realm_domain(
    realm_domain: RealmDomain, allow_subdomains: bool, *, acting_user: Optional[UserProfile]
) -> None:
    realm_domain.allow_subdomains = allow_subdomains
    realm_domain.save(update_fields=["allow_subdomains"])

    RealmAuditLog.objects.create(
        realm=realm_domain.realm,
        acting_user=acting_user,
        event_type=RealmAuditLog.REALM_DOMAIN_CHANGED,
        event_time=timezone_now(),
        extra_data=orjson.dumps(
            {
                "realm_domains": get_realm_domains(realm_domain.realm),
                "changed_domain": {
                    "domain": realm_domain.domain,
                    "allow_subdomains": realm_domain.allow_subdomains,
                },
            }
        ).decode(),
    )

    event = dict(
        type="realm_domains",
        op="change",
        realm_domain=dict(
            domain=realm_domain.domain, allow_subdomains=realm_domain.allow_subdomains
        ),
    )
    transaction.on_commit(
        lambda: send_event(realm_domain.realm, event, active_user_ids(realm_domain.realm_id))
    )


@transaction.atomic(durable=True)
def do_remove_realm_domain(
    realm_domain: RealmDomain, *, acting_user: Optional[UserProfile]
) -> None:
    realm = realm_domain.realm
    domain = realm_domain.domain
    realm_domain.delete()

    RealmAuditLog.objects.create(
        realm=realm,
        acting_user=acting_user,
        event_type=RealmAuditLog.REALM_DOMAIN_REMOVED,
        event_time=timezone_now(),
        extra_data=orjson.dumps(
            {
                "realm_domains": get_realm_domains(realm),
                "removed_domain": {
                    "domain": realm_domain.domain,
                    "allow_subdomains": realm_domain.allow_subdomains,
                },
            }
        ).decode(),
    )

    if RealmDomain.objects.filter(realm=realm).count() == 0 and realm.emails_restricted_to_domains:
        # If this was the last realm domain, we mark the realm as no
        # longer restricted to domain, because the feature doesn't do
        # anything if there are no domains, and this is probably less
        # confusing than the alternative.
        do_set_realm_property(realm, "emails_restricted_to_domains", False, acting_user=acting_user)
    event = dict(type="realm_domains", op="remove", domain=domain)
    transaction.on_commit(lambda: send_event(realm, event, active_user_ids(realm.id)))


def do_send_realm_reactivation_email(realm: Realm, *, acting_user: Optional[UserProfile]) -> None:
    url = create_confirmation_link(realm, Confirmation.REALM_REACTIVATION)
    RealmAuditLog.objects.create(
        realm=realm,
        acting_user=acting_user,
        event_type=RealmAuditLog.REALM_REACTIVATION_EMAIL_SENT,
        event_time=timezone_now(),
    )
    context = {"confirmation_url": url, "realm_uri": realm.uri, "realm_name": realm.name}
    language = realm.default_language
    send_email_to_admins(
        "zerver/emails/realm_reactivation",
        realm,
        from_address=FromAddress.tokenized_no_reply_address(),
        from_name=FromAddress.security_email_from_name(language=language),
        language=language,
        context=context,
    )


def get_topic_messages(user_profile: UserProfile, stream: Stream, topic_name: str) -> List[Message]:
    query = UserMessage.objects.filter(
        user_profile=user_profile,
        message__recipient=stream.recipient,
    ).order_by("id")
    return [um.message for um in filter_by_topic_name_via_message(query, topic_name)]
