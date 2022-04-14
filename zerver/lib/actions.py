import datetime
import hashlib
import logging
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import (
    AbstractSet,
    Any,
    Callable,
    Collection,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)

import orjson
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils.html import escape
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.utils.translation import override as override_language
from typing_extensions import TypedDict

from analytics.lib.counts import COUNT_STATS, do_increment_logging_stat
from confirmation import settings as confirmation_settings
from confirmation.models import Confirmation, create_confirmation_link, generate_key
from zerver.actions.custom_profile_fields import do_remove_realm_custom_profile_fields
from zerver.actions.default_streams import (
    do_remove_default_stream,
    do_remove_streams_from_default_stream_group,
    get_default_streams_for_realm,
)
from zerver.actions.invites import notify_invites_changed
from zerver.actions.uploads import check_attachment_reference_change, do_claim_attachments
from zerver.actions.user_groups import (
    do_send_user_group_members_update_event,
    update_users_in_full_members_system_group,
)
from zerver.actions.user_topics import do_mute_topic, do_unmute_topic
from zerver.actions.users import change_user_is_active, get_service_dicts_for_bot
from zerver.lib import retention as retention
from zerver.lib.addressee import Addressee
from zerver.lib.alert_words import get_alert_word_automaton
from zerver.lib.avatar import avatar_url
from zerver.lib.bulk_create import create_users
from zerver.lib.cache import (
    cache_delete,
    cache_delete_many,
    cache_set,
    cache_with_key,
    delete_user_profile_caches,
    display_recipient_cache_key,
    flush_user_profile,
    get_stream_cache_key,
    to_dict_cache_key_id,
    user_profile_by_api_key_cache_key,
    user_profile_delivery_email_cache_key,
)
from zerver.lib.create_user import create_user, get_display_email_address
from zerver.lib.email_mirror_helpers import encode_email_address
from zerver.lib.email_notifications import enqueue_welcome_emails
from zerver.lib.email_validation import email_reserved_for_system_bots_error
from zerver.lib.emoji import check_emoji_request, emoji_name_to_emoji_code
from zerver.lib.exceptions import (
    JsonableError,
    MarkdownRenderingException,
    StreamDoesNotExistError,
    StreamWithIDDoesNotExistError,
    ZephyrMessageAlreadySentException,
)
from zerver.lib.i18n import get_language_name
from zerver.lib.markdown import MessageRenderingResult, topic_links
from zerver.lib.markdown import version as markdown_version
from zerver.lib.mention import MentionBackend, MentionData, silent_mention_syntax_for_user
from zerver.lib.message import (
    MessageDict,
    SendMessageRequest,
    access_message,
    bulk_access_messages,
    format_unread_message_details,
    get_last_message_id,
    get_raw_unread_data,
    normalize_body,
    render_markdown,
    truncate_topic,
    update_first_visible_message_id,
    update_to_dict_cache,
    wildcard_mention_allowed,
)
from zerver.lib.notification_data import UserMessageNotificationsData, get_user_group_mentions_data
from zerver.lib.queue import queue_json_publish
from zerver.lib.recipient_users import recipient_for_user_profiles
from zerver.lib.retention import move_messages_to_archive
from zerver.lib.send_email import (
    FromAddress,
    clear_scheduled_emails,
    clear_scheduled_invitation_emails,
    send_email,
    send_email_to_admins,
)
from zerver.lib.server_initialization import create_internal_realm, server_initialized
from zerver.lib.sessions import delete_user_sessions
from zerver.lib.stream_color import pick_colors
from zerver.lib.stream_subscription import (
    SubInfo,
    bulk_get_private_peers,
    bulk_get_subscriber_peer_info,
    get_active_subscriptions_for_stream_id,
    get_bulk_stream_subscriber_info,
    get_subscriptions_for_send_message,
    get_used_colors_for_user_ids,
    num_subscribers_for_stream_id,
    subscriber_ids_with_stream_history_access,
)
from zerver.lib.stream_topic import StreamTopicTarget
from zerver.lib.stream_traffic import get_average_weekly_stream_traffic, get_streams_traffic
from zerver.lib.streams import (
    access_stream_by_id,
    access_stream_for_send_message,
    can_access_stream_user_ids,
    check_stream_access_based_on_stream_post_policy,
    ensure_stream,
    get_default_value_for_history_public_to_subscribers,
    get_occupied_streams,
    get_signups_stream,
    get_stream_permission_policy_name,
    render_stream_description,
    send_stream_creation_event,
)
from zerver.lib.string_validation import check_stream_name, check_stream_topic
from zerver.lib.subscription_info import get_subscribers_query
from zerver.lib.timestamp import datetime_to_timestamp, timestamp_to_datetime
from zerver.lib.timezone import canonicalize_timezone
from zerver.lib.topic import (
    ORIG_TOPIC,
    RESOLVED_TOPIC_PREFIX,
    TOPIC_LINKS,
    TOPIC_NAME,
    filter_by_exact_message_topic,
    filter_by_topic_name_via_message,
    messages_for_topic,
    save_message_for_edit_use_case,
    update_edit_history,
    update_messages_for_topic_edit,
)
from zerver.lib.types import EditHistoryEvent
from zerver.lib.upload import delete_avatar_image
from zerver.lib.user_counts import realm_user_count, realm_user_count_by_role
from zerver.lib.user_groups import (
    create_system_user_groups_for_realm,
    get_system_user_group_for_user,
)
from zerver.lib.user_message import UserMessageLite, bulk_insert_ums
from zerver.lib.user_mutes import add_user_mute, get_muting_users, get_user_mutes
from zerver.lib.user_topics import get_users_muting_topic, remove_topic_mute
from zerver.lib.users import (
    check_bot_name_available,
    check_full_name,
    format_user_row,
    get_api_key,
    user_profile_to_user_row,
)
from zerver.lib.utils import generate_api_key, log_statsd_event
from zerver.lib.validator import check_widget_content
from zerver.lib.widget import do_widget_post_save_actions, is_widget_message
from zerver.models import (
    ArchivedAttachment,
    Attachment,
    Client,
    DefaultStream,
    DefaultStreamGroup,
    Draft,
    EmailChangeStatus,
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
    ScheduledMessage,
    ScheduledMessageNotificationEmail,
    Stream,
    Subscription,
    UserGroup,
    UserGroupMembership,
    UserMessage,
    UserPresence,
    UserProfile,
    active_non_guest_user_ids,
    active_user_ids,
    bot_owner_user_ids,
    get_client,
    get_huddle_user_ids,
    get_realm,
    get_realm_domains,
    get_stream,
    get_stream_by_id_in_realm,
    get_system_bot,
    get_user_by_delivery_email,
    is_cross_realm_bot_email,
    query_for_ids,
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


@transaction.atomic(savepoint=False)
def do_deactivate_stream(
    stream: Stream, log: bool = True, *, acting_user: Optional[UserProfile]
) -> None:
    # We want to mark all messages in the to-be-deactivated stream as
    # read for all users; otherwise they will pollute queries like
    # "Get the user's first unread message".  Since this can be an
    # expensive operation, we do it via the deferred_work queue
    # processor.
    deferred_work_event = {
        "type": "mark_stream_messages_as_read_for_everyone",
        "stream_recipient_id": stream.recipient_id,
    }
    transaction.on_commit(lambda: queue_json_publish("deferred_work", deferred_work_event))

    # Get the affected user ids *before* we deactivate everybody.
    affected_user_ids = can_access_stream_user_ids(stream)

    get_active_subscriptions_for_stream_id(stream.id, include_deactivated_users=True).update(
        active=False
    )

    was_invite_only = stream.invite_only
    stream.deactivated = True
    stream.invite_only = True
    # Preserve as much as possible the original stream name while giving it a
    # special prefix that both indicates that the stream is deactivated and
    # frees up the original name for reuse.
    old_name = stream.name

    # Prepend a substring of the hashed stream ID to the new stream name
    streamID = str(stream.id)
    stream_id_hash_object = hashlib.sha512(streamID.encode())
    hashed_stream_id = stream_id_hash_object.hexdigest()[0:7]

    new_name = (hashed_stream_id + "!DEACTIVATED:" + old_name)[: Stream.MAX_NAME_LENGTH]

    stream.name = new_name[: Stream.MAX_NAME_LENGTH]
    stream.save(update_fields=["name", "deactivated", "invite_only"])

    # If this is a default stream, remove it, properly sending a
    # notification to browser clients.
    if DefaultStream.objects.filter(realm_id=stream.realm_id, stream_id=stream.id).exists():
        do_remove_default_stream(stream)

    default_stream_groups_for_stream = DefaultStreamGroup.objects.filter(streams__id=stream.id)
    for group in default_stream_groups_for_stream:
        do_remove_streams_from_default_stream_group(stream.realm, group, [stream])

    # Remove the old stream information from remote cache.
    old_cache_key = get_stream_cache_key(old_name, stream.realm_id)
    cache_delete(old_cache_key)

    stream_dict = stream.to_dict()
    stream_dict.update(dict(name=old_name, invite_only=was_invite_only))
    event = dict(type="stream", op="delete", streams=[stream_dict])
    transaction.on_commit(lambda: send_event(stream.realm, event, affected_user_ids))

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=stream.realm,
        acting_user=acting_user,
        modified_stream=stream,
        event_type=RealmAuditLog.STREAM_DEACTIVATED,
        event_time=event_time,
    )


def send_user_email_update_event(user_profile: UserProfile) -> None:
    payload = dict(user_id=user_profile.id, new_email=user_profile.email)
    event = dict(type="realm_user", op="update", person=payload)
    transaction.on_commit(
        lambda: send_event(
            user_profile.realm,
            event,
            active_user_ids(user_profile.realm_id),
        )
    )


@transaction.atomic(savepoint=False)
def do_change_user_delivery_email(user_profile: UserProfile, new_email: str) -> None:
    delete_user_profile_caches([user_profile])

    user_profile.delivery_email = new_email
    if user_profile.email_address_is_realm_public():
        user_profile.email = new_email
        user_profile.save(update_fields=["email", "delivery_email"])
    else:
        user_profile.save(update_fields=["delivery_email"])

    # We notify just the target user (and eventually org admins, only
    # when email_address_visibility=EMAIL_ADDRESS_VISIBILITY_ADMINS)
    # about their new delivery email, since that field is private.
    payload = dict(user_id=user_profile.id, delivery_email=new_email)
    event = dict(type="realm_user", op="update", person=payload)
    transaction.on_commit(lambda: send_event(user_profile.realm, event, [user_profile.id]))

    if user_profile.avatar_source == UserProfile.AVATAR_FROM_GRAVATAR:
        # If the user is using Gravatar to manage their email address,
        # their Gravatar just changed, and we need to notify other
        # clients.
        notify_avatar_url_change(user_profile)

    if user_profile.email_address_is_realm_public():
        # Additionally, if we're also changing the publicly visible
        # email, we send a new_email event as well.
        send_user_email_update_event(user_profile)

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=user_profile.realm,
        acting_user=user_profile,
        modified_user=user_profile,
        event_type=RealmAuditLog.USER_EMAIL_CHANGED,
        event_time=event_time,
    )


def do_start_email_change_process(user_profile: UserProfile, new_email: str) -> None:
    old_email = user_profile.delivery_email
    obj = EmailChangeStatus.objects.create(
        new_email=new_email,
        old_email=old_email,
        user_profile=user_profile,
        realm=user_profile.realm,
    )

    activation_url = create_confirmation_link(obj, Confirmation.EMAIL_CHANGE)
    from zerver.context_processors import common_context

    context = common_context(user_profile)
    context.update(
        old_email=old_email,
        new_email=new_email,
        activate_url=activation_url,
    )
    language = user_profile.default_language
    send_email(
        "zerver/emails/confirm_new_email",
        to_emails=[new_email],
        from_name=FromAddress.security_email_from_name(language=language),
        from_address=FromAddress.tokenized_no_reply_address(),
        language=language,
        context=context,
        realm=user_profile.realm,
    )


def compute_irc_user_fullname(email: str) -> str:
    return email.split("@")[0] + " (IRC)"


def compute_jabber_user_fullname(email: str) -> str:
    return email.split("@")[0] + " (XMPP)"


@cache_with_key(
    lambda realm, email, f: user_profile_delivery_email_cache_key(email, realm),
    timeout=3600 * 24 * 7,
)
def create_mirror_user_if_needed(
    realm: Realm, email: str, email_to_fullname: Callable[[str], str]
) -> UserProfile:
    try:
        return get_user_by_delivery_email(email, realm)
    except UserProfile.DoesNotExist:
        try:
            # Forge a user for this person
            return create_user(
                email=email,
                password=None,
                realm=realm,
                full_name=email_to_fullname(email),
                active=False,
                is_mirror_dummy=True,
            )
        except IntegrityError:
            return get_user_by_delivery_email(email, realm)


def render_incoming_message(
    message: Message,
    content: str,
    user_ids: Set[int],
    realm: Realm,
    mention_data: Optional[MentionData] = None,
    email_gateway: bool = False,
) -> MessageRenderingResult:
    realm_alert_words_automaton = get_alert_word_automaton(realm)
    try:
        rendering_result = render_markdown(
            message=message,
            content=content,
            realm=realm,
            realm_alert_words_automaton=realm_alert_words_automaton,
            mention_data=mention_data,
            email_gateway=email_gateway,
        )
    except MarkdownRenderingException:
        raise JsonableError(_("Unable to render message"))
    return rendering_result


class RecipientInfoResult(TypedDict):
    active_user_ids: Set[int]
    online_push_user_ids: Set[int]
    pm_mention_email_disabled_user_ids: Set[int]
    pm_mention_push_disabled_user_ids: Set[int]
    stream_email_user_ids: Set[int]
    stream_push_user_ids: Set[int]
    wildcard_mention_user_ids: Set[int]
    muted_sender_user_ids: Set[int]
    um_eligible_user_ids: Set[int]
    long_term_idle_user_ids: Set[int]
    default_bot_user_ids: Set[int]
    service_bot_tuples: List[Tuple[int, int]]
    all_bot_user_ids: Set[int]


def get_recipient_info(
    *,
    realm_id: int,
    recipient: Recipient,
    sender_id: int,
    stream_topic: Optional[StreamTopicTarget],
    possibly_mentioned_user_ids: AbstractSet[int] = set(),
    possible_wildcard_mention: bool = True,
) -> RecipientInfoResult:
    stream_push_user_ids: Set[int] = set()
    stream_email_user_ids: Set[int] = set()
    wildcard_mention_user_ids: Set[int] = set()
    muted_sender_user_ids: Set[int] = get_muting_users(sender_id)

    if recipient.type == Recipient.PERSONAL:
        # The sender and recipient may be the same id, so
        # de-duplicate using a set.
        message_to_user_ids = list({recipient.type_id, sender_id})
        assert len(message_to_user_ids) in [1, 2]

    elif recipient.type == Recipient.STREAM:
        # Anybody calling us w/r/t a stream message needs to supply
        # stream_topic.  We may eventually want to have different versions
        # of this function for different message types.
        assert stream_topic is not None
        user_ids_muting_topic = stream_topic.user_ids_muting_topic()

        subscription_rows = (
            get_subscriptions_for_send_message(
                realm_id=realm_id,
                stream_id=stream_topic.stream_id,
                possible_wildcard_mention=possible_wildcard_mention,
                possibly_mentioned_user_ids=possibly_mentioned_user_ids,
            )
            .annotate(
                user_profile_email_notifications=F(
                    "user_profile__enable_stream_email_notifications"
                ),
                user_profile_push_notifications=F("user_profile__enable_stream_push_notifications"),
                user_profile_wildcard_mentions_notify=F("user_profile__wildcard_mentions_notify"),
            )
            .values(
                "user_profile_id",
                "push_notifications",
                "email_notifications",
                "wildcard_mentions_notify",
                "user_profile_email_notifications",
                "user_profile_push_notifications",
                "user_profile_wildcard_mentions_notify",
                "is_muted",
            )
            .order_by("user_profile_id")
        )

        message_to_user_ids = [row["user_profile_id"] for row in subscription_rows]

        def should_send(setting: str, row: Dict[str, Any]) -> bool:
            # This implements the structure that the UserProfile stream notification settings
            # are defaults, which can be overridden by the stream-level settings (if those
            # values are not null).
            if row["is_muted"]:
                return False
            if row["user_profile_id"] in user_ids_muting_topic:
                return False
            if row[setting] is not None:
                return row[setting]
            return row["user_profile_" + setting]

        stream_push_user_ids = {
            row["user_profile_id"]
            for row in subscription_rows
            # Note: muting a stream overrides stream_push_notify
            if should_send("push_notifications", row)
        }

        stream_email_user_ids = {
            row["user_profile_id"]
            for row in subscription_rows
            # Note: muting a stream overrides stream_email_notify
            if should_send("email_notifications", row)
        }

        if possible_wildcard_mention:
            # If there's a possible wildcard mention, we need to
            # determine the set of users who have enabled the
            # "wildcard_mentions_notify" setting (that is, the set of
            # users for whom wildcard mentions should be treated like
            # personal mentions for notifications). This setting
            # applies to both email and push notifications.
            wildcard_mention_user_ids = {
                row["user_profile_id"]
                for row in subscription_rows
                if should_send("wildcard_mentions_notify", row)
            }

    elif recipient.type == Recipient.HUDDLE:
        message_to_user_ids = get_huddle_user_ids(recipient)

    else:
        raise ValueError("Bad recipient type")

    message_to_user_id_set = set(message_to_user_ids)

    user_ids = set(message_to_user_id_set)
    # Important note: Because we haven't rendered Markdown yet, we
    # don't yet know which of these possibly-mentioned users was
    # actually mentioned in the message (in other words, the
    # mention syntax might have been in a code block or otherwise
    # escaped).  `get_ids_for` will filter these extra user rows
    # for our data structures not related to bots
    user_ids |= possibly_mentioned_user_ids

    if user_ids:
        query = UserProfile.objects.filter(is_active=True).values(
            "id",
            "enable_online_push_notifications",
            "enable_offline_email_notifications",
            "enable_offline_push_notifications",
            "is_bot",
            "bot_type",
            "long_term_idle",
        )

        # query_for_ids is fast highly optimized for large queries, and we
        # need this codepath to be fast (it's part of sending messages)
        query = query_for_ids(
            query=query,
            user_ids=sorted(user_ids),
            field="id",
        )
        rows = list(query)
    else:
        # TODO: We should always have at least one user_id as a recipient
        #       of any message we send.  Right now the exception to this
        #       rule is `notify_new_user`, which, at least in a possibly
        #       contrived test scenario, can attempt to send messages
        #       to an inactive bot.  When we plug that hole, we can avoid
        #       this `else` clause and just `assert(user_ids)`.
        #
        # UPDATE: It's February 2020 (and a couple years after the above
        #         comment was written).  We have simplified notify_new_user
        #         so that it should be a little easier to reason about.
        #         There is currently some cleanup to how we handle cross
        #         realm bots that is still under development.  Once that
        #         effort is complete, we should be able to address this
        #         to-do.
        rows = []

    def get_ids_for(f: Callable[[Dict[str, Any]], bool]) -> Set[int]:
        """Only includes users on the explicit message to line"""
        return {row["id"] for row in rows if f(row)} & message_to_user_id_set

    def is_service_bot(row: Dict[str, Any]) -> bool:
        return row["is_bot"] and (row["bot_type"] in UserProfile.SERVICE_BOT_TYPES)

    active_user_ids = get_ids_for(lambda r: True)
    online_push_user_ids = get_ids_for(
        lambda r: r["enable_online_push_notifications"],
    )

    # We deal with only the users who have disabled this setting, since that
    # will usually be much smaller a set than those who have enabled it (which
    # is the default)
    pm_mention_email_disabled_user_ids = get_ids_for(
        lambda r: not r["enable_offline_email_notifications"]
    )
    pm_mention_push_disabled_user_ids = get_ids_for(
        lambda r: not r["enable_offline_push_notifications"]
    )

    # Service bots don't get UserMessage rows.
    um_eligible_user_ids = get_ids_for(
        lambda r: not is_service_bot(r),
    )

    long_term_idle_user_ids = get_ids_for(
        lambda r: r["long_term_idle"],
    )

    # These three bot data structures need to filter from the full set
    # of users who either are receiving the message or might have been
    # mentioned in it, and so can't use get_ids_for.
    #
    # Further in the do_send_messages code path, once
    # `mentioned_user_ids` has been computed via Markdown, we'll filter
    # these data structures for just those users who are either a
    # direct recipient or were mentioned; for now, we're just making
    # sure we have the data we need for that without extra database
    # queries.
    default_bot_user_ids = {
        row["id"] for row in rows if row["is_bot"] and row["bot_type"] == UserProfile.DEFAULT_BOT
    }

    service_bot_tuples = [(row["id"], row["bot_type"]) for row in rows if is_service_bot(row)]

    # We also need the user IDs of all bots, to avoid trying to send push/email
    # notifications to them. This set will be directly sent to the event queue code
    # where we determine notifiability of the message for users.
    all_bot_user_ids = {row["id"] for row in rows if row["is_bot"]}

    info: RecipientInfoResult = dict(
        active_user_ids=active_user_ids,
        online_push_user_ids=online_push_user_ids,
        pm_mention_email_disabled_user_ids=pm_mention_email_disabled_user_ids,
        pm_mention_push_disabled_user_ids=pm_mention_push_disabled_user_ids,
        stream_push_user_ids=stream_push_user_ids,
        stream_email_user_ids=stream_email_user_ids,
        wildcard_mention_user_ids=wildcard_mention_user_ids,
        muted_sender_user_ids=muted_sender_user_ids,
        um_eligible_user_ids=um_eligible_user_ids,
        long_term_idle_user_ids=long_term_idle_user_ids,
        default_bot_user_ids=default_bot_user_ids,
        service_bot_tuples=service_bot_tuples,
        all_bot_user_ids=all_bot_user_ids,
    )
    return info


def get_service_bot_events(
    sender: UserProfile,
    service_bot_tuples: List[Tuple[int, int]],
    mentioned_user_ids: Set[int],
    active_user_ids: Set[int],
    recipient_type: int,
) -> Dict[str, List[Dict[str, Any]]]:

    event_dict: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    # Avoid infinite loops by preventing messages sent by bots from generating
    # Service events.
    if sender.is_bot:
        return event_dict

    def maybe_add_event(user_profile_id: int, bot_type: int) -> None:
        if bot_type == UserProfile.OUTGOING_WEBHOOK_BOT:
            queue_name = "outgoing_webhooks"
        elif bot_type == UserProfile.EMBEDDED_BOT:
            queue_name = "embedded_bots"
        else:
            logging.error(
                "Unexpected bot_type for Service bot id=%s: %s",
                user_profile_id,
                bot_type,
            )
            return

        is_stream = recipient_type == Recipient.STREAM

        # Important note: service_bot_tuples may contain service bots
        # who were not actually mentioned in the message (e.g. if
        # mention syntax for that bot appeared in a code block).
        # Thus, it is important to filter any users who aren't part of
        # either mentioned_user_ids (the actual mentioned users) or
        # active_user_ids (the actual recipients).
        #
        # So even though this is implied by the logic below, we filter
        # these not-actually-mentioned users here, to help keep this
        # function future-proof.
        if user_profile_id not in mentioned_user_ids and user_profile_id not in active_user_ids:
            return

        # Mention triggers, for stream messages
        if is_stream and user_profile_id in mentioned_user_ids:
            trigger = "mention"
        # PM triggers for personal and huddle messages
        elif (not is_stream) and (user_profile_id in active_user_ids):
            trigger = "private_message"
        else:
            return

        event_dict[queue_name].append(
            {
                "trigger": trigger,
                "user_profile_id": user_profile_id,
            }
        )

    for user_profile_id, bot_type in service_bot_tuples:
        maybe_add_event(
            user_profile_id=user_profile_id,
            bot_type=bot_type,
        )

    return event_dict


def do_schedule_messages(send_message_requests: Sequence[SendMessageRequest]) -> List[int]:
    scheduled_messages: List[ScheduledMessage] = []

    for send_request in send_message_requests:
        scheduled_message = ScheduledMessage()
        scheduled_message.sender = send_request.message.sender
        scheduled_message.recipient = send_request.message.recipient
        topic_name = send_request.message.topic_name()
        scheduled_message.set_topic_name(topic_name=topic_name)
        scheduled_message.content = send_request.message.content
        scheduled_message.sending_client = send_request.message.sending_client
        scheduled_message.stream = send_request.stream
        scheduled_message.realm = send_request.realm
        assert send_request.deliver_at is not None
        scheduled_message.scheduled_timestamp = send_request.deliver_at
        if send_request.delivery_type == "send_later":
            scheduled_message.delivery_type = ScheduledMessage.SEND_LATER
        elif send_request.delivery_type == "remind":
            scheduled_message.delivery_type = ScheduledMessage.REMIND

        scheduled_messages.append(scheduled_message)

    ScheduledMessage.objects.bulk_create(scheduled_messages)
    return [scheduled_message.id for scheduled_message in scheduled_messages]


def build_message_send_dict(
    message: Message,
    stream: Optional[Stream] = None,
    local_id: Optional[str] = None,
    sender_queue_id: Optional[str] = None,
    realm: Optional[Realm] = None,
    widget_content_dict: Optional[Dict[str, Any]] = None,
    email_gateway: bool = False,
    mention_backend: Optional[MentionBackend] = None,
    limit_unread_user_ids: Optional[Set[int]] = None,
) -> SendMessageRequest:
    """Returns a dictionary that can be passed into do_send_messages.  In
    production, this is always called by check_message, but some
    testing code paths call it directly.
    """
    if realm is None:
        realm = message.sender.realm

    if mention_backend is None:
        mention_backend = MentionBackend(realm.id)

    mention_data = MentionData(
        mention_backend=mention_backend,
        content=message.content,
    )

    if message.is_stream_message():
        stream_id = message.recipient.type_id
        stream_topic: Optional[StreamTopicTarget] = StreamTopicTarget(
            stream_id=stream_id,
            topic_name=message.topic_name(),
        )
    else:
        stream_topic = None

    info = get_recipient_info(
        realm_id=realm.id,
        recipient=message.recipient,
        sender_id=message.sender_id,
        stream_topic=stream_topic,
        possibly_mentioned_user_ids=mention_data.get_user_ids(),
        possible_wildcard_mention=mention_data.message_has_wildcards(),
    )

    # Render our message_dicts.
    assert message.rendered_content is None

    rendering_result = render_incoming_message(
        message,
        message.content,
        info["active_user_ids"],
        realm,
        mention_data=mention_data,
        email_gateway=email_gateway,
    )
    message.rendered_content = rendering_result.rendered_content
    message.rendered_content_version = markdown_version
    links_for_embed = rendering_result.links_for_preview

    mentioned_user_groups_map = get_user_group_mentions_data(
        mentioned_user_ids=rendering_result.mentions_user_ids,
        mentioned_user_group_ids=list(rendering_result.mentions_user_group_ids),
        mention_data=mention_data,
    )

    # For single user as well as user group mentions, we set the `mentioned`
    # flag on `UserMessage`
    for group_id in rendering_result.mentions_user_group_ids:
        members = mention_data.get_group_members(group_id)
        rendering_result.mentions_user_ids.update(members)

    # Only send data to Tornado about wildcard mentions if message
    # rendering determined the message had an actual wildcard
    # mention in it (and not e.g. wildcard mention syntax inside a
    # code block).
    if rendering_result.mentions_wildcard:
        wildcard_mention_user_ids = info["wildcard_mention_user_ids"]
    else:
        wildcard_mention_user_ids = set()

    """
    Once we have the actual list of mentioned ids from message
    rendering, we can patch in "default bots" (aka normal bots)
    who were directly mentioned in this message as eligible to
    get UserMessage rows.
    """
    mentioned_user_ids = rendering_result.mentions_user_ids
    default_bot_user_ids = info["default_bot_user_ids"]
    mentioned_bot_user_ids = default_bot_user_ids & mentioned_user_ids
    info["um_eligible_user_ids"] |= mentioned_bot_user_ids

    message_send_dict = SendMessageRequest(
        stream=stream,
        local_id=local_id,
        sender_queue_id=sender_queue_id,
        realm=realm,
        mention_data=mention_data,
        mentioned_user_groups_map=mentioned_user_groups_map,
        message=message,
        rendering_result=rendering_result,
        active_user_ids=info["active_user_ids"],
        online_push_user_ids=info["online_push_user_ids"],
        pm_mention_email_disabled_user_ids=info["pm_mention_email_disabled_user_ids"],
        pm_mention_push_disabled_user_ids=info["pm_mention_push_disabled_user_ids"],
        stream_push_user_ids=info["stream_push_user_ids"],
        stream_email_user_ids=info["stream_email_user_ids"],
        muted_sender_user_ids=info["muted_sender_user_ids"],
        um_eligible_user_ids=info["um_eligible_user_ids"],
        long_term_idle_user_ids=info["long_term_idle_user_ids"],
        default_bot_user_ids=info["default_bot_user_ids"],
        service_bot_tuples=info["service_bot_tuples"],
        all_bot_user_ids=info["all_bot_user_ids"],
        wildcard_mention_user_ids=wildcard_mention_user_ids,
        links_for_embed=links_for_embed,
        widget_content=widget_content_dict,
        limit_unread_user_ids=limit_unread_user_ids,
    )

    return message_send_dict


def do_send_messages(
    send_message_requests_maybe_none: Sequence[Optional[SendMessageRequest]],
    email_gateway: bool = False,
    mark_as_read: Sequence[int] = [],
) -> List[int]:
    """See
    https://zulip.readthedocs.io/en/latest/subsystems/sending-messages.html
    for high-level documentation on this subsystem.
    """

    # Filter out messages which didn't pass internal_prep_message properly
    send_message_requests = [
        send_request
        for send_request in send_message_requests_maybe_none
        if send_request is not None
    ]

    # Save the message receipts in the database
    user_message_flags: Dict[int, Dict[int, List[str]]] = defaultdict(dict)
    with transaction.atomic():
        Message.objects.bulk_create(send_request.message for send_request in send_message_requests)

        # Claim attachments in message
        for send_request in send_message_requests:
            if do_claim_attachments(
                send_request.message, send_request.rendering_result.potential_attachment_path_ids
            ):
                send_request.message.has_attachment = True
                send_request.message.save(update_fields=["has_attachment"])

        ums: List[UserMessageLite] = []
        for send_request in send_message_requests:
            # Service bots (outgoing webhook bots and embedded bots) don't store UserMessage rows;
            # they will be processed later.
            mentioned_user_ids = send_request.rendering_result.mentions_user_ids

            # Extend the set with users who have muted the sender.
            mark_as_read_user_ids = send_request.muted_sender_user_ids
            mark_as_read_user_ids.update(mark_as_read)

            user_messages = create_user_messages(
                message=send_request.message,
                rendering_result=send_request.rendering_result,
                um_eligible_user_ids=send_request.um_eligible_user_ids,
                long_term_idle_user_ids=send_request.long_term_idle_user_ids,
                stream_push_user_ids=send_request.stream_push_user_ids,
                stream_email_user_ids=send_request.stream_email_user_ids,
                mentioned_user_ids=mentioned_user_ids,
                mark_as_read_user_ids=mark_as_read_user_ids,
                limit_unread_user_ids=send_request.limit_unread_user_ids,
            )

            for um in user_messages:
                user_message_flags[send_request.message.id][um.user_profile_id] = um.flags_list()

            ums.extend(user_messages)

            send_request.message.service_queue_events = get_service_bot_events(
                sender=send_request.message.sender,
                service_bot_tuples=send_request.service_bot_tuples,
                mentioned_user_ids=mentioned_user_ids,
                active_user_ids=send_request.active_user_ids,
                recipient_type=send_request.message.recipient.type,
            )

        bulk_insert_ums(ums)

        for send_request in send_message_requests:
            do_widget_post_save_actions(send_request)

    # This next loop is responsible for notifying other parts of the
    # Zulip system about the messages we just committed to the database:
    # * Notifying clients via send_event
    # * Triggering outgoing webhooks via the service event queue.
    # * Updating the `first_message_id` field for streams without any message history.
    # * Implementing the Welcome Bot reply hack
    # * Adding links to the embed_links queue for open graph processing.
    for send_request in send_message_requests:
        realm_id: Optional[int] = None
        if send_request.message.is_stream_message():
            if send_request.stream is None:
                stream_id = send_request.message.recipient.type_id
                send_request.stream = Stream.objects.select_related().get(id=stream_id)
            # assert needed because stubs for django are missing
            assert send_request.stream is not None
            realm_id = send_request.stream.realm_id

        # Deliver events to the real-time push system, as well as
        # enqueuing any additional processing triggered by the message.
        wide_message_dict = MessageDict.wide_dict(send_request.message, realm_id)

        user_flags = user_message_flags.get(send_request.message.id, {})

        """
        TODO:  We may want to limit user_ids to only those users who have
               UserMessage rows, if only for minor performance reasons.

               For now we queue events for all subscribers/sendees of the
               message, since downstream code may still do notifications
               that don't require UserMessage rows.

               Our automated tests have gotten better on this codepath,
               but we may have coverage gaps, so we should be careful
               about changing the next line.
        """
        user_ids = send_request.active_user_ids | set(user_flags.keys())
        sender_id = send_request.message.sender_id

        # We make sure the sender is listed first in the `users` list;
        # this results in the sender receiving the message first if
        # there are thousands of recipients, decreasing perceived latency.
        if sender_id in user_ids:
            user_list = [sender_id] + list(user_ids - {sender_id})
        else:
            user_list = list(user_ids)

        class UserData(TypedDict):
            id: int
            flags: List[str]
            mentioned_user_group_id: Optional[int]

        users: List[UserData] = []
        for user_id in user_list:
            flags = user_flags.get(user_id, [])
            user_data: UserData = dict(id=user_id, flags=flags, mentioned_user_group_id=None)

            if user_id in send_request.mentioned_user_groups_map:
                user_data["mentioned_user_group_id"] = send_request.mentioned_user_groups_map[
                    user_id
                ]

            users.append(user_data)

        sender = send_request.message.sender
        message_type = wide_message_dict["type"]
        active_users_data = [
            ActivePresenceIdleUserData(
                alerted="has_alert_word" in user_flags.get(user_id, []),
                notifications_data=UserMessageNotificationsData.from_user_id_sets(
                    user_id=user_id,
                    flags=user_flags.get(user_id, []),
                    private_message=(message_type == "private"),
                    online_push_user_ids=send_request.online_push_user_ids,
                    pm_mention_push_disabled_user_ids=send_request.pm_mention_push_disabled_user_ids,
                    pm_mention_email_disabled_user_ids=send_request.pm_mention_email_disabled_user_ids,
                    stream_push_user_ids=send_request.stream_push_user_ids,
                    stream_email_user_ids=send_request.stream_email_user_ids,
                    wildcard_mention_user_ids=send_request.wildcard_mention_user_ids,
                    muted_sender_user_ids=send_request.muted_sender_user_ids,
                    all_bot_user_ids=send_request.all_bot_user_ids,
                ),
            )
            for user_id in send_request.active_user_ids
        ]

        presence_idle_user_ids = get_active_presence_idle_user_ids(
            realm=sender.realm,
            sender_id=sender.id,
            active_users_data=active_users_data,
        )

        event = dict(
            type="message",
            message=send_request.message.id,
            message_dict=wide_message_dict,
            presence_idle_user_ids=presence_idle_user_ids,
            online_push_user_ids=list(send_request.online_push_user_ids),
            pm_mention_push_disabled_user_ids=list(send_request.pm_mention_push_disabled_user_ids),
            pm_mention_email_disabled_user_ids=list(
                send_request.pm_mention_email_disabled_user_ids
            ),
            stream_push_user_ids=list(send_request.stream_push_user_ids),
            stream_email_user_ids=list(send_request.stream_email_user_ids),
            wildcard_mention_user_ids=list(send_request.wildcard_mention_user_ids),
            muted_sender_user_ids=list(send_request.muted_sender_user_ids),
            all_bot_user_ids=list(send_request.all_bot_user_ids),
        )

        if send_request.message.is_stream_message():
            # Note: This is where authorization for single-stream
            # get_updates happens! We only attach stream data to the
            # notify new_message request if it's a public stream,
            # ensuring that in the tornado server, non-public stream
            # messages are only associated to their subscribed users.

            # assert needed because stubs for django are missing
            assert send_request.stream is not None
            if send_request.stream.is_public():
                event["realm_id"] = send_request.stream.realm_id
                event["stream_name"] = send_request.stream.name
            if send_request.stream.invite_only:
                event["invite_only"] = True
            if send_request.stream.first_message_id is None:
                send_request.stream.first_message_id = send_request.message.id
                send_request.stream.save(update_fields=["first_message_id"])
        if send_request.local_id is not None:
            event["local_id"] = send_request.local_id
        if send_request.sender_queue_id is not None:
            event["sender_queue_id"] = send_request.sender_queue_id
        send_event(send_request.realm, event, users)

        if send_request.links_for_embed:
            event_data = {
                "message_id": send_request.message.id,
                "message_content": send_request.message.content,
                "message_realm_id": send_request.realm.id,
                "urls": list(send_request.links_for_embed),
            }
            queue_json_publish("embed_links", event_data)

        if send_request.message.recipient.type == Recipient.PERSONAL:
            welcome_bot_id = get_system_bot(
                settings.WELCOME_BOT, send_request.message.sender.realm_id
            ).id
            if (
                welcome_bot_id in send_request.active_user_ids
                and welcome_bot_id != send_request.message.sender_id
            ):
                from zerver.lib.onboarding import send_welcome_bot_response

                send_welcome_bot_response(send_request)

        for queue_name, events in send_request.message.service_queue_events.items():
            for event in events:
                queue_json_publish(
                    queue_name,
                    {
                        "message": wide_message_dict,
                        "trigger": event["trigger"],
                        "user_profile_id": event["user_profile_id"],
                    },
                )

    return [send_request.message.id for send_request in send_message_requests]


def create_user_messages(
    message: Message,
    rendering_result: MessageRenderingResult,
    um_eligible_user_ids: AbstractSet[int],
    long_term_idle_user_ids: AbstractSet[int],
    stream_push_user_ids: AbstractSet[int],
    stream_email_user_ids: AbstractSet[int],
    mentioned_user_ids: AbstractSet[int],
    mark_as_read_user_ids: Set[int],
    limit_unread_user_ids: Optional[Set[int]],
) -> List[UserMessageLite]:
    # These properties on the Message are set via
    # render_markdown by code in the Markdown inline patterns
    ids_with_alert_words = rendering_result.user_ids_with_alert_words
    sender_id = message.sender.id
    is_stream_message = message.is_stream_message()

    base_flags = 0
    if rendering_result.mentions_wildcard:
        base_flags |= UserMessage.flags.wildcard_mentioned
    if message.recipient.type in [Recipient.HUDDLE, Recipient.PERSONAL]:
        base_flags |= UserMessage.flags.is_private

    # For long_term_idle (aka soft-deactivated) users, we are allowed
    # to optimize by lazily not creating UserMessage rows that would
    # have the default 0 flag set (since the soft-reactivation logic
    # knows how to create those when the user comes back).  We need to
    # create the UserMessage rows for these long_term_idle users
    # non-lazily in a few cases:
    #
    # * There are nonzero flags (e.g. the user was mentioned), since
    #   that case is rare and this saves a lot of complexity in
    #   soft-reactivation.
    #
    # * If the user is going to be notified (e.g. they get push/email
    #   notifications for every message on a stream), since in that
    #   case the notifications code will call `access_message` on the
    #   message to re-verify permissions, and for private streams,
    #   will get an error if the UserMessage row doesn't exist yet.
    #
    # See https://zulip.readthedocs.io/en/latest/subsystems/sending-messages.html#soft-deactivation
    # for details on this system.
    user_messages = []
    for user_profile_id in um_eligible_user_ids:
        flags = base_flags
        if (
            (user_profile_id == sender_id and message.sent_by_human())
            or user_profile_id in mark_as_read_user_ids
            or (limit_unread_user_ids is not None and user_profile_id not in limit_unread_user_ids)
        ):
            flags |= UserMessage.flags.read
        if user_profile_id in mentioned_user_ids:
            flags |= UserMessage.flags.mentioned
        if user_profile_id in ids_with_alert_words:
            flags |= UserMessage.flags.has_alert_word

        if (
            user_profile_id in long_term_idle_user_ids
            and user_profile_id not in stream_push_user_ids
            and user_profile_id not in stream_email_user_ids
            and is_stream_message
            and int(flags) == 0
        ):
            continue

        um = UserMessageLite(
            user_profile_id=user_profile_id,
            message_id=message.id,
            flags=flags,
        )
        user_messages.append(um)

    return user_messages


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


def already_sent_mirrored_message_id(message: Message) -> Optional[int]:
    if message.recipient.type == Recipient.HUDDLE:
        # For huddle messages, we use a 10-second window because the
        # timestamps aren't guaranteed to actually match between two
        # copies of the same message.
        time_window = datetime.timedelta(seconds=10)
    else:
        time_window = datetime.timedelta(seconds=0)

    query = Message.objects.filter(
        sender=message.sender,
        recipient=message.recipient,
        content=message.content,
        sending_client=message.sending_client,
        date_sent__gte=message.date_sent - time_window,
        date_sent__lte=message.date_sent + time_window,
    )

    messages = filter_by_exact_message_topic(
        query=query,
        message=message,
    )

    if messages.exists():
        return messages[0].id
    return None


def extract_stream_indicator(s: str) -> Union[str, int]:
    # Users can pass stream name as either an id or a name,
    # and if they choose to pass a name, they may JSON encode
    # it for legacy reasons.

    try:
        data = orjson.loads(s)
    except orjson.JSONDecodeError:
        # If there was no JSON encoding, then we just
        # have a raw stream name.
        return s

    # We should stop supporting this odd use case
    # once we improve our documentation.
    if isinstance(data, list):
        if len(data) != 1:  # nocoverage
            raise JsonableError(_("Expected exactly one stream"))
        data = data[0]

    if isinstance(data, str):
        # We had a JSON-encoded stream name.
        return data

    if isinstance(data, int):
        # We had a stream id.
        return data

    raise JsonableError(_("Invalid data type for stream"))


def extract_private_recipients(s: str) -> Union[List[str], List[int]]:
    # We try to accept multiple incoming formats for recipients.
    # See test_extract_recipients() for examples of what we allow.

    try:
        data = orjson.loads(s)
    except orjson.JSONDecodeError:
        data = s

    if isinstance(data, str):
        data = data.split(",")

    if not isinstance(data, list):
        raise JsonableError(_("Invalid data type for recipients"))

    if not data:
        # We don't complain about empty message recipients here
        return data

    if isinstance(data[0], str):
        return get_validated_emails(data)

    if not isinstance(data[0], int):
        raise JsonableError(_("Invalid data type for recipients"))

    return get_validated_user_ids(data)


def get_validated_user_ids(user_ids: Collection[int]) -> List[int]:
    for user_id in user_ids:
        if not isinstance(user_id, int):
            raise JsonableError(_("Recipient lists may contain emails or user IDs, but not both."))

    return list(set(user_ids))


def get_validated_emails(emails: Collection[str]) -> List[str]:
    for email in emails:
        if not isinstance(email, str):
            raise JsonableError(_("Recipient lists may contain emails or user IDs, but not both."))

    return list(filter(bool, {email.strip() for email in emails}))


def check_send_stream_message(
    sender: UserProfile,
    client: Client,
    stream_name: str,
    topic: str,
    body: str,
    realm: Optional[Realm] = None,
) -> int:
    addressee = Addressee.for_stream_name(stream_name, topic)
    message = check_message(sender, client, addressee, body, realm)

    return do_send_messages([message])[0]


def check_send_stream_message_by_id(
    sender: UserProfile,
    client: Client,
    stream_id: int,
    topic: str,
    body: str,
    realm: Optional[Realm] = None,
) -> int:
    addressee = Addressee.for_stream_id(stream_id, topic)
    message = check_message(sender, client, addressee, body, realm)

    return do_send_messages([message])[0]


def check_send_private_message(
    sender: UserProfile, client: Client, receiving_user: UserProfile, body: str
) -> int:
    addressee = Addressee.for_user_profile(receiving_user)
    message = check_message(sender, client, addressee, body)

    return do_send_messages([message])[0]


# check_send_message:
# Returns the id of the sent message.  Has same argspec as check_message.
def check_send_message(
    sender: UserProfile,
    client: Client,
    message_type_name: str,
    message_to: Union[Sequence[int], Sequence[str]],
    topic_name: Optional[str],
    message_content: str,
    realm: Optional[Realm] = None,
    forged: bool = False,
    forged_timestamp: Optional[float] = None,
    forwarder_user_profile: Optional[UserProfile] = None,
    local_id: Optional[str] = None,
    sender_queue_id: Optional[str] = None,
    widget_content: Optional[str] = None,
    *,
    skip_stream_access_check: bool = False,
) -> int:

    addressee = Addressee.legacy_build(sender, message_type_name, message_to, topic_name)
    try:
        message = check_message(
            sender,
            client,
            addressee,
            message_content,
            realm,
            forged,
            forged_timestamp,
            forwarder_user_profile,
            local_id,
            sender_queue_id,
            widget_content,
            skip_stream_access_check=skip_stream_access_check,
        )
    except ZephyrMessageAlreadySentException as e:
        return e.message_id
    return do_send_messages([message])[0]


def check_schedule_message(
    sender: UserProfile,
    client: Client,
    message_type_name: str,
    message_to: Union[Sequence[str], Sequence[int]],
    topic_name: Optional[str],
    message_content: str,
    delivery_type: str,
    deliver_at: datetime.datetime,
    realm: Optional[Realm] = None,
    forwarder_user_profile: Optional[UserProfile] = None,
) -> int:
    addressee = Addressee.legacy_build(sender, message_type_name, message_to, topic_name)

    send_request = check_message(
        sender,
        client,
        addressee,
        message_content,
        realm=realm,
        forwarder_user_profile=forwarder_user_profile,
    )
    send_request.deliver_at = deliver_at
    send_request.delivery_type = delivery_type

    recipient = send_request.message.recipient
    if delivery_type == "remind" and (
        recipient.type != Recipient.STREAM and recipient.type_id != sender.id
    ):
        raise JsonableError(_("Reminders can only be set for streams."))

    return do_schedule_messages([send_request])[0]


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


def send_rate_limited_pm_notification_to_bot_owner(
    sender: UserProfile, realm: Realm, content: str
) -> None:
    """
    Sends a PM error notification to a bot's owner if one hasn't already
    been sent in the last 5 minutes.
    """
    if sender.realm.is_zephyr_mirror_realm or sender.realm.deactivated:
        return

    if not sender.is_bot or sender.bot_owner is None:
        return

    # Don't send these notifications for cross-realm bot messages
    # (e.g. from EMAIL_GATEWAY_BOT) since the owner for
    # EMAIL_GATEWAY_BOT is probably the server administrator, not
    # the owner of the bot who could potentially fix the problem.
    if sender.realm != realm:
        return

    # We warn the user once every 5 minutes to avoid a flood of
    # PMs on a misconfigured integration, re-using the
    # UserProfile.last_reminder field, which is not used for bots.
    last_reminder = sender.last_reminder
    waitperiod = datetime.timedelta(minutes=UserProfile.BOT_OWNER_STREAM_ALERT_WAITPERIOD)
    if last_reminder and timezone_now() - last_reminder <= waitperiod:
        return

    internal_send_private_message(
        get_system_bot(settings.NOTIFICATION_BOT, sender.bot_owner.realm_id),
        sender.bot_owner,
        content,
    )

    sender.last_reminder = timezone_now()
    sender.save(update_fields=["last_reminder"])


def send_pm_if_empty_stream(
    stream: Optional[Stream],
    realm: Realm,
    sender: UserProfile,
    stream_name: Optional[str] = None,
    stream_id: Optional[int] = None,
) -> None:
    """If a bot sends a message to a stream that doesn't exist or has no
    subscribers, sends a notification to the bot owner (if not a
    cross-realm bot) so that the owner can correct the issue."""
    if not sender.is_bot or sender.bot_owner is None:
        return

    arg_dict = {
        "bot_identity": f"`{sender.delivery_email}`",
        "stream_id": stream_id,
        "stream_name": f"#**{stream_name}**",
        "new_stream_link": "#streams/new",
    }
    if sender.bot_owner is not None:
        with override_language(sender.bot_owner.default_language):
            if stream is None:
                if stream_id is not None:
                    content = _(
                        "Your bot {bot_identity} tried to send a message to stream ID "
                        "{stream_id}, but there is no stream with that ID."
                    ).format(**arg_dict)
                else:
                    assert stream_name is not None
                    content = _(
                        "Your bot {bot_identity} tried to send a message to stream "
                        "{stream_name}, but that stream does not exist. "
                        "Click [here]({new_stream_link}) to create it."
                    ).format(**arg_dict)
            else:
                if num_subscribers_for_stream_id(stream.id) > 0:
                    return
                content = _(
                    "Your bot {bot_identity} tried to send a message to "
                    "stream {stream_name}. The stream exists but "
                    "does not have any subscribers."
                ).format(**arg_dict)

        send_rate_limited_pm_notification_to_bot_owner(sender, realm, content)


def validate_stream_name_with_pm_notification(
    stream_name: str, realm: Realm, sender: UserProfile
) -> Stream:
    stream_name = stream_name.strip()
    check_stream_name(stream_name)

    try:
        stream = get_stream(stream_name, realm)
        send_pm_if_empty_stream(stream, realm, sender)
    except Stream.DoesNotExist:
        send_pm_if_empty_stream(None, realm, sender, stream_name=stream_name)
        raise StreamDoesNotExistError(escape(stream_name))

    return stream


def validate_stream_id_with_pm_notification(
    stream_id: int, realm: Realm, sender: UserProfile
) -> Stream:
    try:
        stream = get_stream_by_id_in_realm(stream_id, realm)
        send_pm_if_empty_stream(stream, realm, sender)
    except Stream.DoesNotExist:
        send_pm_if_empty_stream(None, realm, sender, stream_id=stream_id)
        raise StreamWithIDDoesNotExistError(stream_id)

    return stream


def check_private_message_policy(
    realm: Realm, sender: UserProfile, user_profiles: Sequence[UserProfile]
) -> None:
    if realm.private_message_policy == Realm.PRIVATE_MESSAGE_POLICY_DISABLED:
        if sender.is_bot or (len(user_profiles) == 1 and user_profiles[0].is_bot):
            # We allow PMs only between users and bots, to avoid
            # breaking the tutorial as well as automated
            # notifications from system bots to users.
            return

        raise JsonableError(_("Private messages are disabled in this organization."))


# check_message:
# Returns message ready for sending with do_send_message on success or the error message (string) on error.
def check_message(
    sender: UserProfile,
    client: Client,
    addressee: Addressee,
    message_content_raw: str,
    realm: Optional[Realm] = None,
    forged: bool = False,
    forged_timestamp: Optional[float] = None,
    forwarder_user_profile: Optional[UserProfile] = None,
    local_id: Optional[str] = None,
    sender_queue_id: Optional[str] = None,
    widget_content: Optional[str] = None,
    email_gateway: bool = False,
    *,
    skip_stream_access_check: bool = False,
    mention_backend: Optional[MentionBackend] = None,
    limit_unread_user_ids: Optional[Set[int]] = None,
) -> SendMessageRequest:
    """See
    https://zulip.readthedocs.io/en/latest/subsystems/sending-messages.html
    for high-level documentation on this subsystem.
    """
    stream = None

    message_content = normalize_body(message_content_raw)

    if realm is None:
        realm = sender.realm

    if addressee.is_stream():
        topic_name = addressee.topic()
        topic_name = truncate_topic(topic_name)

        stream_name = addressee.stream_name()
        stream_id = addressee.stream_id()

        if stream_name is not None:
            stream = validate_stream_name_with_pm_notification(stream_name, realm, sender)
        elif stream_id is not None:
            stream = validate_stream_id_with_pm_notification(stream_id, realm, sender)
        else:
            stream = addressee.stream()
        assert stream is not None

        # To save a database round trip, we construct the Recipient
        # object for the Stream rather than fetching it from the
        # database using the stream.recipient foreign key.
        #
        # This is simpler than ensuring that code paths that fetch a
        # Stream that will be used for sending a message have a
        # `select_related("recipient"), which would also needlessly
        # expand Stream objects in memory (all the fields of Recipient
        # are already known given the Stream object).
        recipient = Recipient(
            id=stream.recipient_id,
            type_id=stream.id,
            type=Recipient.STREAM,
        )

        if not skip_stream_access_check:
            access_stream_for_send_message(
                sender=sender, stream=stream, forwarder_user_profile=forwarder_user_profile
            )
        else:
            # Defensive assertion - the only currently supported use case
            # for this option is for outgoing webhook bots and since this
            # is security-sensitive code, it's beneficial to ensure nothing
            # else can sneak past the access check.
            assert sender.bot_type == sender.OUTGOING_WEBHOOK_BOT

        if realm.mandatory_topics and topic_name == "(no topic)":
            raise JsonableError(_("Topics are required in this organization"))

    elif addressee.is_private():
        user_profiles = addressee.user_profiles()
        mirror_message = client and client.name in [
            "zephyr_mirror",
            "irc_mirror",
            "jabber_mirror",
            "JabberMirror",
        ]

        check_private_message_policy(realm, sender, user_profiles)

        # API super-users who set the `forged` flag are allowed to
        # forge messages sent by any user, so we disable the
        # `forwarded_mirror_message` security check in that case.
        forwarded_mirror_message = mirror_message and not forged
        try:
            recipient = recipient_for_user_profiles(
                user_profiles, forwarded_mirror_message, forwarder_user_profile, sender
            )
        except ValidationError as e:
            assert isinstance(e.messages[0], str)
            raise JsonableError(e.messages[0])
    else:
        # This is defensive code--Addressee already validates
        # the message type.
        raise AssertionError("Invalid message type")

    message = Message()
    message.sender = sender
    message.content = message_content
    message.recipient = recipient
    if addressee.is_stream():
        message.set_topic_name(topic_name)
    if forged and forged_timestamp is not None:
        # Forged messages come with a timestamp
        message.date_sent = timestamp_to_datetime(forged_timestamp)
    else:
        message.date_sent = timezone_now()
    message.sending_client = client

    # We render messages later in the process.
    assert message.rendered_content is None

    if client.name == "zephyr_mirror":
        id = already_sent_mirrored_message_id(message)
        if id is not None:
            raise ZephyrMessageAlreadySentException(id)

    widget_content_dict = None
    if widget_content is not None:
        try:
            widget_content_dict = orjson.loads(widget_content)
        except orjson.JSONDecodeError:
            raise JsonableError(_("Widgets: API programmer sent invalid JSON content"))

        try:
            check_widget_content(widget_content_dict)
        except ValidationError as error:
            raise JsonableError(
                _("Widgets: {error_msg}").format(
                    error_msg=error.message,
                )
            )

    message_send_dict = build_message_send_dict(
        message=message,
        stream=stream,
        local_id=local_id,
        sender_queue_id=sender_queue_id,
        realm=realm,
        widget_content_dict=widget_content_dict,
        email_gateway=email_gateway,
        mention_backend=mention_backend,
        limit_unread_user_ids=limit_unread_user_ids,
    )

    if stream is not None and message_send_dict.rendering_result.mentions_wildcard:
        if not wildcard_mention_allowed(sender, stream):
            raise JsonableError(
                _("You do not have permission to use wildcard mentions in this stream.")
            )
    return message_send_dict


def _internal_prep_message(
    realm: Realm,
    sender: UserProfile,
    addressee: Addressee,
    content: str,
    email_gateway: bool = False,
    mention_backend: Optional[MentionBackend] = None,
    limit_unread_user_ids: Optional[Set[int]] = None,
) -> Optional[SendMessageRequest]:
    """
    Create a message object and checks it, but doesn't send it or save it to the database.
    The internal function that calls this can therefore batch send a bunch of created
    messages together as one database query.
    Call do_send_messages with a list of the return values of this method.
    """
    # Remove any null bytes from the content
    if len(content) > settings.MAX_MESSAGE_LENGTH:
        content = content[0:3900] + "\n\n[message was too long and has been truncated]"

    # If we have a stream name, and the stream doesn't exist, we
    # create it here (though this code path should probably be removed
    # eventually, moving that responsibility to the caller).  If
    # addressee.stream_name() is None (i.e. we're sending to a stream
    # by ID), we skip this, as the stream object must already exist.
    if addressee.is_stream():
        stream_name = addressee.stream_name()
        if stream_name is not None:
            ensure_stream(realm, stream_name, acting_user=sender)

    try:
        return check_message(
            sender,
            get_client("Internal"),
            addressee,
            content,
            realm=realm,
            email_gateway=email_gateway,
            mention_backend=mention_backend,
            limit_unread_user_ids=limit_unread_user_ids,
        )
    except JsonableError as e:
        logging.exception(
            "Error queueing internal message by %s: %s",
            sender.delivery_email,
            e.msg,
            stack_info=True,
        )

    return None


def internal_prep_stream_message(
    sender: UserProfile,
    stream: Stream,
    topic: str,
    content: str,
    email_gateway: bool = False,
    limit_unread_user_ids: Optional[Set[int]] = None,
) -> Optional[SendMessageRequest]:
    """
    See _internal_prep_message for details of how this works.
    """
    realm = stream.realm
    addressee = Addressee.for_stream(stream, topic)

    return _internal_prep_message(
        realm=realm,
        sender=sender,
        addressee=addressee,
        content=content,
        email_gateway=email_gateway,
        limit_unread_user_ids=limit_unread_user_ids,
    )


def internal_prep_stream_message_by_name(
    realm: Realm,
    sender: UserProfile,
    stream_name: str,
    topic: str,
    content: str,
) -> Optional[SendMessageRequest]:
    """
    See _internal_prep_message for details of how this works.
    """
    addressee = Addressee.for_stream_name(stream_name, topic)

    return _internal_prep_message(
        realm=realm,
        sender=sender,
        addressee=addressee,
        content=content,
    )


def internal_prep_private_message(
    realm: Realm,
    sender: UserProfile,
    recipient_user: UserProfile,
    content: str,
    mention_backend: Optional[MentionBackend] = None,
) -> Optional[SendMessageRequest]:
    """
    See _internal_prep_message for details of how this works.
    """
    addressee = Addressee.for_user_profile(recipient_user)

    return _internal_prep_message(
        realm=realm,
        sender=sender,
        addressee=addressee,
        content=content,
        mention_backend=mention_backend,
    )


def internal_send_private_message(
    sender: UserProfile, recipient_user: UserProfile, content: str
) -> Optional[int]:
    realm = recipient_user.realm
    message = internal_prep_private_message(realm, sender, recipient_user, content)
    if message is None:
        return None
    message_ids = do_send_messages([message])
    return message_ids[0]


def internal_send_stream_message(
    sender: UserProfile,
    stream: Stream,
    topic: str,
    content: str,
    email_gateway: bool = False,
    limit_unread_user_ids: Optional[Set[int]] = None,
) -> Optional[int]:

    message = internal_prep_stream_message(
        sender, stream, topic, content, email_gateway, limit_unread_user_ids=limit_unread_user_ids
    )

    if message is None:
        return None
    message_ids = do_send_messages([message])
    return message_ids[0]


def internal_send_stream_message_by_name(
    realm: Realm,
    sender: UserProfile,
    stream_name: str,
    topic: str,
    content: str,
) -> Optional[int]:
    message = internal_prep_stream_message_by_name(
        realm,
        sender,
        stream_name,
        topic,
        content,
    )

    if message is None:
        return None
    message_ids = do_send_messages([message])
    return message_ids[0]


def internal_send_huddle_message(
    realm: Realm, sender: UserProfile, emails: List[str], content: str
) -> Optional[int]:
    addressee = Addressee.for_private(emails, realm)
    message = _internal_prep_message(
        realm=realm,
        sender=sender,
        addressee=addressee,
        content=content,
    )
    if message is None:
        return None
    message_ids = do_send_messages([message])
    return message_ids[0]


def get_subscriber_ids(stream: Stream, requesting_user: Optional[UserProfile] = None) -> List[str]:
    subscriptions_query = get_subscribers_query(stream, requesting_user)
    return subscriptions_query.values_list("user_profile_id", flat=True)


@dataclass
class StreamInfo:
    email_address: str
    stream_weekly_traffic: Optional[int]
    subscribers: List[int]


def send_subscription_add_events(
    realm: Realm,
    sub_info_list: List[SubInfo],
    subscriber_dict: Dict[int, Set[int]],
) -> None:
    info_by_user: Dict[int, List[SubInfo]] = defaultdict(list)
    for sub_info in sub_info_list:
        info_by_user[sub_info.user.id].append(sub_info)

    stream_ids = {sub_info.stream.id for sub_info in sub_info_list}
    recent_traffic = get_streams_traffic(stream_ids=stream_ids)

    # We generally only have a few streams, so we compute stream
    # data in its own loop.
    stream_info_dict: Dict[int, StreamInfo] = {}
    for sub_info in sub_info_list:
        stream = sub_info.stream
        if stream.id not in stream_info_dict:
            email_address = encode_email_address(stream, show_sender=True)
            stream_weekly_traffic = get_average_weekly_stream_traffic(
                stream.id, stream.date_created, recent_traffic
            )
            if stream.is_in_zephyr_realm and not stream.invite_only:
                subscribers = []
            else:
                subscribers = list(subscriber_dict[stream.id])
            stream_info_dict[stream.id] = StreamInfo(
                email_address=email_address,
                stream_weekly_traffic=stream_weekly_traffic,
                subscribers=subscribers,
            )

    for user_id, sub_infos in info_by_user.items():
        sub_dicts = []
        for sub_info in sub_infos:
            stream = sub_info.stream
            stream_info = stream_info_dict[stream.id]
            subscription = sub_info.sub
            sub_dict = stream.to_dict()
            for field_name in Subscription.API_FIELDS:
                sub_dict[field_name] = getattr(subscription, field_name)

            sub_dict["in_home_view"] = not subscription.is_muted
            sub_dict["email_address"] = stream_info.email_address
            sub_dict["stream_weekly_traffic"] = stream_info.stream_weekly_traffic
            sub_dict["subscribers"] = stream_info.subscribers
            sub_dicts.append(sub_dict)

        # Send a notification to the user who subscribed.
        event = dict(type="subscription", op="add", subscriptions=sub_dicts)
        send_event(realm, event, [user_id])


SubT = Tuple[List[SubInfo], List[SubInfo]]


def bulk_add_subscriptions(
    realm: Realm,
    streams: Collection[Stream],
    users: Iterable[UserProfile],
    color_map: Mapping[str, str] = {},
    from_user_creation: bool = False,
    *,
    acting_user: Optional[UserProfile],
) -> SubT:
    users = list(users)
    user_ids = [user.id for user in users]

    # Sanity check out callers
    for stream in streams:
        assert stream.realm_id == realm.id

    for user in users:
        assert user.realm_id == realm.id

    recipient_ids = [stream.recipient_id for stream in streams]
    recipient_id_to_stream = {stream.recipient_id: stream for stream in streams}

    recipient_color_map = {}
    for stream in streams:
        color: Optional[str] = color_map.get(stream.name, None)
        if color is not None:
            recipient_color_map[stream.recipient_id] = color

    used_colors_for_user_ids: Dict[int, Set[str]] = get_used_colors_for_user_ids(user_ids)

    existing_subs = Subscription.objects.filter(
        user_profile_id__in=user_ids,
        recipient__type=Recipient.STREAM,
        recipient_id__in=recipient_ids,
    )

    subs_by_user: Dict[int, List[Subscription]] = defaultdict(list)
    for sub in existing_subs:
        subs_by_user[sub.user_profile_id].append(sub)

    already_subscribed: List[SubInfo] = []
    subs_to_activate: List[SubInfo] = []
    subs_to_add: List[SubInfo] = []
    for user_profile in users:
        my_subs = subs_by_user[user_profile.id]

        # Make a fresh set of all new recipient ids, and then we will
        # remove any for which our user already has a subscription
        # (and we'll re-activate any subscriptions as needed).
        new_recipient_ids: Set[int] = {stream.recipient_id for stream in streams}

        for sub in my_subs:
            if sub.recipient_id in new_recipient_ids:
                new_recipient_ids.remove(sub.recipient_id)
                stream = recipient_id_to_stream[sub.recipient_id]
                sub_info = SubInfo(user_profile, sub, stream)
                if sub.active:
                    already_subscribed.append(sub_info)
                else:
                    subs_to_activate.append(sub_info)

        used_colors = used_colors_for_user_ids.get(user_profile.id, set())
        user_color_map = pick_colors(used_colors, recipient_color_map, list(new_recipient_ids))

        for recipient_id in new_recipient_ids:
            stream = recipient_id_to_stream[recipient_id]
            color = user_color_map[recipient_id]

            sub = Subscription(
                user_profile=user_profile,
                is_user_active=user_profile.is_active,
                active=True,
                color=color,
                recipient_id=recipient_id,
            )
            sub_info = SubInfo(user_profile, sub, stream)
            subs_to_add.append(sub_info)

    bulk_add_subs_to_db_with_logging(
        realm=realm,
        acting_user=acting_user,
        subs_to_add=subs_to_add,
        subs_to_activate=subs_to_activate,
    )

    altered_user_dict: Dict[int, Set[int]] = defaultdict(set)
    for sub_info in subs_to_add + subs_to_activate:
        altered_user_dict[sub_info.stream.id].add(sub_info.user.id)

    stream_dict = {stream.id: stream for stream in streams}

    new_streams = [stream_dict[stream_id] for stream_id in altered_user_dict]

    subscriber_peer_info = bulk_get_subscriber_peer_info(
        realm=realm,
        streams=new_streams,
    )

    # We now send several types of events to notify browsers.  The
    # first batches of notifications are sent only to the user(s)
    # being subscribed; we can skip these notifications when this is
    # being called from the new user creation flow.
    if not from_user_creation:
        send_stream_creation_events_for_private_streams(
            realm=realm,
            stream_dict=stream_dict,
            altered_user_dict=altered_user_dict,
        )

        send_subscription_add_events(
            realm=realm,
            sub_info_list=subs_to_add + subs_to_activate,
            subscriber_dict=subscriber_peer_info.subscribed_ids,
        )

    send_peer_subscriber_events(
        op="peer_add",
        realm=realm,
        altered_user_dict=altered_user_dict,
        stream_dict=stream_dict,
        private_peer_dict=subscriber_peer_info.private_peer_dict,
    )

    return (
        subs_to_add + subs_to_activate,
        already_subscribed,
    )


# This function contains all the database changes as part of
# subscribing users to streams; we use a transaction to ensure that
# the RealmAuditLog entries are created atomically with the
# Subscription object creation (and updates).
@transaction.atomic(savepoint=False)
def bulk_add_subs_to_db_with_logging(
    realm: Realm,
    acting_user: Optional[UserProfile],
    subs_to_add: List[SubInfo],
    subs_to_activate: List[SubInfo],
) -> None:

    Subscription.objects.bulk_create(info.sub for info in subs_to_add)
    sub_ids = [info.sub.id for info in subs_to_activate]
    Subscription.objects.filter(id__in=sub_ids).update(active=True)

    # Log subscription activities in RealmAuditLog
    event_time = timezone_now()
    event_last_message_id = get_last_message_id()

    all_subscription_logs: (List[RealmAuditLog]) = []
    for sub_info in subs_to_add:
        all_subscription_logs.append(
            RealmAuditLog(
                realm=realm,
                acting_user=acting_user,
                modified_user=sub_info.user,
                modified_stream=sub_info.stream,
                event_last_message_id=event_last_message_id,
                event_type=RealmAuditLog.SUBSCRIPTION_CREATED,
                event_time=event_time,
            )
        )
    for sub_info in subs_to_activate:
        all_subscription_logs.append(
            RealmAuditLog(
                realm=realm,
                acting_user=acting_user,
                modified_user=sub_info.user,
                modified_stream=sub_info.stream,
                event_last_message_id=event_last_message_id,
                event_type=RealmAuditLog.SUBSCRIPTION_ACTIVATED,
                event_time=event_time,
            )
        )
    # Now since we have all log objects generated we can do a bulk insert
    RealmAuditLog.objects.bulk_create(all_subscription_logs)


def send_stream_creation_events_for_private_streams(
    realm: Realm,
    stream_dict: Dict[int, Stream],
    altered_user_dict: Dict[int, Set[int]],
) -> None:
    for stream_id, stream_users_ids in altered_user_dict.items():
        stream = stream_dict[stream_id]

        if not stream.is_public():
            # Users newly added to invite-only streams
            # need a `create` notification.  The former, because
            # they need the stream to exist before
            # they get the "subscribe" notification, and the latter so
            # they can manage the new stream.
            # Realm admins already have all created private streams.
            realm_admin_ids = {user.id for user in realm.get_admin_users_and_bots()}
            notify_user_ids = list(stream_users_ids - realm_admin_ids)

            if notify_user_ids:
                send_stream_creation_event(stream, notify_user_ids)


def send_peer_subscriber_events(
    op: str,
    realm: Realm,
    stream_dict: Dict[int, Stream],
    altered_user_dict: Dict[int, Set[int]],
    private_peer_dict: Dict[int, Set[int]],
) -> None:
    # Send peer_add/peer_remove events to other users who are tracking the
    # subscribers lists of streams in their browser; everyone for
    # public streams and only existing subscribers for private streams.

    assert op in ["peer_add", "peer_remove"]

    private_stream_ids = [
        stream_id for stream_id in altered_user_dict if stream_dict[stream_id].invite_only
    ]

    for stream_id in private_stream_ids:
        altered_user_ids = altered_user_dict[stream_id]
        peer_user_ids = private_peer_dict[stream_id] - altered_user_ids

        if peer_user_ids and altered_user_ids:
            event = dict(
                type="subscription",
                op=op,
                stream_ids=[stream_id],
                user_ids=sorted(list(altered_user_ids)),
            )
            send_event(realm, event, peer_user_ids)

    public_stream_ids = [
        stream_id
        for stream_id in altered_user_dict
        if not stream_dict[stream_id].invite_only and not stream_dict[stream_id].is_in_zephyr_realm
    ]

    if public_stream_ids:
        user_streams: Dict[int, Set[int]] = defaultdict(set)

        public_peer_ids = set(active_non_guest_user_ids(realm.id))

        for stream_id in public_stream_ids:
            altered_user_ids = altered_user_dict[stream_id]
            peer_user_ids = public_peer_ids - altered_user_ids

            if peer_user_ids and altered_user_ids:
                if len(altered_user_ids) == 1:
                    # If we only have one user, we will try to
                    # find other streams they have (un)subscribed to
                    # (where it's just them).  This optimization
                    # typically works when a single user is subscribed
                    # to multiple default public streams during
                    # new-user registration.
                    #
                    # This optimization depends on all public streams
                    # having the same peers for any single user, which
                    # isn't the case for private streams.
                    altered_user_id = list(altered_user_ids)[0]
                    user_streams[altered_user_id].add(stream_id)
                else:
                    event = dict(
                        type="subscription",
                        op=op,
                        stream_ids=[stream_id],
                        user_ids=sorted(list(altered_user_ids)),
                    )
                    send_event(realm, event, peer_user_ids)

        for user_id, stream_ids in user_streams.items():
            peer_user_ids = public_peer_ids - {user_id}
            event = dict(
                type="subscription",
                op=op,
                stream_ids=sorted(list(stream_ids)),
                user_ids=[user_id],
            )
            send_event(realm, event, peer_user_ids)


def send_peer_remove_events(
    realm: Realm,
    streams: List[Stream],
    altered_user_dict: Dict[int, Set[int]],
) -> None:
    private_streams = [stream for stream in streams if stream.invite_only]

    private_peer_dict = bulk_get_private_peers(
        realm=realm,
        private_streams=private_streams,
    )
    stream_dict = {stream.id: stream for stream in streams}

    send_peer_subscriber_events(
        op="peer_remove",
        realm=realm,
        stream_dict=stream_dict,
        altered_user_dict=altered_user_dict,
        private_peer_dict=private_peer_dict,
    )


def notify_subscriptions_removed(
    realm: Realm, user_profile: UserProfile, streams: Iterable[Stream]
) -> None:

    payload = [dict(name=stream.name, stream_id=stream.id) for stream in streams]
    event = dict(type="subscription", op="remove", subscriptions=payload)
    send_event(realm, event, [user_profile.id])


SubAndRemovedT = Tuple[List[Tuple[UserProfile, Stream]], List[Tuple[UserProfile, Stream]]]


def bulk_remove_subscriptions(
    realm: Realm,
    users: Iterable[UserProfile],
    streams: Iterable[Stream],
    *,
    acting_user: Optional[UserProfile],
) -> SubAndRemovedT:

    users = list(users)
    streams = list(streams)

    # Sanity check our callers
    for stream in streams:
        assert stream.realm_id == realm.id

    for user in users:
        assert user.realm_id == realm.id

    stream_dict = {stream.id: stream for stream in streams}

    existing_subs_by_user = get_bulk_stream_subscriber_info(users, streams)

    def get_non_subscribed_subs() -> List[Tuple[UserProfile, Stream]]:
        stream_ids = {stream.id for stream in streams}

        not_subscribed: List[Tuple[UserProfile, Stream]] = []

        for user_profile in users:
            user_sub_stream_info = existing_subs_by_user[user_profile.id]

            subscribed_stream_ids = {sub_info.stream.id for sub_info in user_sub_stream_info}
            not_subscribed_stream_ids = stream_ids - subscribed_stream_ids

            for stream_id in not_subscribed_stream_ids:
                stream = stream_dict[stream_id]
                not_subscribed.append((user_profile, stream))

        return not_subscribed

    not_subscribed = get_non_subscribed_subs()

    subs_to_deactivate: List[SubInfo] = []
    sub_ids_to_deactivate: List[int] = []

    # This loop just flattens out our data into big lists for
    # bulk operations.
    for sub_infos in existing_subs_by_user.values():
        for sub_info in sub_infos:
            subs_to_deactivate.append(sub_info)
            sub_ids_to_deactivate.append(sub_info.sub.id)

    # We do all the database changes in a transaction to ensure
    # RealmAuditLog entries are atomically created when making changes.
    with transaction.atomic():
        occupied_streams_before = list(get_occupied_streams(realm))
        Subscription.objects.filter(
            id__in=sub_ids_to_deactivate,
        ).update(active=False)
        occupied_streams_after = list(get_occupied_streams(realm))

        # Log subscription activities in RealmAuditLog
        event_time = timezone_now()
        event_last_message_id = get_last_message_id()
        all_subscription_logs = [
            RealmAuditLog(
                realm=sub_info.user.realm,
                acting_user=acting_user,
                modified_user=sub_info.user,
                modified_stream=sub_info.stream,
                event_last_message_id=event_last_message_id,
                event_type=RealmAuditLog.SUBSCRIPTION_DEACTIVATED,
                event_time=event_time,
            )
            for sub_info in subs_to_deactivate
        ]

        # Now since we have all log objects generated we can do a bulk insert
        RealmAuditLog.objects.bulk_create(all_subscription_logs)

    altered_user_dict: Dict[int, Set[int]] = defaultdict(set)
    streams_by_user: Dict[int, List[Stream]] = defaultdict(list)
    for sub_info in subs_to_deactivate:
        stream = sub_info.stream
        streams_by_user[sub_info.user.id].append(stream)
        altered_user_dict[stream.id].add(sub_info.user.id)

    for user_profile in users:
        if len(streams_by_user[user_profile.id]) == 0:
            continue
        notify_subscriptions_removed(realm, user_profile, streams_by_user[user_profile.id])

        event = {
            "type": "mark_stream_messages_as_read",
            "user_profile_id": user_profile.id,
            "stream_recipient_ids": [stream.recipient_id for stream in streams],
        }
        queue_json_publish("deferred_work", event)

    send_peer_remove_events(
        realm=realm,
        streams=streams,
        altered_user_dict=altered_user_dict,
    )

    new_vacant_streams = set(occupied_streams_before) - set(occupied_streams_after)
    new_vacant_private_streams = [stream for stream in new_vacant_streams if stream.invite_only]

    if new_vacant_private_streams:
        # Deactivate any newly-vacant private streams
        for stream in new_vacant_private_streams:
            do_deactivate_stream(stream, acting_user=acting_user)

    return (
        [(sub_info.user, sub_info.stream) for sub_info in subs_to_deactivate],
        not_subscribed,
    )


def do_change_subscription_property(
    user_profile: UserProfile,
    sub: Subscription,
    stream: Stream,
    property_name: str,
    value: Any,
    *,
    acting_user: Optional[UserProfile],
) -> None:
    database_property_name = property_name
    event_property_name = property_name
    database_value = value
    event_value = value

    # For this property, is_muted is used in the database, but
    # in_home_view in the API, since we haven't migrated the events
    # API to the new name yet.
    if property_name == "in_home_view":
        database_property_name = "is_muted"
        database_value = not value
    if property_name == "is_muted":
        event_property_name = "in_home_view"
        event_value = not value

    old_value = getattr(sub, database_property_name)
    setattr(sub, database_property_name, database_value)
    sub.save(update_fields=[database_property_name])
    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=user_profile.realm,
        event_type=RealmAuditLog.SUBSCRIPTION_PROPERTY_CHANGED,
        event_time=event_time,
        modified_user=user_profile,
        acting_user=acting_user,
        modified_stream=stream,
        extra_data=orjson.dumps(
            {
                RealmAuditLog.OLD_VALUE: old_value,
                RealmAuditLog.NEW_VALUE: database_value,
                "property": database_property_name,
            }
        ).decode(),
    )

    event = dict(
        type="subscription",
        op="update",
        property=event_property_name,
        value=event_value,
        stream_id=stream.id,
    )
    send_event(user_profile.realm, event, [user_profile.id])


def do_change_password(user_profile: UserProfile, password: str, commit: bool = True) -> None:
    user_profile.set_password(password)
    if commit:
        user_profile.save(update_fields=["password"])
    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=user_profile.realm,
        acting_user=user_profile,
        modified_user=user_profile,
        event_type=RealmAuditLog.USER_PASSWORD_CHANGED,
        event_time=event_time,
    )


def do_change_full_name(
    user_profile: UserProfile, full_name: str, acting_user: Optional[UserProfile]
) -> None:
    old_name = user_profile.full_name
    user_profile.full_name = full_name
    user_profile.save(update_fields=["full_name"])
    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=user_profile.realm,
        acting_user=acting_user,
        modified_user=user_profile,
        event_type=RealmAuditLog.USER_FULL_NAME_CHANGED,
        event_time=event_time,
        extra_data=old_name,
    )
    payload = dict(user_id=user_profile.id, full_name=user_profile.full_name)
    send_event(
        user_profile.realm,
        dict(type="realm_user", op="update", person=payload),
        active_user_ids(user_profile.realm_id),
    )
    if user_profile.is_bot:
        send_event(
            user_profile.realm,
            dict(type="realm_bot", op="update", bot=payload),
            bot_owner_user_ids(user_profile),
        )


def check_change_full_name(
    user_profile: UserProfile, full_name_raw: str, acting_user: Optional[UserProfile]
) -> str:
    """Verifies that the user's proposed full name is valid.  The caller
    is responsible for checking check permissions.  Returns the new
    full name, which may differ from what was passed in (because this
    function strips whitespace)."""
    new_full_name = check_full_name(full_name_raw)
    do_change_full_name(user_profile, new_full_name, acting_user)
    return new_full_name


def check_change_bot_full_name(
    user_profile: UserProfile, full_name_raw: str, acting_user: UserProfile
) -> None:
    new_full_name = check_full_name(full_name_raw)

    if new_full_name == user_profile.full_name:
        # Our web app will try to patch full_name even if the user didn't
        # modify the name in the form.  We just silently ignore those
        # situations.
        return

    check_bot_name_available(
        realm_id=user_profile.realm_id,
        full_name=new_full_name,
    )
    do_change_full_name(user_profile, new_full_name, acting_user)


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
def do_change_tos_version(user_profile: UserProfile, tos_version: str) -> None:
    user_profile.tos_version = tos_version
    user_profile.save(update_fields=["tos_version"])
    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=user_profile.realm,
        acting_user=user_profile,
        modified_user=user_profile,
        event_type=RealmAuditLog.USER_TERMS_OF_SERVICE_VERSION_CHANGED,
        event_time=event_time,
    )


def do_regenerate_api_key(user_profile: UserProfile, acting_user: UserProfile) -> str:
    old_api_key = user_profile.api_key
    new_api_key = generate_api_key()
    user_profile.api_key = new_api_key
    user_profile.save(update_fields=["api_key"])

    # We need to explicitly delete the old API key from our caches,
    # because the on-save handler for flushing the UserProfile object
    # in zerver/lib/cache.py only has access to the new API key.
    cache_delete(user_profile_by_api_key_cache_key(old_api_key))

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=user_profile.realm,
        acting_user=acting_user,
        modified_user=user_profile,
        event_type=RealmAuditLog.USER_API_KEY_CHANGED,
        event_time=event_time,
    )

    if user_profile.is_bot:
        send_event(
            user_profile.realm,
            dict(
                type="realm_bot",
                op="update",
                bot=dict(
                    user_id=user_profile.id,
                    api_key=new_api_key,
                ),
            ),
            bot_owner_user_ids(user_profile),
        )

    event = {"type": "clear_push_device_tokens", "user_profile_id": user_profile.id}
    queue_json_publish("deferred_work", event)

    return new_api_key


def notify_avatar_url_change(user_profile: UserProfile) -> None:
    if user_profile.is_bot:
        bot_event = dict(
            type="realm_bot",
            op="update",
            bot=dict(
                user_id=user_profile.id,
                avatar_url=avatar_url(user_profile),
            ),
        )
        transaction.on_commit(
            lambda: send_event(
                user_profile.realm,
                bot_event,
                bot_owner_user_ids(user_profile),
            )
        )

    payload = dict(
        avatar_source=user_profile.avatar_source,
        avatar_url=avatar_url(user_profile),
        avatar_url_medium=avatar_url(user_profile, medium=True),
        avatar_version=user_profile.avatar_version,
        # Even clients using client_gravatar don't need the email,
        # since we're sending the URL anyway.
        user_id=user_profile.id,
    )

    event = dict(type="realm_user", op="update", person=payload)
    transaction.on_commit(
        lambda: send_event(
            user_profile.realm,
            event,
            active_user_ids(user_profile.realm_id),
        )
    )


@transaction.atomic(savepoint=False)
def do_change_avatar_fields(
    user_profile: UserProfile,
    avatar_source: str,
    skip_notify: bool = False,
    *,
    acting_user: Optional[UserProfile],
) -> None:
    user_profile.avatar_source = avatar_source
    user_profile.avatar_version += 1
    user_profile.save(update_fields=["avatar_source", "avatar_version"])
    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=user_profile.realm,
        modified_user=user_profile,
        event_type=RealmAuditLog.USER_AVATAR_SOURCE_CHANGED,
        extra_data={"avatar_source": avatar_source},
        event_time=event_time,
        acting_user=acting_user,
    )

    if not skip_notify:
        notify_avatar_url_change(user_profile)


def do_delete_avatar_image(user: UserProfile, *, acting_user: Optional[UserProfile]) -> None:
    do_change_avatar_fields(user, UserProfile.AVATAR_FROM_GRAVATAR, acting_user=acting_user)
    delete_avatar_image(user)


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


def send_change_stream_permission_notification(
    stream: Stream,
    *,
    old_policy_name: str,
    new_policy_name: str,
    acting_user: UserProfile,
) -> None:
    sender = get_system_bot(settings.NOTIFICATION_BOT, acting_user.realm_id)
    user_mention = silent_mention_syntax_for_user(acting_user)

    with override_language(stream.realm.default_language):
        notification_string = _(
            "{user} changed the [access permissions](/help/stream-permissions) "
            "for this stream from **{old_policy}** to **{new_policy}**."
        )
        notification_string = notification_string.format(
            user=user_mention,
            old_policy=old_policy_name,
            new_policy=new_policy_name,
        )
        internal_send_stream_message(
            sender, stream, Realm.STREAM_EVENTS_NOTIFICATION_TOPIC, notification_string
        )


def do_change_stream_permission(
    stream: Stream,
    *,
    invite_only: Optional[bool] = None,
    history_public_to_subscribers: Optional[bool] = None,
    is_web_public: Optional[bool] = None,
    acting_user: UserProfile,
) -> None:
    old_invite_only_value = stream.invite_only
    old_history_public_to_subscribers_value = stream.history_public_to_subscribers
    old_is_web_public_value = stream.is_web_public

    # A note on these assertions: It's possible we'd be better off
    # making all callers of this function pass the full set of
    # parameters, rather than having default values.  Doing so would
    # allow us to remove the messy logic below, where we sometimes
    # ignore the passed parameters.
    #
    # But absent such a refactoring, it's important to assert that
    # we're not requesting an unsupported configurations.
    if is_web_public:
        assert history_public_to_subscribers is not False
        assert invite_only is not True
        stream.is_web_public = True
        stream.invite_only = False
        stream.history_public_to_subscribers = True
    else:
        assert invite_only is not None
        # is_web_public is falsey
        history_public_to_subscribers = get_default_value_for_history_public_to_subscribers(
            stream.realm,
            invite_only,
            history_public_to_subscribers,
        )
        stream.invite_only = invite_only
        stream.history_public_to_subscribers = history_public_to_subscribers
        stream.is_web_public = False

    with transaction.atomic():
        stream.save(update_fields=["invite_only", "history_public_to_subscribers", "is_web_public"])

        event_time = timezone_now()
        if old_invite_only_value != stream.invite_only:
            # Reset the Attachment.is_realm_public cache for all
            # messages in the stream whose permissions were changed.
            Attachment.objects.filter(messages__recipient_id=stream.recipient_id).update(
                is_realm_public=None
            )
            # We need to do the same for ArchivedAttachment to avoid
            # bugs if deleted attachments are later restored.
            ArchivedAttachment.objects.filter(messages__recipient_id=stream.recipient_id).update(
                is_realm_public=None
            )

            RealmAuditLog.objects.create(
                realm=stream.realm,
                acting_user=acting_user,
                modified_stream=stream,
                event_type=RealmAuditLog.STREAM_PROPERTY_CHANGED,
                event_time=event_time,
                extra_data=orjson.dumps(
                    {
                        RealmAuditLog.OLD_VALUE: old_invite_only_value,
                        RealmAuditLog.NEW_VALUE: stream.invite_only,
                        "property": "invite_only",
                    }
                ).decode(),
            )

        if old_history_public_to_subscribers_value != stream.history_public_to_subscribers:
            RealmAuditLog.objects.create(
                realm=stream.realm,
                acting_user=acting_user,
                modified_stream=stream,
                event_type=RealmAuditLog.STREAM_PROPERTY_CHANGED,
                event_time=event_time,
                extra_data=orjson.dumps(
                    {
                        RealmAuditLog.OLD_VALUE: old_history_public_to_subscribers_value,
                        RealmAuditLog.NEW_VALUE: stream.history_public_to_subscribers,
                        "property": "history_public_to_subscribers",
                    }
                ).decode(),
            )

        if old_is_web_public_value != stream.is_web_public:
            # Reset the Attachment.is_realm_public cache for all
            # messages in the stream whose permissions were changed.
            Attachment.objects.filter(messages__recipient_id=stream.recipient_id).update(
                is_web_public=None
            )
            # We need to do the same for ArchivedAttachment to avoid
            # bugs if deleted attachments are later restored.
            ArchivedAttachment.objects.filter(messages__recipient_id=stream.recipient_id).update(
                is_web_public=None
            )

            RealmAuditLog.objects.create(
                realm=stream.realm,
                acting_user=acting_user,
                modified_stream=stream,
                event_type=RealmAuditLog.STREAM_PROPERTY_CHANGED,
                event_time=event_time,
                extra_data=orjson.dumps(
                    {
                        RealmAuditLog.OLD_VALUE: old_is_web_public_value,
                        RealmAuditLog.NEW_VALUE: stream.is_web_public,
                        "property": "is_web_public",
                    }
                ).decode(),
            )

    event = dict(
        op="update",
        type="stream",
        property="invite_only",
        value=stream.invite_only,
        history_public_to_subscribers=stream.history_public_to_subscribers,
        is_web_public=stream.is_web_public,
        stream_id=stream.id,
        name=stream.name,
    )
    send_event(stream.realm, event, can_access_stream_user_ids(stream))

    old_policy_name = get_stream_permission_policy_name(
        invite_only=old_invite_only_value,
        history_public_to_subscribers=old_history_public_to_subscribers_value,
        is_web_public=old_is_web_public_value,
    )
    new_policy_name = get_stream_permission_policy_name(
        invite_only=stream.invite_only,
        history_public_to_subscribers=stream.history_public_to_subscribers,
        is_web_public=stream.is_web_public,
    )
    send_change_stream_permission_notification(
        stream,
        old_policy_name=old_policy_name,
        new_policy_name=new_policy_name,
        acting_user=acting_user,
    )


def send_change_stream_post_policy_notification(
    stream: Stream, *, old_post_policy: int, new_post_policy: int, acting_user: UserProfile
) -> None:
    sender = get_system_bot(settings.NOTIFICATION_BOT, acting_user.realm_id)
    user_mention = silent_mention_syntax_for_user(acting_user)

    with override_language(stream.realm.default_language):
        notification_string = _(
            "{user} changed the [posting permissions](/help/stream-sending-policy) "
            "for this stream:\n\n"
            "* **Old permissions**: {old_policy}.\n"
            "* **New permissions**: {new_policy}.\n"
        )
        notification_string = notification_string.format(
            user=user_mention,
            old_policy=Stream.POST_POLICIES[old_post_policy],
            new_policy=Stream.POST_POLICIES[new_post_policy],
        )
        internal_send_stream_message(
            sender, stream, Realm.STREAM_EVENTS_NOTIFICATION_TOPIC, notification_string
        )


def do_change_stream_post_policy(
    stream: Stream, stream_post_policy: int, *, acting_user: UserProfile
) -> None:
    old_post_policy = stream.stream_post_policy
    with transaction.atomic():
        stream.stream_post_policy = stream_post_policy
        stream.save(update_fields=["stream_post_policy"])
        RealmAuditLog.objects.create(
            realm=stream.realm,
            acting_user=acting_user,
            modified_stream=stream,
            event_type=RealmAuditLog.STREAM_PROPERTY_CHANGED,
            event_time=timezone_now(),
            extra_data=orjson.dumps(
                {
                    RealmAuditLog.OLD_VALUE: old_post_policy,
                    RealmAuditLog.NEW_VALUE: stream_post_policy,
                    "property": "stream_post_policy",
                }
            ).decode(),
        )

    event = dict(
        op="update",
        type="stream",
        property="stream_post_policy",
        value=stream_post_policy,
        stream_id=stream.id,
        name=stream.name,
    )
    send_event(stream.realm, event, can_access_stream_user_ids(stream))

    # Backwards-compatibility code: We removed the
    # is_announcement_only property in early 2020, but we send a
    # duplicate event for legacy mobile clients that might want the
    # data.
    event = dict(
        op="update",
        type="stream",
        property="is_announcement_only",
        value=stream.stream_post_policy == Stream.STREAM_POST_POLICY_ADMINS,
        stream_id=stream.id,
        name=stream.name,
    )
    send_event(stream.realm, event, can_access_stream_user_ids(stream))

    send_change_stream_post_policy_notification(
        stream,
        old_post_policy=old_post_policy,
        new_post_policy=stream_post_policy,
        acting_user=acting_user,
    )


def do_rename_stream(stream: Stream, new_name: str, user_profile: UserProfile) -> Dict[str, str]:
    old_name = stream.name
    stream.name = new_name
    stream.save(update_fields=["name"])

    RealmAuditLog.objects.create(
        realm=stream.realm,
        acting_user=user_profile,
        modified_stream=stream,
        event_type=RealmAuditLog.STREAM_NAME_CHANGED,
        event_time=timezone_now(),
        extra_data=orjson.dumps(
            {
                RealmAuditLog.OLD_VALUE: old_name,
                RealmAuditLog.NEW_VALUE: new_name,
            }
        ).decode(),
    )

    recipient_id = stream.recipient_id
    messages = Message.objects.filter(recipient_id=recipient_id).only("id")

    # Update the display recipient and stream, which are easy single
    # items to set.
    old_cache_key = get_stream_cache_key(old_name, stream.realm_id)
    new_cache_key = get_stream_cache_key(stream.name, stream.realm_id)
    if old_cache_key != new_cache_key:
        cache_delete(old_cache_key)
        cache_set(new_cache_key, stream)
    cache_set(display_recipient_cache_key(recipient_id), stream.name)

    # Delete cache entries for everything else, which is cheaper and
    # clearer than trying to set them. display_recipient is the out of
    # date field in all cases.
    cache_delete_many(to_dict_cache_key_id(message.id) for message in messages)
    new_email = encode_email_address(stream, show_sender=True)

    # We will tell our users to essentially
    # update stream.name = new_name where name = old_name
    # and update stream.email = new_email where name = old_name.
    # We could optimize this by trying to send one message, but the
    # client code really wants one property update at a time, and
    # updating stream names is a pretty infrequent operation.
    # More importantly, we want to key these updates by id, not name,
    # since id is the immutable primary key, and obviously name is not.
    data_updates = [
        ["email_address", new_email],
        ["name", new_name],
    ]
    for property, value in data_updates:
        event = dict(
            op="update",
            type="stream",
            property=property,
            value=value,
            stream_id=stream.id,
            name=old_name,
        )
        send_event(stream.realm, event, can_access_stream_user_ids(stream))
    sender = get_system_bot(settings.NOTIFICATION_BOT, stream.realm_id)
    with override_language(stream.realm.default_language):
        internal_send_stream_message(
            sender,
            stream,
            Realm.STREAM_EVENTS_NOTIFICATION_TOPIC,
            _("{user_name} renamed stream {old_stream_name} to {new_stream_name}.").format(
                user_name=silent_mention_syntax_for_user(user_profile),
                old_stream_name=f"**{old_name}**",
                new_stream_name=f"**{new_name}**",
            ),
        )
    # Even though the token doesn't change, the web client needs to update the
    # email forwarding address to display the correctly-escaped new name.
    return {"email_address": new_email}


def send_change_stream_description_notification(
    stream: Stream, *, old_description: str, new_description: str, acting_user: UserProfile
) -> None:
    sender = get_system_bot(settings.NOTIFICATION_BOT, acting_user.realm_id)
    user_mention = silent_mention_syntax_for_user(acting_user)

    with override_language(stream.realm.default_language):
        if new_description == "":
            new_description = "*" + _("No description.") + "*"
        if old_description == "":
            old_description = "*" + _("No description.") + "*"

        notification_string = (
            _("{user} changed the description for this stream.").format(user=user_mention)
            + "\n\n* **"
            + _("Old description")
            + ":**"
            + f"\n```` quote\n{old_description}\n````\n"
            + "* **"
            + _("New description")
            + ":**"
            + f"\n```` quote\n{new_description}\n````"
        )

        internal_send_stream_message(
            sender, stream, Realm.STREAM_EVENTS_NOTIFICATION_TOPIC, notification_string
        )


def do_change_stream_description(
    stream: Stream, new_description: str, *, acting_user: UserProfile
) -> None:
    old_description = stream.description

    with transaction.atomic():
        stream.description = new_description
        stream.rendered_description = render_stream_description(new_description)
        stream.save(update_fields=["description", "rendered_description"])
        RealmAuditLog.objects.create(
            realm=stream.realm,
            acting_user=acting_user,
            modified_stream=stream,
            event_type=RealmAuditLog.STREAM_PROPERTY_CHANGED,
            event_time=timezone_now(),
            extra_data=orjson.dumps(
                {
                    RealmAuditLog.OLD_VALUE: old_description,
                    RealmAuditLog.NEW_VALUE: new_description,
                    "property": "description",
                }
            ).decode(),
        )

    event = dict(
        type="stream",
        op="update",
        property="description",
        name=stream.name,
        stream_id=stream.id,
        value=new_description,
        rendered_description=stream.rendered_description,
    )
    send_event(stream.realm, event, can_access_stream_user_ids(stream))

    send_change_stream_description_notification(
        stream,
        old_description=old_description,
        new_description=new_description,
        acting_user=acting_user,
    )


def send_change_stream_message_retention_days_notification(
    user_profile: UserProfile, stream: Stream, old_value: Optional[int], new_value: Optional[int]
) -> None:
    sender = get_system_bot(settings.NOTIFICATION_BOT, user_profile.realm_id)
    user_mention = silent_mention_syntax_for_user(user_profile)

    # If switching from or to the organization's default retention policy,
    # we want to take the realm's default into account.
    if old_value is None:
        old_value = stream.realm.message_retention_days
    if new_value is None:
        new_value = stream.realm.message_retention_days

    with override_language(stream.realm.default_language):
        if old_value == Stream.MESSAGE_RETENTION_SPECIAL_VALUES_MAP["unlimited"]:
            old_retention_period = _("Forever")
            new_retention_period = f"{new_value} days"
            summary_line = f"Messages in this stream will now be automatically deleted {new_value} days after they are sent."
        elif new_value == Stream.MESSAGE_RETENTION_SPECIAL_VALUES_MAP["unlimited"]:
            old_retention_period = f"{old_value} days"
            new_retention_period = _("Forever")
            summary_line = _("Messages in this stream will now be retained forever.")
        else:
            old_retention_period = f"{old_value} days"
            new_retention_period = f"{new_value} days"
            summary_line = f"Messages in this stream will now be automatically deleted {new_value} days after they are sent."
        notification_string = _(
            "{user} has changed the [message retention period](/help/message-retention-policy) for this stream:\n"
            "* **Old retention period**: {old_retention_period}\n"
            "* **New retention period**: {new_retention_period}\n\n"
            "{summary_line}"
        )
        notification_string = notification_string.format(
            user=user_mention,
            old_retention_period=old_retention_period,
            new_retention_period=new_retention_period,
            summary_line=summary_line,
        )
        internal_send_stream_message(
            sender, stream, Realm.STREAM_EVENTS_NOTIFICATION_TOPIC, notification_string
        )


def do_change_stream_message_retention_days(
    stream: Stream, acting_user: UserProfile, message_retention_days: Optional[int] = None
) -> None:
    old_message_retention_days_value = stream.message_retention_days

    with transaction.atomic():
        stream.message_retention_days = message_retention_days
        stream.save(update_fields=["message_retention_days"])
        RealmAuditLog.objects.create(
            realm=stream.realm,
            acting_user=acting_user,
            modified_stream=stream,
            event_type=RealmAuditLog.STREAM_MESSAGE_RETENTION_DAYS_CHANGED,
            event_time=timezone_now(),
            extra_data=orjson.dumps(
                {
                    RealmAuditLog.OLD_VALUE: old_message_retention_days_value,
                    RealmAuditLog.NEW_VALUE: message_retention_days,
                }
            ).decode(),
        )

    event = dict(
        op="update",
        type="stream",
        property="message_retention_days",
        value=message_retention_days,
        stream_id=stream.id,
        name=stream.name,
    )
    send_event(stream.realm, event, can_access_stream_user_ids(stream))
    send_change_stream_message_retention_days_notification(
        user_profile=acting_user,
        stream=stream,
        old_value=old_message_retention_days_value,
        new_value=message_retention_days,
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


def update_scheduled_email_notifications_time(
    user_profile: UserProfile, old_batching_period: int, new_batching_period: int
) -> None:
    existing_scheduled_emails = ScheduledMessageNotificationEmail.objects.filter(
        user_profile=user_profile
    )

    scheduled_timestamp_change = datetime.timedelta(
        seconds=new_batching_period
    ) - datetime.timedelta(seconds=old_batching_period)

    existing_scheduled_emails.update(
        scheduled_timestamp=F("scheduled_timestamp") + scheduled_timestamp_change
    )


@transaction.atomic(durable=True)
def do_change_user_setting(
    user_profile: UserProfile,
    setting_name: str,
    setting_value: Union[bool, str, int],
    *,
    acting_user: Optional[UserProfile],
) -> None:
    old_value = getattr(user_profile, setting_name)
    event_time = timezone_now()

    if setting_name == "timezone":
        assert isinstance(setting_value, str)
        setting_value = canonicalize_timezone(setting_value)
    else:
        property_type = UserProfile.property_types[setting_name]
        assert isinstance(setting_value, property_type)
    setattr(user_profile, setting_name, setting_value)

    # TODO: Move these database actions into a transaction.atomic block.
    user_profile.save(update_fields=[setting_name])

    if setting_name in UserProfile.notification_setting_types:
        # Prior to all personal settings being managed by property_types,
        # these were only created for notification settings.
        #
        # TODO: Start creating these for all settings, and do a
        # backfilled=True migration.
        RealmAuditLog.objects.create(
            realm=user_profile.realm,
            event_type=RealmAuditLog.USER_SETTING_CHANGED,
            event_time=event_time,
            acting_user=acting_user,
            modified_user=user_profile,
            extra_data=orjson.dumps(
                {
                    RealmAuditLog.OLD_VALUE: old_value,
                    RealmAuditLog.NEW_VALUE: setting_value,
                    "property": setting_name,
                }
            ).decode(),
        )
    # Disabling digest emails should clear a user's email queue
    if setting_name == "enable_digest_emails" and not setting_value:
        clear_scheduled_emails(user_profile.id, ScheduledEmail.DIGEST)

    if setting_name == "email_notifications_batching_period_seconds":
        assert isinstance(old_value, int)
        assert isinstance(setting_value, int)
        update_scheduled_email_notifications_time(user_profile, old_value, setting_value)

    event = {
        "type": "user_settings",
        "op": "update",
        "property": setting_name,
        "value": setting_value,
    }
    if setting_name == "default_language":
        assert isinstance(setting_value, str)
        event["language_name"] = get_language_name(setting_value)

    transaction.on_commit(lambda: send_event(user_profile.realm, event, [user_profile.id]))

    if setting_name in UserProfile.notification_settings_legacy:
        # This legacy event format is for backwards-compatibility with
        # clients that don't support the new user_settings event type.
        # We only send this for settings added before Feature level 89.
        legacy_event = {
            "type": "update_global_notifications",
            "user": user_profile.email,
            "notification_name": setting_name,
            "setting": setting_value,
        }
        transaction.on_commit(
            lambda: send_event(user_profile.realm, legacy_event, [user_profile.id])
        )

    if setting_name in UserProfile.display_settings_legacy or setting_name == "timezone":
        # This legacy event format is for backwards-compatibility with
        # clients that don't support the new user_settings event type.
        # We only send this for settings added before Feature level 89.
        legacy_event = {
            "type": "update_display_settings",
            "user": user_profile.email,
            "setting_name": setting_name,
            "setting": setting_value,
        }
        if setting_name == "default_language":
            assert isinstance(setting_value, str)
            legacy_event["language_name"] = get_language_name(setting_value)

        transaction.on_commit(
            lambda: send_event(user_profile.realm, legacy_event, [user_profile.id])
        )

    # Updates to the time zone display setting are sent to all users
    if setting_name == "timezone":
        payload = dict(
            email=user_profile.email,
            user_id=user_profile.id,
            timezone=canonicalize_timezone(user_profile.timezone),
        )
        timezone_event = dict(type="realm_user", op="update", person=payload)
        transaction.on_commit(
            lambda: send_event(
                user_profile.realm,
                timezone_event,
                active_user_ids(user_profile.realm_id),
            )
        )

    if setting_name == "enable_drafts_synchronization" and setting_value is False:
        # Delete all of the drafts from the backend but don't send delete events
        # for them since all that's happened is that we stopped syncing changes,
        # not deleted every previously synced draft - to do that use the DELETE
        # endpoint.
        Draft.objects.filter(user_profile=user_profile).delete()


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


class ActivePresenceIdleUserData(TypedDict):
    alerted: bool
    notifications_data: UserMessageNotificationsData


def get_active_presence_idle_user_ids(
    realm: Realm,
    sender_id: int,
    active_users_data: List[ActivePresenceIdleUserData],
) -> List[int]:
    """
    Given a list of active_user_ids, we build up a subset
    of those users who fit these criteria:

        * They are likely to need notifications.
        * They are no longer "present" according to the
          UserPresence table.
    """

    if realm.presence_disabled:
        return []

    user_ids = set()
    for user_data in active_users_data:
        user_notifications_data: UserMessageNotificationsData = user_data["notifications_data"]
        alerted = user_data["alerted"]

        # We only need to know the presence idle state for a user if this message would be notifiable
        # for them if they were indeed idle. Only including those users in the calculation below is a
        # very important optimization for open communities with many inactive users.
        if user_notifications_data.is_notifiable(sender_id, idle=True) or alerted:
            user_ids.add(user_notifications_data.user_id)

    return filter_presence_idle_user_ids(user_ids)


def filter_presence_idle_user_ids(user_ids: Set[int]) -> List[int]:
    # Given a set of user IDs (the recipients of a message), accesses
    # the UserPresence table to determine which of these users are
    # currently idle and should potentially get email notifications
    # (and push notifications with with
    # user_profile.enable_online_push_notifications=False).
    #
    # We exclude any presence data from ZulipMobile for the purpose of
    # triggering these notifications; the mobile app can more
    # effectively do its own client-side filtering of notification
    # sounds/etc. for the case that the user is actively doing a PM
    # conversation in the app.

    if not user_ids:
        return []

    # Matches presence.js constant
    OFFLINE_THRESHOLD_SECS = 140

    recent = timezone_now() - datetime.timedelta(seconds=OFFLINE_THRESHOLD_SECS)
    rows = (
        UserPresence.objects.filter(
            user_profile_id__in=user_ids,
            status=UserPresence.ACTIVE,
            timestamp__gte=recent,
        )
        .exclude(client__name="ZulipMobile")
        .distinct("user_profile_id")
        .values("user_profile_id")
    )
    active_user_ids = {row["user_profile_id"] for row in rows}
    idle_user_ids = user_ids - active_user_ids
    return sorted(idle_user_ids)


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
