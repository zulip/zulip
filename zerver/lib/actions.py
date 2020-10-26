import datetime
import itertools
import logging
import os
import time
from collections import defaultdict
from operator import itemgetter
from typing import (
    AbstractSet,
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)

import django.db.utils
import orjson
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.files import File
from django.db import IntegrityError, connection, transaction
from django.db.models import Count, Exists, F, OuterRef, Q, Sum
from django.db.models.query import QuerySet
from django.utils.html import escape
from django.utils.timezone import now as timezone_now
from django.utils.translation import override as override_language
from django.utils.translation import ugettext as _
from psycopg2.extras import execute_values
from psycopg2.sql import SQL
from typing_extensions import TypedDict

from analytics.lib.counts import COUNT_STATS, RealmCount, do_increment_logging_stat
from analytics.models import StreamCount
from confirmation import settings as confirmation_settings
from confirmation.models import (
    Confirmation,
    confirmation_url,
    create_confirmation_link,
    generate_key,
)
from zerver.decorator import statsd_increment
from zerver.lib import retention as retention
from zerver.lib.addressee import Addressee
from zerver.lib.alert_words import (
    add_user_alert_words,
    get_alert_word_automaton,
    remove_user_alert_words,
)
from zerver.lib.avatar import avatar_url, avatar_url_from_dict
from zerver.lib.bot_config import ConfigError, get_bot_config, get_bot_configs, set_bot_config
from zerver.lib.bulk_create import bulk_create_users
from zerver.lib.cache import (
    bot_dict_fields,
    cache_delete,
    cache_delete_many,
    cache_set,
    cache_set_many,
    cache_with_key,
    delete_user_profile_caches,
    display_recipient_cache_key,
    flush_user_profile,
    to_dict_cache_key_id,
    user_profile_by_api_key_cache_key,
    user_profile_by_email_cache_key,
)
from zerver.lib.create_user import create_user, get_display_email_address
from zerver.lib.email_mirror_helpers import encode_email_address, encode_email_address_helper
from zerver.lib.email_notifications import enqueue_welcome_emails
from zerver.lib.email_validation import (
    email_reserved_for_system_bots_error,
    get_existing_user_errors,
    get_realm_email_validator,
    validate_email_is_valid,
)
from zerver.lib.emoji import get_emoji_file_name
from zerver.lib.exceptions import (
    ErrorCode,
    JsonableError,
    MarkdownRenderingException,
    StreamDoesNotExistError,
    StreamWithIDDoesNotExistError,
)
from zerver.lib.export import get_realm_exports_serialized
from zerver.lib.external_accounts import DEFAULT_EXTERNAL_ACCOUNTS
from zerver.lib.hotspots import get_next_hotspots
from zerver.lib.i18n import get_language_name
from zerver.lib.markdown import MentionData, topic_links
from zerver.lib.markdown import version as markdown_version
from zerver.lib.message import (
    MessageDict,
    access_message,
    get_last_message_id,
    render_markdown,
    truncate_body,
    truncate_topic,
    update_first_visible_message_id,
    wildcard_mention_allowed,
)
from zerver.lib.pysa import mark_sanitized
from zerver.lib.queue import queue_json_publish
from zerver.lib.realm_icon import realm_icon_url
from zerver.lib.realm_logo import get_realm_logo_data
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
from zerver.lib.storage import static_path
from zerver.lib.stream_subscription import (
    SubInfo,
    bulk_get_private_peers,
    bulk_get_subscriber_peer_info,
    get_active_subscriptions_for_stream_id,
    get_bulk_stream_subscriber_info,
    get_stream_subscriptions_for_user,
    get_stream_subscriptions_for_users,
    get_subscribed_stream_ids_for_user,
    num_subscribers_for_stream_id,
)
from zerver.lib.stream_topic import StreamTopicTarget
from zerver.lib.streams import (
    access_stream_for_send_message,
    check_stream_name,
    create_stream_if_needed,
    get_default_value_for_history_public_to_subscribers,
    render_stream_description,
    send_stream_creation_event,
    subscribed_to_stream,
)
from zerver.lib.timestamp import datetime_to_timestamp, timestamp_to_datetime
from zerver.lib.topic import (
    LEGACY_PREV_TOPIC,
    ORIG_TOPIC,
    TOPIC_LINKS,
    TOPIC_NAME,
    filter_by_exact_message_topic,
    filter_by_topic_name_via_message,
    save_message_for_edit_use_case,
    update_messages_for_topic_edit,
)
from zerver.lib.topic_mutes import add_topic_mute, get_topic_mutes, remove_topic_mute
from zerver.lib.types import ProfileFieldData
from zerver.lib.upload import (
    claim_attachment,
    delete_avatar_image,
    delete_export_tarball,
    delete_message_image,
    upload_emoji_image,
)
from zerver.lib.user_groups import access_user_group_by_id, create_user_group
from zerver.lib.user_status import update_user_status
from zerver.lib.users import (
    check_bot_name_available,
    check_full_name,
    format_user_row,
    get_api_key,
    user_profile_to_user_row,
)
from zerver.lib.utils import generate_api_key, log_statsd_event
from zerver.lib.validator import check_widget_content
from zerver.lib.widget import do_widget_post_save_actions
from zerver.models import (
    MAX_MESSAGE_LENGTH,
    Attachment,
    Client,
    CustomProfileField,
    CustomProfileFieldValue,
    DefaultStream,
    DefaultStreamGroup,
    EmailChangeStatus,
    Message,
    MultiuseInvite,
    PreregistrationUser,
    Reaction,
    Realm,
    RealmAuditLog,
    RealmDomain,
    RealmEmoji,
    RealmFilter,
    Recipient,
    ScheduledEmail,
    ScheduledMessage,
    Service,
    Stream,
    SubMessage,
    Subscription,
    UserActivity,
    UserActivityInterval,
    UserGroup,
    UserGroupMembership,
    UserHotspot,
    UserMessage,
    UserPresence,
    UserProfile,
    UserStatus,
    active_non_guest_user_ids,
    active_user_ids,
    custom_profile_fields_for_realm,
    filter_to_valid_prereg_users,
    get_active_streams,
    get_bot_dicts_in_realm,
    get_bot_services,
    get_client,
    get_default_stream_groups,
    get_huddle_recipient,
    get_huddle_user_ids,
    get_old_unclaimed_attachments,
    get_stream,
    get_stream_by_id_in_realm,
    get_stream_cache_key,
    get_system_bot,
    get_user_by_delivery_email,
    get_user_by_id_in_realm_including_cross_realm,
    get_user_profile_by_id,
    is_cross_realm_bot_email,
    query_for_ids,
    realm_filters_for_realm,
    stream_name_in_use,
    validate_attachment_request,
)
from zerver.tornado.django_api import send_event

if settings.BILLING_ENABLED:
    from corporate.lib.stripe import (
        downgrade_now_without_creating_additional_invoices,
        update_license_ledger_if_needed,
    )

# This will be used to type annotate parameters in a function if the function
# works on both str and unicode in python 2 but in python 3 it only works on str.
SizedTextIterable = Union[Sequence[str], AbstractSet[str]]
ONBOARDING_TOTAL_MESSAGES = 1000
ONBOARDING_UNREAD_MESSAGES = 20

STREAM_ASSIGNMENT_COLORS = [
    "#76ce90", "#fae589", "#a6c7e5", "#e79ab5",
    "#bfd56f", "#f4ae55", "#b0a5fd", "#addfe5",
    "#f5ce6e", "#c2726a", "#94c849", "#bd86e5",
    "#ee7e4a", "#a6dcbf", "#95a5fd", "#53a063",
    "#9987e1", "#e4523d", "#c2c2c2", "#4f8de4",
    "#c6a8ad", "#e7cc4d", "#c8bebf", "#a47462"]

def subscriber_info(user_id: int) -> Dict[str, Any]:
    return {
        'id': user_id,
        'flags': ['read']
    }

def can_access_stream_user_ids(stream: Stream) -> Set[int]:
    # return user ids of users who can access the attributes of
    # a stream, such as its name/description.
    if stream.is_public():
        # For a public stream, this is everyone in the realm
        # except unsubscribed guest users
        return public_stream_user_ids(stream)
    else:
        # for a private stream, it's subscribers plus realm admins.
        return private_stream_user_ids(
            stream.id) | {user.id for user in stream.realm.get_admin_users_and_bots()}

def private_stream_user_ids(stream_id: int) -> Set[int]:
    # TODO: Find similar queries elsewhere and de-duplicate this code.
    subscriptions = get_active_subscriptions_for_stream_id(stream_id)
    return {sub['user_profile_id'] for sub in subscriptions.values('user_profile_id')}

def public_stream_user_ids(stream: Stream) -> Set[int]:
    guest_subscriptions = get_active_subscriptions_for_stream_id(
        stream.id).filter(user_profile__role=UserProfile.ROLE_GUEST)
    guest_subscriptions = {sub['user_profile_id'] for sub in guest_subscriptions.values('user_profile_id')}
    return set(active_non_guest_user_ids(stream.realm_id)) | guest_subscriptions

def bot_owner_user_ids(user_profile: UserProfile) -> Set[int]:
    is_private_bot = (
        user_profile.default_sending_stream and
        user_profile.default_sending_stream.invite_only or
        user_profile.default_events_register_stream and
        user_profile.default_events_register_stream.invite_only)
    if is_private_bot:
        return {user_profile.bot_owner_id}
    else:
        users = {user.id for user in user_profile.realm.get_human_admin_users()}
        users.add(user_profile.bot_owner_id)
        return users

def realm_user_count(realm: Realm) -> int:
    return UserProfile.objects.filter(realm=realm, is_active=True, is_bot=False).count()

def realm_user_count_by_role(realm: Realm) -> Dict[str, Any]:
    human_counts = {str(UserProfile.ROLE_REALM_ADMINISTRATOR): 0,
                    str(UserProfile.ROLE_REALM_OWNER): 0,
                    str(UserProfile.ROLE_MEMBER): 0,
                    str(UserProfile.ROLE_GUEST): 0}
    for value_dict in list(UserProfile.objects.filter(
            realm=realm, is_bot=False, is_active=True).values('role').annotate(Count('role'))):
        human_counts[str(value_dict['role'])] = value_dict['role__count']
    bot_count = UserProfile.objects.filter(realm=realm, is_bot=True, is_active=True).count()
    return {
        RealmAuditLog.ROLE_COUNT_HUMANS: human_counts,
        RealmAuditLog.ROLE_COUNT_BOTS: bot_count,
    }

def get_signups_stream(realm: Realm) -> Stream:
    # This one-liner helps us work around a lint rule.
    return get_stream("signups", realm)

def notify_new_user(user_profile: UserProfile) -> None:
    sender_email = settings.NOTIFICATION_BOT
    sender = get_system_bot(sender_email)

    user_count = realm_user_count(user_profile.realm)
    signup_notifications_stream = user_profile.realm.get_signup_notifications_stream()
    # Send notification to realm signup notifications stream if it exists
    # Don't send notification for the first user in a realm
    if signup_notifications_stream is not None and user_count > 1:
        with override_language(user_profile.realm.default_language):
            message = _("{user} just signed up for Zulip. (total: {user_count})").format(
                user=f"@_**{user_profile.full_name}|{user_profile.id}**",
                user_count=user_count
            )
            internal_send_stream_message(
                user_profile.realm,
                sender,
                signup_notifications_stream,
                _("signups"),
                message
            )

    # We also send a notification to the Zulip administrative realm
    admin_realm = sender.realm
    try:
        # Check whether the stream exists
        signups_stream = get_signups_stream(admin_realm)
        with override_language(admin_realm.default_language):
            # We intentionally use the same strings as above to avoid translation burden.
            message = _("{user} just signed up for Zulip. (total: {user_count})").format(
                user=f"{user_profile.full_name} <`{user_profile.email}`>",
                user_count=user_count
            )
            internal_send_stream_message(
                admin_realm,
                sender,
                signups_stream,
                user_profile.realm.display_subdomain,
                message
            )

    except Stream.DoesNotExist:
        # If the signups stream hasn't been created in the admin
        # realm, don't auto-create it to send to it; just do nothing.
        pass

def notify_invites_changed(user_profile: UserProfile) -> None:
    event = dict(type="invites_changed")
    admin_ids = [user.id for user in
                 user_profile.realm.get_admin_users_and_bots()]
    send_event(user_profile.realm, event, admin_ids)

def add_new_user_history(user_profile: UserProfile, streams: Iterable[Stream]) -> None:
    """Give you the last ONBOARDING_TOTAL_MESSAGES messages on your public
    streams, so you have something to look at in your home view once
    you finish the tutorial.  The most recent ONBOARDING_UNREAD_MESSAGES
    are marked unread.
    """
    one_week_ago = timezone_now() - datetime.timedelta(weeks=1)

    recipient_ids = [stream.recipient_id for stream in streams if not stream.invite_only]
    recent_messages = Message.objects.filter(recipient_id__in=recipient_ids,
                                             date_sent__gt=one_week_ago).order_by("-id")
    message_ids_to_use = list(reversed(recent_messages.values_list(
        'id', flat=True)[0:ONBOARDING_TOTAL_MESSAGES]))
    if len(message_ids_to_use) == 0:
        return

    # Handle the race condition where a message arrives between
    # bulk_add_subscriptions above and the Message query just above
    already_ids = set(UserMessage.objects.filter(message_id__in=message_ids_to_use,
                                                 user_profile=user_profile).values_list("message_id",
                                                                                        flat=True))

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
# * subscribe the user to newsletter if newsletter_data is specified
def process_new_human_user(user_profile: UserProfile,
                           prereg_user: Optional[PreregistrationUser]=None,
                           newsletter_data: Optional[Mapping[str, str]]=None,
                           default_stream_groups: Sequence[DefaultStreamGroup]=[],
                           realm_creation: bool=False) -> None:
    realm = user_profile.realm

    mit_beta_user = realm.is_zephyr_mirror_realm
    if prereg_user is not None:
        prereg_user.status = confirmation_settings.STATUS_ACTIVE
        prereg_user.save(update_fields=['status'])
        streams = prereg_user.streams.all()
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

    bulk_add_subscriptions(realm, streams, [user_profile], acting_user=acting_user,
                           from_user_creation=True)

    add_new_user_history(user_profile, streams)

    # mit_beta_users don't have a referred_by field
    if not mit_beta_user and prereg_user is not None and prereg_user.referred_by is not None:
        # This is a cross-realm private message.
        with override_language(prereg_user.referred_by.default_language):
            internal_send_private_message(
                realm,
                get_system_bot(settings.NOTIFICATION_BOT),
                prereg_user.referred_by,
                _("{user} accepted your invitation to join Zulip!").format(user=f"{user_profile.full_name} <`{user_profile.email}`>")
            )
    # Mark any other PreregistrationUsers that are STATUS_ACTIVE as
    # inactive so we can keep track of the PreregistrationUser we
    # actually used for analytics
    if prereg_user is not None:
        PreregistrationUser.objects.filter(
            email__iexact=user_profile.delivery_email).exclude(id=prereg_user.id)\
            .update(status=confirmation_settings.STATUS_REVOKED)

        if prereg_user.referred_by is not None:
            notify_invites_changed(user_profile)
    else:
        PreregistrationUser.objects.filter(email__iexact=user_profile.delivery_email)\
            .update(status=confirmation_settings.STATUS_REVOKED)

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

    if newsletter_data is not None:
        # If the user was created automatically via the API, we may
        # not want to register them for the newsletter
        queue_json_publish(
            "signups",
            {
                'email_address': user_profile.delivery_email,
                'user_id': user_profile.id,
                'merge_fields': {
                    'NAME': user_profile.full_name,
                    'REALM_ID': user_profile.realm_id,
                    'OPTIN_IP': newsletter_data["IP"],
                    'OPTIN_TIME': datetime.datetime.isoformat(timezone_now().replace(microsecond=0)),
                },
            },
            lambda event: None)

def notify_created_user(user_profile: UserProfile) -> None:
    user_row = user_profile_to_user_row(user_profile)
    person = format_user_row(user_profile.realm, user_profile, user_row,
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
                             custom_profile_field_data={})
    event: Dict[str, Any] = dict(type="realm_user", op="add", person=person)
    send_event(user_profile.realm, event, active_user_ids(user_profile.realm_id))

def created_bot_event(user_profile: UserProfile) -> Dict[str, Any]:
    def stream_name(stream: Optional[Stream]) -> Optional[str]:
        if not stream:
            return None
        return stream.name

    default_sending_stream_name = stream_name(user_profile.default_sending_stream)
    default_events_register_stream_name = stream_name(user_profile.default_events_register_stream)

    bot = dict(email=user_profile.email,
               user_id=user_profile.id,
               full_name=user_profile.full_name,
               bot_type=user_profile.bot_type,
               is_active=user_profile.is_active,
               api_key=get_api_key(user_profile),
               default_sending_stream=default_sending_stream_name,
               default_events_register_stream=default_events_register_stream_name,
               default_all_public_streams=user_profile.default_all_public_streams,
               avatar_url=avatar_url(user_profile),
               services = get_service_dicts_for_bot(user_profile.id),
               )

    # Set the owner key only when the bot has an owner.
    # The default bots don't have an owner. So don't
    # set the owner key while reactivating them.
    if user_profile.bot_owner is not None:
        bot['owner_id'] = user_profile.bot_owner.id

    return dict(type="realm_bot", op="add", bot=bot)

def notify_created_bot(user_profile: UserProfile) -> None:
    event = created_bot_event(user_profile)
    send_event(user_profile.realm, event, bot_owner_user_ids(user_profile))

def create_users(realm: Realm, name_list: Iterable[Tuple[str, str]], bot_type: Optional[int]=None) -> None:
    user_set = set()
    for full_name, email in name_list:
        user_set.add((email, full_name, True))
    bulk_create_users(realm, user_set, bot_type)

def do_create_user(email: str, password: Optional[str], realm: Realm, full_name: str,
                   bot_type: Optional[int]=None, role: Optional[int]=None,
                   bot_owner: Optional[UserProfile]=None, tos_version: Optional[str]=None,
                   timezone: str="", avatar_source: str=UserProfile.AVATAR_FROM_GRAVATAR,
                   default_sending_stream: Optional[Stream]=None,
                   default_events_register_stream: Optional[Stream]=None,
                   default_all_public_streams: Optional[bool]=None,
                   prereg_user: Optional[PreregistrationUser]=None,
                   newsletter_data: Optional[Dict[str, str]]=None,
                   default_stream_groups: Sequence[DefaultStreamGroup]=[],
                   source_profile: Optional[UserProfile]=None,
                   realm_creation: bool=False,
                   acting_user: Optional[UserProfile]=None) -> UserProfile:

    user_profile = create_user(email=email, password=password, realm=realm,
                               full_name=full_name,
                               role=role, bot_type=bot_type, bot_owner=bot_owner,
                               tos_version=tos_version, timezone=timezone, avatar_source=avatar_source,
                               default_sending_stream=default_sending_stream,
                               default_events_register_stream=default_events_register_stream,
                               default_all_public_streams=default_all_public_streams,
                               source_profile=source_profile)

    event_time = user_profile.date_joined
    if not acting_user:
        acting_user = user_profile
    RealmAuditLog.objects.create(
        realm=user_profile.realm, acting_user=acting_user, modified_user=user_profile,
        event_type=RealmAuditLog.USER_CREATED, event_time=event_time,
        extra_data=orjson.dumps({
            RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(user_profile.realm),
        }).decode())
    do_increment_logging_stat(user_profile.realm, COUNT_STATS['active_users_log:is_bot:day'],
                              user_profile.is_bot, event_time)
    if settings.BILLING_ENABLED:
        update_license_ledger_if_needed(user_profile.realm, event_time)

    # Note that for bots, the caller will send an additional event
    # with bot-specific info like services.
    notify_created_user(user_profile)
    if bot_type is None:
        process_new_human_user(user_profile, prereg_user=prereg_user,
                               newsletter_data=newsletter_data,
                               default_stream_groups=default_stream_groups,
                               realm_creation=realm_creation)
    return user_profile

def do_activate_user(user_profile: UserProfile, acting_user: Optional[UserProfile]=None) -> None:
    user_profile.is_active = True
    user_profile.is_mirror_dummy = False
    user_profile.set_unusable_password()
    user_profile.date_joined = timezone_now()
    user_profile.tos_version = settings.TOS_VERSION
    user_profile.save(update_fields=["is_active", "date_joined", "password",
                                     "is_mirror_dummy", "tos_version"])

    event_time = user_profile.date_joined
    RealmAuditLog.objects.create(
        realm=user_profile.realm, modified_user=user_profile, acting_user=acting_user,
        event_type=RealmAuditLog.USER_ACTIVATED, event_time=event_time,
        extra_data=orjson.dumps({
            RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(user_profile.realm),
        }).decode())
    do_increment_logging_stat(user_profile.realm, COUNT_STATS['active_users_log:is_bot:day'],
                              user_profile.is_bot, event_time)
    if settings.BILLING_ENABLED:
        update_license_ledger_if_needed(user_profile.realm, event_time)

    notify_created_user(user_profile)

def do_reactivate_user(user_profile: UserProfile, acting_user: Optional[UserProfile]=None) -> None:
    # Unlike do_activate_user, this is meant for re-activating existing users,
    # so it doesn't reset their password, etc.
    user_profile.is_active = True
    user_profile.save(update_fields=["is_active"])

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=user_profile.realm, modified_user=user_profile, acting_user=acting_user,
        event_type=RealmAuditLog.USER_REACTIVATED, event_time=event_time,
        extra_data=orjson.dumps({
            RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(user_profile.realm),
        }).decode())
    do_increment_logging_stat(user_profile.realm, COUNT_STATS['active_users_log:is_bot:day'],
                              user_profile.is_bot, event_time)
    if settings.BILLING_ENABLED:
        update_license_ledger_if_needed(user_profile.realm, event_time)

    notify_created_user(user_profile)

    if user_profile.is_bot:
        notify_created_bot(user_profile)

def active_humans_in_realm(realm: Realm) -> Sequence[UserProfile]:
    return UserProfile.objects.filter(realm=realm, is_active=True, is_bot=False)


def do_set_realm_property(realm: Realm, name: str, value: Any,
                          acting_user: Optional[UserProfile] = None) -> None:
    """Takes in a realm object, the name of an attribute to update, the
       value to update and and the user who initiated the update.
    """
    property_type = Realm.property_types[name]
    assert isinstance(value, property_type), (
        f'Cannot update {name}: {value} is not an instance of {property_type}')

    old_value = getattr(realm, name)
    setattr(realm, name, value)
    realm.save(update_fields=[name])

    event = dict(
        type='realm',
        op='update',
        property=name,
        value=value,
    )
    send_event(realm, event, active_user_ids(realm.id))

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=realm, event_type=RealmAuditLog.REALM_PROPERTY_CHANGED, event_time=event_time,
        acting_user=acting_user, extra_data=orjson.dumps({
            RealmAuditLog.OLD_VALUE: old_value,
            RealmAuditLog.NEW_VALUE: value,
            'property': name,
        }).decode())

    if name == "email_address_visibility":
        if Realm.EMAIL_ADDRESS_VISIBILITY_EVERYONE not in [old_value, value]:
            # We use real email addresses on UserProfile.email only if
            # EMAIL_ADDRESS_VISIBILITY_EVERYONE is configured, so
            # changes between values that will not require changing
            # that field, so we can save work and return here.
            return

        user_profiles = UserProfile.objects.filter(realm=realm, is_bot=False)
        for user_profile in user_profiles:
            user_profile.email = get_display_email_address(user_profile, realm)
            # TODO: Design a bulk event for this or force-reload all clients
            send_user_email_update_event(user_profile)
        UserProfile.objects.bulk_update(user_profiles, ['email'])

        for user_profile in user_profiles:
            flush_user_profile(sender=UserProfile, instance=user_profile)

def do_set_realm_authentication_methods(realm: Realm,
                                        authentication_methods: Dict[str, bool],
                                        acting_user: Optional[UserProfile]=None) -> None:
    old_value = realm.authentication_methods_dict()
    for key, value in list(authentication_methods.items()):
        index = getattr(realm.authentication_methods, key).number
        realm.authentication_methods.set_bit(index, int(value))
    realm.save(update_fields=['authentication_methods'])
    updated_value = realm.authentication_methods_dict()
    RealmAuditLog.objects.create(
        realm=realm, event_type=RealmAuditLog.REALM_PROPERTY_CHANGED, event_time=timezone_now(),
        acting_user=acting_user, extra_data=orjson.dumps({
            RealmAuditLog.OLD_VALUE: old_value,
            RealmAuditLog.NEW_VALUE: updated_value,
            'property': 'authentication_methods',
        }).decode())
    event = dict(
        type="realm",
        op="update_dict",
        property='default',
        data=dict(authentication_methods=updated_value),
    )
    send_event(realm, event, active_user_ids(realm.id))

def do_set_realm_message_editing(realm: Realm,
                                 allow_message_editing: bool,
                                 message_content_edit_limit_seconds: int,
                                 allow_community_topic_editing: bool,
                                 acting_user: Optional[UserProfile]=None) -> None:
    old_values = dict(allow_message_editing=realm.allow_message_editing,
                      message_content_edit_limit_seconds=realm.message_content_edit_limit_seconds,
                      allow_community_topic_editing=realm.allow_community_topic_editing)

    realm.allow_message_editing = allow_message_editing
    realm.message_content_edit_limit_seconds = message_content_edit_limit_seconds
    realm.allow_community_topic_editing = allow_community_topic_editing

    event_time = timezone_now()
    updated_properties = dict(allow_message_editing=allow_message_editing,
                              message_content_edit_limit_seconds=message_content_edit_limit_seconds,
                              allow_community_topic_editing=allow_community_topic_editing)

    for updated_property, updated_value in updated_properties.items():
        if updated_value == old_values[updated_property]:
            continue
        RealmAuditLog.objects.create(
            realm=realm, event_type=RealmAuditLog.REALM_PROPERTY_CHANGED, event_time=event_time,
            acting_user=acting_user, extra_data=orjson.dumps({
                RealmAuditLog.OLD_VALUE: old_values[updated_property],
                RealmAuditLog.NEW_VALUE: updated_value,
                'property': updated_property,
            }).decode())

    realm.save(update_fields=list(updated_properties.keys()))
    event = dict(
        type="realm",
        op="update_dict",
        property="default",
        data=updated_properties,
    )
    send_event(realm, event, active_user_ids(realm.id))

def do_set_realm_notifications_stream(realm: Realm, stream: Optional[Stream], stream_id: int,
                                      acting_user: Optional[UserProfile]=None) -> None:
    old_value = realm.notifications_stream_id
    realm.notifications_stream = stream
    realm.save(update_fields=['notifications_stream'])

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=realm, event_type=RealmAuditLog.REALM_PROPERTY_CHANGED, event_time=event_time,
        acting_user=acting_user, extra_data=orjson.dumps({
            RealmAuditLog.OLD_VALUE: old_value,
            RealmAuditLog.NEW_VALUE: stream_id,
            'property': 'notifications_stream',
        }).decode())

    event = dict(
        type="realm",
        op="update",
        property="notifications_stream_id",
        value=stream_id,
    )
    send_event(realm, event, active_user_ids(realm.id))

def do_set_realm_signup_notifications_stream(realm: Realm, stream: Optional[Stream], stream_id: int,
                                             acting_user: Optional[UserProfile]=None) -> None:
    old_value = realm.signup_notifications_stream_id
    realm.signup_notifications_stream = stream
    realm.save(update_fields=['signup_notifications_stream'])

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=realm, event_type=RealmAuditLog.REALM_PROPERTY_CHANGED, event_time=event_time,
        acting_user=acting_user, extra_data=orjson.dumps({
            RealmAuditLog.OLD_VALUE: old_value,
            RealmAuditLog.NEW_VALUE: stream_id,
            'property': 'signup_notifications_stream',
        }).decode())
    event = dict(
        type="realm",
        op="update",
        property="signup_notifications_stream_id",
        value=stream_id,
    )
    send_event(realm, event, active_user_ids(realm.id))

def do_deactivate_realm(realm: Realm, acting_user: Optional[UserProfile]=None) -> None:
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
        realm=realm, event_type=RealmAuditLog.REALM_DEACTIVATED, event_time=event_time,
        acting_user=acting_user, extra_data=orjson.dumps({
            RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(realm),
        }).decode())

    ScheduledEmail.objects.filter(realm=realm).delete()
    for user in active_humans_in_realm(realm):
        # Don't deactivate the users, but do delete their sessions so they get
        # bumped to the login screen, where they'll get a realm deactivation
        # notice when they try to log in.
        delete_user_sessions(user)

    event = dict(type="realm", op="deactivated",
                 realm_id=realm.id)
    send_event(realm, event, active_user_ids(realm.id))

def do_reactivate_realm(realm: Realm) -> None:
    realm.deactivated = False
    realm.save(update_fields=["deactivated"])

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=realm, event_type=RealmAuditLog.REALM_REACTIVATED, event_time=event_time,
        extra_data=orjson.dumps({
            RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(realm),
        }).decode())

def do_change_realm_subdomain(realm: Realm, new_subdomain: str) -> None:
    realm.string_id = new_subdomain
    realm.save(update_fields=["string_id"])

def do_scrub_realm(realm: Realm, acting_user: Optional[UserProfile]=None) -> None:
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

    RealmAuditLog.objects.create(realm=realm, event_time=timezone_now(),
                                 acting_user=acting_user,
                                 event_type=RealmAuditLog.REALM_SCRUBBED)

def do_deactivate_user(user_profile: UserProfile,
                       acting_user: Optional[UserProfile]=None,
                       _cascade: bool=True) -> None:
    if not user_profile.is_active:
        return

    if user_profile.realm.is_zephyr_mirror_realm:  # nocoverage
        # For zephyr mirror users, we need to make them a mirror dummy
        # again; otherwise, other users won't get the correct behavior
        # when trying to send messages to this person inside Zulip.
        #
        # Ideally, we need to also ensure their zephyr mirroring bot
        # isn't running, but that's a separate issue.
        user_profile.is_mirror_dummy = True
    user_profile.is_active = False
    user_profile.save(update_fields=["is_active"])

    delete_user_sessions(user_profile)
    clear_scheduled_emails([user_profile.id])

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=user_profile.realm, modified_user=user_profile, acting_user=acting_user,
        event_type=RealmAuditLog.USER_DEACTIVATED, event_time=event_time,
        extra_data=orjson.dumps({
            RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(user_profile.realm),
        }).decode())
    do_increment_logging_stat(user_profile.realm, COUNT_STATS['active_users_log:is_bot:day'],
                              user_profile.is_bot, event_time, increment=-1)
    if settings.BILLING_ENABLED:
        update_license_ledger_if_needed(user_profile.realm, event_time)

    event = dict(type="realm_user", op="remove",
                 person=dict(user_id=user_profile.id,
                             full_name=user_profile.full_name))
    send_event(user_profile.realm, event, active_user_ids(user_profile.realm_id))

    if user_profile.is_bot:
        event = dict(type="realm_bot", op="remove",
                     bot=dict(user_id=user_profile.id,
                              full_name=user_profile.full_name))
        send_event(user_profile.realm, event, bot_owner_user_ids(user_profile))

    if _cascade:
        bot_profiles = UserProfile.objects.filter(is_bot=True, is_active=True,
                                                  bot_owner=user_profile)
        for profile in bot_profiles:
            do_deactivate_user(profile, acting_user=acting_user, _cascade=False)

def do_deactivate_stream(stream: Stream, log: bool=True, acting_user: Optional[UserProfile]=None) -> None:
    # We want to mark all messages in the to-be-deactivated stream as
    # read for all users; otherwise they will pollute queries like
    # "Get the user's first unread message".  Since this can be an
    # expensive operation, we do it via the deferred_work queue
    # processor.
    deferred_work_event = {
        "type": "mark_stream_messages_as_read_for_everyone",
        "stream_recipient_id": stream.recipient_id
    }
    queue_json_publish("deferred_work", deferred_work_event)

    # Get the affected user ids *before* we deactivate everybody.
    affected_user_ids = can_access_stream_user_ids(stream)

    get_active_subscriptions_for_stream_id(stream.id).update(active=False)

    was_invite_only = stream.invite_only
    stream.deactivated = True
    stream.invite_only = True
    # Preserve as much as possible the original stream name while giving it a
    # special prefix that both indicates that the stream is deactivated and
    # frees up the original name for reuse.
    old_name = stream.name
    new_name = ("!DEACTIVATED:" + old_name)[:Stream.MAX_NAME_LENGTH]
    for i in range(20):
        if stream_name_in_use(new_name, stream.realm_id):
            # This stream has already been deactivated, keep prepending !s until
            # we have a unique stream name or you've hit a rename limit.
            new_name = ("!" + new_name)[:Stream.MAX_NAME_LENGTH]
        else:
            break

    # If you don't have a unique name at this point, this will fail later in the
    # code path.

    stream.name = new_name[:Stream.MAX_NAME_LENGTH]
    stream.save(update_fields=['name', 'deactivated', 'invite_only'])

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
    event = dict(type="stream", op="delete",
                 streams=[stream_dict])
    send_event(stream.realm, event, affected_user_ids)

    event_time = timezone_now()
    RealmAuditLog.objects.create(realm=stream.realm, acting_user=acting_user,
                                 modified_stream=stream, event_type=RealmAuditLog.STREAM_DEACTIVATED,
                                 event_time=event_time)

def send_user_email_update_event(user_profile: UserProfile) -> None:
    payload = dict(user_id=user_profile.id,
                   new_email=user_profile.email)
    send_event(user_profile.realm,
               dict(type='realm_user', op='update', person=payload),
               active_user_ids(user_profile.realm_id))

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
    payload = dict(user_id=user_profile.id,
                   delivery_email=new_email)
    event = dict(type='realm_user', op='update', person=payload)
    send_event(user_profile.realm, event, [user_profile.id])

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
    RealmAuditLog.objects.create(realm=user_profile.realm, acting_user=user_profile,
                                 modified_user=user_profile, event_type=RealmAuditLog.USER_EMAIL_CHANGED,
                                 event_time=event_time)

def do_start_email_change_process(user_profile: UserProfile, new_email: str) -> None:
    old_email = user_profile.delivery_email
    obj = EmailChangeStatus.objects.create(new_email=new_email, old_email=old_email,
                                           user_profile=user_profile, realm=user_profile.realm)

    activation_url = create_confirmation_link(obj, Confirmation.EMAIL_CHANGE)
    from zerver.context_processors import common_context
    context = common_context(user_profile)
    context.update(
        old_email=old_email,
        new_email=new_email,
        activate_url=activation_url,
    )
    language = user_profile.default_language
    send_email('zerver/emails/confirm_new_email', to_emails=[new_email],
               from_name=FromAddress.security_email_from_name(language=language),
               from_address=FromAddress.tokenized_no_reply_address(),
               language=language, context=context,
               realm=user_profile.realm)

def compute_irc_user_fullname(email: str) -> str:
    return email.split("@")[0] + " (IRC)"

def compute_jabber_user_fullname(email: str) -> str:
    return email.split("@")[0] + " (XMPP)"

@cache_with_key(lambda realm, email, f: user_profile_by_email_cache_key(email),
                timeout=3600*24*7)
def create_mirror_user_if_needed(realm: Realm, email: str,
                                 email_to_fullname: Callable[[str], str]) -> UserProfile:
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

def render_incoming_message(message: Message,
                            content: str,
                            user_ids: Set[int],
                            realm: Realm,
                            mention_data: Optional[MentionData]=None,
                            email_gateway: bool=False) -> str:
    realm_alert_words_automaton = get_alert_word_automaton(realm)
    try:
        rendered_content = render_markdown(
            message=message,
            content=content,
            realm=realm,
            realm_alert_words_automaton = realm_alert_words_automaton,
            mention_data=mention_data,
            email_gateway=email_gateway,
        )
    except MarkdownRenderingException:
        raise JsonableError(_('Unable to render message'))
    return rendered_content

class RecipientInfoResult(TypedDict):
    active_user_ids: Set[int]
    push_notify_user_ids: Set[int]
    stream_email_user_ids: Set[int]
    stream_push_user_ids: Set[int]
    wildcard_mention_user_ids: Set[int]
    um_eligible_user_ids: Set[int]
    long_term_idle_user_ids: Set[int]
    default_bot_user_ids: Set[int]
    service_bot_tuples: List[Tuple[int, int]]

def get_recipient_info(recipient: Recipient,
                       sender_id: int,
                       stream_topic: Optional[StreamTopicTarget],
                       possibly_mentioned_user_ids: AbstractSet[int]=set(),
                       possible_wildcard_mention: bool=True) -> RecipientInfoResult:
    stream_push_user_ids: Set[int] = set()
    stream_email_user_ids: Set[int] = set()
    wildcard_mention_user_ids: Set[int] = set()

    if recipient.type == Recipient.PERSONAL:
        # The sender and recipient may be the same id, so
        # de-duplicate using a set.
        message_to_user_ids = list({recipient.type_id, sender_id})
        assert(len(message_to_user_ids) in [1, 2])

    elif recipient.type == Recipient.STREAM:
        # Anybody calling us w/r/t a stream message needs to supply
        # stream_topic.  We may eventually want to have different versions
        # of this function for different message types.
        assert(stream_topic is not None)
        user_ids_muting_topic = stream_topic.user_ids_muting_topic()

        subscription_rows = stream_topic.get_active_subscriptions().annotate(
            user_profile_email_notifications=F('user_profile__enable_stream_email_notifications'),
            user_profile_push_notifications=F('user_profile__enable_stream_push_notifications'),
            user_profile_wildcard_mentions_notify=F(
                'user_profile__wildcard_mentions_notify'),
        ).values(
            'user_profile_id',
            'push_notifications',
            'email_notifications',
            'wildcard_mentions_notify',
            'user_profile_email_notifications',
            'user_profile_push_notifications',
            'user_profile_wildcard_mentions_notify',
            'is_muted',
        ).order_by('user_profile_id')

        message_to_user_ids = [
            row['user_profile_id']
            for row in subscription_rows
        ]

        def should_send(setting: str, row: Dict[str, Any]) -> bool:
            # This implements the structure that the UserProfile stream notification settings
            # are defaults, which can be overridden by the stream-level settings (if those
            # values are not null).
            if row['is_muted']:
                return False
            if row['user_profile_id'] in user_ids_muting_topic:
                return False
            if row[setting] is not None:
                return row[setting]
            return row['user_profile_' + setting]

        stream_push_user_ids = {
            row['user_profile_id']
            for row in subscription_rows
            # Note: muting a stream overrides stream_push_notify
            if should_send('push_notifications', row)
        }

        stream_email_user_ids = {
            row['user_profile_id']
            for row in subscription_rows
            # Note: muting a stream overrides stream_email_notify
            if should_send('email_notifications', row)
        }

        if possible_wildcard_mention:
            # If there's a possible wildcard mention, we need to
            # determine which users would receive a wildcard mention
            # notification for this message should the message indeed
            # contain a wildcard mention.
            #
            # We don't have separate values for push/email
            # notifications here; at this stage, we're just
            # determining whether this wildcard mention should be
            # treated as a mention (and follow the user's mention
            # notification preferences) or a normal message.
            wildcard_mention_user_ids = {
                row['user_profile_id']
                for row in subscription_rows
                if should_send("wildcard_mentions_notify", row)
            }

    elif recipient.type == Recipient.HUDDLE:
        message_to_user_ids = get_huddle_user_ids(recipient)

    else:
        raise ValueError('Bad recipient type')

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
        query = UserProfile.objects.filter(
            is_active=True
        ).values(
            'id',
            'enable_online_push_notifications',
            'is_bot',
            'bot_type',
            'long_term_idle',
        )

        # query_for_ids is fast highly optimized for large queries, and we
        # need this codepath to be fast (it's part of sending messages)
        query = query_for_ids(
            query=query,
            user_ids=sorted(user_ids),
            field='id',
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
        return {
            row['id']
            for row in rows
            if f(row)
        } & message_to_user_id_set

    def is_service_bot(row: Dict[str, Any]) -> bool:
        return row['is_bot'] and (row['bot_type'] in UserProfile.SERVICE_BOT_TYPES)

    active_user_ids = get_ids_for(lambda r: True)
    push_notify_user_ids = get_ids_for(
        lambda r: r['enable_online_push_notifications'],
    )

    # Service bots don't get UserMessage rows.
    um_eligible_user_ids = get_ids_for(
        lambda r: not is_service_bot(r),
    )

    long_term_idle_user_ids = get_ids_for(
        lambda r: r['long_term_idle'],
    )

    # These two bot data structures need to filter from the full set
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
        row['id']
        for row in rows
        if row['is_bot'] and row['bot_type'] == UserProfile.DEFAULT_BOT
    }

    service_bot_tuples = [
        (row['id'], row['bot_type'])
        for row in rows
        if is_service_bot(row)
    ]

    info: RecipientInfoResult = dict(
        active_user_ids=active_user_ids,
        push_notify_user_ids=push_notify_user_ids,
        stream_push_user_ids=stream_push_user_ids,
        stream_email_user_ids=stream_email_user_ids,
        wildcard_mention_user_ids=wildcard_mention_user_ids,
        um_eligible_user_ids=um_eligible_user_ids,
        long_term_idle_user_ids=long_term_idle_user_ids,
        default_bot_user_ids=default_bot_user_ids,
        service_bot_tuples=service_bot_tuples,
    )
    return info

def get_service_bot_events(sender: UserProfile, service_bot_tuples: List[Tuple[int, int]],
                           mentioned_user_ids: Set[int], active_user_ids: Set[int],
                           recipient_type: int) -> Dict[str, List[Dict[str, Any]]]:

    event_dict: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    # Avoid infinite loops by preventing messages sent by bots from generating
    # Service events.
    if sender.is_bot:
        return event_dict

    def maybe_add_event(user_profile_id: int, bot_type: int) -> None:
        if bot_type == UserProfile.OUTGOING_WEBHOOK_BOT:
            queue_name = 'outgoing_webhooks'
        elif bot_type == UserProfile.EMBEDDED_BOT:
            queue_name = 'embedded_bots'
        else:
            logging.error(
                'Unexpected bot_type for Service bot id=%s: %s',
                user_profile_id, bot_type,
            )
            return

        is_stream = (recipient_type == Recipient.STREAM)

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
            trigger = 'mention'
        # PM triggers for personal and huddle messages
        elif (not is_stream) and (user_profile_id in active_user_ids):
            trigger = 'private_message'
        else:
            return

        event_dict[queue_name].append({
            'trigger': trigger,
            'user_profile_id': user_profile_id,
        })

    for user_profile_id, bot_type in service_bot_tuples:
        maybe_add_event(
            user_profile_id=user_profile_id,
            bot_type=bot_type,
        )

    return event_dict

def do_schedule_messages(messages: Sequence[Mapping[str, Any]]) -> List[int]:
    scheduled_messages: List[ScheduledMessage] = []

    for message in messages:
        scheduled_message = ScheduledMessage()
        scheduled_message.sender = message['message'].sender
        scheduled_message.recipient = message['message'].recipient
        topic_name = message['message'].topic_name()
        scheduled_message.set_topic_name(topic_name=topic_name)
        scheduled_message.content = message['message'].content
        scheduled_message.sending_client = message['message'].sending_client
        scheduled_message.stream = message['stream']
        scheduled_message.realm = message['realm']
        scheduled_message.scheduled_timestamp = message['deliver_at']
        if message['delivery_type'] == 'send_later':
            scheduled_message.delivery_type = ScheduledMessage.SEND_LATER
        elif message['delivery_type'] == 'remind':
            scheduled_message.delivery_type = ScheduledMessage.REMIND

        scheduled_messages.append(scheduled_message)

    ScheduledMessage.objects.bulk_create(scheduled_messages)
    return [scheduled_message.id for scheduled_message in scheduled_messages]


def build_message_send_dict(message_dict: Dict[str, Any],
                            email_gateway: bool=False) -> Dict[str, Any]:
    """Returns a dictionary that can be passed into do_send_messages.  In
    production, this is always called by check_message, but some
    testing code paths call it directly.
    """
    message_dict['stream'] = message_dict.get('stream', None)
    message_dict['local_id'] = message_dict.get('local_id', None)
    message_dict['sender_queue_id'] = message_dict.get('sender_queue_id', None)
    message_dict['realm'] = message_dict.get('realm', message_dict['message'].sender.realm)

    mention_data = MentionData(
        realm_id=message_dict['realm'].id,
        content=message_dict['message'].content,
    )
    message_dict['mention_data'] = mention_data

    if message_dict['message'].is_stream_message():
        stream_id = message_dict['message'].recipient.type_id
        stream_topic: Optional[StreamTopicTarget] = StreamTopicTarget(
            stream_id=stream_id,
            topic_name=message_dict['message'].topic_name(),
        )
    else:
        stream_topic = None

    info = get_recipient_info(
        recipient=message_dict['message'].recipient,
        sender_id=message_dict['message'].sender_id,
        stream_topic=stream_topic,
        possibly_mentioned_user_ids=mention_data.get_user_ids(),
        possible_wildcard_mention=mention_data.message_has_wildcards(),
    )

    message_dict['active_user_ids'] = info['active_user_ids']
    message_dict['push_notify_user_ids'] = info['push_notify_user_ids']
    message_dict['stream_push_user_ids'] = info['stream_push_user_ids']
    message_dict['stream_email_user_ids'] = info['stream_email_user_ids']
    message_dict['um_eligible_user_ids'] = info['um_eligible_user_ids']
    message_dict['long_term_idle_user_ids'] = info['long_term_idle_user_ids']
    message_dict['default_bot_user_ids'] = info['default_bot_user_ids']
    message_dict['service_bot_tuples'] = info['service_bot_tuples']

    # Render our message_dicts.
    assert message_dict['message'].rendered_content is None

    rendered_content = render_incoming_message(
        message_dict['message'],
        message_dict['message'].content,
        message_dict['active_user_ids'],
        message_dict['realm'],
        mention_data=message_dict['mention_data'],
        email_gateway=email_gateway,
    )
    message_dict['message'].rendered_content = rendered_content
    message_dict['message'].rendered_content_version = markdown_version
    message_dict['links_for_embed'] = message_dict['message'].links_for_preview

    # Add members of the mentioned user groups into `mentions_user_ids`.
    for group_id in message_dict['message'].mentions_user_group_ids:
        members = message_dict['mention_data'].get_group_members(group_id)
        message_dict['message'].mentions_user_ids.update(members)

    # Only send data to Tornado about wildcard mentions if message
    # rendering determined the message had an actual wildcard
    # mention in it (and not e.g. wildcard mention syntax inside a
    # code block).
    if message_dict['message'].mentions_wildcard:
        message_dict['wildcard_mention_user_ids'] = info['wildcard_mention_user_ids']
    else:
        message_dict['wildcard_mention_user_ids'] = []

    '''
    Once we have the actual list of mentioned ids from message
    rendering, we can patch in "default bots" (aka normal bots)
    who were directly mentioned in this message as eligible to
    get UserMessage rows.
    '''
    mentioned_user_ids = message_dict['message'].mentions_user_ids
    default_bot_user_ids = message_dict['default_bot_user_ids']
    mentioned_bot_user_ids = default_bot_user_ids & mentioned_user_ids
    message_dict['um_eligible_user_ids'] |= mentioned_bot_user_ids

    return message_dict

def do_send_messages(messages_maybe_none: Sequence[Optional[MutableMapping[str, Any]]],
                     email_gateway: bool=False,
                     mark_as_read: Sequence[int]=[]) -> List[int]:
    """See
    https://zulip.readthedocs.io/en/latest/subsystems/sending-messages.html
    for high-level documentation on this subsystem.
    """

    # Filter out messages which didn't pass internal_prep_message properly
    messages = [message for message in messages_maybe_none if message is not None]

    # Filter out zephyr mirror anomalies where the message was already sent
    already_sent_ids: List[int] = []
    new_messages: List[MutableMapping[str, Any]] = []
    for message in messages:
        if isinstance(message['message'], int):
            already_sent_ids.append(message['message'])
        else:
            new_messages.append(message)
    messages = new_messages

    # Save the message receipts in the database
    user_message_flags: Dict[int, Dict[int, List[str]]] = defaultdict(dict)
    with transaction.atomic():
        Message.objects.bulk_create(message['message'] for message in messages)

        # Claim attachments in message
        for message in messages:
            if do_claim_attachments(message['message'],
                                    message['message'].potential_attachment_path_ids):
                message['message'].has_attachment = True
                message['message'].save(update_fields=['has_attachment'])

        ums: List[UserMessageLite] = []
        for message in messages:
            # Service bots (outgoing webhook bots and embedded bots) don't store UserMessage rows;
            # they will be processed later.
            mentioned_user_ids = message['message'].mentions_user_ids
            user_messages = create_user_messages(
                message=message['message'],
                um_eligible_user_ids=message['um_eligible_user_ids'],
                long_term_idle_user_ids=message['long_term_idle_user_ids'],
                stream_push_user_ids = message['stream_push_user_ids'],
                stream_email_user_ids = message['stream_email_user_ids'],
                mentioned_user_ids=mentioned_user_ids,
                mark_as_read=mark_as_read,
            )

            for um in user_messages:
                user_message_flags[message['message'].id][um.user_profile_id] = um.flags_list()

            ums.extend(user_messages)

            message['message'].service_queue_events = get_service_bot_events(
                sender=message['message'].sender,
                service_bot_tuples=message['service_bot_tuples'],
                mentioned_user_ids=mentioned_user_ids,
                active_user_ids=message['active_user_ids'],
                recipient_type=message['message'].recipient.type,
            )

        bulk_insert_ums(ums)

        for message in messages:
            do_widget_post_save_actions(message)

    # This next loop is responsible for notifying other parts of the
    # Zulip system about the messages we just committed to the database:
    # * Notifying clients via send_event
    # * Triggering outgoing webhooks via the service event queue.
    # * Updating the `first_message_id` field for streams without any message history.
    # * Implementing the Welcome Bot reply hack
    # * Adding links to the embed_links queue for open graph processing.
    for message in messages:
        realm_id: Optional[int] = None
        if message['message'].is_stream_message():
            if message['stream'] is None:
                stream_id = message['message'].recipient.type_id
                message['stream'] = Stream.objects.select_related().get(id=stream_id)
            # assert needed because stubs for django are missing
            assert message['stream'] is not None
            realm_id = message['stream'].realm_id

        # Deliver events to the real-time push system, as well as
        # enqueuing any additional processing triggered by the message.
        wide_message_dict = MessageDict.wide_dict(message['message'], realm_id)

        user_flags = user_message_flags.get(message['message'].id, {})
        sender = message['message'].sender
        message_type = wide_message_dict['type']

        presence_idle_user_ids = get_active_presence_idle_user_ids(
            realm=sender.realm,
            sender_id=sender.id,
            message_type=message_type,
            active_user_ids=message['active_user_ids'],
            user_flags=user_flags,
        )

        event = dict(
            type='message',
            message=message['message'].id,
            message_dict=wide_message_dict,
            presence_idle_user_ids=presence_idle_user_ids,
        )

        '''
        TODO:  We may want to limit user_ids to only those users who have
               UserMessage rows, if only for minor performance reasons.

               For now we queue events for all subscribers/sendees of the
               message, since downstream code may still do notifications
               that don't require UserMessage rows.

               Our automated tests have gotten better on this codepath,
               but we may have coverage gaps, so we should be careful
               about changing the next line.
        '''
        user_ids = message['active_user_ids'] | set(user_flags.keys())

        users = [
            dict(
                id=user_id,
                flags=user_flags.get(user_id, []),
                always_push_notify=(user_id in message['push_notify_user_ids']),
                stream_push_notify=(user_id in message['stream_push_user_ids']),
                stream_email_notify=(user_id in message['stream_email_user_ids']),
                wildcard_mention_notify=(user_id in message['wildcard_mention_user_ids']),
            )
            for user_id in user_ids
        ]

        if message['message'].is_stream_message():
            # Note: This is where authorization for single-stream
            # get_updates happens! We only attach stream data to the
            # notify new_message request if it's a public stream,
            # ensuring that in the tornado server, non-public stream
            # messages are only associated to their subscribed users.

            # assert needed because stubs for django are missing
            assert message['stream'] is not None
            if message['stream'].is_public():
                event['realm_id'] = message['stream'].realm_id
                event['stream_name'] = message['stream'].name
            if message['stream'].invite_only:
                event['invite_only'] = True
            if message['stream'].first_message_id is None:
                message['stream'].first_message_id = message['message'].id
                message['stream'].save(update_fields=["first_message_id"])
        if message['local_id'] is not None:
            event['local_id'] = message['local_id']
        if message['sender_queue_id'] is not None:
            event['sender_queue_id'] = message['sender_queue_id']
        send_event(message['realm'], event, users)

        if message['links_for_embed']:
            event_data = {
                'message_id': message['message'].id,
                'message_content': message['message'].content,
                'message_realm_id': message['realm'].id,
                'urls': list(message['links_for_embed'])}
            queue_json_publish('embed_links', event_data)

        if message['message'].recipient.type == Recipient.PERSONAL:
            welcome_bot_id = get_system_bot(settings.WELCOME_BOT).id
            if (welcome_bot_id in message['active_user_ids'] and
                    welcome_bot_id != message['message'].sender_id):
                from zerver.lib.onboarding import send_welcome_bot_response
                send_welcome_bot_response(message)

        for queue_name, events in message['message'].service_queue_events.items():
            for event in events:
                queue_json_publish(
                    queue_name,
                    {
                        "message": wide_message_dict,
                        "trigger": event['trigger'],
                        "user_profile_id": event["user_profile_id"],
                    },
                )

    # Note that this does not preserve the order of message ids
    # returned.  In practice, this shouldn't matter, as we only
    # mirror single zephyr messages at a time and don't otherwise
    # intermingle sending zephyr messages with other messages.
    return already_sent_ids + [message['message'].id for message in messages]

class UserMessageLite:
    '''
    The Django ORM is too slow for bulk operations.  This class
    is optimized for the simple use case of inserting a bunch of
    rows into zerver_usermessage.
    '''

    def __init__(self, user_profile_id: int, message_id: int, flags: int) -> None:
        self.user_profile_id = user_profile_id
        self.message_id = message_id
        self.flags = flags

    def flags_list(self) -> List[str]:
        return UserMessage.flags_list_for_flags(self.flags)

def create_user_messages(message: Message,
                         um_eligible_user_ids: AbstractSet[int],
                         long_term_idle_user_ids: AbstractSet[int],
                         stream_push_user_ids: AbstractSet[int],
                         stream_email_user_ids: AbstractSet[int],
                         mentioned_user_ids: AbstractSet[int],
                         mark_as_read: Sequence[int] = []) -> List[UserMessageLite]:
    ums_to_create = []
    for user_profile_id in um_eligible_user_ids:
        um = UserMessageLite(
            user_profile_id=user_profile_id,
            message_id=message.id,
            flags=0,
        )
        ums_to_create.append(um)

    # These properties on the Message are set via
    # render_markdown by code in the Markdown inline patterns
    wildcard = message.mentions_wildcard
    ids_with_alert_words = message.user_ids_with_alert_words

    for um in ums_to_create:
        if (um.user_profile_id == message.sender.id and
                message.sent_by_human()) or \
           um.user_profile_id in mark_as_read:
            um.flags |= UserMessage.flags.read
        if wildcard:
            um.flags |= UserMessage.flags.wildcard_mentioned
        if um.user_profile_id in mentioned_user_ids:
            um.flags |= UserMessage.flags.mentioned
        if um.user_profile_id in ids_with_alert_words:
            um.flags |= UserMessage.flags.has_alert_word
        if message.recipient.type in [Recipient.HUDDLE, Recipient.PERSONAL]:
            um.flags |= UserMessage.flags.is_private

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
    for um in ums_to_create:
        if (um.user_profile_id in long_term_idle_user_ids and
                um.user_profile_id not in stream_push_user_ids and
                um.user_profile_id not in stream_email_user_ids and
                message.is_stream_message() and
                int(um.flags) == 0):
            continue
        user_messages.append(um)

    return user_messages

def bulk_insert_ums(ums: List[UserMessageLite]) -> None:
    '''
    Doing bulk inserts this way is much faster than using Django,
    since we don't have any ORM overhead.  Profiling with 1000
    users shows a speedup of 0.436 -> 0.027 seconds, so we're
    talking about a 15x speedup.
    '''
    if not ums:
        return

    vals = [
        (um.user_profile_id, um.message_id, um.flags)
        for um in ums
    ]
    query = SQL('''
        INSERT into
            zerver_usermessage (user_profile_id, message_id, flags)
        VALUES %s
    ''')

    with connection.cursor() as cursor:
        execute_values(cursor.cursor, query, vals)

def do_add_submessage(realm: Realm,
                      sender_id: int,
                      message_id: int,
                      msg_type: str,
                      content: str,
                      ) -> None:
    submessage = SubMessage(
        sender_id=sender_id,
        message_id=message_id,
        msg_type=msg_type,
        content=content,
    )
    submessage.save()

    event = dict(
        type="submessage",
        msg_type=msg_type,
        message_id=message_id,
        submessage_id=submessage.id,
        sender_id=sender_id,
        content=content,
    )
    ums = UserMessage.objects.filter(message_id=message_id)
    target_user_ids = [um.user_profile_id for um in ums]

    send_event(realm, event, target_user_ids)

def notify_reaction_update(user_profile: UserProfile, message: Message,
                           reaction: Reaction, op: str) -> None:
    user_dict = {'user_id': user_profile.id,
                 'email': user_profile.email,
                 'full_name': user_profile.full_name}

    event: Dict[str, Any] = {
        'type': 'reaction',
        'op': op,
        'user_id': user_profile.id,
        # TODO: We plan to remove this redundant user_dict object once
        # clients are updated to support accessing use user_id.  See
        # https://github.com/zulip/zulip/pull/14711 for details.
        'user': user_dict,
        'message_id': message.id,
        'emoji_name': reaction.emoji_name,
        'emoji_code': reaction.emoji_code,
        'reaction_type': reaction.reaction_type,
    }

    # Update the cached message since new reaction is added.
    update_to_dict_cache([message])

    # Recipients for message update events, including reactions, are
    # everyone who got the original message.  This means reactions
    # won't live-update in preview narrows, but it's the right
    # performance tradeoff, since otherwise we'd need to send all
    # reactions to public stream messages to every browser for every
    # client in the organization, which doesn't scale.
    #
    # However, to ensure that reactions do live-update for any user
    # who has actually participated in reacting to a message, we add a
    # "historical" UserMessage row for any user who reacts to message,
    # subscribing them to future notifications.
    ums = UserMessage.objects.filter(message=message.id)
    send_event(user_profile.realm, event, [um.user_profile_id for um in ums])

def do_add_reaction(user_profile: UserProfile, message: Message,
                    emoji_name: str, emoji_code: str, reaction_type: str) -> None:
    reaction = Reaction(user_profile=user_profile, message=message,
                        emoji_name=emoji_name, emoji_code=emoji_code,
                        reaction_type=reaction_type)
    try:
        reaction.save()
    except django.db.utils.IntegrityError:  # nocoverage
        # This can happen when a race results in the check in views
        # code not catching an attempt to double-add a reaction, or
        # perhaps if the emoji_name/emoji_code mapping is busted.
        raise JsonableError(_("Reaction already exists."))

    notify_reaction_update(user_profile, message, reaction, "add")

def do_remove_reaction(user_profile: UserProfile, message: Message,
                       emoji_code: str, reaction_type: str) -> None:
    reaction = Reaction.objects.filter(user_profile=user_profile,
                                       message=message,
                                       emoji_code=emoji_code,
                                       reaction_type=reaction_type).get()
    reaction.delete()
    notify_reaction_update(user_profile, message, reaction, "remove")

def do_send_typing_notification(
        realm: Realm,
        sender: UserProfile,
        recipient_user_profiles: List[UserProfile],
        operator: str) -> None:

    sender_dict = {'user_id': sender.id, 'email': sender.email}

    # Include a list of recipients in the event body to help identify where the typing is happening
    recipient_dicts = [{'user_id': profile.id, 'email': profile.email}
                       for profile in recipient_user_profiles]
    event = dict(
        type='typing',
        op=operator,
        sender=sender_dict,
        recipients=recipient_dicts,
    )

    # Only deliver the notification to active user recipients
    user_ids_to_notify = [
        user.id
        for user in recipient_user_profiles
        if user.is_active
    ]

    send_event(realm, event, user_ids_to_notify)

# check_send_typing_notification:
# Checks the typing notification and sends it
def check_send_typing_notification(sender: UserProfile,
                                   user_ids: List[int],
                                   operator: str) -> None:

    realm = sender.realm
    if len(user_ids) == 0:
        raise JsonableError(_('Missing parameter: \'to\' (recipient)'))
    elif operator not in ('start', 'stop'):
        raise JsonableError(_('Invalid \'op\' value (should be start or stop)'))

    ''' The next chunk of code will go away when we upgrade old mobile
    users away from versions of mobile that send emails.  For the
    small number of very outdated mobile clients, we do double work
    here in terms of fetching users, but this structure reduces lots
    of other unnecessary duplicated code and will make it convenient
    to mostly delete code when we desupport old versions of the
    app.'''

    if sender.id not in user_ids:
        user_ids.append(sender.id)

    # If any of the user_ids being sent in are invalid, we will
    # just reject the whole request, since a partial list of user_ids
    # can create confusion related to huddles.  Plus it's a good
    # sign that a client is confused (or possibly even malicious) if
    # we get bad user_ids.
    user_profiles = []
    for user_id in user_ids:
        try:
            # We include cross-bot realms as possible recipients,
            # so that clients can know which huddle conversation
            # is relevant here.
            user_profile = get_user_by_id_in_realm_including_cross_realm(
                user_id, sender.realm)
        except UserProfile.DoesNotExist:
            raise JsonableError(_("Invalid user ID {}").format(user_id))
        user_profiles.append(user_profile)

    do_send_typing_notification(
        realm=realm,
        sender=sender,
        recipient_user_profiles=user_profiles,
        operator=operator,
    )


def ensure_stream(realm: Realm,
                  stream_name: str,
                  invite_only: bool=False,
                  stream_description: str="",
                  acting_user: Optional[UserProfile]=None) -> Stream:
    return create_stream_if_needed(realm, stream_name,
                                   invite_only=invite_only,
                                   stream_description=stream_description,
                                   acting_user=acting_user)[0]

def get_recipient_from_user_profiles(recipient_profiles: Sequence[UserProfile],
                                     forwarded_mirror_message: bool,
                                     forwarder_user_profile: Optional[UserProfile],
                                     sender: UserProfile) -> Recipient:

    # Avoid mutating the passed in list of recipient_profiles.
    recipient_profiles_map = {user_profile.id: user_profile for user_profile in recipient_profiles}

    if forwarded_mirror_message:
        # In our mirroring integrations with some third-party
        # protocols, bots subscribed to the third-party protocol
        # forward to Zulip messages that they received in the
        # third-party service.  The permissions model for that
        # forwarding is that users can only submit to Zulip private
        # messages they personally received, and here we do the check
        # for whether forwarder_user_profile is among the private
        # message recipients of the message.
        assert forwarder_user_profile is not None
        if forwarder_user_profile.id not in recipient_profiles_map:
            raise ValidationError(_("User not authorized for this query"))

    # If the private message is just between the sender and
    # another person, force it to be a personal internally
    if (len(recipient_profiles_map) == 2 and sender.id in recipient_profiles_map):
        del recipient_profiles_map[sender.id]

    assert recipient_profiles_map
    if len(recipient_profiles_map) == 1:
        [user_profile] = recipient_profiles_map.values()
        return user_profile.recipient

    # Otherwise, we need a huddle.  Make sure the sender is included in huddle messages
    recipient_profiles_map[sender.id] = sender

    user_ids = set(recipient_profiles_map)
    return get_huddle_recipient(user_ids)

def validate_recipient_user_profiles(user_profiles: Sequence[UserProfile],
                                     sender: UserProfile,
                                     allow_deactivated: bool=False) -> Sequence[UserProfile]:
    recipient_profiles_map: Dict[int, UserProfile] = {}

    # We exempt cross-realm bots from the check that all the recipients
    # are in the same realm.
    realms = set()
    if not is_cross_realm_bot_email(sender.email):
        realms.add(sender.realm_id)

    for user_profile in user_profiles:
        if (not user_profile.is_active and not user_profile.is_mirror_dummy and
                not allow_deactivated) or user_profile.realm.deactivated:
            raise ValidationError(_("'{email}' is no longer using Zulip.").format(email=user_profile.email))
        recipient_profiles_map[user_profile.id] = user_profile
        if not is_cross_realm_bot_email(user_profile.email):
            realms.add(user_profile.realm_id)

    if len(realms) > 1:
        raise ValidationError(_("You can't send private messages outside of your organization."))

    return list(recipient_profiles_map.values())

def recipient_for_user_profiles(user_profiles: Sequence[UserProfile], forwarded_mirror_message: bool,
                                forwarder_user_profile: Optional[UserProfile],
                                sender: UserProfile, allow_deactivated: bool=False) -> Recipient:

    recipient_profiles = validate_recipient_user_profiles(user_profiles, sender,
                                                          allow_deactivated=allow_deactivated)

    return get_recipient_from_user_profiles(recipient_profiles, forwarded_mirror_message,
                                            forwarder_user_profile, sender)

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
        date_sent__lte=message.date_sent + time_window)

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
        data = data.split(',')

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

def get_validated_user_ids(user_ids: Iterable[int]) -> List[int]:
    for user_id in user_ids:
        if not isinstance(user_id, int):
            raise JsonableError(_("Recipient lists may contain emails or user IDs, but not both."))

    return list(set(user_ids))

def get_validated_emails(emails: Iterable[str]) -> List[str]:
    for email in emails:
        if not isinstance(email, str):
            raise JsonableError(_("Recipient lists may contain emails or user IDs, but not both."))

    return list(filter(bool, {email.strip() for email in emails}))

def check_send_stream_message(sender: UserProfile, client: Client, stream_name: str,
                              topic: str, body: str, realm: Optional[Realm]=None) -> int:
    addressee = Addressee.for_stream_name(stream_name, topic)
    message = check_message(sender, client, addressee, body, realm)

    return do_send_messages([message])[0]

def check_send_private_message(sender: UserProfile, client: Client,
                               receiving_user: UserProfile, body: str) -> int:
    addressee = Addressee.for_user_profile(receiving_user)
    message = check_message(sender, client, addressee, body)

    return do_send_messages([message])[0]

# check_send_message:
# Returns the id of the sent message.  Has same argspec as check_message.
def check_send_message(sender: UserProfile, client: Client, message_type_name: str,
                       message_to: Union[Sequence[int], Sequence[str]],
                       topic_name: Optional[str],
                       message_content: str, realm: Optional[Realm]=None,
                       forged: bool=False, forged_timestamp: Optional[float]=None,
                       forwarder_user_profile: Optional[UserProfile]=None,
                       local_id: Optional[str]=None,
                       sender_queue_id: Optional[str]=None,
                       widget_content: Optional[str]=None) -> int:

    addressee = Addressee.legacy_build(
        sender,
        message_type_name,
        message_to,
        topic_name)

    message = check_message(sender, client, addressee,
                            message_content, realm, forged, forged_timestamp,
                            forwarder_user_profile, local_id, sender_queue_id,
                            widget_content)
    return do_send_messages([message])[0]

def check_schedule_message(sender: UserProfile, client: Client,
                           message_type_name: str,
                           message_to: Union[Sequence[str], Sequence[int]],
                           topic_name: Optional[str], message_content: str,
                           delivery_type: str, deliver_at: datetime.datetime,
                           realm: Optional[Realm]=None,
                           forwarder_user_profile: Optional[UserProfile]=None,
                           ) -> int:
    addressee = Addressee.legacy_build(
        sender,
        message_type_name,
        message_to,
        topic_name)

    message = check_message(sender, client, addressee,
                            message_content, realm=realm,
                            forwarder_user_profile=forwarder_user_profile)
    message['deliver_at'] = deliver_at
    message['delivery_type'] = delivery_type

    recipient = message['message'].recipient
    if (delivery_type == 'remind' and (recipient.type != Recipient.STREAM and
                                       recipient.type_id != sender.id)):
        raise JsonableError(_("Reminders can only be set for streams."))

    return do_schedule_messages([message])[0]


def check_default_stream_group_name(group_name: str) -> None:
    if group_name.strip() == "":
        raise JsonableError(_("Invalid default stream group name '{}'").format(group_name))
    if len(group_name) > DefaultStreamGroup.MAX_NAME_LENGTH:
        raise JsonableError(_("Default stream group name too long (limit: {} characters)").format(
            DefaultStreamGroup.MAX_NAME_LENGTH,
        ))
    for i in group_name:
        if ord(i) == 0:
            raise JsonableError(_("Default stream group name '{}' contains NULL (0x00) characters.").format(
                group_name,
            ))

def send_rate_limited_pm_notification_to_bot_owner(sender: UserProfile,
                                                   realm: Realm,
                                                   content: str) -> None:
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

    internal_send_private_message(realm, get_system_bot(settings.NOTIFICATION_BOT),
                                  sender.bot_owner, content)

    sender.last_reminder = timezone_now()
    sender.save(update_fields=['last_reminder'])


def send_pm_if_empty_stream(stream: Optional[Stream],
                            realm: Realm,
                            sender: UserProfile,
                            stream_name: Optional[str]=None,
                            stream_id: Optional[int]=None) -> None:
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
                    content = _("Your bot {bot_identity} tried to send a message to stream ID "
                                "{stream_id}, but there is no stream with that ID.").format(**arg_dict)
                else:
                    assert(stream_name is not None)
                    content = _("Your bot {bot_identity} tried to send a message to stream "
                                "{stream_name}, but that stream does not exist. "
                                "Click [here]({new_stream_link}) to create it.").format(**arg_dict)
            else:
                if num_subscribers_for_stream_id(stream.id) > 0:
                    return
                content = _("Your bot {bot_identity} tried to send a message to "
                            "stream {stream_name}. The stream exists but "
                            "does not have any subscribers.").format(**arg_dict)

        send_rate_limited_pm_notification_to_bot_owner(sender, realm, content)

def validate_stream_name_with_pm_notification(stream_name: str, realm: Realm,
                                              sender: UserProfile) -> Stream:
    stream_name = stream_name.strip()
    check_stream_name(stream_name)

    try:
        stream = get_stream(stream_name, realm)
        send_pm_if_empty_stream(stream, realm, sender)
    except Stream.DoesNotExist:
        send_pm_if_empty_stream(None, realm, sender, stream_name=stream_name)
        raise StreamDoesNotExistError(escape(stream_name))

    return stream

def validate_stream_id_with_pm_notification(stream_id: int, realm: Realm,
                                            sender: UserProfile) -> Stream:
    try:
        stream = get_stream_by_id_in_realm(stream_id, realm)
        send_pm_if_empty_stream(stream, realm, sender)
    except Stream.DoesNotExist:
        send_pm_if_empty_stream(None, realm, sender, stream_id=stream_id)
        raise StreamWithIDDoesNotExistError(stream_id)

    return stream

def check_private_message_policy(realm: Realm, sender: UserProfile,
                                 user_profiles: Sequence[UserProfile]) -> None:
    if realm.private_message_policy == Realm.PRIVATE_MESSAGE_POLICY_DISABLED:
        if sender.is_bot or (len(user_profiles) == 1 and user_profiles[0].is_bot):
            # We allow PMs only between users and bots, to avoid
            # breaking the tutorial as well as automated
            # notifications from system bots to users.
            return

        raise JsonableError(_("Private messages are disabled in this organization."))

# check_message:
# Returns message ready for sending with do_send_message on success or the error message (string) on error.
def check_message(sender: UserProfile, client: Client, addressee: Addressee,
                  message_content_raw: str, realm: Optional[Realm]=None, forged: bool=False,
                  forged_timestamp: Optional[float]=None,
                  forwarder_user_profile: Optional[UserProfile]=None,
                  local_id: Optional[str]=None,
                  sender_queue_id: Optional[str]=None,
                  widget_content: Optional[str]=None,
                  email_gateway: bool=False) -> Dict[str, Any]:
    """See
    https://zulip.readthedocs.io/en/latest/subsystems/sending-messages.html
    for high-level documentation on this subsystem.
    """
    stream = None

    message_content = message_content_raw.rstrip()
    if len(message_content) == 0:
        raise JsonableError(_("Message must not be empty"))
    if '\x00' in message_content:
        raise JsonableError(_("Message must not contain null bytes"))

    message_content = truncate_body(message_content)

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

        if sender.bot_type != sender.OUTGOING_WEBHOOK_BOT:
            access_stream_for_send_message(
                sender=sender,
                stream=stream,
                forwarder_user_profile=forwarder_user_profile)

    elif addressee.is_private():
        user_profiles = addressee.user_profiles()
        mirror_message = client and client.name in ["zephyr_mirror", "irc_mirror",
                                                    "jabber_mirror", "JabberMirror"]

        check_private_message_policy(realm, sender, user_profiles)

        # API Super-users who set the `forged` flag are allowed to
        # forge messages sent by any user, so we disable the
        # `forwarded_mirror_message` security check in that case.
        forwarded_mirror_message = mirror_message and not forged
        try:
            recipient = recipient_for_user_profiles(user_profiles,
                                                    forwarded_mirror_message,
                                                    forwarder_user_profile, sender)
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
            return {'message': id}

    if widget_content is not None:
        try:
            widget_content = orjson.loads(widget_content)
        except orjson.JSONDecodeError:
            raise JsonableError(_('Widgets: API programmer sent invalid JSON content'))

        try:
            check_widget_content(widget_content)
        except ValidationError as error:
            raise JsonableError(_('Widgets: {error_msg}').format(
                error_msg=error.message,
            ))

    message_dict = {'message': message, 'stream': stream, 'local_id': local_id,
                    'sender_queue_id': sender_queue_id, 'realm': realm,
                    'widget_content': widget_content}
    message_send_dict = build_message_send_dict(message_dict, email_gateway)

    if stream is not None and message_send_dict['message'].mentions_wildcard:
        if not wildcard_mention_allowed(sender, stream):
            raise JsonableError(_("You do not have permission to use wildcard mentions in this stream."))
    return message_send_dict

def _internal_prep_message(realm: Realm,
                           sender: UserProfile,
                           addressee: Addressee,
                           content: str,
                           email_gateway: bool=False) -> Optional[Dict[str, Any]]:
    """
    Create a message object and checks it, but doesn't send it or save it to the database.
    The internal function that calls this can therefore batch send a bunch of created
    messages together as one database query.
    Call do_send_messages with a list of the return values of this method.
    """
    # Remove any null bytes from the content
    if len(content) > MAX_MESSAGE_LENGTH:
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
        return check_message(sender, get_client("Internal"), addressee,
                             content, realm=realm, email_gateway=email_gateway)
    except JsonableError as e:
        logging.exception("Error queueing internal message by %s: %s", sender.delivery_email, e.msg, stack_info=True)

    return None

def internal_prep_stream_message(
        realm: Realm, sender: UserProfile,
        stream: Stream, topic: str, content: str,
        email_gateway: bool=False,
) -> Optional[Dict[str, Any]]:
    """
    See _internal_prep_message for details of how this works.
    """
    addressee = Addressee.for_stream(stream, topic)

    return _internal_prep_message(
        realm=realm,
        sender=sender,
        addressee=addressee,
        content=content,
        email_gateway=email_gateway,
    )

def internal_prep_stream_message_by_name(
        realm: Realm, sender: UserProfile,
        stream_name: str, topic: str, content: str,
) -> Optional[Dict[str, Any]]:
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

def internal_prep_private_message(realm: Realm,
                                  sender: UserProfile,
                                  recipient_user: UserProfile,
                                  content: str) -> Optional[Dict[str, Any]]:
    """
    See _internal_prep_message for details of how this works.
    """
    addressee = Addressee.for_user_profile(recipient_user)

    return _internal_prep_message(
        realm=realm,
        sender=sender,
        addressee=addressee,
        content=content,
    )

def internal_send_private_message(realm: Realm,
                                  sender: UserProfile,
                                  recipient_user: UserProfile,
                                  content: str) -> Optional[int]:
    message = internal_prep_private_message(realm, sender, recipient_user, content)
    if message is None:
        return None
    message_ids = do_send_messages([message])
    return message_ids[0]

def internal_send_stream_message(
        realm: Realm,
        sender: UserProfile,
        stream: Stream,
        topic: str,
        content: str,
        email_gateway: bool=False) -> Optional[int]:

    message = internal_prep_stream_message(
        realm, sender, stream,
        topic, content, email_gateway
    )

    if message is None:
        return None
    message_ids = do_send_messages([message])
    return message_ids[0]

def internal_send_stream_message_by_name(
        realm: Realm, sender: UserProfile,
        stream_name: str, topic: str, content: str,
) -> Optional[int]:
    message = internal_prep_stream_message_by_name(
        realm, sender, stream_name,
        topic, content,
    )

    if message is None:
        return None
    message_ids = do_send_messages([message])
    return message_ids[0]

def internal_send_huddle_message(realm: Realm, sender: UserProfile, emails: List[str],
                                 content: str) -> Optional[int]:
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

def pick_color(user_profile: UserProfile, used_colors: Set[str]) -> str:
    # These colors are shared with the palette in subs.js.
    available_colors = [s for s in STREAM_ASSIGNMENT_COLORS if s not in used_colors]

    if available_colors:
        return available_colors[0]
    else:
        return STREAM_ASSIGNMENT_COLORS[len(used_colors) % len(STREAM_ASSIGNMENT_COLORS)]

def validate_user_access_to_subscribers(user_profile: Optional[UserProfile],
                                        stream: Stream) -> None:
    """ Validates whether the user can view the subscribers of a stream.  Raises a JsonableError if:
        * The user and the stream are in different realms
        * The realm is MIT and the stream is not invite only.
        * The stream is invite only, requesting_user is passed, and that user
          does not subscribe to the stream.
    """
    validate_user_access_to_subscribers_helper(
        user_profile,
        {"realm_id": stream.realm_id,
         "is_web_public": stream.is_web_public,
         "invite_only": stream.invite_only},
        # We use a lambda here so that we only compute whether the
        # user is subscribed if we have to
        lambda user_profile: subscribed_to_stream(user_profile, stream.id))

def validate_user_access_to_subscribers_helper(
    user_profile: Optional[UserProfile],
    stream_dict: Mapping[str, Any],
    check_user_subscribed: Callable[[UserProfile], bool],
) -> None:
    """Helper for validate_user_access_to_subscribers that doesn't require
    a full stream object.  This function is a bit hard to read,
    because it is carefully optimized for performance in the two code
    paths we call it from:

    * In `bulk_get_subscriber_user_ids`, we already know whether the
    user was subscribed via `sub_dict`, and so we want to avoid a
    database query at all (especially since it calls this in a loop);
    * In `validate_user_access_to_subscribers`, we want to only check
    if the user is subscribed when we absolutely have to, since it
    costs a database query.

    The `check_user_subscribed` argument is a function that reports
    whether the user is subscribed to the stream.

    Note also that we raise a ValidationError in cases where the
    caller is doing the wrong thing (maybe these should be
    AssertionErrors), and JsonableError for 400 type errors.
    """
    if user_profile is None:
        raise ValidationError("Missing user to validate access for")

    if user_profile.realm_id != stream_dict["realm_id"]:
        raise ValidationError("Requesting user not in given realm")

    # Even guest users can access subscribers to web-public streams,
    # since they can freely become subscribers to these streams.
    if stream_dict["is_web_public"]:
        return

    # Guest users can access subscribed public stream's subscribers
    if user_profile.is_guest:
        if check_user_subscribed(user_profile):
            return
        # We could put an AssertionError here; in that we don't have
        # any code paths that would allow a guest user to access other
        # streams in the first place.

    if not user_profile.can_access_public_streams() and not stream_dict["invite_only"]:
        raise JsonableError(_("Subscriber data is not available for this stream"))

    # Organization administrators can view subscribers for all streams.
    if user_profile.is_realm_admin:
        return

    if (stream_dict["invite_only"] and not check_user_subscribed(user_profile)):
        raise JsonableError(_("Unable to retrieve subscribers for private stream"))

def bulk_get_subscriber_user_ids(
    stream_dicts: Iterable[Mapping[str, Any]],
    user_profile: UserProfile,
    subscribed_stream_ids: Set[int],
) -> Dict[int, List[int]]:
    """sub_dict maps stream_id => whether the user is subscribed to that stream."""
    target_stream_dicts = []
    for stream_dict in stream_dicts:
        stream_id = stream_dict["id"]
        is_subscribed = stream_id in subscribed_stream_ids

        try:
            validate_user_access_to_subscribers_helper(
                user_profile,
                stream_dict,
                lambda user_profile: is_subscribed,
            )
        except JsonableError:
            continue
        target_stream_dicts.append(stream_dict)

    recip_to_stream_id = {stream["recipient_id"]: stream["id"] for stream in target_stream_dicts}
    recipient_ids = sorted([stream["recipient_id"] for stream in target_stream_dicts])

    result: Dict[int, List[int]] = {stream["id"]: [] for stream in stream_dicts}
    if not recipient_ids:
        return result

    '''
    The raw SQL below leads to more than a 2x speedup when tested with
    20k+ total subscribers.  (For large realms with lots of default
    streams, this function deals with LOTS of data, so it is important
    to optimize.)
    '''

    query = SQL('''
        SELECT
            zerver_subscription.recipient_id,
            zerver_subscription.user_profile_id
        FROM
            zerver_subscription
        INNER JOIN zerver_userprofile ON
            zerver_userprofile.id = zerver_subscription.user_profile_id
        WHERE
            zerver_subscription.recipient_id in %(recipient_ids)s AND
            zerver_subscription.active AND
            zerver_userprofile.is_active
        ORDER BY
            zerver_subscription.recipient_id,
            zerver_subscription.user_profile_id
        ''')

    cursor = connection.cursor()
    cursor.execute(query, {"recipient_ids": tuple(recipient_ids)})
    rows = cursor.fetchall()
    cursor.close()

    '''
    Using groupby/itemgetter here is important for performance, at scale.
    It makes it so that all interpreter overhead is just O(N) in nature.
    '''
    for recip_id, recip_rows in itertools.groupby(rows, itemgetter(0)):
        user_profile_ids = [r[1] for r in recip_rows]
        stream_id = recip_to_stream_id[recip_id]
        result[stream_id] = list(user_profile_ids)

    return result

def get_subscribers_query(stream: Stream, requesting_user: Optional[UserProfile]) -> QuerySet:
    # TODO: Make a generic stub for QuerySet
    """ Build a query to get the subscribers list for a stream, raising a JsonableError if:

    'realm' is optional in stream.

    The caller can refine this query with select_related(), values(), etc. depending
    on whether it wants objects or just certain fields
    """
    validate_user_access_to_subscribers(requesting_user, stream)

    # Note that non-active users may still have "active" subscriptions, because we
    # want to be able to easily reactivate them with their old subscriptions.  This
    # is why the query here has to look at the UserProfile.is_active flag.
    subscriptions = get_active_subscriptions_for_stream_id(stream.id).filter(
        user_profile__is_active=True,
    )
    return subscriptions


def get_subscriber_emails(stream: Stream,
                          requesting_user: Optional[UserProfile]=None) -> List[str]:
    subscriptions_query = get_subscribers_query(stream, requesting_user)
    subscriptions = subscriptions_query.values('user_profile__email')
    return [subscription['user_profile__email'] for subscription in subscriptions]


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

    for user_id, sub_infos in info_by_user.items():
        sub_dicts = []
        for sub_info in sub_infos:
            stream = sub_info.stream
            subscription = sub_info.sub
            sub_dict = stream.to_dict()
            for field_name in Subscription.API_FIELDS:
                sub_dict[field_name] = getattr(subscription, field_name)

            sub_dict['in_home_view'] = not subscription.is_muted
            sub_dict['email_address'] = encode_email_address(stream, show_sender=True)
            sub_dict['stream_weekly_traffic'] = get_average_weekly_stream_traffic(
                stream.id, stream.date_created, recent_traffic)
            if stream.is_in_zephyr_realm and not stream.invite_only:
                sub_dict['subscribers'] = []
            else:
                sub_dict['subscribers'] = list(subscriber_dict[stream.id])
            sub_dicts.append(sub_dict)

        # Send a notification to the user who subscribed.
        event = dict(type="subscription", op="add",
                     subscriptions=sub_dicts)
        send_event(realm, event, [user_id])

SubT = Tuple[List[SubInfo], List[SubInfo]]
def bulk_add_subscriptions(
    realm: Realm,
    streams: Iterable[Stream],
    users: Iterable[UserProfile],
    color_map: Mapping[str, str]={},
    acting_user: Optional[UserProfile]=None,
    from_user_creation: bool=False,
) -> SubT:
    users = list(users)

    # Sanity check out callers
    for stream in streams:
        assert stream.realm_id == realm.id

    for user in users:
        assert user.realm_id == realm.id

    recipient_id_to_stream = {stream.recipient_id: stream for stream in streams}

    subs_by_user: Dict[int, List[Subscription]] = defaultdict(list)
    all_subs_query = get_stream_subscriptions_for_users(users)
    for sub in all_subs_query:
        subs_by_user[sub.user_profile_id].append(sub)

    already_subscribed: List[SubInfo] = []
    subs_to_activate: List[SubInfo] = []
    subs_to_add: List[SubInfo] = []
    for user_profile in users:
        my_subs = subs_by_user[user_profile.id]
        used_colors = {sub.color for sub in my_subs}

        # Make a fresh set of all new recipient ids, and then we will
        # remove any for which our user already has a subscription
        # (and we'll re-activate any subscriptions as needed).
        new_recipient_ids = {stream.recipient_id for stream in streams}

        for sub in my_subs:
            if sub.recipient_id in new_recipient_ids:
                new_recipient_ids.remove(sub.recipient_id)
                stream = recipient_id_to_stream[sub.recipient_id]
                sub_info = SubInfo(user_profile, sub, stream)
                if sub.active:
                    already_subscribed.append(sub_info)
                else:
                    subs_to_activate.append(sub_info)

        for recipient_id in new_recipient_ids:
            stream = recipient_id_to_stream[recipient_id]

            if stream.name in color_map:
                color = color_map[stream.name]
            else:
                color = pick_color(user_profile, used_colors)
            used_colors.add(color)

            sub = Subscription(
                user_profile=user_profile,
                active=True,
                color=color,
                recipient_id=recipient_id
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

    new_streams = [
        stream_dict[stream_id]
        for stream_id in altered_user_dict
    ]

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
@transaction.atomic
def bulk_add_subs_to_db_with_logging(
    realm: Realm,
    acting_user: Optional[UserProfile],
    subs_to_add: List[SubInfo],
    subs_to_activate: List[SubInfo],
) -> None:

    Subscription.objects.bulk_create(info.sub for info in subs_to_add)
    sub_ids = [info.sub.id for info in subs_to_activate]
    Subscription.objects.filter(id__in=sub_ids).update(active=True)

    # Log Subscription Activities in RealmAuditLog
    event_time = timezone_now()
    event_last_message_id = get_last_message_id()

    all_subscription_logs: (List[RealmAuditLog]) = []
    for sub_info in subs_to_add:
        all_subscription_logs.append(RealmAuditLog(realm=realm,
                                                   acting_user=acting_user,
                                                   modified_user=sub_info.user,
                                                   modified_stream=sub_info.stream,
                                                   event_last_message_id=event_last_message_id,
                                                   event_type=RealmAuditLog.SUBSCRIPTION_CREATED,
                                                   event_time=event_time))
    for sub_info in subs_to_activate:
        all_subscription_logs.append(RealmAuditLog(realm=realm,
                                                   acting_user=acting_user,
                                                   modified_user=sub_info.user,
                                                   modified_stream=sub_info.stream,
                                                   event_last_message_id=event_last_message_id,
                                                   event_type=RealmAuditLog.SUBSCRIPTION_ACTIVATED,
                                                   event_time=event_time))
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
        stream_id for stream_id in altered_user_dict
        if stream_dict[stream_id].invite_only
    ]

    for stream_id in private_stream_ids:
        altered_user_ids = altered_user_dict[stream_id]
        peer_user_ids = private_peer_dict[stream_id] - altered_user_ids

        if peer_user_ids and altered_user_ids:
            event = dict(
                type="subscription",
                op=op,
                stream_ids=[stream_id],
                user_ids=sorted(list(altered_user_ids))
            )
            send_event(realm, event, peer_user_ids)

    public_stream_ids = [
        stream_id for stream_id in altered_user_dict
        if not stream_dict[stream_id].invite_only
        and not stream_dict[stream_id].is_in_zephyr_realm
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

def get_available_notification_sounds() -> List[str]:
    notification_sounds_path = static_path('audio/notification_sounds')
    available_notification_sounds = []

    for file_name in os.listdir(notification_sounds_path):
        root, ext = os.path.splitext(file_name)
        if '.' in root:  # nocoverage
            # Exclude e.g. zulip.abcd1234.ogg (generated by production hash-naming)
            # to avoid spurious duplicates.
            continue
        if ext == '.ogg':
            available_notification_sounds.append(root)

    return available_notification_sounds

def notify_subscriptions_removed(user_profile: UserProfile, streams: Iterable[Stream]) -> None:

    payload = [dict(name=stream.name, stream_id=stream.id) for stream in streams]
    event = dict(type="subscription", op="remove",
                 subscriptions=payload)
    send_event(user_profile.realm, event, [user_profile.id])

SubAndRemovedT = Tuple[List[Tuple[UserProfile, Stream]], List[Tuple[UserProfile, Stream]]]
def bulk_remove_subscriptions(users: Iterable[UserProfile],
                              streams: Iterable[Stream],
                              acting_client: Client,
                              acting_user: Optional[UserProfile]=None) -> SubAndRemovedT:

    users = list(users)
    streams = list(streams)

    stream_dict = {stream.id: stream for stream in streams}

    existing_subs_by_user = get_bulk_stream_subscriber_info(users, streams)

    def get_non_subscribed_subs() -> List[Tuple[UserProfile, Stream]]:
        stream_ids = {stream.id for stream in streams}

        not_subscribed: List[Tuple[UserProfile, Stream]] = []

        for user_profile in users:
            user_sub_stream_info = existing_subs_by_user[user_profile.id]

            subscribed_stream_ids = {
                sub_info.stream.id
                for sub_info in user_sub_stream_info
            }
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

    our_realm = users[0].realm

    # We do all the database changes in a transaction to ensure
    # RealmAuditLog entries are atomically created when making changes.
    with transaction.atomic():
        occupied_streams_before = list(get_occupied_streams(our_realm))
        Subscription.objects.filter(
            id__in=sub_ids_to_deactivate,
        ) .update(active=False)
        occupied_streams_after = list(get_occupied_streams(our_realm))

        # Log Subscription Activities in RealmAuditLog
        event_time = timezone_now()
        event_last_message_id = get_last_message_id()
        all_subscription_logs = [
            RealmAuditLog(
                realm=sub.user.realm,
                acting_user=acting_user,
                modified_user=sub_info.user,
                modified_stream=sub_info.stream,
                event_last_message_id=event_last_message_id,
                event_type=RealmAuditLog.SUBSCRIPTION_DEACTIVATED,
                event_time=event_time,
            )
            for sub in subs_to_deactivate
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
        notify_subscriptions_removed(user_profile, streams_by_user[user_profile.id])

        event = {'type': 'mark_stream_messages_as_read',
                 'user_profile_id': user_profile.id,
                 'stream_recipient_ids': [stream.recipient_id for stream in streams]}
        queue_json_publish("deferred_work", event)

    send_peer_remove_events(
        realm=our_realm,
        streams=streams,
        altered_user_dict=altered_user_dict,
    )

    new_vacant_streams = set(occupied_streams_before) - set(occupied_streams_after)
    new_vacant_private_streams = [stream for stream in new_vacant_streams
                                  if stream.invite_only]

    if new_vacant_private_streams:
        # Deactivate any newly-vacant private streams
        for stream in new_vacant_private_streams:
            do_deactivate_stream(stream, acting_user=acting_user)

    return (
        [(sub_info.user, sub_info.stream) for sub_info in subs_to_deactivate],
        not_subscribed,
    )

def do_change_subscription_property(user_profile: UserProfile, sub: Subscription,
                                    stream: Stream, property_name: str, value: Any,
                                    acting_user: Optional[UserProfile]=None) -> None:
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
        realm=user_profile.realm, event_type=RealmAuditLog.SUBSCRIPTION_PROPERTY_CHANGED,
        event_time=event_time, modified_user=user_profile, acting_user=acting_user,
        modified_stream=stream, extra_data=orjson.dumps({
            RealmAuditLog.OLD_VALUE: old_value,
            RealmAuditLog.NEW_VALUE: database_value,
            'property': database_property_name,
        }).decode())

    event = dict(type="subscription",
                 op="update",
                 email=user_profile.email,
                 property=event_property_name,
                 value=event_value,
                 stream_id=stream.id,
                 name=stream.name)
    send_event(user_profile.realm, event, [user_profile.id])

def do_change_password(user_profile: UserProfile, password: str, commit: bool=True) -> None:
    user_profile.set_password(password)
    if commit:
        user_profile.save(update_fields=["password"])
    event_time = timezone_now()
    RealmAuditLog.objects.create(realm=user_profile.realm, acting_user=user_profile,
                                 modified_user=user_profile, event_type=RealmAuditLog.USER_PASSWORD_CHANGED,
                                 event_time=event_time)

def do_change_full_name(user_profile: UserProfile, full_name: str,
                        acting_user: Optional[UserProfile]) -> None:
    old_name = user_profile.full_name
    user_profile.full_name = full_name
    user_profile.save(update_fields=["full_name"])
    event_time = timezone_now()
    RealmAuditLog.objects.create(realm=user_profile.realm, acting_user=acting_user,
                                 modified_user=user_profile, event_type=RealmAuditLog.USER_FULL_NAME_CHANGED,
                                 event_time=event_time, extra_data=old_name)
    payload = dict(user_id=user_profile.id,
                   full_name=user_profile.full_name)
    send_event(user_profile.realm,
               dict(type='realm_user', op='update', person=payload),
               active_user_ids(user_profile.realm_id))
    if user_profile.is_bot:
        send_event(user_profile.realm,
                   dict(type='realm_bot', op='update', bot=payload),
                   bot_owner_user_ids(user_profile))

def check_change_full_name(user_profile: UserProfile, full_name_raw: str,
                           acting_user: UserProfile) -> str:
    """Verifies that the user's proposed full name is valid.  The caller
    is responsible for checking check permissions.  Returns the new
    full name, which may differ from what was passed in (because this
    function strips whitespace)."""
    new_full_name = check_full_name(full_name_raw)
    do_change_full_name(user_profile, new_full_name, acting_user)
    return new_full_name

def check_change_bot_full_name(user_profile: UserProfile, full_name_raw: str,
                               acting_user: UserProfile) -> None:
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

def do_change_bot_owner(user_profile: UserProfile, bot_owner: UserProfile,
                        acting_user: UserProfile) -> None:
    previous_owner = user_profile.bot_owner
    user_profile.bot_owner = bot_owner
    user_profile.save()  # Can't use update_fields because of how the foreign key works.
    event_time = timezone_now()
    RealmAuditLog.objects.create(realm=user_profile.realm, acting_user=acting_user,
                                 modified_user=user_profile, event_type=RealmAuditLog.USER_BOT_OWNER_CHANGED,
                                 event_time=event_time)

    update_users = bot_owner_user_ids(user_profile)

    # For admins, update event is sent instead of delete/add
    # event. bot_data of admin contains all the
    # bots and none of them should be removed/(added again).

    # Delete the bot from previous owner's bot data.
    if previous_owner and not previous_owner.is_realm_admin:
        send_event(user_profile.realm,
                   dict(type='realm_bot',
                        op="delete",
                        bot=dict(
                            user_id=user_profile.id,
                        )),
                   {previous_owner.id})
        # Do not send update event for previous bot owner.
        update_users = update_users - {previous_owner.id}

    # Notify the new owner that the bot has been added.
    if not bot_owner.is_realm_admin:
        add_event = created_bot_event(user_profile)
        send_event(user_profile.realm, add_event, {bot_owner.id})
        # Do not send update event for bot_owner.
        update_users = update_users - {bot_owner.id}

    send_event(user_profile.realm,
               dict(type='realm_bot',
                    op='update',
                    bot=dict(user_id=user_profile.id,
                             owner_id=user_profile.bot_owner.id,
                             )),
               update_users)

    # Since `bot_owner_id` is included in the user profile dict we need
    # to update the users dict with the new bot owner id
    event: Dict[str, Any] = dict(
        type="realm_user",
        op="update",
        person=dict(
            user_id=user_profile.id,
            bot_owner_id=user_profile.bot_owner.id,
        ),
    )
    send_event(user_profile.realm, event, active_user_ids(user_profile.realm_id))

def do_change_tos_version(user_profile: UserProfile, tos_version: str) -> None:
    user_profile.tos_version = tos_version
    user_profile.save(update_fields=["tos_version"])
    event_time = timezone_now()
    RealmAuditLog.objects.create(realm=user_profile.realm, acting_user=user_profile,
                                 modified_user=user_profile,
                                 event_type=RealmAuditLog.USER_TOS_VERSION_CHANGED,
                                 event_time=event_time)

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
    RealmAuditLog.objects.create(realm=user_profile.realm, acting_user=acting_user,
                                 modified_user=user_profile, event_type=RealmAuditLog.USER_API_KEY_CHANGED,
                                 event_time=event_time)

    if user_profile.is_bot:
        send_event(user_profile.realm,
                   dict(type='realm_bot',
                        op='update',
                        bot=dict(user_id=user_profile.id,
                                 api_key=new_api_key,
                                 )),
                   bot_owner_user_ids(user_profile))

    event = {'type': 'clear_push_device_tokens',
             'user_profile_id': user_profile.id}
    queue_json_publish("deferred_work", event)

    return new_api_key

def notify_avatar_url_change(user_profile: UserProfile) -> None:
    if user_profile.is_bot:
        send_event(user_profile.realm,
                   dict(type='realm_bot',
                        op='update',
                        bot=dict(user_id=user_profile.id,
                                 avatar_url=avatar_url(user_profile),
                                 )),
                   bot_owner_user_ids(user_profile))

    payload = dict(
        avatar_source=user_profile.avatar_source,
        avatar_url=avatar_url(user_profile),
        avatar_url_medium=avatar_url(user_profile, medium=True),
        avatar_version=user_profile.avatar_version,
        # Even clients using client_gravatar don't need the email,
        # since we're sending the URL anyway.
        user_id=user_profile.id,
    )

    send_event(user_profile.realm,
               dict(type='realm_user',
                    op='update',
                    person=payload),
               active_user_ids(user_profile.realm_id))

def do_change_avatar_fields(user_profile: UserProfile, avatar_source: str,
                            skip_notify: bool=False, acting_user: Optional[UserProfile]=None) -> None:
    user_profile.avatar_source = avatar_source
    user_profile.avatar_version += 1
    user_profile.save(update_fields=["avatar_source", "avatar_version"])
    event_time = timezone_now()
    RealmAuditLog.objects.create(realm=user_profile.realm, modified_user=user_profile,
                                 event_type=RealmAuditLog.USER_AVATAR_SOURCE_CHANGED,
                                 extra_data={'avatar_source': avatar_source},
                                 event_time=event_time, acting_user=acting_user)

    if not skip_notify:
        notify_avatar_url_change(user_profile)

def do_delete_avatar_image(user: UserProfile, acting_user: Optional[UserProfile]=None) -> None:
    do_change_avatar_fields(user, UserProfile.AVATAR_FROM_GRAVATAR, acting_user=acting_user)
    delete_avatar_image(user)

def do_change_icon_source(realm: Realm, icon_source: str, acting_user: Optional[UserProfile]=None) -> None:
    realm.icon_source = icon_source
    realm.icon_version += 1
    realm.save(update_fields=["icon_source", "icon_version"])

    event_time = timezone_now()
    RealmAuditLog.objects.create(realm=realm,
                                 event_type=RealmAuditLog.REALM_ICON_SOURCE_CHANGED,
                                 extra_data={'icon_source': icon_source,
                                             'icon_version': realm.icon_version},
                                 event_time=event_time, acting_user=acting_user)

    send_event(realm,
               dict(type='realm',
                    op='update_dict',
                    property="icon",
                    data=dict(icon_source=realm.icon_source,
                              icon_url=realm_icon_url(realm))),
               active_user_ids(realm.id))

def do_change_logo_source(realm: Realm, logo_source: str, night: bool, acting_user: Optional[UserProfile]=None) -> None:
    if not night:
        realm.logo_source = logo_source
        realm.logo_version += 1
        realm.save(update_fields=["logo_source", "logo_version"])

    else:
        realm.night_logo_source = logo_source
        realm.night_logo_version += 1
        realm.save(update_fields=["night_logo_source", "night_logo_version"])

    RealmAuditLog.objects.create(event_type=RealmAuditLog.REALM_LOGO_CHANGED,
                                 realm=realm, event_time=timezone_now(),
                                 acting_user=acting_user)

    event = dict(type='realm',
                 op='update_dict',
                 property="night_logo" if night else "logo",
                 data=get_realm_logo_data(realm, night))
    send_event(realm, event, active_user_ids(realm.id))

def do_change_plan_type(realm: Realm, plan_type: int) -> None:
    old_value = realm.plan_type
    realm.plan_type = plan_type
    realm.save(update_fields=['plan_type'])
    RealmAuditLog.objects.create(event_type=RealmAuditLog.REALM_PLAN_TYPE_CHANGED,
                                 realm=realm, event_time=timezone_now(),
                                 extra_data={'old_value': old_value, 'new_value': plan_type})

    if plan_type == Realm.STANDARD:
        realm.max_invites = Realm.INVITES_STANDARD_REALM_DAILY_MAX
        realm.message_visibility_limit = None
        realm.upload_quota_gb = Realm.UPLOAD_QUOTA_STANDARD
    elif plan_type == Realm.SELF_HOSTED:
        realm.max_invites = None  # type: ignore[assignment] # Apparent mypy bug with Optional[int] setter.
        realm.message_visibility_limit = None
        realm.upload_quota_gb = None
    elif plan_type == Realm.STANDARD_FREE:
        realm.max_invites = Realm.INVITES_STANDARD_REALM_DAILY_MAX
        realm.message_visibility_limit = None
        realm.upload_quota_gb = Realm.UPLOAD_QUOTA_STANDARD
    elif plan_type == Realm.LIMITED:
        realm.max_invites = settings.INVITES_DEFAULT_REALM_DAILY_MAX
        realm.message_visibility_limit = Realm.MESSAGE_VISIBILITY_LIMITED
        realm.upload_quota_gb = Realm.UPLOAD_QUOTA_LIMITED
    else:
        raise AssertionError("Invalid plan type")

    update_first_visible_message_id(realm)

    realm.save(update_fields=['_max_invites', 'message_visibility_limit', 'upload_quota_gb'])

    event = {'type': 'realm', 'op': 'update', 'property': 'plan_type', 'value': plan_type,
             'extra_data': {'upload_quota': realm.upload_quota_bytes()}}
    send_event(realm, event, active_user_ids(realm.id))

def do_change_default_sending_stream(user_profile: UserProfile, stream: Optional[Stream],
                                     acting_user: Optional[UserProfile]=None) -> None:
    old_value = user_profile.default_sending_stream_id
    user_profile.default_sending_stream = stream
    user_profile.save(update_fields=['default_sending_stream'])

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=user_profile.realm, event_type=RealmAuditLog.USER_DEFAULT_SENDING_STREAM_CHANGED,
        event_time=event_time, modified_user=user_profile,
        acting_user=acting_user, extra_data=orjson.dumps({
            RealmAuditLog.OLD_VALUE: old_value,
            RealmAuditLog.NEW_VALUE: None if stream is None else stream.id,
        }).decode())

    if user_profile.is_bot:
        if stream:
            stream_name: Optional[str] = stream.name
        else:
            stream_name = None
        send_event(user_profile.realm,
                   dict(type='realm_bot',
                        op='update',
                        bot=dict(user_id=user_profile.id,
                                 default_sending_stream=stream_name,
                                 )),
                   bot_owner_user_ids(user_profile))

def do_change_default_events_register_stream(user_profile: UserProfile,
                                             stream: Optional[Stream],
                                             acting_user: Optional[UserProfile]=None) -> None:
    old_value = user_profile.default_events_register_stream_id
    user_profile.default_events_register_stream = stream
    user_profile.save(update_fields=['default_events_register_stream'])

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=user_profile.realm, event_type=RealmAuditLog.USER_DEFAULT_REGISTER_STREAM_CHANGED,
        event_time=event_time, modified_user=user_profile,
        acting_user=acting_user, extra_data=orjson.dumps({
            RealmAuditLog.OLD_VALUE: old_value,
            RealmAuditLog.NEW_VALUE: None if stream is None else stream.id,
        }).decode())

    if user_profile.is_bot:
        if stream:
            stream_name: Optional[str] = stream.name
        else:
            stream_name = None
        send_event(user_profile.realm,
                   dict(type='realm_bot',
                        op='update',
                        bot=dict(user_id=user_profile.id,
                                 default_events_register_stream=stream_name,
                                 )),
                   bot_owner_user_ids(user_profile))

def do_change_default_all_public_streams(user_profile: UserProfile, value: bool,
                                         acting_user: Optional[UserProfile]=None) -> None:
    old_value = user_profile.default_all_public_streams
    user_profile.default_all_public_streams = value
    user_profile.save(update_fields=['default_all_public_streams'])

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=user_profile.realm, event_type=RealmAuditLog.USER_DEFAULT_ALL_PUBLIC_STREAMS_CHANGED,
        event_time=event_time, modified_user=user_profile,
        acting_user=acting_user, extra_data=orjson.dumps({
            RealmAuditLog.OLD_VALUE: old_value,
            RealmAuditLog.NEW_VALUE: value,
        }).decode())

    if user_profile.is_bot:
        send_event(user_profile.realm,
                   dict(type='realm_bot',
                        op='update',
                        bot=dict(user_id=user_profile.id,
                                 default_all_public_streams=user_profile.default_all_public_streams,
                                 )),
                   bot_owner_user_ids(user_profile))

def do_change_user_role(user_profile: UserProfile, value: int, acting_user: Optional[UserProfile]=None) -> None:
    old_value = user_profile.role
    user_profile.role = value
    user_profile.save(update_fields=["role"])
    RealmAuditLog.objects.create(
        realm=user_profile.realm, modified_user=user_profile, acting_user=acting_user,
        event_type=RealmAuditLog.USER_ROLE_CHANGED, event_time=timezone_now(),
        extra_data=orjson.dumps({
            RealmAuditLog.OLD_VALUE: old_value,
            RealmAuditLog.NEW_VALUE: value,
            RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(user_profile.realm),
        }).decode())
    event = dict(type="realm_user", op="update",
                 person=dict(user_id=user_profile.id, role=user_profile.role))
    send_event(user_profile.realm, event, active_user_ids(user_profile.realm_id))

def do_change_is_api_super_user(user_profile: UserProfile, value: bool) -> None:
    user_profile.is_api_super_user = value
    user_profile.save(update_fields=["is_api_super_user"])

def do_change_stream_invite_only(stream: Stream, invite_only: bool,
                                 history_public_to_subscribers: Optional[bool]=None) -> None:
    history_public_to_subscribers = get_default_value_for_history_public_to_subscribers(
        stream.realm,
        invite_only,
        history_public_to_subscribers,
    )
    stream.invite_only = invite_only
    stream.history_public_to_subscribers = history_public_to_subscribers
    stream.save(update_fields=['invite_only', 'history_public_to_subscribers'])
    event = dict(
        op="update",
        type="stream",
        property="invite_only",
        value=invite_only,
        history_public_to_subscribers=history_public_to_subscribers,
        stream_id=stream.id,
        name=stream.name,
    )
    send_event(stream.realm, event, can_access_stream_user_ids(stream))

def do_change_stream_web_public(stream: Stream, is_web_public: bool) -> None:
    stream.is_web_public = is_web_public
    stream.save(update_fields=['is_web_public'])

def do_change_stream_post_policy(stream: Stream, stream_post_policy: int) -> None:
    stream.stream_post_policy = stream_post_policy
    stream.save(update_fields=['stream_post_policy'])
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

def do_rename_stream(stream: Stream,
                     new_name: str,
                     user_profile: UserProfile) -> Dict[str, str]:
    old_name = stream.name
    stream.name = new_name
    stream.save(update_fields=["name"])

    RealmAuditLog.objects.create(
        realm=stream.realm, acting_user=user_profile, modified_stream=stream,
        event_type=RealmAuditLog.STREAM_NAME_CHANGED, event_time=timezone_now(),
        extra_data=orjson.dumps({
            RealmAuditLog.OLD_VALUE: old_name,
            RealmAuditLog.NEW_VALUE: new_name,
        }).decode())

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
    cache_delete_many(
        to_dict_cache_key_id(message.id) for message in messages)
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
        ['email_address', new_email],
        ['name', new_name],
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
    sender = get_system_bot(settings.NOTIFICATION_BOT)
    with override_language(stream.realm.default_language):
        internal_send_stream_message(
            stream.realm,
            sender,
            stream,
            Realm.STREAM_EVENTS_NOTIFICATION_TOPIC,
            _('{user_name} renamed stream {old_stream_name} to {new_stream_name}.').format(
                user_name=f"@_**{user_profile.full_name}|{user_profile.id}**",
                old_stream_name=f"**{old_name}**",
                new_stream_name=f"**{new_name}**",
            ),
        )
    # Even though the token doesn't change, the web client needs to update the
    # email forwarding address to display the correctly-escaped new name.
    return {"email_address": new_email}

def do_change_stream_description(stream: Stream, new_description: str) -> None:
    stream.description = new_description
    stream.rendered_description = render_stream_description(new_description)
    stream.save(update_fields=['description', 'rendered_description'])

    event = dict(
        type='stream',
        op='update',
        property='description',
        name=stream.name,
        stream_id=stream.id,
        value=new_description,
        rendered_description=stream.rendered_description,
    )
    send_event(stream.realm, event, can_access_stream_user_ids(stream))

def do_change_stream_message_retention_days(stream: Stream, message_retention_days: Optional[int]=None) -> None:
    stream.message_retention_days = message_retention_days
    stream.save(update_fields=['message_retention_days'])

    event = dict(
        op="update",
        type="stream",
        property="message_retention_days",
        value=message_retention_days,
        stream_id=stream.id,
        name=stream.name,
    )
    send_event(stream.realm, event, can_access_stream_user_ids(stream))

def do_create_realm(string_id: str, name: str,
                    emails_restricted_to_domains: Optional[bool]=None) -> Realm:
    if Realm.objects.filter(string_id=string_id).exists():
        raise AssertionError(f"Realm {string_id} already exists!")
    if not server_initialized():
        logging.info("Server not yet initialized. Creating the internal realm first.")
        create_internal_realm()

    kwargs: Dict[str, Any] = {}
    if emails_restricted_to_domains is not None:
        kwargs['emails_restricted_to_domains'] = emails_restricted_to_domains
    realm = Realm(string_id=string_id, name=name, **kwargs)
    realm.save()

    # Create stream once Realm object has been saved
    notifications_stream = ensure_stream(
        realm, Realm.DEFAULT_NOTIFICATION_STREAM_NAME,
        stream_description="Everyone is added to this stream by default. Welcome! :octopus:", acting_user=None)
    realm.notifications_stream = notifications_stream

    # With the current initial streams situation, the only public
    # stream is the notifications_stream.
    DefaultStream.objects.create(stream=notifications_stream, realm=realm)

    signup_notifications_stream = ensure_stream(
        realm, Realm.INITIAL_PRIVATE_STREAM_NAME, invite_only=True,
        stream_description="A private stream for core team members.", acting_user=None)
    realm.signup_notifications_stream = signup_notifications_stream

    realm.save(update_fields=['notifications_stream', 'signup_notifications_stream'])

    if settings.BILLING_ENABLED:
        do_change_plan_type(realm, Realm.LIMITED)

    sender = get_system_bot(settings.NOTIFICATION_BOT)
    admin_realm = sender.realm
    # Send a notification to the admin realm
    with override_language(admin_realm.default_language):
        signup_message = _("Signups enabled")

    try:
        signups_stream = get_signups_stream(admin_realm)
        topic = realm.display_subdomain

        internal_send_stream_message(
            admin_realm,
            sender,
            signups_stream,
            topic,
            signup_message,
        )
    except Stream.DoesNotExist:  # nocoverage
        # If the signups stream hasn't been created in the admin
        # realm, don't auto-create it to send to it; just do nothing.
        pass
    return realm

def do_change_notification_settings(user_profile: UserProfile, name: str,
                                    value: Union[bool, int, str],
                                    acting_user: Optional[UserProfile]=None) -> None:
    """Takes in a UserProfile object, the name of a global notification
    preference to update, and the value to update to
    """

    old_value = getattr(user_profile, name)
    notification_setting_type = UserProfile.notification_setting_types[name]
    assert isinstance(value, notification_setting_type), (
        f'Cannot update {name}: {value} is not an instance of {notification_setting_type}')

    setattr(user_profile, name, value)

    # Disabling digest emails should clear a user's email queue
    if name == 'enable_digest_emails' and not value:
        clear_scheduled_emails([user_profile.id], ScheduledEmail.DIGEST)

    user_profile.save(update_fields=[name])
    event = {'type': 'update_global_notifications',
             'user': user_profile.email,
             'notification_name': name,
             'setting': value}
    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=user_profile.realm, event_type=RealmAuditLog.USER_NOTIFICATION_SETTINGS_CHANGED, event_time=event_time,
        acting_user=acting_user, modified_user=user_profile, extra_data=orjson.dumps({
            RealmAuditLog.OLD_VALUE: old_value,
            RealmAuditLog.NEW_VALUE: value,
            'property': name,
        }).decode())

    send_event(user_profile.realm, event, [user_profile.id])

def do_change_enter_sends(user_profile: UserProfile, enter_sends: bool) -> None:
    user_profile.enter_sends = enter_sends
    user_profile.save(update_fields=["enter_sends"])

def do_set_user_display_setting(user_profile: UserProfile,
                                setting_name: str,
                                setting_value: Union[bool, str, int]) -> None:
    property_type = UserProfile.property_types[setting_name]
    assert isinstance(setting_value, property_type)
    setattr(user_profile, setting_name, setting_value)
    user_profile.save(update_fields=[setting_name])
    event = {'type': 'update_display_settings',
             'user': user_profile.email,
             'setting_name': setting_name,
             'setting': setting_value}
    if setting_name == "default_language":
        assert isinstance(setting_value, str)
        event['language_name'] = get_language_name(setting_value)

    send_event(user_profile.realm, event, [user_profile.id])

    # Updates to the timezone display setting are sent to all users
    if setting_name == "timezone":
        payload = dict(email=user_profile.email,
                       user_id=user_profile.id,
                       timezone=user_profile.timezone)
        send_event(user_profile.realm,
                   dict(type='realm_user', op='update', person=payload),
                   active_user_ids(user_profile.realm_id))

def lookup_default_stream_groups(default_stream_group_names: List[str],
                                 realm: Realm) -> List[DefaultStreamGroup]:
    default_stream_groups = []
    for group_name in default_stream_group_names:
        try:
            default_stream_group = DefaultStreamGroup.objects.get(
                name=group_name, realm=realm)
        except DefaultStreamGroup.DoesNotExist:
            raise JsonableError(_('Invalid default stream group {}').format(group_name))
        default_stream_groups.append(default_stream_group)
    return default_stream_groups

def notify_default_streams(realm: Realm) -> None:
    event = dict(
        type="default_streams",
        default_streams=streams_to_dicts_sorted(get_default_streams_for_realm(realm.id)),
    )
    send_event(realm, event, active_non_guest_user_ids(realm.id))

def notify_default_stream_groups(realm: Realm) -> None:
    event = dict(
        type="default_stream_groups",
        default_stream_groups=default_stream_groups_to_dicts_sorted(get_default_stream_groups(realm)),
    )
    send_event(realm, event, active_non_guest_user_ids(realm.id))

def do_add_default_stream(stream: Stream) -> None:
    realm_id = stream.realm_id
    stream_id = stream.id
    if not DefaultStream.objects.filter(realm_id=realm_id, stream_id=stream_id).exists():
        DefaultStream.objects.create(realm_id=realm_id, stream_id=stream_id)
        notify_default_streams(stream.realm)

def do_remove_default_stream(stream: Stream) -> None:
    realm_id = stream.realm_id
    stream_id = stream.id
    DefaultStream.objects.filter(realm_id=realm_id, stream_id=stream_id).delete()
    notify_default_streams(stream.realm)

def do_create_default_stream_group(realm: Realm, group_name: str,
                                   description: str, streams: List[Stream]) -> None:
    default_streams = get_default_streams_for_realm(realm.id)
    for stream in streams:
        if stream in default_streams:
            raise JsonableError(_(
                "'{stream_name}' is a default stream and cannot be added to '{group_name}'",
            ).format(stream_name=stream.name, group_name=group_name))

    check_default_stream_group_name(group_name)
    (group, created) = DefaultStreamGroup.objects.get_or_create(
        name=group_name, realm=realm, description=description)
    if not created:
        raise JsonableError(_(
            "Default stream group '{group_name}' already exists",
        ).format(group_name=group_name))

    group.streams.set(streams)
    notify_default_stream_groups(realm)

def do_add_streams_to_default_stream_group(realm: Realm, group: DefaultStreamGroup,
                                           streams: List[Stream]) -> None:
    default_streams = get_default_streams_for_realm(realm.id)
    for stream in streams:
        if stream in default_streams:
            raise JsonableError(_(
                "'{stream_name}' is a default stream and cannot be added to '{group_name}'",
            ).format(stream_name=stream.name, group_name=group.name))
        if stream in group.streams.all():
            raise JsonableError(_(
                "Stream '{stream_name}' is already present in default stream group '{group_name}'",
            ).format(stream_name=stream.name, group_name=group.name))
        group.streams.add(stream)

    group.save()
    notify_default_stream_groups(realm)

def do_remove_streams_from_default_stream_group(realm: Realm, group: DefaultStreamGroup,
                                                streams: List[Stream]) -> None:
    for stream in streams:
        if stream not in group.streams.all():
            raise JsonableError(_(
                "Stream '{stream_name}' is not present in default stream group '{group_name}'",
            ).format(stream_name=stream.name, group_name=group.name))
        group.streams.remove(stream)

    group.save()
    notify_default_stream_groups(realm)

def do_change_default_stream_group_name(realm: Realm, group: DefaultStreamGroup,
                                        new_group_name: str) -> None:
    if group.name == new_group_name:
        raise JsonableError(_("This default stream group is already named '{}'").format(new_group_name))

    if DefaultStreamGroup.objects.filter(name=new_group_name, realm=realm).exists():
        raise JsonableError(_("Default stream group '{}' already exists").format(new_group_name))

    group.name = new_group_name
    group.save()
    notify_default_stream_groups(realm)

def do_change_default_stream_group_description(realm: Realm, group: DefaultStreamGroup,
                                               new_description: str) -> None:
    group.description = new_description
    group.save()
    notify_default_stream_groups(realm)

def do_remove_default_stream_group(realm: Realm, group: DefaultStreamGroup) -> None:
    group.delete()
    notify_default_stream_groups(realm)

def get_default_streams_for_realm(realm_id: int) -> List[Stream]:
    return [default.stream for default in
            DefaultStream.objects.select_related().filter(realm_id=realm_id)]

def get_default_subs(user_profile: UserProfile) -> List[Stream]:
    # Right now default streams are realm-wide.  This wrapper gives us flexibility
    # to some day further customize how we set up default streams for new users.
    return get_default_streams_for_realm(user_profile.realm_id)

# returns default streams in json serializeable format
def streams_to_dicts_sorted(streams: List[Stream]) -> List[Dict[str, Any]]:
    return sorted((stream.to_dict() for stream in streams), key=lambda elt: elt["name"])

def default_stream_groups_to_dicts_sorted(groups: List[DefaultStreamGroup]) -> List[Dict[str, Any]]:
    return sorted((group.to_dict() for group in groups), key=lambda elt: elt["name"])

def do_update_user_activity_interval(user_profile: UserProfile,
                                     log_time: datetime.datetime) -> None:
    effective_end = log_time + UserActivityInterval.MIN_INTERVAL_LENGTH
    # This code isn't perfect, because with various races we might end
    # up creating two overlapping intervals, but that shouldn't happen
    # often, and can be corrected for in post-processing
    try:
        last = UserActivityInterval.objects.filter(user_profile=user_profile).order_by("-end")[0]
        # There are two ways our intervals could overlap:
        # (1) The start of the new interval could be inside the old interval
        # (2) The end of the new interval could be inside the old interval
        # In either case, we just extend the old interval to include the new interval.
        if ((log_time <= last.end and log_time >= last.start) or
                (effective_end <= last.end and effective_end >= last.start)):
            last.end = max(last.end, effective_end)
            last.start = min(last.start, log_time)
            last.save(update_fields=["start", "end"])
            return
    except IndexError:
        pass

    # Otherwise, the intervals don't overlap, so we should make a new one
    UserActivityInterval.objects.create(user_profile=user_profile, start=log_time,
                                        end=effective_end)

@statsd_increment('user_activity')
def do_update_user_activity(user_profile_id: int,
                            client_id: int,
                            query: str,
                            count: int,
                            log_time: datetime.datetime) -> None:
    (activity, created) = UserActivity.objects.get_or_create(
        user_profile_id = user_profile_id,
        client_id = client_id,
        query = query,
        defaults={'last_visit': log_time, 'count': count})

    if not created:
        activity.count += count
        activity.last_visit = log_time
        activity.save(update_fields=["last_visit", "count"])

def send_presence_changed(user_profile: UserProfile, presence: UserPresence) -> None:
    presence_dict = presence.to_dict()
    event = dict(type="presence",
                 email=user_profile.email,
                 user_id=user_profile.id,
                 server_timestamp=time.time(),
                 presence={presence_dict['client']: presence_dict})
    send_event(user_profile.realm, event, active_user_ids(user_profile.realm_id))

def consolidate_client(client: Client) -> Client:
    # The web app reports a client as 'website'
    # The desktop app reports a client as ZulipDesktop
    # due to it setting a custom user agent. We want both
    # to count as web users

    # Alias ZulipDesktop to website
    if client.name in ['ZulipDesktop']:
        return get_client('website')
    else:
        return client

@statsd_increment('user_presence')
def do_update_user_presence(user_profile: UserProfile,
                            client: Client,
                            log_time: datetime.datetime,
                            status: int) -> None:
    client = consolidate_client(client)

    defaults = dict(
        timestamp=log_time,
        status=status,
        realm_id=user_profile.realm_id,
    )

    (presence, created) = UserPresence.objects.get_or_create(
        user_profile = user_profile,
        client = client,
        defaults = defaults,
    )

    stale_status = (log_time - presence.timestamp) > datetime.timedelta(minutes=1, seconds=10)
    was_idle = presence.status == UserPresence.IDLE
    became_online = (status == UserPresence.ACTIVE) and (stale_status or was_idle)

    # If an object was created, it has already been saved.
    #
    # We suppress changes from ACTIVE to IDLE before stale_status is reached;
    # this protects us from the user having two clients open: one active, the
    # other idle. Without this check, we would constantly toggle their status
    # between the two states.
    if not created and stale_status or was_idle or status == presence.status:
        # The following block attempts to only update the "status"
        # field in the event that it actually changed.  This is
        # important to avoid flushing the UserPresence cache when the
        # data it would return to a client hasn't actually changed
        # (see the UserPresence post_save hook for details).
        presence.timestamp = log_time
        update_fields = ["timestamp"]
        if presence.status != status:
            presence.status = status
            update_fields.append("status")
        presence.save(update_fields=update_fields)

    if not user_profile.realm.presence_disabled and (created or became_online):
        # Push event to all users in the realm so they see the new user
        # appear in the presence list immediately, or the newly online
        # user without delay.  Note that we won't send an update here for a
        # timestamp update, because we rely on the browser to ping us every 50
        # seconds for realm-wide status updates, and those updates should have
        # recent timestamps, which means the browser won't think active users
        # have gone idle.  If we were more aggressive in this function about
        # sending timestamp updates, we could eliminate the ping responses, but
        # that's not a high priority for now, considering that most of our non-MIT
        # realms are pretty small.
        send_presence_changed(user_profile, presence)

def update_user_activity_interval(user_profile: UserProfile, log_time: datetime.datetime) -> None:
    event = {'user_profile_id': user_profile.id,
             'time': datetime_to_timestamp(log_time)}
    queue_json_publish("user_activity_interval", event)

def update_user_presence(user_profile: UserProfile, client: Client, log_time: datetime.datetime,
                         status: int, new_user_input: bool) -> None:
    event = {'user_profile_id': user_profile.id,
             'status': status,
             'time': datetime_to_timestamp(log_time),
             'client': client.name}

    queue_json_publish("user_presence", event)

    if new_user_input:
        update_user_activity_interval(user_profile, log_time)

def do_update_user_status(user_profile: UserProfile,
                          away: Optional[bool],
                          status_text: Optional[str],
                          client_id: int) -> None:
    if away:
        status = UserStatus.AWAY
    else:
        status = UserStatus.NORMAL

    realm = user_profile.realm

    update_user_status(
        user_profile_id=user_profile.id,
        status=status,
        status_text=status_text,
        client_id=client_id,
    )

    event = dict(
        type='user_status',
        user_id=user_profile.id,
    )

    if away is not None:
        event['away'] = away

    if status_text is not None:
        event['status_text'] = status_text

    send_event(realm, event, active_user_ids(realm.id))

def do_mark_all_as_read(user_profile: UserProfile, client: Client) -> int:
    log_statsd_event('bankruptcy')

    # First, we clear mobile push notifications.  This is safer in the
    # event that the below logic times out and we're killed.
    all_push_message_ids = UserMessage.objects.filter(
        user_profile=user_profile,
    ).extra(
        where=[UserMessage.where_active_push_notification()],
    ).values_list("message_id", flat=True)[0:10000]
    do_clear_mobile_push_notifications_for_ids([user_profile.id], all_push_message_ids)

    msgs = UserMessage.objects.filter(
        user_profile=user_profile
    ).extra(
        where=[UserMessage.where_unread()],
    )

    count = msgs.update(
        flags=F('flags').bitor(UserMessage.flags.read),
    )

    event = dict(
        type='update_message_flags',
        op ='add',
        operation='add',
        flag='read',
        messages=[],  # we don't send messages, since the client reloads anyway
        all=True,
    )
    event_time = timezone_now()

    send_event(user_profile.realm, event, [user_profile.id])

    do_increment_logging_stat(user_profile, COUNT_STATS['messages_read::hour'],
                              None, event_time, increment=count)
    do_increment_logging_stat(user_profile, COUNT_STATS['messages_read_interactions::hour'],
                              None, event_time, increment=min(1, count))

    return count

def do_mark_stream_messages_as_read(
    user_profile: UserProfile,
    stream_recipient_id: int,
    topic_name: Optional[str]=None
) -> int:
    log_statsd_event('mark_stream_as_read')

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

    message_ids = list(msgs.values_list('message__id', flat=True))

    count = msgs.update(
        flags=F('flags').bitor(UserMessage.flags.read),
    )

    event = dict(
        type='update_message_flags',
        op='add',
        operation='add',
        flag='read',
        messages=message_ids,
        all=False,
    )
    event_time = timezone_now()

    send_event(user_profile.realm, event, [user_profile.id])
    do_clear_mobile_push_notifications_for_ids([user_profile.id], message_ids)

    do_increment_logging_stat(user_profile, COUNT_STATS['messages_read::hour'],
                              None, event_time, increment=count)
    do_increment_logging_stat(user_profile, COUNT_STATS['messages_read_interactions::hour'],
                              None, event_time, increment=min(1, count))
    return count

def do_update_mobile_push_notification(message: Message,
                                       prior_mention_user_ids: Set[int],
                                       stream_push_user_ids: Set[int]) -> None:
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

    remove_notify_users = prior_mention_user_ids - message.mentions_user_ids - stream_push_user_ids
    do_clear_mobile_push_notifications_for_ids(list(remove_notify_users), [message.id])

def do_clear_mobile_push_notifications_for_ids(user_profile_ids: List[int],
                                               message_ids: List[int]) -> None:
    if len(message_ids) == 0:
        return

    # This function supports clearing notifications for several users
    # only for the message-edit use case where we'll have a single message_id.
    assert len(user_profile_ids) == 1 or len(message_ids) == 1

    messages_by_user = defaultdict(list)
    notifications_to_update = list(UserMessage.objects.filter(
        message_id__in=message_ids,
        user_profile_id__in=user_profile_ids,
    ).extra(
        where=[UserMessage.where_active_push_notification()],
    ).values_list('user_profile_id', 'message_id'))

    for (user_id, message_id) in notifications_to_update:
        messages_by_user[user_id].append(message_id)

    for (user_profile_id, event_message_ids) in messages_by_user.items():
        queue_json_publish("missedmessage_mobile_notifications", {
            "type": "remove",
            "user_profile_id": user_profile_id,
            "message_ids": event_message_ids,
        })

def do_update_message_flags(user_profile: UserProfile,
                            client: Client,
                            operation: str,
                            flag: str,
                            messages: List[int]) -> int:
    valid_flags = [item for item in UserMessage.flags
                   if item not in UserMessage.NON_API_FLAGS]
    if flag not in valid_flags:
        raise JsonableError(_("Invalid flag: '{}'").format(flag))
    if flag in UserMessage.NON_EDITABLE_FLAGS:
        raise JsonableError(_("Flag not editable: '{}'").format(flag))
    if operation not in ('add', 'remove'):
        raise JsonableError(_("Invalid message flag operation: '{}'").format(operation))
    flagattr = getattr(UserMessage.flags, flag)

    msgs = UserMessage.objects.filter(user_profile=user_profile,
                                      message__id__in=messages)
    # This next block allows you to star any message, even those you
    # didn't receive (e.g. because you're looking at a public stream
    # you're not subscribed to, etc.).  The problem is that starring
    # is a flag boolean on UserMessage, and UserMessage rows are
    # normally created only when you receive a message to support
    # searching your personal history.  So we need to create one.  We
    # add UserMessage.flags.historical, so that features that need
    # "messages you actually received" can exclude these UserMessages.
    if msgs.count() == 0:
        if not len(messages) == 1:
            raise JsonableError(_("Invalid message(s)"))
        if flag != "starred":
            raise JsonableError(_("Invalid message(s)"))
        # Validate that the user could have read the relevant message
        message = access_message(user_profile, messages[0])[0]

        # OK, this is a message that you legitimately have access
        # to via narrowing to the stream it is on, even though you
        # didn't actually receive it.  So we create a historical,
        # read UserMessage message row for you to star.
        UserMessage.objects.create(user_profile=user_profile,
                                   message=message,
                                   flags=UserMessage.flags.historical | UserMessage.flags.read)

    if operation == 'add':
        count = msgs.update(flags=F('flags').bitor(flagattr))
    elif operation == 'remove':
        count = msgs.update(flags=F('flags').bitand(~flagattr))

    event = {'type': 'update_message_flags',
             'op': operation,
             'operation': operation,
             'flag': flag,
             'messages': messages,
             'all': False}
    send_event(user_profile.realm, event, [user_profile.id])

    if flag == "read" and operation == "add":
        event_time = timezone_now()
        do_clear_mobile_push_notifications_for_ids([user_profile.id], messages)

        do_increment_logging_stat(user_profile, COUNT_STATS['messages_read::hour'],
                                  None, event_time, increment=count)
        do_increment_logging_stat(user_profile, COUNT_STATS['messages_read_interactions::hour'],
                                  None, event_time, increment=min(1, count))
    return count

class MessageUpdateUserInfoResult(TypedDict):
    message_user_ids: Set[int]
    mention_user_ids: Set[int]

def notify_topic_moved_streams(user_profile: UserProfile,
                               old_stream: Stream, old_topic: str,
                               new_stream: Stream, new_topic: Optional[str],
                               send_notification_to_old_thread: bool,
                               send_notification_to_new_thread: bool) -> None:
    # Since moving content between streams is highly disruptive,
    # it's worth adding a couple tombstone messages showing what
    # happened.
    sender = get_system_bot(settings.NOTIFICATION_BOT)

    if new_topic is None:
        new_topic = old_topic

    user_mention = f"@_**{user_profile.full_name}|{user_profile.id}**"
    old_topic_link = f"#**{old_stream.name}>{old_topic}**"
    new_topic_link = f"#**{new_stream.name}>{new_topic}**"
    if send_notification_to_new_thread:
        with override_language(new_stream.realm.default_language):
            internal_send_stream_message(
                new_stream.realm, sender, new_stream, new_topic,
                _("This topic was moved here from {old_location} by {user}").format(
                    old_location=old_topic_link, user=user_mention,
                ),
            )

    if send_notification_to_old_thread:
        with override_language(old_stream.realm.default_language):
            # Send a notification to the old stream that the topic was moved.
            internal_send_stream_message(
                old_stream.realm, sender, old_stream, old_topic,
                _("This topic was moved by {user} to {new_location}").format(
                    user=user_mention, new_location=new_topic_link,
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
    ).values('user_profile_id', 'flags')
    rows = list(query)

    message_user_ids = {
        row['user_profile_id']
        for row in rows
    }

    mask = UserMessage.flags.mentioned | UserMessage.flags.wildcard_mentioned

    mention_user_ids = {
        row['user_profile_id']
        for row in rows
        if int(row['flags']) & mask
    }

    return dict(
        message_user_ids=message_user_ids,
        mention_user_ids=mention_user_ids,
    )

def update_user_message_flags(message: Message, ums: Iterable[UserMessage]) -> None:
    wildcard = message.mentions_wildcard
    mentioned_ids = message.mentions_user_ids
    ids_with_alert_words = message.user_ids_with_alert_words
    changed_ums: Set[UserMessage] = set()

    def update_flag(um: UserMessage, should_set: bool, flag: int) -> None:
        if should_set:
            if not (um.flags & flag):
                um.flags |= flag
                changed_ums.add(um)
        else:
            if (um.flags & flag):
                um.flags &= ~flag
                changed_ums.add(um)

    for um in ums:
        has_alert_word = um.user_profile_id in ids_with_alert_words
        update_flag(um, has_alert_word, UserMessage.flags.has_alert_word)

        mentioned = um.user_profile_id in mentioned_ids
        update_flag(um, mentioned, UserMessage.flags.mentioned)

        update_flag(um, wildcard, UserMessage.flags.wildcard_mentioned)

    for um in changed_ums:
        um.save(update_fields=['flags'])

def update_to_dict_cache(changed_messages: List[Message], realm_id: Optional[int]=None) -> List[int]:
    """Updates the message as stored in the to_dict cache (for serving
    messages)."""
    items_for_remote_cache = {}
    message_ids = []
    changed_messages_to_dict = MessageDict.to_dict_uncached(changed_messages, realm_id)
    for msg_id, msg in changed_messages_to_dict.items():
        message_ids.append(msg_id)
        key = to_dict_cache_key_id(msg_id)
        items_for_remote_cache[key] = (msg,)

    cache_set_many(items_for_remote_cache)
    return message_ids

# We use transaction.atomic to support select_for_update in the attachment codepath.
@transaction.atomic
def do_update_embedded_data(user_profile: UserProfile,
                            message: Message,
                            content: Optional[str],
                            rendered_content: Optional[str]) -> None:
    event: Dict[str, Any] = {
        'type': 'update_message',
        'message_id': message.id}
    changed_messages = [message]

    ums = UserMessage.objects.filter(message=message.id)

    if content is not None:
        update_user_message_flags(message, ums)
        message.content = content
        message.rendered_content = rendered_content
        message.rendered_content_version = markdown_version
        event["content"] = content
        event["rendered_content"] = rendered_content

    message.save(update_fields=["content", "rendered_content"])

    event['message_ids'] = update_to_dict_cache(changed_messages)

    def user_info(um: UserMessage) -> Dict[str, Any]:
        return {
            'id': um.user_profile_id,
            'flags': um.flags_list(),
        }
    send_event(user_profile.realm, event, list(map(user_info, ums)))

class DeleteMessagesEvent(TypedDict, total=False):
    type: str
    message_ids: List[int]
    message_type: str
    sender_id: int
    recipient_id: int
    topic: str
    stream_id: int

# We use transaction.atomic to support select_for_update in the attachment codepath.
@transaction.atomic
def do_update_message(user_profile: UserProfile, message: Message,
                      new_stream: Optional[Stream], topic_name: Optional[str],
                      propagate_mode: str, send_notification_to_old_thread: bool,
                      send_notification_to_new_thread: bool, content: Optional[str],
                      rendered_content: Optional[str], prior_mention_user_ids: Set[int],
                      mention_user_ids: Set[int], mention_data: Optional[MentionData]=None) -> int:
    """
    The main function for message editing.  A message edit event can
    modify:
    * the message's content (in which case the caller will have
      set both content and rendered_content),
    * the topic, in which case the caller will have set topic_name
    * or both

    With topic edits, propagate_mode determines whether other message
    also have their topics edited.
    """
    timestamp = timezone_now()
    message.last_edit_time = timestamp

    event: Dict[str, Any] = {
        'type': 'update_message',
        'user_id': user_profile.id,
        'edit_timestamp': datetime_to_timestamp(timestamp),
        'message_id': message.id,
    }

    edit_history_event: Dict[str, Any] = {
        'user_id': user_profile.id,
        'timestamp': event['edit_timestamp'],
    }

    changed_messages = [message]

    stream_being_edited = None
    if message.is_stream_message():
        stream_id = message.recipient.type_id
        stream_being_edited = get_stream_by_id_in_realm(stream_id, user_profile.realm)
        event['stream_name'] = stream_being_edited.name

    ums = UserMessage.objects.filter(message=message.id)

    if content is not None:
        assert rendered_content is not None

        # mention_data is required if there's a content edit.
        assert mention_data is not None

        # add data from group mentions to mentions_user_ids.
        for group_id in message.mentions_user_group_ids:
            members = mention_data.get_group_members(group_id)
            message.mentions_user_ids.update(members)

        update_user_message_flags(message, ums)

        # One could imagine checking realm.allow_edit_history here and
        # modifying the events based on that setting, but doing so
        # doesn't really make sense.  We need to send the edit event
        # to clients regardless, and a client already had access to
        # the original/pre-edit content of the message anyway.  That
        # setting must be enforced on the client side, and making a
        # change here simply complicates the logic for clients parsing
        # edit history events.
        event['orig_content'] = message.content
        event['orig_rendered_content'] = message.rendered_content
        edit_history_event["prev_content"] = message.content
        edit_history_event["prev_rendered_content"] = message.rendered_content
        edit_history_event["prev_rendered_content_version"] = message.rendered_content_version
        message.content = content
        message.rendered_content = rendered_content
        message.rendered_content_version = markdown_version
        event["content"] = content
        event["rendered_content"] = rendered_content
        event['prev_rendered_content_version'] = message.rendered_content_version
        event['is_me_message'] = Message.is_status_message(content, rendered_content)

        # message.has_image and message.has_link will have been
        # already updated by Markdown rendering in the caller.
        message.has_attachment = check_attachment_reference_change(message)

        if message.is_stream_message():
            if topic_name is not None:
                new_topic_name = topic_name
            else:
                new_topic_name = message.topic_name()

            stream_topic: Optional[StreamTopicTarget] = StreamTopicTarget(
                stream_id=stream_id,
                topic_name=new_topic_name,
            )
        else:
            stream_topic = None

        info = get_recipient_info(
            recipient=message.recipient,
            sender_id=message.sender_id,
            stream_topic=stream_topic,
            possible_wildcard_mention=mention_data.message_has_wildcards(),
        )

        event['push_notify_user_ids'] = list(info['push_notify_user_ids'])
        event['stream_push_user_ids'] = list(info['stream_push_user_ids'])
        event['stream_email_user_ids'] = list(info['stream_email_user_ids'])
        event['prior_mention_user_ids'] = list(prior_mention_user_ids)
        event['mention_user_ids'] = list(mention_user_ids)
        event['presence_idle_user_ids'] = filter_presence_idle_user_ids(info['active_user_ids'])
        if message.mentions_wildcard:
            event['wildcard_mention_user_ids'] = list(info['wildcard_mention_user_ids'])
        else:
            event['wildcard_mention_user_ids'] = []

        do_update_mobile_push_notification(message, prior_mention_user_ids, info['stream_push_user_ids'])

    if topic_name is not None or new_stream is not None:
        orig_topic_name = message.topic_name()
        event["propagate_mode"] = propagate_mode
        event["stream_id"] = message.recipient.type_id

    if new_stream is not None:
        assert content is None
        assert message.is_stream_message()
        assert stream_being_edited is not None

        edit_history_event['prev_stream'] = stream_being_edited.id
        event[ORIG_TOPIC] = orig_topic_name
        message.recipient_id = new_stream.recipient_id

        event["new_stream_id"] = new_stream.id
        event["propagate_mode"] = propagate_mode

        # When messages are moved from one stream to another, some
        # users may lose access to those messages, including guest
        # users and users not subscribed to the new stream (if it is a
        # private stream).  For those users, their experience is as
        # though the messages were deleted, and we should send a
        # delete_message event to them instead.

        subscribers = get_active_subscriptions_for_stream_id(
            stream_id).select_related("user_profile")
        subs_to_new_stream = list(get_active_subscriptions_for_stream_id(
            new_stream.id).select_related("user_profile"))

        old_stream_sub_ids = [user.user_profile_id for user in subscribers]
        new_stream_sub_ids = [user.user_profile_id for user in subs_to_new_stream]

        # Get users who aren't subscribed to the new_stream.
        subs_losing_usermessages  = [
            sub for sub in subscribers
            if sub.user_profile_id not in new_stream_sub_ids
        ]
        # Users who can longer access the message without some action
        # from administrators.
        subs_losing_access = [
            sub for sub in subs_losing_usermessages
            if sub.user_profile.is_guest or not new_stream.is_public()
        ]
        ums = ums.exclude(user_profile_id__in=[
            sub.user_profile_id for sub in subs_losing_usermessages])

        subs_gaining_usermessages = []
        if not new_stream.is_history_public_to_subscribers():
            # For private streams, with history not public to subscribers,
            # We find out users who are not present in the msgs' old stream
            # and create new UserMessage for these users so that they can
            # access this message.
            subs_gaining_usermessages += [
                user_id for user_id in new_stream_sub_ids
                if user_id not in old_stream_sub_ids
            ]

    if topic_name is not None:
        topic_name = truncate_topic(topic_name)
        message.set_topic_name(topic_name)

        # These fields have legacy field names.
        event[ORIG_TOPIC] = orig_topic_name
        event[TOPIC_NAME] = topic_name
        event[TOPIC_LINKS] = topic_links(message.sender.realm_id, topic_name)
        edit_history_event[LEGACY_PREV_TOPIC] = orig_topic_name

    delete_event_notify_user_ids: List[int] = []
    if propagate_mode in ["change_later", "change_all"]:
        assert topic_name is not None or new_stream is not None
        messages_list = update_messages_for_topic_edit(
            message=message,
            propagate_mode=propagate_mode,
            orig_topic_name=orig_topic_name,
            topic_name=topic_name,
            new_stream=new_stream,
        )
        changed_messages += messages_list

        if new_stream is not None:
            assert stream_being_edited is not None

            if subs_gaining_usermessages:
                ums_to_create = []
                for msg in changed_messages:
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
                            message_id=msg.id,
                            flags=UserMessage.flags.read,
                        )
                        ums_to_create.append(um)
                bulk_insert_ums(ums_to_create)

            message_ids = [msg.id for msg in changed_messages]
            # Delete UserMessage objects for users who will no
            # longer have access to these messages.  Note: This could be
            # very expensive, since it's N guest users x M messages.
            UserMessage.objects.filter(
                user_profile_id__in=[sub.user_profile_id for sub in
                                     subs_losing_usermessages],
                message_id__in=message_ids,
            ).delete()

            delete_event: DeleteMessagesEvent = {
                'type': 'delete_message',
                'message_ids': message_ids,
                'message_type': 'stream',
                'stream_id': stream_being_edited.id,
                'topic': orig_topic_name,
            }
            delete_event_notify_user_ids = [sub.user_profile_id for sub in subs_losing_access]
            send_event(user_profile.realm, delete_event, delete_event_notify_user_ids)

    if message.edit_history is not None:
        edit_history = orjson.loads(message.edit_history)
        edit_history.insert(0, edit_history_event)
    else:
        edit_history = [edit_history_event]
    message.edit_history = orjson.dumps(edit_history).decode()

    # This does message.save(update_fields=[...])
    save_message_for_edit_use_case(message=message)

    realm_id: Optional[int] = None
    if stream_being_edited is not None:
        realm_id = stream_being_edited.realm_id

    event['message_ids'] = update_to_dict_cache(changed_messages, realm_id)

    def user_info(um: UserMessage) -> Dict[str, Any]:
        return {
            'id': um.user_profile_id,
            'flags': um.flags_list(),
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
            subscribers = get_active_subscriptions_for_stream_id(stream_id)
            # We exclude long-term idle users, since they by
            # definition have no active clients.
            subscribers = subscribers.exclude(user_profile__long_term_idle=True)
            # Remove duplicates by excluding the id of users already
            # in users_to_be_notified list.  This is the case where a
            # user both has a UserMessage row and is a current
            # Subscriber
            subscribers = subscribers.exclude(user_profile_id__in=[um.user_profile_id for um in ums])

            if new_stream is not None:
                assert delete_event_notify_user_ids is not None
                subscribers = subscribers.exclude(user_profile_id__in=delete_event_notify_user_ids)

            # All users that are subscribed to the stream must be
            # notified when a message is edited
            subscriber_ids = [user.user_profile_id for user in subscribers]

            if new_stream is not None:
                # TODO: Guest users don't see the new moved topic
                # unless breadcrumb message for new stream is
                # enabled. Excluding these users from receiving this
                # event helps us avoid a error trackeback for our
                # clients. We should figure out a way to inform the
                # guest users of this new topic if sending a 'message'
                # event for these messages is not an option.
                #
                # Don't send this event to guest subs who are not
                # subscribers of the old stream but are subscribed to
                # the new stream; clients will be confused.
                old_stream_unsubbed_guests = [
                    sub for sub in subs_to_new_stream
                    if sub.user_profile.is_guest
                    and sub.user_profile_id not in subscriber_ids
                ]
                subscribers = subscribers.exclude(user_profile_id__in=[
                    sub.user_profile_id for sub in old_stream_unsubbed_guests])
                subscriber_ids = [user.user_profile_id for user in subscribers]

            users_to_be_notified += list(map(subscriber_info, subscriber_ids))

    send_event(user_profile.realm, event, users_to_be_notified)

    if (len(changed_messages) > 0 and new_stream is not None and
            stream_being_edited is not None):
        # Notify users that the topic was moved.
        notify_topic_moved_streams(user_profile, stream_being_edited, orig_topic_name,
                                   new_stream, topic_name, send_notification_to_old_thread,
                                   send_notification_to_new_thread)

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
        'type': 'delete_message',
        'message_ids': message_ids,
    }

    sample_message = messages[0]
    message_type = "stream"
    users_to_notify = []
    if not sample_message.is_stream_message():
        assert len(messages) == 1
        message_type = "private"
        ums = UserMessage.objects.filter(message_id__in=message_ids)
        users_to_notify = [um.user_profile_id for um in ums]
        # TODO: We should plan to remove `sender_id` here.
        event['recipient_id'] = sample_message.recipient_id
        event['sender_id'] = sample_message.sender_id
        archiving_chunk_size = retention.MESSAGE_BATCH_SIZE

    if message_type == "stream":
        stream_id = sample_message.recipient.type_id
        event['stream_id'] = stream_id
        event['topic'] = sample_message.topic_name()
        subscribers = get_active_subscriptions_for_stream_id(stream_id)
        # We exclude long-term idle users, since they by definition have no active clients.
        subscribers = subscribers.exclude(user_profile__long_term_idle=True)
        subscriber_ids = [user.user_profile_id for user in subscribers]
        users_to_notify = list(map(subscriber_info, subscriber_ids))
        archiving_chunk_size = retention.STREAM_MESSAGE_BATCH_SIZE

    move_messages_to_archive(message_ids, realm=realm, chunk_size=archiving_chunk_size)

    event['message_type'] = message_type
    send_event(realm, event, users_to_notify)

def do_delete_messages_by_sender(user: UserProfile) -> None:
    message_ids = list(Message.objects.filter(sender=user).values_list('id', flat=True).order_by('id'))
    if message_ids:
        move_messages_to_archive(message_ids, chunk_size=retention.STREAM_MESSAGE_BATCH_SIZE)

def get_streams_traffic(stream_ids: Set[int]) -> Dict[int, int]:
    stat = COUNT_STATS['messages_in_stream:is_bot:day']
    traffic_from = timezone_now() - datetime.timedelta(days=28)

    query = StreamCount.objects.filter(property=stat.property,
                                       end_time__gt=traffic_from)
    query = query.filter(stream_id__in=stream_ids)

    traffic_list = query.values('stream_id').annotate(value=Sum('value'))
    traffic_dict = {}
    for traffic in traffic_list:
        traffic_dict[traffic["stream_id"]] = traffic["value"]

    return traffic_dict

def round_to_2_significant_digits(number: int) -> int:
    return int(round(number, 2 - len(str(number))))

STREAM_TRAFFIC_CALCULATION_MIN_AGE_DAYS = 7

def get_average_weekly_stream_traffic(stream_id: int, stream_date_created: datetime.datetime,
                                      recent_traffic: Dict[int, int]) -> Optional[int]:
    try:
        stream_traffic = recent_traffic[stream_id]
    except KeyError:
        stream_traffic = 0

    stream_age = (timezone_now() - stream_date_created).days

    if stream_age >= 28:
        average_weekly_traffic = int(stream_traffic // 4)
    elif stream_age >= STREAM_TRAFFIC_CALCULATION_MIN_AGE_DAYS:
        average_weekly_traffic = int(stream_traffic * 7 // stream_age)
    else:
        return None

    if average_weekly_traffic == 0 and stream_traffic > 0:
        average_weekly_traffic = 1

    return round_to_2_significant_digits(average_weekly_traffic)

SubHelperT = Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]

def get_web_public_subs(realm: Realm) -> SubHelperT:
    color_idx = 0

    def get_next_color() -> str:
        nonlocal color_idx
        color = STREAM_ASSIGNMENT_COLORS[color_idx]
        color_idx = (color_idx + 1) % len(STREAM_ASSIGNMENT_COLORS)
        return color

    subscribed = []
    for stream in Stream.objects.filter(realm=realm, is_web_public=True, deactivated=False):
        stream_dict = stream.to_dict()

        # Add versions of the Subscription fields based on a simulated
        # new user subscription set.
        stream_dict['is_muted'] = False
        stream_dict['color'] = get_next_color()
        stream_dict['desktop_notifications'] = True
        stream_dict['audible_notifications'] = True
        stream_dict['push_notifications'] = True
        stream_dict['email_notifications'] = True
        stream_dict['pin_to_top'] = False
        stream_weekly_traffic = get_average_weekly_stream_traffic(stream.id,
                                                                  stream.date_created,
                                                                  {})
        stream_dict['stream_weekly_traffic'] = stream_weekly_traffic
        stream_dict['email_address'] = ''
        subscribed.append(stream_dict)

    return (subscribed, [], [])

def build_stream_dict_for_sub(
    user: UserProfile,
    sub: Subscription,
    stream: Stream,
    subscribers: Optional[List[int]],
    recent_traffic: Dict[int, int],
) -> Dict[str, object]:
    # We first construct a dictionary based on the standard Stream
    # and Subscription models' API_FIELDS.
    result = {}
    for field_name in Stream.API_FIELDS:
        if field_name == "id":
            result["stream_id"] = stream["id"]
            continue
        elif field_name == "date_created":
            result["date_created"] = datetime_to_timestamp(stream[field_name])
            continue
        result[field_name] = stream[field_name]

    # Copy Subscription.API_FIELDS.
    for field_name in Subscription.API_FIELDS:
        result[field_name] = sub[field_name]

    # Backwards-compatibility for clients that haven't been
    # updated for the in_home_view => is_muted API migration.
    result["in_home_view"] = not result["is_muted"]

    # Backwards-compatibility for clients that haven't been
    # updated for the is_announcement_only -> stream_post_policy
    # migration.
    result["is_announcement_only"] = \
        stream["stream_post_policy"] == Stream.STREAM_POST_POLICY_ADMINS

    # Add a few computed fields not directly from the data models.
    result["stream_weekly_traffic"] = get_average_weekly_stream_traffic(
        stream["id"], stream["date_created"], recent_traffic)

    result["email_address"] = encode_email_address_helper(
        stream["name"], stream["email_token"], show_sender=True)

    # Important: don't show the subscribers if the stream is invite only
    # and this user isn't on it anymore (or a realm administrator).
    if stream["invite_only"] and not (sub["active"] or user.is_realm_admin):
        subscribers = None

    # Guest users lose access to subscribers when they are unsubscribed if the stream
    # is not web-public.
    if not sub["active"] and user.is_guest and not stream["is_web_public"]:
        subscribers = None
    if subscribers is not None:
        result["subscribers"] = subscribers

    return result

def build_stream_dict_for_never_sub(
    stream: Stream,
    subscribers: Optional[List[int]],
    recent_traffic: Dict[int, int],
) -> Dict[str, object]:
    result = {}
    for field_name in Stream.API_FIELDS:
        if field_name == "id":
            result["stream_id"] = stream["id"]
            continue
        elif field_name == "date_created":
            result["date_created"] = datetime_to_timestamp(stream[field_name])
            continue
        result[field_name] = stream[field_name]

    result["stream_weekly_traffic"] = get_average_weekly_stream_traffic(
        stream["id"], stream["date_created"], recent_traffic)

    # Backwards-compatibility addition of removed field.
    result["is_announcement_only"] = stream["stream_post_policy"] == Stream.STREAM_POST_POLICY_ADMINS

    if subscribers is not None:
        result["subscribers"] = subscribers

    return result

# In general, it's better to avoid using .values() because it makes
# the code pretty ugly, but in this case, it has significant
# performance impact for loading / for users with large numbers of
# subscriptions, so it's worth optimizing.
def gather_subscriptions_helper(user_profile: UserProfile,
                                include_subscribers: bool=True) -> SubHelperT:
    realm = user_profile.realm
    all_streams = get_active_streams(realm).values(
        *Stream.API_FIELDS,
        # The realm_id and recipient_id are generally not needed in the API.
        "realm_id",
        "recipient_id",
        # email_token isn't public to some users with access to
        # the stream, so doesn't belong in API_FIELDS.
        "email_token",
    )
    recip_id_to_stream_id = {stream["recipient_id"]: stream["id"] for stream in all_streams}
    all_streams_map = {stream["id"]: stream for stream in all_streams}

    sub_dicts = get_stream_subscriptions_for_user(user_profile).values(
        *Subscription.API_FIELDS,
        "recipient_id",
        "active",
    ).order_by("recipient_id")

    # We only care about subscriptions for active streams.
    sub_dicts = [
        sub for sub in sub_dicts
        if recip_id_to_stream_id.get(sub["recipient_id"])
    ]

    def get_stream_id(sub: Subscription) -> int:
        return recip_id_to_stream_id[sub["recipient_id"]]

    traffic_stream_ids = {get_stream_id(sub) for sub in sub_dicts}
    recent_traffic = get_streams_traffic(stream_ids=traffic_stream_ids)

    # The highly optimized bulk_get_subscriber_user_ids wants to know which
    # streams we are subscribed to, for validation purposes, and it uses that
    # info to know if it's allowed to find OTHER subscribers.
    subscribed_stream_ids = {get_stream_id(sub) for sub in sub_dicts if sub["active"]}

    if include_subscribers:
        subscriber_map: Mapping[int, Optional[List[int]]] = bulk_get_subscriber_user_ids(
            all_streams,
            user_profile,
            subscribed_stream_ids,
        )
    else:
        # If we're not including subscribers, always return None,
        # which the below code needs to check for anyway.
        subscriber_map = defaultdict(lambda: None)

    # Okay, now we finally get to populating our main results, which
    # will be these three lists.
    subscribed = []
    unsubscribed = []
    never_subscribed = []

    sub_unsub_stream_ids = set()
    for sub in sub_dicts:
        stream_id = get_stream_id(sub)
        sub_unsub_stream_ids.add(stream_id)
        stream = all_streams_map[stream_id]

        stream_dict = build_stream_dict_for_sub(
            user=user_profile,
            sub=sub,
            stream=stream,
            subscribers=subscriber_map[stream_id],
            recent_traffic=recent_traffic,
        )

        # is_active is represented in this structure by which list we include it in.
        is_active = sub["active"]
        if is_active:
            subscribed.append(stream_dict)
        else:
            unsubscribed.append(stream_dict)

    if user_profile.can_access_public_streams():
        never_subscribed_stream_ids = set(all_streams_map) - sub_unsub_stream_ids
    else:
        web_public_stream_ids = {stream['id'] for stream in all_streams if stream['is_web_public']}
        never_subscribed_stream_ids = web_public_stream_ids - sub_unsub_stream_ids

    never_subscribed_streams = [
        all_streams_map[stream_id]
        for stream_id in never_subscribed_stream_ids
    ]

    for stream in never_subscribed_streams:
        is_public = not stream['invite_only']
        if is_public or user_profile.is_realm_admin:
            stream_dict = build_stream_dict_for_never_sub(
                stream=stream,
                subscribers=subscriber_map[stream["id"]],
                recent_traffic=recent_traffic
            )

            never_subscribed.append(stream_dict)

    return (sorted(subscribed, key=lambda x: x['name']),
            sorted(unsubscribed, key=lambda x: x['name']),
            sorted(never_subscribed, key=lambda x: x['name']))

def gather_subscriptions(
    user_profile: UserProfile,
    include_subscribers: bool=False,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    subscribed, unsubscribed, _ = gather_subscriptions_helper(
        user_profile, include_subscribers=include_subscribers)

    if include_subscribers:
        user_ids = set()
        for subs in [subscribed, unsubscribed]:
            for sub in subs:
                if 'subscribers' in sub:
                    for subscriber in sub['subscribers']:
                        user_ids.add(subscriber)
        email_dict = get_emails_from_user_ids(list(user_ids))

        for subs in [subscribed, unsubscribed]:
            for sub in subs:
                if 'subscribers' in sub:
                    sub['subscribers'] = sorted(
                        email_dict[user_id] for user_id in sub['subscribers']
                    )

    return (subscribed, unsubscribed)

def get_active_presence_idle_user_ids(realm: Realm,
                                      sender_id: int,
                                      message_type: str,
                                      active_user_ids: Set[int],
                                      user_flags: Dict[int, List[str]]) -> List[int]:
    '''
    Given a list of active_user_ids, we build up a subset
    of those users who fit these criteria:

        * They are likely to need notifications (either due
          to mentions, alert words, or being PM'ed).
        * They are no longer "present" according to the
          UserPresence table.
    '''

    if realm.presence_disabled:
        return []

    is_pm = message_type == 'private'

    user_ids = set()
    for user_id in active_user_ids:
        flags: Iterable[str] = user_flags.get(user_id, [])
        mentioned = 'mentioned' in flags or 'wildcard_mentioned' in flags
        private_message = is_pm and user_id != sender_id
        alerted = 'has_alert_word' in flags
        if mentioned or private_message or alerted:
            user_ids.add(user_id)

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
    rows = UserPresence.objects.filter(
        user_profile_id__in=user_ids,
        status=UserPresence.ACTIVE,
        timestamp__gte=recent,
    ).exclude(client__name="ZulipMobile").distinct('user_profile_id').values('user_profile_id')
    active_user_ids = {row['user_profile_id'] for row in rows}
    idle_user_ids = user_ids - active_user_ids
    return sorted(idle_user_ids)

def do_send_confirmation_email(invitee: PreregistrationUser,
                               referrer: UserProfile) -> str:
    """
    Send the confirmation/welcome e-mail to an invited user.
    """
    activation_url = create_confirmation_link(invitee, Confirmation.INVITATION)
    context = {'referrer_full_name': referrer.full_name, 'referrer_email': referrer.delivery_email,
               'activate_url': activation_url, 'referrer_realm_name': referrer.realm.name}
    from_name = f"{referrer.full_name} (via Zulip)"
    send_email('zerver/emails/invitation', to_emails=[invitee.email], from_name=from_name,
               from_address=FromAddress.tokenized_no_reply_address(),
               language=referrer.realm.default_language, context=context,
               realm=referrer.realm)
    return activation_url

def email_not_system_bot(email: str) -> None:
    if is_cross_realm_bot_email(email):
        msg = email_reserved_for_system_bots_error(email)
        code = msg
        raise ValidationError(
            msg,
            code=code,
            params=dict(deactivated=False),
        )

class InvitationError(JsonableError):
    code = ErrorCode.INVITATION_FAILED
    data_fields = ['errors', 'sent_invitations']

    def __init__(self, msg: str, errors: List[Tuple[str, str, bool]],
                 sent_invitations: bool) -> None:
        self._msg: str = msg
        self.errors: List[Tuple[str, str, bool]] = errors
        self.sent_invitations: bool = sent_invitations

def estimate_recent_invites(realms: Iterable[Realm], *, days: int) -> int:
    '''An upper bound on the number of invites sent in the last `days` days'''
    recent_invites = RealmCount.objects.filter(
        realm__in=realms,
        property='invites_sent::day',
        end_time__gte=timezone_now() - datetime.timedelta(days=days),
    ).aggregate(Sum('value'))['value__sum']
    if recent_invites is None:
        return 0
    return recent_invites

def check_invite_limit(realm: Realm, num_invitees: int) -> None:
    '''Discourage using invitation emails as a vector for carrying spam.'''
    msg = _("You do not have enough remaining invites. "
            "Please contact {email} to have your limit raised. "
            "No invitations were sent.").format(email=settings.ZULIP_ADMINISTRATOR)
    if not settings.OPEN_REALM_CREATION:
        return

    recent_invites = estimate_recent_invites([realm], days=1)
    if num_invitees + recent_invites > realm.max_invites:
        raise InvitationError(msg, [], sent_invitations=False)

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
            raise InvitationError(msg, [], sent_invitations=False)

def do_invite_users(user_profile: UserProfile,
                    invitee_emails: SizedTextIterable,
                    streams: Iterable[Stream],
                    invite_as: int=PreregistrationUser.INVITE_AS['MEMBER']) -> None:

    check_invite_limit(user_profile.realm, len(invitee_emails))

    realm = user_profile.realm
    if not realm.invite_required:
        # Inhibit joining an open realm to send spam invitations.
        min_age = datetime.timedelta(days=settings.INVITES_MIN_USER_AGE_DAYS)
        if (user_profile.date_joined > timezone_now() - min_age
                and not user_profile.is_realm_admin):
            raise InvitationError(
                _("Your account is too new to send invites for this organization. "
                  "Ask an organization admin, or a more experienced user."),
                [], sent_invitations=False)

    good_emails: Set[str] = set()
    errors: List[Tuple[str, str, bool]] = []
    validate_email_allowed_in_realm = get_realm_email_validator(user_profile.realm)
    for email in invitee_emails:
        if email == '':
            continue
        email_error = validate_email_is_valid(
            email,
            validate_email_allowed_in_realm,
        )

        if email_error:
            errors.append((email, email_error, False))
        else:
            good_emails.add(email)

    '''
    good_emails are emails that look ok so far,
    but we still need to make sure they're not
    gonna conflict with existing users
    '''
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
            errors + skipped, sent_invitations=False)

    if skipped and len(skipped) == len(invitee_emails):
        # All e-mails were skipped, so we didn't actually invite anyone.
        raise InvitationError(_("We weren't able to invite anyone."),
                              skipped, sent_invitations=False)

    # We do this here rather than in the invite queue processor since this
    # is used for rate limiting invitations, rather than keeping track of
    # when exactly invitations were sent
    do_increment_logging_stat(user_profile.realm, COUNT_STATS['invites_sent::day'],
                              None, timezone_now(), increment=len(validated_emails))

    # Now that we are past all the possible errors, we actually create
    # the PreregistrationUser objects and trigger the email invitations.
    for email in validated_emails:
        # The logged in user is the referrer.
        prereg_user = PreregistrationUser(email=email, referred_by=user_profile,
                                          invited_as=invite_as,
                                          realm=user_profile.realm)
        prereg_user.save()
        stream_ids = [stream.id for stream in streams]
        prereg_user.streams.set(stream_ids)

        event = {"prereg_id": prereg_user.id, "referrer_id": user_profile.id}
        queue_json_publish("invites", event)

    if skipped:
        raise InvitationError(_("Some of those addresses are already using Zulip, "
                                "so we didn't send them an invitation. We did send "
                                "invitations to everyone else!"),
                              skipped, sent_invitations=True)
    notify_invites_changed(user_profile)

def do_get_user_invites(user_profile: UserProfile) -> List[Dict[str, Any]]:
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
        invites.append(dict(email=invitee.email,
                            invited_by_user_id=invitee.referred_by.id,
                            invited=datetime_to_timestamp(invitee.invited_at),
                            id=invitee.id,
                            invited_as=invitee.invited_as,
                            is_multiuse=False))

    if not user_profile.is_realm_admin:
        # We do not return multiuse invites to non-admin users.
        return invites

    lowest_datetime = timezone_now() - datetime.timedelta(days=settings.INVITATION_LINK_VALIDITY_DAYS)
    multiuse_confirmation_objs = Confirmation.objects.filter(realm=user_profile.realm,
                                                             type=Confirmation.MULTIUSE_INVITE,
                                                             date_sent__gte=lowest_datetime)
    for confirmation_obj in multiuse_confirmation_objs:
        invite = confirmation_obj.content_object
        invites.append(dict(invited_by_user_id=invite.referred_by.id,
                            invited=datetime_to_timestamp(confirmation_obj.date_sent),
                            id=invite.id,
                            link_url=confirmation_url(confirmation_obj.confirmation_key,
                                                      user_profile.realm,
                                                      Confirmation.MULTIUSE_INVITE),
                            invited_as=invite.invited_as,
                            is_multiuse=True))
    return invites

def do_create_multiuse_invite_link(referred_by: UserProfile, invited_as: int,
                                   streams: Sequence[Stream] = []) -> str:
    realm = referred_by.realm
    invite = MultiuseInvite.objects.create(realm=realm, referred_by=referred_by)
    if streams:
        invite.streams.set(streams)
    invite.invited_as = invited_as
    invite.save()
    notify_invites_changed(referred_by)
    return create_confirmation_link(invite, Confirmation.MULTIUSE_INVITE)

def do_revoke_user_invite(prereg_user: PreregistrationUser) -> None:
    email = prereg_user.email

    # Delete both the confirmation objects and the prereg_user object.
    # TODO: Probably we actually want to set the confirmation objects
    # to a "revoked" status so that we can give the invited user a better
    # error message.
    content_type = ContentType.objects.get_for_model(PreregistrationUser)
    Confirmation.objects.filter(content_type=content_type,
                                object_id=prereg_user.id).delete()
    prereg_user.delete()
    clear_scheduled_invitation_emails(email)
    notify_invites_changed(prereg_user)

def do_revoke_multi_use_invite(multiuse_invite: MultiuseInvite) -> None:
    content_type = ContentType.objects.get_for_model(MultiuseInvite)
    Confirmation.objects.filter(content_type=content_type,
                                object_id=multiuse_invite.id).delete()
    multiuse_invite.delete()
    notify_invites_changed(multiuse_invite.referred_by)

def do_resend_user_invite_email(prereg_user: PreregistrationUser) -> int:
    # These are two structurally for the caller's code path.
    assert prereg_user.referred_by is not None
    assert prereg_user.realm is not None

    check_invite_limit(prereg_user.referred_by.realm, 1)

    prereg_user.invited_at = timezone_now()
    prereg_user.save()

    do_increment_logging_stat(prereg_user.realm, COUNT_STATS['invites_sent::day'],
                              None, prereg_user.invited_at)

    clear_scheduled_invitation_emails(prereg_user.email)
    # We don't store the custom email body, so just set it to None
    event = {"prereg_id": prereg_user.id, "referrer_id": prereg_user.referred_by.id, "email_body": None}
    queue_json_publish("invites", event)

    return datetime_to_timestamp(prereg_user.invited_at)

def notify_realm_emoji(realm: Realm) -> None:
    event = dict(type="realm_emoji", op="update",
                 realm_emoji=realm.get_emoji())
    send_event(realm, event, active_user_ids(realm.id))

def check_add_realm_emoji(realm: Realm,
                          name: str,
                          author: UserProfile,
                          image_file: File) -> Optional[RealmEmoji]:
    realm_emoji = RealmEmoji(realm=realm, name=name, author=author)
    realm_emoji.full_clean()
    realm_emoji.save()

    emoji_file_name = get_emoji_file_name(image_file.name, realm_emoji.id)

    # The only user-controlled portion of 'emoji_file_name' is an extension,
    # which can not contain '..' or '/' or '\', making it difficult to exploit
    emoji_file_name = mark_sanitized(emoji_file_name)

    emoji_uploaded_successfully = False
    try:
        upload_emoji_image(image_file, emoji_file_name, author)
        emoji_uploaded_successfully = True
    finally:
        if not emoji_uploaded_successfully:
            realm_emoji.delete()
            return None
        else:
            realm_emoji.file_name = emoji_file_name
            realm_emoji.save(update_fields=['file_name'])
            notify_realm_emoji(realm_emoji.realm)
    return realm_emoji

def do_remove_realm_emoji(realm: Realm, name: str) -> None:
    emoji = RealmEmoji.objects.get(realm=realm, name=name, deactivated=False)
    emoji.deactivated = True
    emoji.save(update_fields=['deactivated'])
    notify_realm_emoji(realm)

def notify_alert_words(user_profile: UserProfile, words: Iterable[str]) -> None:
    event = dict(type="alert_words", alert_words=words)
    send_event(user_profile.realm, event, [user_profile.id])

def do_add_alert_words(user_profile: UserProfile, alert_words: Iterable[str]) -> None:
    words = add_user_alert_words(user_profile, alert_words)
    notify_alert_words(user_profile, words)

def do_remove_alert_words(user_profile: UserProfile, alert_words: Iterable[str]) -> None:
    words = remove_user_alert_words(user_profile, alert_words)
    notify_alert_words(user_profile, words)

def do_mute_topic(
    user_profile: UserProfile,
    stream: Stream,
    topic: str,
    date_muted: Optional[datetime.datetime]=None
) -> None:
    if date_muted is None:
        date_muted = timezone_now()
    add_topic_mute(user_profile, stream.id, stream.recipient_id, topic, date_muted)
    event = dict(type="muted_topics", muted_topics=get_topic_mutes(user_profile))
    send_event(user_profile.realm, event, [user_profile.id])

def do_unmute_topic(user_profile: UserProfile, stream: Stream, topic: str) -> None:
    remove_topic_mute(user_profile, stream.id, topic)
    event = dict(type="muted_topics", muted_topics=get_topic_mutes(user_profile))
    send_event(user_profile.realm, event, [user_profile.id])

def do_mark_hotspot_as_read(user: UserProfile, hotspot: str) -> None:
    UserHotspot.objects.get_or_create(user=user, hotspot=hotspot)
    event = dict(type="hotspots", hotspots=get_next_hotspots(user))
    send_event(user.realm, event, [user.id])

def notify_realm_filters(realm: Realm) -> None:
    realm_filters = realm_filters_for_realm(realm.id)
    event = dict(type="realm_filters", realm_filters=realm_filters)
    send_event(realm, event, active_user_ids(realm.id))

# NOTE: Regexes must be simple enough that they can be easily translated to JavaScript
# RegExp syntax. In addition to JS-compatible syntax, the following features are available:
#   * Named groups will be converted to numbered groups automatically
#   * Inline-regex flags will be stripped, and where possible translated to RegExp-wide flags
def do_add_realm_filter(realm: Realm, pattern: str, url_format_string: str) -> int:
    pattern = pattern.strip()
    url_format_string = url_format_string.strip()
    realm_filter = RealmFilter(
        realm=realm, pattern=pattern,
        url_format_string=url_format_string)
    realm_filter.full_clean()
    realm_filter.save()
    notify_realm_filters(realm)

    return realm_filter.id

def do_remove_realm_filter(realm: Realm, pattern: Optional[str]=None,
                           id: Optional[int]=None) -> None:
    if pattern is not None:
        RealmFilter.objects.get(realm=realm, pattern=pattern).delete()
    else:
        RealmFilter.objects.get(realm=realm, pk=id).delete()
    notify_realm_filters(realm)

def get_emails_from_user_ids(user_ids: Sequence[int]) -> Dict[int, str]:
    # We may eventually use memcached to speed this up, but the DB is fast.
    return UserProfile.emails_from_ids(user_ids)

def do_add_realm_domain(realm: Realm, domain: str, allow_subdomains: bool) -> (RealmDomain):
    realm_domain = RealmDomain.objects.create(realm=realm, domain=domain,
                                              allow_subdomains=allow_subdomains)
    event = dict(type="realm_domains", op="add",
                 realm_domain=dict(domain=realm_domain.domain,
                                   allow_subdomains=realm_domain.allow_subdomains))
    send_event(realm, event, active_user_ids(realm.id))
    return realm_domain

def do_change_realm_domain(realm_domain: RealmDomain, allow_subdomains: bool) -> None:
    realm_domain.allow_subdomains = allow_subdomains
    realm_domain.save(update_fields=['allow_subdomains'])
    event = dict(type="realm_domains", op="change",
                 realm_domain=dict(domain=realm_domain.domain,
                                   allow_subdomains=realm_domain.allow_subdomains))
    send_event(realm_domain.realm, event, active_user_ids(realm_domain.realm_id))

def do_remove_realm_domain(realm_domain: RealmDomain, acting_user: Optional[UserProfile]=None) -> None:
    realm = realm_domain.realm
    domain = realm_domain.domain
    realm_domain.delete()
    if RealmDomain.objects.filter(realm=realm).count() == 0 and realm.emails_restricted_to_domains:
        # If this was the last realm domain, we mark the realm as no
        # longer restricted to domain, because the feature doesn't do
        # anything if there are no domains, and this is probably less
        # confusing than the alternative.
        do_set_realm_property(realm, 'emails_restricted_to_domains', False, acting_user=acting_user)
    event = dict(type="realm_domains", op="remove", domain=domain)
    send_event(realm, event, active_user_ids(realm.id))

def get_occupied_streams(realm: Realm) -> QuerySet:
    # TODO: Make a generic stub for QuerySet
    """ Get streams with subscribers """
    exists_expression = Exists(
        Subscription.objects.filter(active=True, user_profile__is_active=True,
                                    user_profile__realm=realm,
                                    recipient_id=OuterRef('recipient_id')),
    )
    occupied_streams = Stream.objects.filter(realm=realm, deactivated=False) \
        .annotate(occupied=exists_expression).filter(occupied=True)
    return occupied_streams

def get_web_public_streams(realm: Realm) -> List[Dict[str, Any]]:
    query = Stream.objects.filter(realm=realm, deactivated=False, is_web_public=True)
    streams = Stream.get_client_data(query)
    return streams

def do_get_streams(
        user_profile: UserProfile, include_public: bool=True, include_web_public: bool=False,
        include_subscribed: bool=True, include_all_active: bool=False,
        include_default: bool=False, include_owner_subscribed: bool=False,
) -> List[Dict[str, Any]]:
    # This function is only used by API clients now.

    if include_all_active and not user_profile.is_api_super_user:
        raise JsonableError(_("User not authorized for this query"))

    include_public = include_public and user_profile.can_access_public_streams()

    # Start out with all active streams in the realm.
    query = Stream.objects.filter(realm=user_profile.realm, deactivated=False)

    if include_all_active:
        streams = Stream.get_client_data(query)
    else:
        # We construct a query as the or (|) of the various sources
        # this user requested streams from.
        query_filter: Optional[Q] = None

        def add_filter_option(option: Q) -> None:
            nonlocal query_filter
            if query_filter is None:
                query_filter = option
            else:
                query_filter |= option

        if include_subscribed:
            subscribed_stream_ids = get_subscribed_stream_ids_for_user(user_profile)
            recipient_check = Q(id__in=set(subscribed_stream_ids))
            add_filter_option(recipient_check)
        if include_public:
            invite_only_check = Q(invite_only=False)
            add_filter_option(invite_only_check)
        if include_web_public:
            web_public_check = Q(is_web_public=True)
            add_filter_option(web_public_check)
        if include_owner_subscribed and user_profile.is_bot:
            bot_owner = user_profile.bot_owner
            assert bot_owner is not None
            owner_stream_ids = get_subscribed_stream_ids_for_user(bot_owner)
            owner_subscribed_check = Q(id__in=set(owner_stream_ids))
            add_filter_option(owner_subscribed_check)

        if query_filter is not None:
            query = query.filter(query_filter)
            streams = Stream.get_client_data(query)
        else:
            # Don't bother going to the database with no valid sources
            streams = []

    streams.sort(key=lambda elt: elt["name"])

    if include_default:
        is_default = {}
        default_streams = get_default_streams_for_realm(user_profile.realm_id)
        for default_stream in default_streams:
            is_default[default_stream.id] = True
        for stream in streams:
            stream['is_default'] = is_default.get(stream["stream_id"], False)

    return streams

def notify_attachment_update(user_profile: UserProfile, op: str,
                             attachment_dict: Dict[str, Any]) -> None:
    event = {
        'type': 'attachment',
        'op': op,
        'attachment': attachment_dict,
        "upload_space_used": user_profile.realm.currently_used_upload_space_bytes(),
    }
    send_event(user_profile.realm, event, [user_profile.id])

def do_claim_attachments(message: Message, potential_path_ids: List[str]) -> bool:
    claimed = False
    for path_id in potential_path_ids:
        user_profile = message.sender
        is_message_realm_public = False
        is_message_web_public = False
        if message.is_stream_message():
            stream = Stream.objects.get(id=message.recipient.type_id)
            is_message_realm_public = stream.is_public()
            is_message_web_public = stream.is_web_public

        if not validate_attachment_request(user_profile, path_id):
            # Technically, there are 2 cases here:
            # * The user put something in their message that has the form
            # of an upload, but doesn't correspond to a file that doesn't
            # exist.  validate_attachment_request will return None.
            # * The user is trying to send a link to a file they don't have permission to
            # access themselves.  validate_attachment_request will return False.
            #
            # Either case is unusual and suggests a UI bug that got
            # the user in this situation, so we log in these cases.
            logging.warning(
                "User %s tried to share upload %s in message %s, but lacks permission",
                user_profile.id, path_id, message.id,
            )
            continue

        claimed = True
        attachment = claim_attachment(user_profile,
                                      path_id, message,
                                      is_message_realm_public,
                                      is_message_web_public)
        notify_attachment_update(user_profile, "update", attachment.to_dict())
    return claimed

def do_delete_old_unclaimed_attachments(weeks_ago: int) -> None:
    old_unclaimed_attachments = get_old_unclaimed_attachments(weeks_ago)

    for attachment in old_unclaimed_attachments:
        delete_message_image(attachment.path_id)
        attachment.delete()

def check_attachment_reference_change(message: Message) -> bool:
    # For a unsaved message edit (message.* has been updated, but not
    # saved to the database), adjusts Attachment data to correspond to
    # the new content.
    prev_attachments = {a.path_id for a in message.attachment_set.all()}
    new_attachments = set(message.potential_attachment_path_ids)

    if new_attachments == prev_attachments:
        return bool(prev_attachments)

    to_remove = list(prev_attachments - new_attachments)
    if len(to_remove) > 0:
        attachments_to_update = Attachment.objects.filter(path_id__in=to_remove).select_for_update()
        message.attachment_set.remove(*attachments_to_update)

    to_add = list(new_attachments - prev_attachments)
    if len(to_add) > 0:
        do_claim_attachments(message, to_add)

    return message.attachment_set.exists()

def notify_realm_custom_profile_fields(realm: Realm, operation: str) -> None:
    fields = custom_profile_fields_for_realm(realm.id)
    event = dict(type="custom_profile_fields",
                 op=operation,
                 fields=[f.as_dict() for f in fields])
    send_event(realm, event, active_user_ids(realm.id))

def try_add_realm_default_custom_profile_field(realm: Realm,
                                               field_subtype: str) -> CustomProfileField:
    field_data = DEFAULT_EXTERNAL_ACCOUNTS[field_subtype]
    field = CustomProfileField(realm=realm, name=field_data['name'],
                               field_type=CustomProfileField.EXTERNAL_ACCOUNT,
                               hint=field_data['hint'],
                               field_data=orjson.dumps(dict(subtype=field_subtype)).decode())
    field.save()
    field.order = field.id
    field.save(update_fields=['order'])
    notify_realm_custom_profile_fields(realm, 'add')
    return field

def try_add_realm_custom_profile_field(realm: Realm, name: str, field_type: int,
                                       hint: str='',
                                       field_data: Optional[ProfileFieldData]=None) -> CustomProfileField:
    field = CustomProfileField(realm=realm, name=name, field_type=field_type)
    field.hint = hint
    if (field.field_type == CustomProfileField.CHOICE or
            field.field_type == CustomProfileField.EXTERNAL_ACCOUNT):
        field.field_data = orjson.dumps(field_data or {}).decode()

    field.save()
    field.order = field.id
    field.save(update_fields=['order'])
    notify_realm_custom_profile_fields(realm, 'add')
    return field

def do_remove_realm_custom_profile_field(realm: Realm, field: CustomProfileField) -> None:
    """
    Deleting a field will also delete the user profile data
    associated with it in CustomProfileFieldValue model.
    """
    field.delete()
    notify_realm_custom_profile_fields(realm, 'delete')

def do_remove_realm_custom_profile_fields(realm: Realm) -> None:
    CustomProfileField.objects.filter(realm=realm).delete()

def try_update_realm_custom_profile_field(realm: Realm, field: CustomProfileField,
                                          name: str, hint: str='',
                                          field_data: Optional[ProfileFieldData]=None) -> None:
    field.name = name
    field.hint = hint
    if (field.field_type == CustomProfileField.CHOICE or
            field.field_type == CustomProfileField.EXTERNAL_ACCOUNT):
        field.field_data = orjson.dumps(field_data or {}).decode()
    field.save()
    notify_realm_custom_profile_fields(realm, 'update')

def try_reorder_realm_custom_profile_fields(realm: Realm, order: List[int]) -> None:
    order_mapping = {_[1]: _[0] for _ in enumerate(order)}
    fields = CustomProfileField.objects.filter(realm=realm)
    for field in fields:
        if field.id not in order_mapping:
            raise JsonableError(_("Invalid order mapping."))
    for field in fields:
        field.order = order_mapping[field.id]
        field.save(update_fields=['order'])
    notify_realm_custom_profile_fields(realm, 'update')

def notify_user_update_custom_profile_data(user_profile: UserProfile,
                                           field: Dict[str, Union[int, str, List[int], None]]) -> None:
    data = dict(id=field['id'])
    if field['type'] == CustomProfileField.USER:
        data["value"] = orjson.dumps(field['value']).decode()
    else:
        data['value'] = field['value']
    if field['rendered_value']:
        data['rendered_value'] = field['rendered_value']
    payload = dict(user_id=user_profile.id, custom_profile_field=data)
    event = dict(type="realm_user", op="update", person=payload)
    send_event(user_profile.realm, event, active_user_ids(user_profile.realm.id))

def do_update_user_custom_profile_data_if_changed(user_profile: UserProfile,
                                                  data: List[Dict[str, Union[int, str, List[int]]]],
                                                  ) -> None:
    with transaction.atomic():
        for field in data:
            field_value, created = CustomProfileFieldValue.objects.get_or_create(
                user_profile=user_profile,
                field_id=field['id'])

            if not created and field_value.value == str(field['value']):
                # If the field value isn't actually being changed to a different one,
                # and always_notify is disabled, we have nothing to do here for this field.
                # Note: field_value.value is a TextField() so we need to cast field['value']
                # to a string for the comparison in this if.
                continue

            field_value.value = field['value']
            if field_value.field.is_renderable():
                field_value.rendered_value = render_stream_description(str(field['value']))
                field_value.save(update_fields=['value', 'rendered_value'])
            else:
                field_value.save(update_fields=['value'])
            notify_user_update_custom_profile_data(user_profile, {
                "id": field_value.field_id,
                "value": field_value.value,
                "rendered_value": field_value.rendered_value,
                "type": field_value.field.field_type})

def check_remove_custom_profile_field_value(user_profile: UserProfile, field_id: int) -> None:
    try:
        field = CustomProfileField.objects.get(realm=user_profile.realm, id=field_id)
        field_value = CustomProfileFieldValue.objects.get(field=field, user_profile=user_profile)
        field_value.delete()
        notify_user_update_custom_profile_data(user_profile, {'id': field_id,
                                                              'value': None,
                                                              'rendered_value': None,
                                                              'type': field.field_type})
    except CustomProfileField.DoesNotExist:
        raise JsonableError(_('Field id {id} not found.').format(id=field_id))
    except CustomProfileFieldValue.DoesNotExist:
        pass

def do_send_create_user_group_event(user_group: UserGroup, members: List[UserProfile]) -> None:
    event = dict(type="user_group",
                 op="add",
                 group=dict(name=user_group.name,
                            members=[member.id for member in members],
                            description=user_group.description,
                            id=user_group.id,
                            ),
                 )
    send_event(user_group.realm, event, active_user_ids(user_group.realm_id))

def check_add_user_group(realm: Realm, name: str, initial_members: List[UserProfile],
                         description: str) -> None:
    try:
        user_group = create_user_group(name, initial_members, realm, description=description)
        do_send_create_user_group_event(user_group, initial_members)
    except django.db.utils.IntegrityError:
        raise JsonableError(_("User group '{}' already exists.").format(name))

def do_send_user_group_update_event(user_group: UserGroup, data: Dict[str, str]) -> None:
    event = dict(type="user_group", op='update', group_id=user_group.id, data=data)
    send_event(user_group.realm, event, active_user_ids(user_group.realm_id))

def do_update_user_group_name(user_group: UserGroup, name: str) -> None:
    try:
        user_group.name = name
        user_group.save(update_fields=['name'])
    except django.db.utils.IntegrityError:
        raise JsonableError(_("User group '{}' already exists.").format(name))
    do_send_user_group_update_event(user_group, dict(name=name))

def do_update_user_group_description(user_group: UserGroup, description: str) -> None:
    user_group.description = description
    user_group.save(update_fields=['description'])
    do_send_user_group_update_event(user_group, dict(description=description))

def do_update_outgoing_webhook_service(bot_profile: UserProfile,
                                       service_interface: int,
                                       service_payload_url: str) -> None:
    # TODO: First service is chosen because currently one bot can only have one service.
    # Update this once multiple services are supported.
    service = get_bot_services(bot_profile.id)[0]
    service.base_url = service_payload_url
    service.interface = service_interface
    service.save()
    send_event(bot_profile.realm,
               dict(type='realm_bot',
                    op='update',
                    bot=dict(user_id=bot_profile.id,
                             services = [dict(base_url=service.base_url,
                                              interface=service.interface,
                                              token=service.token)],
                             ),
                    ),
               bot_owner_user_ids(bot_profile))

def do_update_bot_config_data(bot_profile: UserProfile,
                              config_data: Dict[str, str]) -> None:
    for key, value in config_data.items():
        set_bot_config(bot_profile, key, value)
    updated_config_data = get_bot_config(bot_profile)
    send_event(bot_profile.realm,
               dict(type='realm_bot',
                    op='update',
                    bot=dict(user_id=bot_profile.id,
                             services = [dict(config_data=updated_config_data)],
                             ),
                    ),
               bot_owner_user_ids(bot_profile))

def get_service_dicts_for_bot(user_profile_id: int) -> List[Dict[str, Any]]:
    user_profile = get_user_profile_by_id(user_profile_id)
    services = get_bot_services(user_profile_id)
    service_dicts: List[Dict[str, Any]] = []
    if user_profile.bot_type == UserProfile.OUTGOING_WEBHOOK_BOT:
        service_dicts = [{'base_url': service.base_url,
                          'interface': service.interface,
                          'token': service.token,
                          }
                         for service in services]
    elif user_profile.bot_type == UserProfile.EMBEDDED_BOT:
        try:
            service_dicts = [{'config_data': get_bot_config(user_profile),
                              'service_name': services[0].name,
                              }]
        # A ConfigError just means that there are no config entries for user_profile.
        except ConfigError:
            pass
    return service_dicts

def get_service_dicts_for_bots(bot_dicts: List[Dict[str, Any]],
                               realm: Realm) -> Dict[int, List[Dict[str, Any]]]:
    bot_profile_ids = [bot_dict['id'] for bot_dict in bot_dicts]
    bot_services_by_uid: Dict[int, List[Service]] = defaultdict(list)
    for service in Service.objects.filter(user_profile_id__in=bot_profile_ids):
        bot_services_by_uid[service.user_profile_id].append(service)

    embedded_bot_ids = [bot_dict['id'] for bot_dict in bot_dicts
                        if bot_dict['bot_type'] == UserProfile.EMBEDDED_BOT]
    embedded_bot_configs = get_bot_configs(embedded_bot_ids)

    service_dicts_by_uid: Dict[int, List[Dict[str, Any]]] = {}
    for bot_dict in bot_dicts:
        bot_profile_id = bot_dict["id"]
        bot_type = bot_dict["bot_type"]
        services = bot_services_by_uid[bot_profile_id]
        service_dicts: List[Dict[str, Any]] = []
        if bot_type  == UserProfile.OUTGOING_WEBHOOK_BOT:
            service_dicts = [{'base_url': service.base_url,
                              'interface': service.interface,
                              'token': service.token,
                              }
                             for service in services]
        elif bot_type == UserProfile.EMBEDDED_BOT:
            if bot_profile_id in embedded_bot_configs.keys():
                bot_config = embedded_bot_configs[bot_profile_id]
                service_dicts = [{'config_data': bot_config,
                                  'service_name': services[0].name,
                                  }]
        service_dicts_by_uid[bot_profile_id] = service_dicts
    return service_dicts_by_uid

def get_owned_bot_dicts(user_profile: UserProfile,
                        include_all_realm_bots_if_admin: bool=True) -> List[Dict[str, Any]]:
    if user_profile.is_realm_admin and include_all_realm_bots_if_admin:
        result = get_bot_dicts_in_realm(user_profile.realm)
    else:
        result = UserProfile.objects.filter(realm=user_profile.realm, is_bot=True,
                                            bot_owner=user_profile).values(*bot_dict_fields)
    services_by_ids = get_service_dicts_for_bots(result, user_profile.realm)
    return [{'email': botdict['email'],
             'user_id': botdict['id'],
             'full_name': botdict['full_name'],
             'bot_type': botdict['bot_type'],
             'is_active': botdict['is_active'],
             'api_key': botdict['api_key'],
             'default_sending_stream': botdict['default_sending_stream__name'],
             'default_events_register_stream': botdict['default_events_register_stream__name'],
             'default_all_public_streams': botdict['default_all_public_streams'],
             'owner_id': botdict['bot_owner__id'],
             'avatar_url': avatar_url_from_dict(botdict),
             'services': services_by_ids[botdict['id']],
             }
            for botdict in result]

def do_send_user_group_members_update_event(event_name: str,
                                            user_group: UserGroup,
                                            user_ids: List[int]) -> None:
    event = dict(type="user_group",
                 op=event_name,
                 group_id=user_group.id,
                 user_ids=user_ids)
    send_event(user_group.realm, event, active_user_ids(user_group.realm_id))

def bulk_add_members_to_user_group(user_group: UserGroup,
                                   user_profiles: List[UserProfile]) -> None:
    memberships = [UserGroupMembership(user_group_id=user_group.id,
                                       user_profile=user_profile)
                   for user_profile in user_profiles]
    UserGroupMembership.objects.bulk_create(memberships)

    user_ids = [up.id for up in user_profiles]
    do_send_user_group_members_update_event('add_members', user_group, user_ids)

def remove_members_from_user_group(user_group: UserGroup,
                                   user_profiles: List[UserProfile]) -> None:
    UserGroupMembership.objects.filter(
        user_group_id=user_group.id,
        user_profile__in=user_profiles).delete()

    user_ids = [up.id for up in user_profiles]
    do_send_user_group_members_update_event('remove_members', user_group, user_ids)

def do_send_delete_user_group_event(realm: Realm, user_group_id: int,
                                    realm_id: int) -> None:
    event = dict(type="user_group",
                 op="remove",
                 group_id=user_group_id)
    send_event(realm, event, active_user_ids(realm_id))

def check_delete_user_group(user_group_id: int, user_profile: UserProfile) -> None:
    user_group = access_user_group_by_id(user_group_id, user_profile)
    user_group.delete()
    do_send_delete_user_group_event(user_profile.realm, user_group_id, user_profile.realm.id)

def do_send_realm_reactivation_email(realm: Realm) -> None:
    url = create_confirmation_link(realm, Confirmation.REALM_REACTIVATION)
    context = {'confirmation_url': url,
               'realm_uri': realm.uri,
               'realm_name': realm.name}
    language = realm.default_language
    send_email_to_admins(
        'zerver/emails/realm_reactivation', realm,
        from_address=FromAddress.tokenized_no_reply_address(),
        from_name=FromAddress.security_email_from_name(language=language),
        language=language, context=context)

def do_set_zoom_token(user: UserProfile, token: Optional[Dict[str, object]]) -> None:
    user.zoom_token = token
    user.save(update_fields=["zoom_token"])
    send_event(
        user.realm, dict(type="has_zoom_token", value=token is not None), [user.id],
    )

def notify_realm_export(user_profile: UserProfile) -> None:
    # In the future, we may want to send this event to all realm admins.
    event = dict(type='realm_export',
                 exports=get_realm_exports_serialized(user_profile))
    send_event(user_profile.realm, event, [user_profile.id])

def do_delete_realm_export(user_profile: UserProfile, export: RealmAuditLog) -> None:
    # Give mypy a hint so it knows `orjson.loads`
    # isn't being passed an `Optional[str]`.
    export_extra_data = export.extra_data
    assert export_extra_data is not None
    export_data = orjson.loads(export_extra_data)
    export_path = export_data.get('export_path')

    if export_path:
        # Allow removal even if the export failed.
        delete_export_tarball(export_path)

    export_data.update(deleted_timestamp=timezone_now().timestamp())
    export.extra_data = orjson.dumps(export_data).decode()
    export.save(update_fields=['extra_data'])
    notify_realm_export(user_profile)

def get_topic_messages(user_profile: UserProfile, stream: Stream,
                       topic_name: str) -> List[Message]:
    query = UserMessage.objects.filter(
        user_profile=user_profile,
        message__recipient=stream.recipient,
    ).order_by("id")
    return [um.message for um in filter_by_topic_name_via_message(query, topic_name)]
