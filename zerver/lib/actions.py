from typing import (
    AbstractSet, Any, AnyStr, Callable, Dict, Iterable, List, Mapping, MutableMapping,
    Optional, Sequence, Set, Text, Tuple, TypeVar, Union, cast
)
from mypy_extensions import TypedDict

import django.db.utils
from django.db.models import Count
from django.contrib.contenttypes.models import ContentType
from django.utils.html import escape
from django.utils.translation import ugettext as _
from django.conf import settings
from django.core import validators
from django.core.files import File
from analytics.lib.counts import COUNT_STATS, do_increment_logging_stat, \
    RealmCount

from zerver.lib.bugdown import (
    BugdownRenderingException,
    version as bugdown_version,
    url_embed_preview_enabled_for_realm
)
from zerver.lib.addressee import (
    Addressee,
    user_profiles_from_unvalidated_emails,
)
from zerver.lib.bot_config import (
    ConfigError,
    get_bot_config,
    get_bot_configs,
    set_bot_config,
)
from zerver.lib.cache import (
    bot_dict_fields,
    delete_user_profile_caches,
    to_dict_cache_key_id,
)
from zerver.lib.context_managers import lockfile
from zerver.lib.emoji import emoji_name_to_emoji_code, get_emoji_file_name
from zerver.lib.exceptions import StreamDoesNotExistError
from zerver.lib.hotspots import get_next_hotspots
from zerver.lib.message import (
    access_message,
    MessageDict,
    render_markdown,
)
from zerver.lib.realm_icon import realm_icon_url
from zerver.lib.retention import move_message_to_archive
from zerver.lib.send_email import send_email, FromAddress
from zerver.lib.stream_subscription import (
    get_active_subscriptions_for_stream_id,
    get_active_subscriptions_for_stream_ids,
    get_bulk_stream_subscriber_info,
    get_stream_subscriptions_for_user,
    get_stream_subscriptions_for_users,
    num_subscribers_for_stream_id,
)
from zerver.lib.stream_topic import StreamTopicTarget
from zerver.lib.topic_mutes import (
    get_topic_mutes,
    add_topic_mute,
    remove_topic_mute,
)
from zerver.lib.users import bulk_get_users, check_full_name, user_ids_to_users
from zerver.lib.user_groups import create_user_group, access_user_group_by_id
from zerver.models import Realm, RealmEmoji, Stream, UserProfile, UserActivity, \
    RealmDomain, \
    Subscription, Recipient, Message, Attachment, UserMessage, RealmAuditLog, \
    UserHotspot, MultiuseInvite, ScheduledMessage, \
    Client, DefaultStream, DefaultStreamGroup, UserPresence, PushDeviceToken, \
    ScheduledEmail, MAX_SUBJECT_LENGTH, \
    MAX_MESSAGE_LENGTH, get_client, get_stream, get_personal_recipient, get_huddle, \
    get_user_profile_by_id, PreregistrationUser, get_display_recipient, \
    get_realm, bulk_get_recipients, get_stream_recipient, get_stream_recipients, \
    email_allowed_for_realm, email_to_username, display_recipient_cache_key, \
    get_user, get_stream_cache_key, \
    UserActivityInterval, active_user_ids, get_active_streams, \
    realm_filters_for_realm, RealmFilter, stream_name_in_use, \
    get_old_unclaimed_attachments, is_cross_realm_bot_email, \
    Reaction, EmailChangeStatus, CustomProfileField, \
    custom_profile_fields_for_realm, get_huddle_user_ids, \
    CustomProfileFieldValue, validate_attachment_request, get_system_bot, \
    get_display_recipient_by_id, query_for_ids, get_huddle_recipient, \
    UserGroup, UserGroupMembership, get_default_stream_groups, \
    get_bot_services, get_bot_dicts_in_realm, DomainNotAllowedForRealmError, \
    get_services_for_bots

from zerver.lib.alert_words import alert_words_in_realm
from zerver.lib.avatar import avatar_url, avatar_url_from_dict
from zerver.lib.stream_recipient import StreamRecipientMap

from django.db import transaction, IntegrityError, connection
from django.db.models import F, Q, Max, Sum
from django.db.models.query import QuerySet
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.utils.timezone import now as timezone_now

from confirmation.models import Confirmation, create_confirmation_link
from confirmation import settings as confirmation_settings
from six import unichr

from zerver.lib.bulk_create import bulk_create_users
from zerver.lib.create_user import random_api_key
from zerver.lib.timestamp import timestamp_to_datetime, datetime_to_timestamp
from zerver.lib.queue import queue_json_publish
from zerver.lib.create_user import create_user
from zerver.lib import bugdown
from zerver.lib.cache import cache_with_key, cache_set, \
    user_profile_by_email_cache_key, user_profile_cache_key, \
    cache_set_many, cache_delete, cache_delete_many
from zerver.decorator import statsd_increment
from zerver.lib.utils import log_statsd_event, statsd
from zerver.lib.html_diff import highlight_html_differences
from zerver.lib.i18n import get_language_name
from zerver.lib.alert_words import user_alert_words, add_user_alert_words, \
    remove_user_alert_words, set_user_alert_words
from zerver.lib.notifications import clear_scheduled_emails, \
    clear_scheduled_invitation_emails, enqueue_welcome_emails
from zerver.lib.narrow import check_supported_events_narrow_filter
from zerver.lib.exceptions import JsonableError, ErrorCode
from zerver.lib.sessions import delete_user_sessions
from zerver.lib.upload import attachment_url_re, attachment_url_to_path_id, \
    claim_attachment, delete_message_image, upload_emoji_image
from zerver.lib.str_utils import NonBinaryStr, force_str
from zerver.tornado.event_queue import request_event_queue, send_event

from analytics.models import StreamCount

import DNS
import ujson
import time
import traceback
import re
import datetime
import os
import platform
import logging
import itertools
from collections import defaultdict
from operator import itemgetter

# This will be used to type annotate parameters in a function if the function
# works on both str and unicode in python 2 but in python 3 it only works on str.
SizedTextIterable = Union[Sequence[Text], AbstractSet[Text]]

STREAM_ASSIGNMENT_COLORS = [
    "#76ce90", "#fae589", "#a6c7e5", "#e79ab5",
    "#bfd56f", "#f4ae55", "#b0a5fd", "#addfe5",
    "#f5ce6e", "#c2726a", "#94c849", "#bd86e5",
    "#ee7e4a", "#a6dcbf", "#95a5fd", "#53a063",
    "#9987e1", "#e4523d", "#c2c2c2", "#4f8de4",
    "#c6a8ad", "#e7cc4d", "#c8bebf", "#a47462"]

# Store an event in the log for re-importing messages
def log_event(event: MutableMapping[str, Any]) -> None:
    if settings.EVENT_LOG_DIR is None:
        return

    if "timestamp" not in event:
        event["timestamp"] = time.time()

    if not os.path.exists(settings.EVENT_LOG_DIR):
        os.mkdir(settings.EVENT_LOG_DIR)

    template = os.path.join(settings.EVENT_LOG_DIR,
                            '%s.' + platform.node() +
                            timezone_now().strftime('.%Y-%m-%d'))

    with lockfile(template % ('lock',)):
        with open(template % ('events',), 'a') as log:
            log.write(ujson.dumps(event) + '\n')

def can_access_stream_user_ids(stream: Stream) -> Set[int]:
    # return user ids of users who can access the attributes of
    # a stream, such as its name/description
    if stream.is_public():
        return set(active_user_ids(stream.realm_id))
    else:
        return private_stream_user_ids(stream.id)

def private_stream_user_ids(stream_id: int) -> Set[int]:
    # TODO: Find similar queries elsewhere and de-duplicate this code.
    subscriptions = get_active_subscriptions_for_stream_id(stream_id)
    return {sub['user_profile_id'] for sub in subscriptions.values('user_profile_id')}

def bot_owner_user_ids(user_profile: UserProfile) -> Set[int]:
    is_private_bot = (
        user_profile.default_sending_stream and
        user_profile.default_sending_stream.invite_only or
        user_profile.default_events_register_stream and
        user_profile.default_events_register_stream.invite_only)
    if is_private_bot:
        return {user_profile.bot_owner_id, }
    else:
        users = {user.id for user in user_profile.realm.get_admin_users()}
        users.add(user_profile.bot_owner_id)
        return users

def realm_user_count(realm: Realm) -> int:
    return UserProfile.objects.filter(realm=realm, is_active=True, is_bot=False).count()

def get_topic_history_for_stream(user_profile: UserProfile,
                                 recipient: Recipient,
                                 public_history: bool) -> List[Dict[str, Any]]:
    cursor = connection.cursor()
    if public_history:
        query = '''
        SELECT
            "zerver_message"."subject" as topic,
            max("zerver_message".id) as max_message_id
        FROM "zerver_message"
        WHERE (
            "zerver_message"."recipient_id" = %s
        )
        GROUP BY (
            "zerver_message"."subject"
        )
        ORDER BY max("zerver_message".id) DESC
        '''
        cursor.execute(query, [recipient.id])
    else:
        query = '''
        SELECT
            "zerver_message"."subject" as topic,
            max("zerver_message".id) as max_message_id
        FROM "zerver_message"
        INNER JOIN "zerver_usermessage" ON (
            "zerver_usermessage"."message_id" = "zerver_message"."id"
        )
        WHERE (
            "zerver_usermessage"."user_profile_id" = %s AND
            "zerver_message"."recipient_id" = %s
        )
        GROUP BY (
            "zerver_message"."subject"
        )
        ORDER BY max("zerver_message".id) DESC
        '''
        cursor.execute(query, [user_profile.id, recipient.id])
    rows = cursor.fetchall()
    cursor.close()

    canonical_topic_names = set()  # type: Set[str]
    history = []
    for (topic_name, max_message_id) in rows:
        canonical_name = topic_name.lower()
        if canonical_name in canonical_topic_names:
            continue

        canonical_topic_names.add(canonical_name)
        history.append(dict(
            name=topic_name,
            max_id=max_message_id))

    return history

def send_signup_message(sender: UserProfile, admin_realm_signup_notifications_stream: Text,
                        user_profile: UserProfile, internal: bool=False,
                        realm: Optional[Realm]=None) -> None:
    if internal:
        # When this is done using manage.py vs. the web interface
        internal_blurb = " **INTERNAL SIGNUP** "
    else:
        internal_blurb = " "

    user_count = realm_user_count(user_profile.realm)
    signup_notifications_stream = user_profile.realm.get_signup_notifications_stream()
    # Send notification to realm signup notifications stream if it exists
    # Don't send notification for the first user in a realm
    if signup_notifications_stream is not None and user_count > 1:
        internal_send_message(
            user_profile.realm,
            sender,
            "stream",
            signup_notifications_stream.name,
            "signups",
            "%s (%s) just signed up for Zulip. (total: %i)" % (
                user_profile.full_name, user_profile.email, user_count
            )
        )

    # We also send a notification to the Zulip administrative realm
    admin_realm = get_system_bot(sender).realm
    try:
        # Check whether the stream exists
        get_stream(admin_realm_signup_notifications_stream, admin_realm)
    except Stream.DoesNotExist:
        # If the signups stream hasn't been created in the admin
        # realm, don't auto-create it to send to it; just do nothing.
        return
    internal_send_message(
        admin_realm,
        sender,
        "stream",
        admin_realm_signup_notifications_stream,
        user_profile.realm.display_subdomain,
        "%s <`%s`> just signed up for Zulip!%s(total: **%i**)" % (
            user_profile.full_name,
            user_profile.email,
            internal_blurb,
            user_count,
        )
    )

def notify_new_user(user_profile: UserProfile, internal: bool=False) -> None:
    if settings.NOTIFICATION_BOT is not None:
        send_signup_message(settings.NOTIFICATION_BOT, "signups", user_profile, internal)
    statsd.gauge("users.signups.%s" % (user_profile.realm.string_id), 1, delta=True)

    # We also clear any scheduled invitation emails to prevent them
    # from being sent after the user is created.
    clear_scheduled_invitation_emails(user_profile.email)

def add_new_user_history(user_profile: UserProfile, streams: Iterable[Stream]) -> None:
    """Give you the last 1000 messages on your public streams, so you have
    something to look at in your home view once you finish the
    tutorial."""
    one_week_ago = timezone_now() - datetime.timedelta(weeks=1)

    stream_ids = [stream.id for stream in streams if not stream.invite_only]
    recipients = get_stream_recipients(stream_ids)
    recent_messages = Message.objects.filter(recipient_id__in=recipients,
                                             pub_date__gt=one_week_ago).order_by("-id")
    message_ids_to_use = list(reversed(recent_messages.values_list('id', flat=True)[0:1000]))
    if len(message_ids_to_use) == 0:
        return

    # Handle the race condition where a message arrives between
    # bulk_add_subscriptions above and the Message query just above
    already_ids = set(UserMessage.objects.filter(message_id__in=message_ids_to_use,
                                                 user_profile=user_profile).values_list("message_id",
                                                                                        flat=True))
    ums_to_create = [UserMessage(user_profile=user_profile, message_id=message_id,
                                 flags=UserMessage.flags.read)
                     for message_id in message_ids_to_use
                     if message_id not in already_ids]

    UserMessage.objects.bulk_create(ums_to_create)

# Does the processing for a new user account:
# * Subscribes to default/invitation streams
# * Fills in some recent historical messages
# * Notifies other users in realm and Zulip about the signup
# * Deactivates PreregistrationUser objects
# * subscribe the user to newsletter if newsletter_data is specified
def process_new_human_user(user_profile: UserProfile,
                           prereg_user: Optional[PreregistrationUser]=None,
                           newsletter_data: Optional[Dict[str, str]]=None,
                           default_stream_groups: List[DefaultStreamGroup]=[]) -> None:
    mit_beta_user = user_profile.realm.is_zephyr_mirror_realm
    if prereg_user is not None:
        streams = prereg_user.streams.all()
        acting_user = prereg_user.referred_by  # type: Optional[UserProfile]
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

    bulk_add_subscriptions(streams, [user_profile], acting_user=acting_user)

    add_new_user_history(user_profile, streams)

    # mit_beta_users don't have a referred_by field
    if not mit_beta_user and prereg_user is not None and prereg_user.referred_by is not None \
            and settings.NOTIFICATION_BOT is not None:
        # This is a cross-realm private message.
        internal_send_private_message(
            user_profile.realm,
            get_system_bot(settings.NOTIFICATION_BOT),
            prereg_user.referred_by,
            "%s <`%s`> accepted your invitation to join Zulip!" % (
                user_profile.full_name,
                user_profile.email,
            )
        )
    # Mark any other PreregistrationUsers that are STATUS_ACTIVE as
    # inactive so we can keep track of the PreregistrationUser we
    # actually used for analytics
    if prereg_user is not None:
        PreregistrationUser.objects.filter(email__iexact=user_profile.email).exclude(
            id=prereg_user.id).update(status=0)
    else:
        PreregistrationUser.objects.filter(email__iexact=user_profile.email).update(status=0)

    notify_new_user(user_profile)
    if user_profile.realm.send_welcome_emails:
        enqueue_welcome_emails(user_profile)

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
                'email_address': user_profile.email,
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
    event = dict(type="realm_user", op="add",
                 person=dict(email=user_profile.email,
                             user_id=user_profile.id,
                             is_admin=user_profile.is_realm_admin,
                             full_name=user_profile.full_name,
                             avatar_url=avatar_url(user_profile),
                             timezone=user_profile.timezone,
                             is_bot=user_profile.is_bot))
    send_event(event, active_user_ids(user_profile.realm_id))

def created_bot_event(user_profile: UserProfile) -> Dict[str, Any]:
    def stream_name(stream: Optional[Stream]) -> Optional[Text]:
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
               api_key=user_profile.api_key,
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
        bot['owner'] = user_profile.bot_owner.email

    return dict(type="realm_bot", op="add", bot=bot)

def notify_created_bot(user_profile: UserProfile) -> None:
    event = created_bot_event(user_profile)
    send_event(event, bot_owner_user_ids(user_profile))

def create_users(realm: Realm, name_list: Iterable[Tuple[Text, Text]], bot_type: int=None) -> None:
    user_set = set()
    for full_name, email in name_list:
        short_name = email_to_username(email)
        user_set.add((email, full_name, short_name, True))
    bulk_create_users(realm, user_set, bot_type)

def do_create_user(email: Text, password: Optional[Text], realm: Realm, full_name: Text,
                   short_name: Text, is_realm_admin: bool=False, bot_type: Optional[int]=None,
                   bot_owner: Optional[UserProfile]=None, tos_version: Optional[Text]=None,
                   timezone: Text="", avatar_source: Text=UserProfile.AVATAR_FROM_GRAVATAR,
                   default_sending_stream: Optional[Stream]=None,
                   default_events_register_stream: Optional[Stream]=None,
                   default_all_public_streams: bool=None,
                   prereg_user: Optional[PreregistrationUser]=None,
                   newsletter_data: Optional[Dict[str, str]]=None,
                   default_stream_groups: List[DefaultStreamGroup]=[]) -> UserProfile:

    user_profile = create_user(email=email, password=password, realm=realm,
                               full_name=full_name, short_name=short_name,
                               is_realm_admin=is_realm_admin,
                               bot_type=bot_type, bot_owner=bot_owner,
                               tos_version=tos_version, timezone=timezone, avatar_source=avatar_source,
                               default_sending_stream=default_sending_stream,
                               default_events_register_stream=default_events_register_stream,
                               default_all_public_streams=default_all_public_streams)

    event_time = user_profile.date_joined
    RealmAuditLog.objects.create(realm=user_profile.realm, modified_user=user_profile,
                                 event_type='user_created', event_time=event_time)
    do_increment_logging_stat(user_profile.realm, COUNT_STATS['active_users_log:is_bot:day'],
                              user_profile.is_bot, event_time)

    notify_created_user(user_profile)
    if bot_type:
        notify_created_bot(user_profile)
    else:
        process_new_human_user(user_profile, prereg_user=prereg_user,
                               newsletter_data=newsletter_data,
                               default_stream_groups=default_stream_groups)
    return user_profile

def do_activate_user(user_profile: UserProfile) -> None:
    user_profile.is_active = True
    user_profile.is_mirror_dummy = False
    user_profile.set_unusable_password()
    user_profile.date_joined = timezone_now()
    user_profile.tos_version = settings.TOS_VERSION
    user_profile.save(update_fields=["is_active", "date_joined", "password",
                                     "is_mirror_dummy", "tos_version"])

    event_time = user_profile.date_joined
    RealmAuditLog.objects.create(realm=user_profile.realm, modified_user=user_profile,
                                 event_type='user_activated', event_time=event_time)
    do_increment_logging_stat(user_profile.realm, COUNT_STATS['active_users_log:is_bot:day'],
                              user_profile.is_bot, event_time)

    notify_created_user(user_profile)

def do_reactivate_user(user_profile: UserProfile, acting_user: Optional[UserProfile]=None) -> None:
    # Unlike do_activate_user, this is meant for re-activating existing users,
    # so it doesn't reset their password, etc.
    user_profile.is_active = True
    user_profile.save(update_fields=["is_active"])

    event_time = timezone_now()
    RealmAuditLog.objects.create(realm=user_profile.realm, modified_user=user_profile,
                                 event_type='user_reactivated', event_time=event_time,
                                 acting_user=acting_user)
    do_increment_logging_stat(user_profile.realm, COUNT_STATS['active_users_log:is_bot:day'],
                              user_profile.is_bot, event_time)

    notify_created_user(user_profile)

    if user_profile.is_bot:
        notify_created_bot(user_profile)

def active_humans_in_realm(realm: Realm) -> Sequence[UserProfile]:
    return UserProfile.objects.filter(realm=realm, is_active=True, is_bot=False)


def do_set_realm_property(realm: Realm, name: str, value: Any) -> None:
    """Takes in a realm object, the name of an attribute to update, and the
    value to update.
    """
    property_type = Realm.property_types[name]
    assert isinstance(value, property_type), (
        'Cannot update %s: %s is not an instance of %s' % (
            name, value, property_type,))

    setattr(realm, name, value)
    realm.save(update_fields=[name])
    event = dict(
        type='realm',
        op='update',
        property=name,
        value=value,
    )
    send_event(event, active_user_ids(realm.id))


def do_set_realm_authentication_methods(realm: Realm,
                                        authentication_methods: Dict[str, bool]) -> None:
    for key, value in list(authentication_methods.items()):
        index = getattr(realm.authentication_methods, key).number
        realm.authentication_methods.set_bit(index, int(value))
    realm.save(update_fields=['authentication_methods'])
    event = dict(
        type="realm",
        op="update_dict",
        property='default',
        data=dict(authentication_methods=realm.authentication_methods_dict())
    )
    send_event(event, active_user_ids(realm.id))

def do_set_realm_message_editing(realm: Realm,
                                 allow_message_editing: bool,
                                 message_content_edit_limit_seconds: int,
                                 allow_community_topic_editing: bool) -> None:
    realm.allow_message_editing = allow_message_editing
    realm.message_content_edit_limit_seconds = message_content_edit_limit_seconds
    realm.allow_community_topic_editing = allow_community_topic_editing
    realm.save(update_fields=['allow_message_editing',
                              'allow_community_topic_editing',
                              'message_content_edit_limit_seconds',
                              ]
               )
    event = dict(
        type="realm",
        op="update_dict",
        property="default",
        data=dict(allow_message_editing=allow_message_editing,
                  message_content_edit_limit_seconds=message_content_edit_limit_seconds,
                  allow_community_topic_editing=allow_community_topic_editing),
    )
    send_event(event, active_user_ids(realm.id))

def do_set_realm_notifications_stream(realm: Realm, stream: Stream, stream_id: int) -> None:
    realm.notifications_stream = stream
    realm.save(update_fields=['notifications_stream'])
    event = dict(
        type="realm",
        op="update",
        property="notifications_stream_id",
        value=stream_id
    )
    send_event(event, active_user_ids(realm.id))

def do_set_realm_signup_notifications_stream(realm: Realm, stream: Stream,
                                             stream_id: int) -> None:
    realm.signup_notifications_stream = stream
    realm.save(update_fields=['signup_notifications_stream'])
    event = dict(
        type="realm",
        op="update",
        property="signup_notifications_stream_id",
        value=stream_id
    )
    send_event(event, active_user_ids(realm.id))

def do_deactivate_realm(realm: Realm) -> None:
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

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=realm, event_type='realm_deactivated', event_time=event_time)

    ScheduledEmail.objects.filter(realm=realm).delete()
    for user in active_humans_in_realm(realm):
        # Don't deactivate the users, but do delete their sessions so they get
        # bumped to the login screen, where they'll get a realm deactivation
        # notice when they try to log in.
        delete_user_sessions(user)

    event = dict(type="realm", op="deactivated",
                 realm_id=realm.id)
    send_event(event, active_user_ids(realm.id))

def do_reactivate_realm(realm: Realm) -> None:
    realm.deactivated = False
    realm.save(update_fields=["deactivated"])

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=realm, event_type='realm_reactivated', event_time=event_time)

def do_deactivate_user(user_profile: UserProfile,
                       acting_user: Optional[UserProfile]=None,
                       _cascade: bool=True) -> None:
    if not user_profile.is_active:
        return

    user_profile.is_active = False
    user_profile.save(update_fields=["is_active"])

    delete_user_sessions(user_profile)
    clear_scheduled_emails(user_profile.id)

    event_time = timezone_now()
    RealmAuditLog.objects.create(realm=user_profile.realm, modified_user=user_profile,
                                 acting_user=acting_user,
                                 event_type='user_deactivated', event_time=event_time)
    do_increment_logging_stat(user_profile.realm, COUNT_STATS['active_users_log:is_bot:day'],
                              user_profile.is_bot, event_time, increment=-1)

    event = dict(type="realm_user", op="remove",
                 person=dict(email=user_profile.email,
                             user_id=user_profile.id,
                             full_name=user_profile.full_name))
    send_event(event, active_user_ids(user_profile.realm_id))

    if user_profile.is_bot:
        event = dict(type="realm_bot", op="remove",
                     bot=dict(email=user_profile.email,
                              user_id=user_profile.id,
                              full_name=user_profile.full_name))
        send_event(event, bot_owner_user_ids(user_profile))

    if _cascade:
        bot_profiles = UserProfile.objects.filter(is_bot=True, is_active=True,
                                                  bot_owner=user_profile)
        for profile in bot_profiles:
            do_deactivate_user(profile, acting_user=acting_user, _cascade=False)

def do_deactivate_stream(stream: Stream, log: bool=True) -> None:

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
            # This stream has alrady been deactivated, keep prepending !s until
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

    # Remove the old stream information from remote cache.
    old_cache_key = get_stream_cache_key(old_name, stream.realm_id)
    cache_delete(old_cache_key)

    stream_dict = stream.to_dict()
    stream_dict.update(dict(name=old_name, invite_only=was_invite_only))
    event = dict(type="stream", op="delete",
                 streams=[stream_dict])
    send_event(event, affected_user_ids)

def do_change_user_email(user_profile: UserProfile, new_email: Text) -> None:
    delete_user_profile_caches([user_profile])

    user_profile.email = new_email
    user_profile.save(update_fields=["email"])

    payload = dict(user_id=user_profile.id,
                   new_email=new_email)
    send_event(dict(type='realm_user', op='update', person=payload),
               active_user_ids(user_profile.realm_id))
    event_time = timezone_now()
    RealmAuditLog.objects.create(realm=user_profile.realm, acting_user=user_profile,
                                 modified_user=user_profile, event_type='user_email_changed',
                                 event_time=event_time)

def do_start_email_change_process(user_profile: UserProfile, new_email: Text) -> None:
    old_email = user_profile.email
    user_profile.email = new_email
    obj = EmailChangeStatus.objects.create(new_email=new_email, old_email=old_email,
                                           user_profile=user_profile, realm=user_profile.realm)

    activation_url = create_confirmation_link(obj, user_profile.realm.host, Confirmation.EMAIL_CHANGE)
    from zerver.context_processors import common_context
    context = common_context(user_profile)
    context.update({
        'old_email': old_email,
        'new_email': new_email,
        'activate_url': activation_url
    })
    send_email('zerver/emails/confirm_new_email', to_email=new_email,
               from_name='Zulip Account Security', from_address=FromAddress.NOREPLY,
               context=context)

def compute_irc_user_fullname(email: NonBinaryStr) -> NonBinaryStr:
    return email.split("@")[0] + " (IRC)"

def compute_jabber_user_fullname(email: NonBinaryStr) -> NonBinaryStr:
    return email.split("@")[0] + " (XMPP)"

def compute_mit_user_fullname(email: NonBinaryStr) -> NonBinaryStr:
    try:
        # Input is either e.g. username@mit.edu or user|CROSSREALM.INVALID@mit.edu
        match_user = re.match(r'^([a-zA-Z0-9_.-]+)(\|.+)?@mit\.edu$', email.lower())
        if match_user and match_user.group(2) is None:
            answer = DNS.dnslookup(
                "%s.passwd.ns.athena.mit.edu" % (match_user.group(1),),
                DNS.Type.TXT)
            hesiod_name = force_str(answer[0][0]).split(':')[4].split(',')[0].strip()
            if hesiod_name != "":
                return hesiod_name
        elif match_user:
            return match_user.group(1).lower() + "@" + match_user.group(2).upper()[1:]
    except DNS.Base.ServerError:
        pass
    except Exception:
        print("Error getting fullname for %s:" % (email,))
        traceback.print_exc()
    return email.lower()

@cache_with_key(lambda realm, email, f: user_profile_by_email_cache_key(email),
                timeout=3600*24*7)
def create_mirror_user_if_needed(realm: Realm, email: Text,
                                 email_to_fullname: Callable[[Text], Text]) -> UserProfile:
    try:
        return get_user(email, realm)
    except UserProfile.DoesNotExist:
        try:
            # Forge a user for this person
            return create_user(email, None, realm,
                               email_to_fullname(email), email_to_username(email),
                               active=False, is_mirror_dummy=True)
        except IntegrityError:
            return get_user(email, realm)

def send_welcome_bot_response(message: MutableMapping[str, Any]) -> None:
    welcome_bot = get_system_bot(settings.WELCOME_BOT)
    human_recipient = get_personal_recipient(message['message'].sender.id)
    if Message.objects.filter(sender=welcome_bot, recipient=human_recipient).count() < 2:
        internal_send_private_message(
            message['realm'], welcome_bot, message['message'].sender,
            "Congratulations on your first reply! :tada:\n\n"
            "Feel free to continue using this space to practice your new messaging "
            "skills. Or, try clicking on some of the stream names to your left!")

def render_incoming_message(message: Message,
                            content: Text,
                            user_ids: Set[int],
                            realm: Realm,
                            mention_data: Optional[bugdown.MentionData]=None,
                            email_gateway: Optional[bool]=False) -> Text:
    realm_alert_words = alert_words_in_realm(realm)
    try:
        rendered_content = render_markdown(
            message=message,
            content=content,
            realm=realm,
            realm_alert_words=realm_alert_words,
            user_ids=user_ids,
            mention_data=mention_data,
            email_gateway=email_gateway,
        )
    except BugdownRenderingException:
        raise JsonableError(_('Unable to render message'))
    return rendered_content

def get_typing_user_profiles(recipient: Recipient, sender_id: int) -> List[UserProfile]:
    if recipient.type == Recipient.STREAM:
        '''
        We don't support typing indicators for streams because they
        are expensive and initial user feedback was they were too
        distracting.
        '''
        raise ValueError('Typing indicators not supported for streams')

    if recipient.type == Recipient.PERSONAL:
        # The sender and recipient may be the same id, so
        # de-duplicate using a set.
        user_ids = list({recipient.type_id, sender_id})
        assert(len(user_ids) in [1, 2])

    elif recipient.type == Recipient.HUDDLE:
        user_ids = get_huddle_user_ids(recipient)

    else:
        raise ValueError('Bad recipient type')

    users = [get_user_profile_by_id(user_id) for user_id in user_ids]
    return users

RecipientInfoResult = TypedDict('RecipientInfoResult', {
    'active_user_ids': Set[int],
    'push_notify_user_ids': Set[int],
    'stream_push_user_ids': Set[int],
    'um_eligible_user_ids': Set[int],
    'long_term_idle_user_ids': Set[int],
    'default_bot_user_ids': Set[int],
    'service_bot_tuples': List[Tuple[int, int]],
})

def get_recipient_info(recipient: Recipient,
                       sender_id: int,
                       stream_topic: Optional[StreamTopicTarget],
                       possibly_mentioned_user_ids: Optional[Set[int]]=None) -> RecipientInfoResult:
    stream_push_user_ids = set()  # type: Set[int]

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

        subscription_rows = stream_topic.get_active_subscriptions().values(
            'user_profile_id',
            'push_notifications',
            'in_home_view',
        ).order_by('user_profile_id')

        message_to_user_ids = [
            row['user_profile_id']
            for row in subscription_rows
        ]

        stream_push_user_ids = {
            row['user_profile_id']
            for row in subscription_rows
            # Note: muting a stream overrides stream_push_notify
            if row['push_notifications'] and row['in_home_view']
        } - stream_topic.user_ids_muting_topic()

    elif recipient.type == Recipient.HUDDLE:
        message_to_user_ids = get_huddle_user_ids(recipient)

    else:
        raise ValueError('Bad recipient type')

    message_to_user_id_set = set(message_to_user_ids)

    user_ids = set(message_to_user_id_set)
    if possibly_mentioned_user_ids:
        # Important note: Because we haven't rendered bugdown yet, we
        # don't yet know which of these possibly-mentioned users was
        # actually mentioned in the message (in other words, the
        # mention syntax might have been in a code block or otherwise
        # escaped).  `get_ids_for` will filter these extra user rows
        # for our data structures not related to bots
        user_ids |= possibly_mentioned_user_ids

    if user_ids:
        query = UserProfile.objects.filter(
            is_active=True,
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
            user_ids=sorted(list(user_ids)),
            field='id'
        )
        rows = list(query)
    else:
        # TODO: We should always have at least one user_id as a recipient
        #       of any message we send.  Right now the exception to this
        #       rule is `notify_new_user`, which, at least in a possibly
        #       contrived test scenario, can attempt to send messages
        #       to an inactive bot.  When we plug that hole, we can avoid
        #       this `else` clause and just `assert(user_ids)`.
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
        lambda r: r['enable_online_push_notifications']
    )

    # Service bots don't get UserMessage rows.
    um_eligible_user_ids = get_ids_for(
        lambda r: not is_service_bot(r)
    )

    long_term_idle_user_ids = get_ids_for(
        lambda r: r['long_term_idle']
    )

    # These two bot data structures need to filter from the full set
    # of users who either are receiving the message or might have been
    # mentioned in it, and so can't use get_ids_for.
    #
    # Further in the do_send_messages code path, once
    # `mentioned_user_ids` has been computed via bugdown, we'll filter
    # these data structures for just those users who are either a
    # direct recipient or were mentioned; for now, we're just making
    # sure we have the data we need for that without extra database
    # queries.
    default_bot_user_ids = set([
        row['id']
        for row in rows
        if row['is_bot'] and row['bot_type'] == UserProfile.DEFAULT_BOT
    ])

    service_bot_tuples = [
        (row['id'], row['bot_type'])
        for row in rows
        if is_service_bot(row)
    ]

    info = dict(
        active_user_ids=active_user_ids,
        push_notify_user_ids=push_notify_user_ids,
        stream_push_user_ids=stream_push_user_ids,
        um_eligible_user_ids=um_eligible_user_ids,
        long_term_idle_user_ids=long_term_idle_user_ids,
        default_bot_user_ids=default_bot_user_ids,
        service_bot_tuples=service_bot_tuples
    )  # type: RecipientInfoResult
    return info

def get_service_bot_events(sender: UserProfile, service_bot_tuples: List[Tuple[int, int]],
                           mentioned_user_ids: Set[int], active_user_ids: Set[int],
                           recipient_type: int) -> Dict[str, List[Dict[str, Any]]]:

    event_dict = defaultdict(list)  # type: Dict[str, List[Dict[str, Any]]]

    # Avoid infinite loops by preventing messages sent by bots from generating
    # Service events.
    if sender.is_bot:
        return event_dict

    for user_profile_id, bot_type in service_bot_tuples:
        if bot_type == UserProfile.OUTGOING_WEBHOOK_BOT:
            queue_name = 'outgoing_webhooks'
        elif bot_type == UserProfile.EMBEDDED_BOT:
            queue_name = 'embedded_bots'
        else:
            logging.error(
                'Unexpected bot_type for Service bot id=%s: %s' %
                (user_profile_id, bot_type))
            continue

        is_stream = (recipient_type == Recipient.STREAM)

        # Important note: service_bot_tuples may contain service bots
        # who were not actually mentioned in the message (e.g. if
        # mention syntax for that bot appeared in a code block).
        # Thus, it is important to filter any users who aren't part of
        # either mentioned_user_ids (the actual mentioned users) or
        # active_user_ids (the actual recipients).
        #
        # So even though this is implied by the logic below, we filter
        # these not-actually-mentioned users here, to help keep[ this
        # function future-proof.
        if user_profile_id not in mentioned_user_ids and user_profile_id not in active_user_ids:
            continue

        # Mention triggers, primarily for stream messages
        if user_profile_id in mentioned_user_ids:
            trigger = 'mention'
        # PM triggers for personal and huddle messsages
        elif (not is_stream) and (user_profile_id in active_user_ids):
            trigger = 'private_message'
        else:
            continue

        event_dict[queue_name].append({
            'trigger': trigger,
            'user_profile_id': user_profile_id,
        })

    return event_dict

def do_schedule_messages(messages: Sequence[Mapping[str, Any]]) -> List[int]:
    scheduled_messages = []  # type: List[ScheduledMessage]

    for message in messages:
        scheduled_message = ScheduledMessage()
        scheduled_message.sender = message['message'].sender
        scheduled_message.recipient = message['message'].recipient
        scheduled_message.subject = message['message'].subject
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


def do_send_messages(messages_maybe_none: Sequence[Optional[MutableMapping[str, Any]]],
                     email_gateway: Optional[bool]=False) -> List[int]:
    # Filter out messages which didn't pass internal_prep_message properly
    messages = [message for message in messages_maybe_none if message is not None]

    # Filter out zephyr mirror anomalies where the message was already sent
    already_sent_ids = []  # type: List[int]
    new_messages = []  # type: List[MutableMapping[str, Any]]
    for message in messages:
        if isinstance(message['message'], int):
            already_sent_ids.append(message['message'])
        else:
            new_messages.append(message)
    messages = new_messages

    links_for_embed = set()  # type: Set[Text]
    # For consistency, changes to the default values for these gets should also be applied
    # to the default args in do_send_message
    for message in messages:
        message['rendered_content'] = message.get('rendered_content', None)
        message['stream'] = message.get('stream', None)
        message['local_id'] = message.get('local_id', None)
        message['sender_queue_id'] = message.get('sender_queue_id', None)
        message['realm'] = message.get('realm', message['message'].sender.realm)

        mention_data = bugdown.MentionData(
            realm_id=message['realm'].id,
            content=message['message'].content,
        )
        message['mention_data'] = mention_data

        if message['message'].is_stream_message():
            stream_id = message['message'].recipient.type_id
            stream_topic = StreamTopicTarget(
                stream_id=stream_id,
                topic_name=message['message'].topic_name()
            )  # type: Optional[StreamTopicTarget]
        else:
            stream_topic = None

        info = get_recipient_info(
            recipient=message['message'].recipient,
            sender_id=message['message'].sender_id,
            stream_topic=stream_topic,
            possibly_mentioned_user_ids=mention_data.get_user_ids(),
        )

        message['active_user_ids'] = info['active_user_ids']
        message['push_notify_user_ids'] = info['push_notify_user_ids']
        message['stream_push_user_ids'] = info['stream_push_user_ids']
        message['um_eligible_user_ids'] = info['um_eligible_user_ids']
        message['long_term_idle_user_ids'] = info['long_term_idle_user_ids']
        message['default_bot_user_ids'] = info['default_bot_user_ids']
        message['service_bot_tuples'] = info['service_bot_tuples']

        # Render our messages.
        assert message['message'].rendered_content is None

        rendered_content = render_incoming_message(
            message['message'],
            message['message'].content,
            message['active_user_ids'],
            message['realm'],
            mention_data=message['mention_data'],
            email_gateway=email_gateway,
        )
        message['message'].rendered_content = rendered_content
        message['message'].rendered_content_version = bugdown_version
        links_for_embed |= message['message'].links_for_preview

        # Add members of the mentioned user groups into `mentions_user_ids`.
        mention_data = message['mention_data']
        for group_id in message['message'].mentions_user_group_ids:
            members = message['mention_data'].get_group_members(group_id)
            message['message'].mentions_user_ids.update(members)

        '''
        Once we have the actual list of mentioned ids from message
        rendering, we can patch in "default bots" (aka normal bots)
        who were directly mentioned in this message as eligible to
        get UserMessage rows.
        '''
        mentioned_user_ids = message['message'].mentions_user_ids
        default_bot_user_ids = message['default_bot_user_ids']
        mentioned_bot_user_ids = default_bot_user_ids & mentioned_user_ids
        message['um_eligible_user_ids'] |= mentioned_bot_user_ids

        # Update calculated fields of the message
        message['message'].update_calculated_fields()

    # Save the message receipts in the database
    user_message_flags = defaultdict(dict)  # type: Dict[int, Dict[int, List[str]]]
    with transaction.atomic():
        Message.objects.bulk_create([message['message'] for message in messages])
        ums = []  # type: List[UserMessageLite]
        for message in messages:
            # Service bots (outgoing webhook bots and embedded bots) don't store UserMessage rows;
            # they will be processed later.
            mentioned_user_ids = message['message'].mentions_user_ids
            user_messages = create_user_messages(
                message=message['message'],
                um_eligible_user_ids=message['um_eligible_user_ids'],
                long_term_idle_user_ids=message['long_term_idle_user_ids'],
                mentioned_user_ids=mentioned_user_ids,
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

        # Claim attachments in message
        for message in messages:
            if Message.content_has_attachment(message['message'].content):
                do_claim_attachments(message['message'])

    for message in messages:
        # Deliver events to the real-time push system, as well as
        # enqueuing any additional processing triggered by the message.
        wide_message_dict = MessageDict.wide_dict(message['message'])

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
            )
            for user_id in user_ids
        ]

        if message['message'].is_stream_message():
            # Note: This is where authorization for single-stream
            # get_updates happens! We only attach stream data to the
            # notify new_message request if it's a public stream,
            # ensuring that in the tornado server, non-public stream
            # messages are only associated to their subscribed users.
            if message['stream'] is None:
                stream_id = message['message'].recipient.type_id
                message['stream'] = Stream.objects.select_related("realm").get(id=stream_id)
            assert message['stream'] is not None  # assert needed because stubs for django are missing
            if message['stream'].is_public():
                event['realm_id'] = message['stream'].realm_id
                event['stream_name'] = message['stream'].name
            if message['stream'].invite_only:
                event['invite_only'] = True
        if message['local_id'] is not None:
            event['local_id'] = message['local_id']
        if message['sender_queue_id'] is not None:
            event['sender_queue_id'] = message['sender_queue_id']
        send_event(event, users)

        if url_embed_preview_enabled_for_realm(message['message']) and links_for_embed:
            event_data = {
                'message_id': message['message'].id,
                'message_content': message['message'].content,
                'message_realm_id': message['realm'].id,
                'urls': links_for_embed}
            queue_json_publish('embed_links', event_data)

        if (settings.ENABLE_FEEDBACK and settings.FEEDBACK_BOT and
                message['message'].recipient.type == Recipient.PERSONAL):

            feedback_bot_id = get_system_bot(email=settings.FEEDBACK_BOT).id
            if feedback_bot_id in message['active_user_ids']:
                queue_json_publish(
                    'feedback_messages',
                    wide_message_dict,
                )

        if message['message'].recipient.type == Recipient.PERSONAL:
            welcome_bot_id = get_system_bot(settings.WELCOME_BOT).id
            if (welcome_bot_id in message['active_user_ids'] and
                    welcome_bot_id != message['message'].sender_id):
                send_welcome_bot_response(message)

        for queue_name, events in message['message'].service_queue_events.items():
            for event in events:
                queue_json_publish(
                    queue_name,
                    {
                        "message": wide_message_dict,
                        "trigger": event['trigger'],
                        "user_profile_id": event["user_profile_id"],
                    }
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
    def __init__(self, user_profile_id: int, message_id: int) -> None:
        self.user_profile_id = user_profile_id
        self.message_id = message_id
        self.flags = 0

    def flags_list(self) -> List[str]:
        return UserMessage.flags_list_for_flags(self.flags)

def create_user_messages(message: Message,
                         um_eligible_user_ids: Set[int],
                         long_term_idle_user_ids: Set[int],
                         mentioned_user_ids: Set[int]) -> List[UserMessageLite]:
    ums_to_create = []

    for user_profile_id in um_eligible_user_ids:
        um = UserMessageLite(
            user_profile_id=user_profile_id,
            message_id=message.id,
        )
        ums_to_create.append(um)

    # These properties on the Message are set via
    # render_markdown by code in the bugdown inline patterns
    wildcard = message.mentions_wildcard
    ids_with_alert_words = message.user_ids_with_alert_words

    for um in ums_to_create:
        if um.user_profile_id == message.sender.id and \
                message.sent_by_human():
            um.flags |= UserMessage.flags.read
        if wildcard:
            um.flags |= UserMessage.flags.wildcard_mentioned
        if um.user_profile_id in mentioned_user_ids:
            um.flags |= UserMessage.flags.mentioned
        if um.user_profile_id in ids_with_alert_words:
            um.flags |= UserMessage.flags.has_alert_word

    user_messages = []
    for um in ums_to_create:
        if (um.user_profile_id in long_term_idle_user_ids and
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

    vals = ','.join([
        '(%d, %d, %d)' % (um.user_profile_id, um.message_id, um.flags)
        for um in ums
    ])
    query = '''
        INSERT into
            zerver_usermessage (user_profile_id, message_id, flags)
        VALUES
    ''' + vals

    with connection.cursor() as cursor:
        cursor.execute(query)

def notify_reaction_update(user_profile: UserProfile, message: Message,
                           reaction: Reaction, op: Text) -> None:
    user_dict = {'user_id': user_profile.id,
                 'email': user_profile.email,
                 'full_name': user_profile.full_name}

    event = {'type': 'reaction',
             'op': op,
             'user': user_dict,
             'message_id': message.id,
             'emoji_name': reaction.emoji_name,
             'emoji_code': reaction.emoji_code,
             'reaction_type': reaction.reaction_type}  # type: Dict[str, Any]

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
    send_event(event, [um.user_profile_id for um in ums])

def do_add_reaction_legacy(user_profile: UserProfile, message: Message, emoji_name: Text) -> None:
    (emoji_code, reaction_type) = emoji_name_to_emoji_code(user_profile.realm, emoji_name)
    reaction = Reaction(user_profile=user_profile, message=message,
                        emoji_name=emoji_name, emoji_code=emoji_code,
                        reaction_type=reaction_type)
    reaction.save()
    notify_reaction_update(user_profile, message, reaction, "add")

def do_remove_reaction_legacy(user_profile: UserProfile, message: Message, emoji_name: Text) -> None:
    reaction = Reaction.objects.filter(user_profile=user_profile,
                                       message=message,
                                       emoji_name=emoji_name).get()
    reaction.delete()
    notify_reaction_update(user_profile, message, reaction, "remove")

def do_add_reaction(user_profile: UserProfile, message: Message,
                    emoji_name: Text, emoji_code: Text, reaction_type: Text) -> None:
    reaction = Reaction(user_profile=user_profile, message=message,
                        emoji_name=emoji_name, emoji_code=emoji_code,
                        reaction_type=reaction_type)
    reaction.save()
    notify_reaction_update(user_profile, message, reaction, "add")

def do_remove_reaction(user_profile: UserProfile, message: Message,
                       emoji_code: Text, reaction_type: Text) -> None:
    reaction = Reaction.objects.filter(user_profile=user_profile,
                                       message=message,
                                       emoji_code=emoji_code,
                                       reaction_type=reaction_type).get()
    reaction.delete()
    notify_reaction_update(user_profile, message, reaction, "remove")

def do_send_typing_notification(notification: Dict[str, Any]) -> None:
    recipient_user_profiles = get_typing_user_profiles(notification['recipient'],
                                                       notification['sender'].id)
    # Only deliver the notification to active user recipients
    user_ids_to_notify = [profile.id for profile in recipient_user_profiles if profile.is_active]
    sender_dict = {'user_id': notification['sender'].id, 'email': notification['sender'].email}
    # Include a list of recipients in the event body to help identify where the typing is happening
    recipient_dicts = [{'user_id': profile.id, 'email': profile.email}
                       for profile in recipient_user_profiles]
    event = dict(
        type            = 'typing',
        op              = notification['op'],
        sender          = sender_dict,
        recipients      = recipient_dicts)

    send_event(event, user_ids_to_notify)

# check_send_typing_notification:
# Checks the typing notification and sends it
def check_send_typing_notification(sender: UserProfile, notification_to: Sequence[Text],
                                   operator: Text) -> None:
    typing_notification = check_typing_notification(sender, notification_to, operator)
    do_send_typing_notification(typing_notification)

# check_typing_notification:
# Returns typing notification ready for sending with do_send_typing_notification on success
# or the error message (string) on error.
def check_typing_notification(sender: UserProfile, notification_to: Sequence[Text],
                              operator: Text) -> Dict[str, Any]:
    if len(notification_to) == 0:
        raise JsonableError(_('Missing parameter: \'to\' (recipient)'))
    elif operator not in ('start', 'stop'):
        raise JsonableError(_('Invalid \'op\' value (should be start or stop)'))
    else:
        try:
            recipient = recipient_for_emails(notification_to, False,
                                             sender, sender)
        except ValidationError as e:
            assert isinstance(e.messages[0], str)
            raise JsonableError(e.messages[0])
    if recipient.type == Recipient.STREAM:
        raise ValueError('Forbidden recipient type')
    return {'sender': sender, 'recipient': recipient, 'op': operator}

def stream_welcome_message(stream: Stream) -> Text:
    content = _('Welcome to #**%s**.') % (stream.name,)

    if stream.description:
        content += '\n\n**' + _('Description') + '**: '
        content += stream.description

    return content

def prep_stream_welcome_message(stream: Stream) -> Optional[Dict[str, Any]]:
    realm = stream.realm
    sender = get_system_bot(settings.WELCOME_BOT)
    topic = _('hello')
    content = stream_welcome_message(stream)

    message = internal_prep_stream_message(
        realm=realm,
        sender=sender,
        stream_name=stream.name,
        topic=topic,
        content=content)

    return message

def send_stream_creation_event(stream: Stream, user_ids: List[int]) -> None:
    event = dict(type="stream", op="create",
                 streams=[stream.to_dict()])
    send_event(event, user_ids)

def create_stream_if_needed(realm: Realm,
                            stream_name: Text,
                            invite_only: bool=False,
                            stream_description: Text="") -> Tuple[Stream, bool]:
    (stream, created) = Stream.objects.get_or_create(
        realm=realm,
        name__iexact=stream_name,
        defaults = dict(
            name=stream_name,
            description=stream_description,
            invite_only=invite_only,
            is_in_zephyr_realm=realm.is_zephyr_mirror_realm
        )
    )

    if created:
        Recipient.objects.create(type_id=stream.id, type=Recipient.STREAM)
        if stream.is_public():
            send_stream_creation_event(stream, active_user_ids(stream.realm_id))
        else:
            realm_admin_ids = [user.id for user in stream.realm.get_admin_users()]
            send_stream_creation_event(stream, realm_admin_ids)
    return stream, created

def ensure_stream(realm: Realm,
                  stream_name: Text,
                  invite_only: bool=False,
                  stream_description: Text="") -> Stream:
    return create_stream_if_needed(realm, stream_name, invite_only, stream_description)[0]

def create_streams_if_needed(realm: Realm,
                             stream_dicts: List[Mapping[str, Any]]) -> Tuple[List[Stream], List[Stream]]:
    """Note that stream_dict["name"] is assumed to already be stripped of
    whitespace"""
    added_streams = []  # type: List[Stream]
    existing_streams = []  # type: List[Stream]
    for stream_dict in stream_dicts:
        stream, created = create_stream_if_needed(realm,
                                                  stream_dict["name"],
                                                  invite_only=stream_dict.get("invite_only", False),
                                                  stream_description=stream_dict.get("description", ""))

        if created:
            added_streams.append(stream)
        else:
            existing_streams.append(stream)

    return added_streams, existing_streams


def get_recipient_from_user_ids(recipient_profile_ids: Set[int],
                                not_forged_mirror_message: bool,
                                forwarder_user_profile: Optional[UserProfile],
                                sender: UserProfile) -> Recipient:

    # Avoid mutating the passed in set of recipient_profile_ids.
    recipient_profile_ids = set(recipient_profile_ids)

    # If the private message is just between the sender and
    # another person, force it to be a personal internally

    if not_forged_mirror_message:
        assert forwarder_user_profile is not None
        if forwarder_user_profile.id not in recipient_profile_ids:
            raise ValidationError(_("User not authorized for this query"))

    if (len(recipient_profile_ids) == 2 and sender.id in recipient_profile_ids):
        recipient_profile_ids.remove(sender.id)

    if len(recipient_profile_ids) > 1:
        # Make sure the sender is included in huddle messages
        recipient_profile_ids.add(sender.id)
        return get_huddle_recipient(recipient_profile_ids)
    else:
        return get_personal_recipient(list(recipient_profile_ids)[0])

def validate_recipient_user_profiles(user_profiles: List[UserProfile],
                                     sender: UserProfile) -> Set[int]:
    recipient_profile_ids = set()

    # We exempt cross-realm bots from the check that all the recipients
    # are in the same realm.
    realms = set()
    if not is_cross_realm_bot_email(sender.email):
        realms.add(sender.realm_id)

    for user_profile in user_profiles:
        if (not user_profile.is_active and not user_profile.is_mirror_dummy) or \
                user_profile.realm.deactivated:
            raise ValidationError(_("'%s' is no longer using Zulip.") % (user_profile.email,))
        recipient_profile_ids.add(user_profile.id)
        if not is_cross_realm_bot_email(user_profile.email):
            realms.add(user_profile.realm_id)

    if len(realms) > 1:
        raise ValidationError(_("You can't send private messages outside of your organization."))

    return recipient_profile_ids

def recipient_for_emails(emails: Iterable[Text], not_forged_mirror_message: bool,
                         forwarder_user_profile: Optional[UserProfile],
                         sender: UserProfile) -> Recipient:

    user_profiles = user_profiles_from_unvalidated_emails(emails, sender.realm)

    return recipient_for_user_profiles(
        user_profiles=user_profiles,
        not_forged_mirror_message=not_forged_mirror_message,
        forwarder_user_profile=forwarder_user_profile,
        sender=sender
    )

def recipient_for_user_profiles(user_profiles: List[UserProfile], not_forged_mirror_message: bool,
                                forwarder_user_profile: Optional[UserProfile],
                                sender: UserProfile) -> Recipient:

    recipient_profile_ids = validate_recipient_user_profiles(user_profiles, sender)

    return get_recipient_from_user_ids(recipient_profile_ids, not_forged_mirror_message,
                                       forwarder_user_profile, sender)

def already_sent_mirrored_message_id(message: Message) -> Optional[int]:
    if message.recipient.type == Recipient.HUDDLE:
        # For huddle messages, we use a 10-second window because the
        # timestamps aren't guaranteed to actually match between two
        # copies of the same message.
        time_window = datetime.timedelta(seconds=10)
    else:
        time_window = datetime.timedelta(seconds=0)

    messages = Message.objects.filter(
        sender=message.sender,
        recipient=message.recipient,
        content=message.content,
        subject=message.subject,
        sending_client=message.sending_client,
        pub_date__gte=message.pub_date - time_window,
        pub_date__lte=message.pub_date + time_window)

    if messages.exists():
        return messages[0].id
    return None

def extract_recipients(s: Union[str, Iterable[Text]]) -> List[Text]:
    # We try to accept multiple incoming formats for recipients.
    # See test_extract_recipients() for examples of what we allow.
    try:
        data = ujson.loads(s)  # type: ignore # This function has a super weird union argument.
    except ValueError:
        data = s

    if isinstance(data, str):
        data = data.split(',')

    if not isinstance(data, list):
        raise ValueError("Invalid data type for recipients")

    recipients = data

    # Strip recipients, and then remove any duplicates and any that
    # are the empty string after being stripped.
    recipients = [recipient.strip() for recipient in recipients]
    return list(set(recipient for recipient in recipients if recipient))

def check_send_stream_message(sender: UserProfile, client: Client, stream_name: Text,
                              topic: Text, body: Text) -> int:
    addressee = Addressee.for_stream(stream_name, topic)
    message = check_message(sender, client, addressee, body)

    return do_send_messages([message])[0]

def check_send_private_message(sender: UserProfile, client: Client,
                               receiving_user: UserProfile, body: Text) -> int:
    addressee = Addressee.for_user_profile(receiving_user)
    message = check_message(sender, client, addressee, body)

    return do_send_messages([message])[0]

# check_send_message:
# Returns the id of the sent message.  Has same argspec as check_message.
def check_send_message(sender: UserProfile, client: Client, message_type_name: Text,
                       message_to: Sequence[Text], topic_name: Optional[Text],
                       message_content: Text, realm: Optional[Realm]=None,
                       forged: bool=False, forged_timestamp: Optional[float]=None,
                       forwarder_user_profile: Optional[UserProfile]=None,
                       local_id: Optional[Text]=None,
                       sender_queue_id: Optional[Text]=None) -> int:

    addressee = Addressee.legacy_build(
        sender,
        message_type_name,
        message_to,
        topic_name)

    message = check_message(sender, client, addressee,
                            message_content, realm, forged, forged_timestamp,
                            forwarder_user_profile, local_id, sender_queue_id)
    return do_send_messages([message])[0]

def check_schedule_message(sender: UserProfile, client: Client,
                           message_type_name: Text, message_to: Sequence[Text],
                           topic_name: Optional[Text], message_content: Text,
                           delivery_type: Text, deliver_at: datetime.datetime,
                           realm: Optional[Realm]=None,
                           forwarder_user_profile: Optional[UserProfile]=None
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
    return do_schedule_messages([message])[0]

def check_stream_name(stream_name: Text) -> None:
    if stream_name.strip() == "":
        raise JsonableError(_("Invalid stream name '%s'" % (stream_name)))
    if len(stream_name) > Stream.MAX_NAME_LENGTH:
        raise JsonableError(_("Stream name too long (limit: %s characters)." % (Stream.MAX_NAME_LENGTH)))
    for i in stream_name:
        if ord(i) == 0:
            raise JsonableError(_("Stream name '%s' contains NULL (0x00) characters." % (stream_name)))

def check_default_stream_group_name(group_name: Text) -> None:
    if group_name.strip() == "":
        raise JsonableError(_("Invalid default stream group name '%s'" % (group_name)))
    if len(group_name) > DefaultStreamGroup.MAX_NAME_LENGTH:
        raise JsonableError(_("Default stream group name too long (limit: %s characters)"
                            % (DefaultStreamGroup.MAX_NAME_LENGTH)))
    for i in group_name:
        if ord(i) == 0:
            raise JsonableError(_("Default stream group name '%s' contains NULL (0x00) characters."
                                % (group_name)))

def send_pm_if_empty_stream(sender: UserProfile,
                            stream: Optional[Stream],
                            stream_name: Text,
                            realm: Realm) -> None:
    """If a bot sends a message to a stream that doesn't exist or has no
    subscribers, sends a notification to the bot owner (if not a
    cross-realm bot) so that the owner can correct the issue."""
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

    if stream is not None:
        num_subscribers = num_subscribers_for_stream_id(stream.id)
        if num_subscribers > 0:
            return

    # We warn the user once every 5 minutes to avoid a flood of
    # PMs on a misconfigured integration, re-using the
    # UserProfile.last_reminder field, which is not used for bots.
    last_reminder = sender.last_reminder
    waitperiod = datetime.timedelta(minutes=UserProfile.BOT_OWNER_STREAM_ALERT_WAITPERIOD)
    if last_reminder and timezone_now() - last_reminder <= waitperiod:
        return

    if stream is None:
        error_msg = "that stream does not yet exist. To create it, "
    else:
        # num_subscribers == 0
        error_msg = "there are no subscribers to that stream. To join it, "

    content = ("Hi there! We thought you'd like to know that your bot **%s** just "
               "tried to send a message to stream `%s`, but %s"
               "click the gear in the left-side stream list." %
               (sender.full_name, stream_name, error_msg))

    internal_send_private_message(realm, get_system_bot(settings.NOTIFICATION_BOT),
                                  sender.bot_owner, content)

    sender.last_reminder = timezone_now()
    sender.save(update_fields=['last_reminder'])

# check_message:
# Returns message ready for sending with do_send_message on success or the error message (string) on error.
def check_message(sender: UserProfile, client: Client, addressee: Addressee,
                  message_content_raw: Text, realm: Optional[Realm]=None, forged: bool=False,
                  forged_timestamp: Optional[float]=None,
                  forwarder_user_profile: Optional[UserProfile]=None,
                  local_id: Optional[Text]=None,
                  sender_queue_id: Optional[Text]=None) -> Dict[str, Any]:
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
        stream_name = addressee.stream_name()

        stream_name = stream_name.strip()
        check_stream_name(stream_name)

        topic_name = addressee.topic()
        topic_name = truncate_topic(topic_name)

        try:
            stream = get_stream(stream_name, realm)

            send_pm_if_empty_stream(sender, stream, stream_name, realm)

        except Stream.DoesNotExist:
            send_pm_if_empty_stream(sender, None, stream_name, realm)
            raise StreamDoesNotExistError(escape(stream_name))
        recipient = get_stream_recipient(stream.id)

        if not stream.invite_only:
            # This is a public stream
            pass
        elif subscribed_to_stream(sender, stream.id):
            # Or it is private, but your are subscribed
            pass
        elif sender.is_api_super_user or (forwarder_user_profile is not None and
                                          forwarder_user_profile.is_api_super_user):
            # Or this request is being done on behalf of a super user
            pass
        elif sender.is_bot and (sender.bot_owner is not None and
                                subscribed_to_stream(sender.bot_owner, stream.id)):
            # Or you're a bot and your owner is subscribed.
            pass
        elif sender.email == settings.WELCOME_BOT:
            # The welcome bot welcomes folks to the stream.
            pass
        elif sender.email == settings.NOTIFICATION_BOT:
            pass
        else:
            # All other cases are an error.
            raise JsonableError(_("Not authorized to send to stream '%s'") % (stream.name,))

    elif addressee.is_private():
        user_profiles = addressee.user_profiles()

        if user_profiles is None or len(user_profiles) == 0:
            raise JsonableError(_("Message must have recipients"))

        mirror_message = client and client.name in ["zephyr_mirror", "irc_mirror",
                                                    "jabber_mirror", "JabberMirror"]
        not_forged_mirror_message = mirror_message and not forged
        try:
            recipient = recipient_for_user_profiles(user_profiles, not_forged_mirror_message,
                                                    forwarder_user_profile, sender)
        except ValidationError as e:
            assert isinstance(e.messages[0], str)
            raise JsonableError(e.messages[0])
    else:
        raise JsonableError(_("Invalid message type"))

    message = Message()
    message.sender = sender
    message.content = message_content
    message.recipient = recipient
    if addressee.is_stream():
        message.subject = topic_name
    if forged and forged_timestamp is not None:
        # Forged messages come with a timestamp
        message.pub_date = timestamp_to_datetime(forged_timestamp)
    else:
        message.pub_date = timezone_now()
    message.sending_client = client

    # We render messages later in the process.
    assert message.rendered_content is None

    if client.name == "zephyr_mirror":
        id = already_sent_mirrored_message_id(message)
        if id is not None:
            return {'message': id}

    return {'message': message, 'stream': stream, 'local_id': local_id,
            'sender_queue_id': sender_queue_id, 'realm': realm}

def _internal_prep_message(realm: Realm,
                           sender: UserProfile,
                           addressee: Addressee,
                           content: Text) -> Optional[Dict[str, Any]]:
    """
    Create a message object and checks it, but doesn't send it or save it to the database.
    The internal function that calls this can therefore batch send a bunch of created
    messages together as one database query.
    Call do_send_messages with a list of the return values of this method.
    """
    # Remove any null bytes from the content
    if len(content) > MAX_MESSAGE_LENGTH:
        content = content[0:3900] + "\n\n[message was too long and has been truncated]"

    if realm is None:
        raise RuntimeError("None is not a valid realm for internal_prep_message!")

    if addressee.is_stream():
        ensure_stream(realm, addressee.stream_name())

    try:
        return check_message(sender, get_client("Internal"), addressee,
                             content, realm=realm)
    except JsonableError as e:
        logging.exception("Error queueing internal message by %s: %s" % (sender.email, e))

    return None

def internal_prep_stream_message(realm: Realm, sender: UserProfile,
                                 stream_name: Text, topic: Text,
                                 content: Text) -> Optional[Dict[str, Any]]:
    """
    See _internal_prep_message for details of how this works.
    """
    addressee = Addressee.for_stream(stream_name, topic)

    return _internal_prep_message(
        realm=realm,
        sender=sender,
        addressee=addressee,
        content=content,
    )

def internal_prep_private_message(realm: Realm,
                                  sender: UserProfile,
                                  recipient_user: UserProfile,
                                  content: Text) -> Optional[Dict[str, Any]]:
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

def internal_send_message(realm: Realm, sender_email: Text, recipient_type_name: str,
                          recipients: Text, topic_name: Text, content: Text,
                          email_gateway: Optional[bool]=False) -> None:
    """internal_send_message should only be used where `sender_email` is a
    system bot."""

    # Verify the user is in fact a system bot
    assert(is_cross_realm_bot_email(sender_email) or sender_email == settings.ERROR_BOT)

    sender = get_system_bot(sender_email)
    parsed_recipients = extract_recipients(recipients)

    addressee = Addressee.legacy_build(
        sender,
        recipient_type_name,
        parsed_recipients,
        topic_name,
        realm=realm)

    msg = _internal_prep_message(
        realm=realm,
        sender=sender,
        addressee=addressee,
        content=content,
    )
    if msg is None:
        return

    do_send_messages([msg], email_gateway=email_gateway)

def internal_send_private_message(realm: Realm,
                                  sender: UserProfile,
                                  recipient_user: UserProfile,
                                  content: Text) -> None:
    message = internal_prep_private_message(realm, sender, recipient_user, content)
    if message is None:
        return
    do_send_messages([message])

def internal_send_stream_message(realm: Realm, sender: UserProfile, stream_name: str,
                                 topic: str, content: str) -> None:
    message = internal_prep_stream_message(realm, sender, stream_name, topic, content)
    if message is None:
        return
    do_send_messages([message])

def internal_send_huddle_message(realm: Realm, sender: UserProfile, emails: List[str],
                                 content: str) -> None:
    addressee = Addressee.for_private(emails, realm)
    message = _internal_prep_message(
        realm=realm,
        sender=sender,
        addressee=addressee,
        content=content,
    )
    if message is None:
        return
    do_send_messages([message])

def pick_color(user_profile: UserProfile) -> Text:
    subs = get_stream_subscriptions_for_user(user_profile).filter(active=True)
    return pick_color_helper(user_profile, subs)

def pick_color_helper(user_profile: UserProfile, subs: Iterable[Subscription]) -> Text:
    # These colors are shared with the palette in subs.js.
    used_colors = [sub.color for sub in subs if sub.active]
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
         "invite_only": stream.invite_only},
        # We use a lambda here so that we only compute whether the
        # user is subscribed if we have to
        lambda: subscribed_to_stream(cast(UserProfile, user_profile), stream.id))

def validate_user_access_to_subscribers_helper(user_profile: Optional[UserProfile],
                                               stream_dict: Mapping[str, Any],
                                               check_user_subscribed: Callable[[], bool]) -> None:
    """ Helper for validate_user_access_to_subscribers that doesn't require a full stream object

    * check_user_subscribed reports whether the user is subscribed to the stream.
    """
    if user_profile is None:
        raise ValidationError("Missing user to validate access for")

    if user_profile.realm_id != stream_dict["realm_id"]:
        raise ValidationError("Requesting user not in given realm")

    if user_profile.realm.is_zephyr_mirror_realm and not stream_dict["invite_only"]:
        raise JsonableError(_("Subscriber data is not available for this stream"))

    # Organization administrators can view subscribers for all streams.
    if user_profile.is_realm_admin:
        return

    if (stream_dict["invite_only"] and not check_user_subscribed()):
        raise JsonableError(_("Unable to retrieve subscribers for invite-only stream"))

def bulk_get_subscriber_user_ids(stream_dicts: Iterable[Mapping[str, Any]],
                                 user_profile: UserProfile,
                                 sub_dict: Mapping[int, bool],
                                 stream_recipient: StreamRecipientMap) -> Dict[int, List[int]]:
    """sub_dict maps stream_id => whether the user is subscribed to that stream."""
    target_stream_dicts = []
    for stream_dict in stream_dicts:
        try:
            validate_user_access_to_subscribers_helper(user_profile, stream_dict,
                                                       lambda: sub_dict[stream_dict["id"]])
        except JsonableError:
            continue
        target_stream_dicts.append(stream_dict)

    stream_ids = [stream['id'] for stream in target_stream_dicts]
    stream_recipient.populate_for_stream_ids(stream_ids)
    recipient_ids = sorted([
        stream_recipient.recipient_id_for(stream_id)
        for stream_id in stream_ids
    ])

    result = dict((stream["id"], []) for stream in stream_dicts)  # type: Dict[int, List[int]]
    if not recipient_ids:
        return result

    '''
    The raw SQL below leads to more than a 2x speedup when tested with
    20k+ total subscribers.  (For large realms with lots of default
    streams, this function deals with LOTS of data, so it is important
    to optimize.)
    '''

    id_list = ', '.join(str(recipient_id) for recipient_id in recipient_ids)

    query = '''
        SELECT
            zerver_subscription.recipient_id,
            zerver_subscription.user_profile_id
        FROM
            zerver_subscription
        INNER JOIN zerver_userprofile ON
            zerver_userprofile.id = zerver_subscription.user_profile_id
        WHERE
            zerver_subscription.recipient_id in (%s) AND
            zerver_subscription.active AND
            zerver_userprofile.is_active
        ORDER BY
            zerver_subscription.recipient_id
        ''' % (id_list,)

    cursor = connection.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.close()

    recip_to_stream_id = stream_recipient.recipient_to_stream_id_dict()

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
        user_profile__is_active=True
    )
    return subscriptions

def get_subscribers(stream: Stream,
                    requesting_user: Optional[UserProfile]=None) -> List[UserProfile]:
    subscriptions = get_subscribers_query(stream, requesting_user).select_related()
    return [subscription.user_profile for subscription in subscriptions]

def get_subscriber_emails(stream: Stream,
                          requesting_user: Optional[UserProfile]=None) -> List[Text]:
    subscriptions_query = get_subscribers_query(stream, requesting_user)
    subscriptions = subscriptions_query.values('user_profile__email')
    return [subscription['user_profile__email'] for subscription in subscriptions]

def maybe_get_subscriber_emails(stream: Stream, user_profile: UserProfile) -> List[Text]:
    """ Alternate version of get_subscriber_emails that takes a Stream object only
    (not a name), and simply returns an empty list if unable to get a real
    subscriber list (because we're on the MIT realm). """
    try:
        subscribers = get_subscriber_emails(stream, requesting_user=user_profile)
    except JsonableError:
        subscribers = []
    return subscribers

def notify_subscriptions_added(user_profile: UserProfile,
                               sub_pairs: Iterable[Tuple[Subscription, Stream]],
                               stream_user_ids: Callable[[Stream], List[int]],
                               recent_traffic: Dict[int, int],
                               no_log: bool=False) -> None:
    if not no_log:
        log_event({'type': 'subscription_added',
                   'user': user_profile.email,
                   'names': [stream.name for sub, stream in sub_pairs],
                   'realm': user_profile.realm.string_id})

    # Send a notification to the user who subscribed.
    payload = [dict(name=stream.name,
                    stream_id=stream.id,
                    in_home_view=subscription.in_home_view,
                    invite_only=stream.invite_only,
                    color=subscription.color,
                    email_address=encode_email_address(stream),
                    desktop_notifications=subscription.desktop_notifications,
                    audible_notifications=subscription.audible_notifications,
                    push_notifications=subscription.push_notifications,
                    description=stream.description,
                    pin_to_top=subscription.pin_to_top,
                    is_old_stream=is_old_stream(stream.date_created),
                    stream_weekly_traffic=get_average_weekly_stream_traffic(
                        stream.id, stream.date_created, recent_traffic),
                    subscribers=stream_user_ids(stream))
               for (subscription, stream) in sub_pairs]
    event = dict(type="subscription", op="add",
                 subscriptions=payload)
    send_event(event, [user_profile.id])

def get_peer_user_ids_for_stream_change(stream: Stream,
                                        altered_user_ids: Iterable[int],
                                        subscribed_user_ids: Iterable[int]) -> Set[int]:
    '''
    altered_user_ids is the user_ids that we are adding/removing
    subscribed_user_ids is the already-subscribed user_ids

    Based on stream policy, we notify the correct bystanders, while
    not notifying altered_users (who get subscribers via another event)
    '''

    if stream.invite_only:
        # PRIVATE STREAMS
        # Realm admins can access all private stream subscribers. Send them an
        # event even if they aren't subscribed to stream.
        realm_admin_ids = [user.id for user in stream.realm.get_admin_users()]
        user_ids_to_notify = []
        user_ids_to_notify.extend(realm_admin_ids)
        user_ids_to_notify.extend(subscribed_user_ids)
        return set(user_ids_to_notify) - set(altered_user_ids)

    else:
        # PUBLIC STREAMS
        # We now do "peer_add" or "peer_remove" events even for streams
        # users were never subscribed to, in order for the neversubscribed
        # structure to stay up-to-date.
        return set(active_user_ids(stream.realm_id)) - set(altered_user_ids)

def get_user_ids_for_streams(streams: Iterable[Stream]) -> Dict[int, List[int]]:
    stream_ids = [stream.id for stream in streams]

    all_subs = get_active_subscriptions_for_stream_ids(stream_ids).filter(
        user_profile__is_active=True,
    ).values(
        'recipient__type_id',
        'user_profile_id',
    ).order_by(
        'recipient__type_id',
    )

    get_stream_id = itemgetter('recipient__type_id')

    all_subscribers_by_stream = defaultdict(list)  # type: Dict[int, List[int]]
    for stream_id, rows in itertools.groupby(all_subs, get_stream_id):
        user_ids = [row['user_profile_id'] for row in rows]
        all_subscribers_by_stream[stream_id] = user_ids

    return all_subscribers_by_stream

SubT = Tuple[List[Tuple[UserProfile, Stream]], List[Tuple[UserProfile, Stream]]]
def bulk_add_subscriptions(streams: Iterable[Stream],
                           users: Iterable[UserProfile],
                           from_stream_creation: bool=False,
                           acting_user: Optional[UserProfile]=None) -> SubT:
    users = list(users)

    recipients_map = bulk_get_recipients(Recipient.STREAM, [stream.id for stream in streams])  # type: Mapping[int, Recipient]
    recipients = [recipient.id for recipient in recipients_map.values()]  # type: List[int]

    stream_map = {}  # type: Dict[int, Stream]
    for stream in streams:
        stream_map[recipients_map[stream.id].id] = stream

    subs_by_user = defaultdict(list)  # type: Dict[int, List[Subscription]]
    all_subs_query = get_stream_subscriptions_for_users(users).select_related('user_profile')
    for sub in all_subs_query:
        subs_by_user[sub.user_profile_id].append(sub)

    already_subscribed = []  # type: List[Tuple[UserProfile, Stream]]
    subs_to_activate = []  # type: List[Tuple[Subscription, Stream]]
    new_subs = []  # type: List[Tuple[UserProfile, int, Stream]]
    for user_profile in users:
        needs_new_sub = set(recipients)  # type: Set[int]
        for sub in subs_by_user[user_profile.id]:
            if sub.recipient_id in needs_new_sub:
                needs_new_sub.remove(sub.recipient_id)
                if sub.active:
                    already_subscribed.append((user_profile, stream_map[sub.recipient_id]))
                else:
                    subs_to_activate.append((sub, stream_map[sub.recipient_id]))
                    # Mark the sub as active, without saving, so that
                    # pick_color will consider this to be an active
                    # subscription when picking colors
                    sub.active = True
        for recipient_id in needs_new_sub:
            new_subs.append((user_profile, recipient_id, stream_map[recipient_id]))

    subs_to_add = []  # type: List[Tuple[Subscription, Stream]]
    for (user_profile, recipient_id, stream) in new_subs:
        color = pick_color_helper(user_profile, subs_by_user[user_profile.id])
        sub_to_add = Subscription(user_profile=user_profile, active=True,
                                  color=color, recipient_id=recipient_id,
                                  desktop_notifications=user_profile.enable_stream_desktop_notifications,
                                  audible_notifications=user_profile.enable_stream_sounds,
                                  push_notifications=user_profile.enable_stream_push_notifications,
                                  )
        subs_by_user[user_profile.id].append(sub_to_add)
        subs_to_add.append((sub_to_add, stream))

    # TODO: XXX: This transaction really needs to be done at the serializeable
    # transaction isolation level.
    with transaction.atomic():
        occupied_streams_before = list(get_occupied_streams(user_profile.realm))
        Subscription.objects.bulk_create([sub for (sub, stream) in subs_to_add])
        sub_ids = [sub.id for (sub, stream) in subs_to_activate]
        Subscription.objects.filter(id__in=sub_ids).update(active=True)
        occupied_streams_after = list(get_occupied_streams(user_profile.realm))

    # Log Subscription Activities in RealmAuditLog
    event_time = timezone_now()
    event_last_message_id = Message.objects.aggregate(Max('id'))['id__max']
    if event_last_message_id is None:
        # During initial realm creation, there might be 0 messages in
        # the database; in that case, the `aggregate` query returns
        # None.  Since we want an int for "beginning of time", use -1.
        event_last_message_id = -1

    all_subscription_logs = []  # type: (List[RealmAuditLog])
    for (sub, stream) in subs_to_add:
        all_subscription_logs.append(RealmAuditLog(realm=sub.user_profile.realm,
                                                   acting_user=acting_user,
                                                   modified_user=sub.user_profile,
                                                   modified_stream=stream,
                                                   event_last_message_id=event_last_message_id,
                                                   event_type='subscription_created',
                                                   event_time=event_time))
    for (sub, stream) in subs_to_activate:
        all_subscription_logs.append(RealmAuditLog(realm=sub.user_profile.realm,
                                                   acting_user=acting_user,
                                                   modified_user=sub.user_profile,
                                                   modified_stream=stream,
                                                   event_last_message_id=event_last_message_id,
                                                   event_type='subscription_activated',
                                                   event_time=event_time))
    # Now since we have all log objects generated we can do a bulk insert
    RealmAuditLog.objects.bulk_create(all_subscription_logs)

    new_occupied_streams = [stream for stream in
                            set(occupied_streams_after) - set(occupied_streams_before)
                            if not stream.invite_only]
    if new_occupied_streams and not from_stream_creation:
        event = dict(type="stream", op="occupy",
                     streams=[stream.to_dict()
                              for stream in new_occupied_streams])
        send_event(event, active_user_ids(user_profile.realm_id))

    # Notify all existing users on streams that users have joined

    # First, get all users subscribed to the streams that we care about
    # We fetch all subscription information upfront, as it's used throughout
    # the following code and we want to minize DB queries
    all_subscribers_by_stream = get_user_ids_for_streams(streams=streams)

    def fetch_stream_subscriber_user_ids(stream: Stream) -> List[int]:
        if stream.is_in_zephyr_realm and not stream.invite_only:
            return []
        user_ids = all_subscribers_by_stream[stream.id]
        return user_ids

    sub_tuples_by_user = defaultdict(list)  # type: Dict[int, List[Tuple[Subscription, Stream]]]
    new_streams = set()  # type: Set[Tuple[int, int]]
    for (sub, stream) in subs_to_add + subs_to_activate:
        sub_tuples_by_user[sub.user_profile.id].append((sub, stream))
        new_streams.add((sub.user_profile.id, stream.id))

    # We now send several types of events to notify browsers.  The
    # first batch is notifications to users on invite-only streams
    # that the stream exists.
    for stream in streams:
        if not stream.is_public():
            # Users newly added to invite-only streams
            # need a `create` notification.  The former, because
            # they need the stream to exist before
            # they get the "subscribe" notification, and the latter so
            # they can manage the new stream.
            # Realm admins already have all created private streams.
            realm_admin_ids = [user.id for user in user_profile.realm.get_admin_users()]
            new_users_ids = [user.id for user in users if (user.id, stream.id) in new_streams and
                             user.id not in realm_admin_ids]
            send_stream_creation_event(stream, new_users_ids)

    recent_traffic = get_streams_traffic(streams)
    # The second batch is events for the users themselves that they
    # were subscribed to the new streams.
    for user_profile in users:
        if len(sub_tuples_by_user[user_profile.id]) == 0:
            continue
        sub_pairs = sub_tuples_by_user[user_profile.id]
        notify_subscriptions_added(user_profile, sub_pairs, fetch_stream_subscriber_user_ids,
                                   recent_traffic)

    # The second batch is events for other users who are tracking the
    # subscribers lists of streams in their browser; everyone for
    # public streams and only existing subscribers for private streams.
    for stream in streams:
        if stream.is_in_zephyr_realm and not stream.invite_only:
            continue

        new_user_ids = [user.id for user in users if (user.id, stream.id) in new_streams]
        subscribed_user_ids = all_subscribers_by_stream[stream.id]

        peer_user_ids = get_peer_user_ids_for_stream_change(
            stream=stream,
            altered_user_ids=new_user_ids,
            subscribed_user_ids=subscribed_user_ids,
        )

        if peer_user_ids:
            for new_user_id in new_user_ids:
                event = dict(type="subscription", op="peer_add",
                             subscriptions=[stream.name],
                             user_id=new_user_id)
                send_event(event, peer_user_ids)

    return ([(user_profile, stream) for (user_profile, recipient_id, stream) in new_subs] +
            [(sub.user_profile, stream) for (sub, stream) in subs_to_activate],
            already_subscribed)

def notify_subscriptions_removed(user_profile: UserProfile, streams: Iterable[Stream],
                                 no_log: bool=False) -> None:
    if not no_log:
        log_event({'type': 'subscription_removed',
                   'user': user_profile.email,
                   'names': [stream.name for stream in streams],
                   'realm': user_profile.realm.string_id})

    payload = [dict(name=stream.name, stream_id=stream.id) for stream in streams]
    event = dict(type="subscription", op="remove",
                 subscriptions=payload)
    send_event(event, [user_profile.id])

SubAndRemovedT = Tuple[List[Tuple[UserProfile, Stream]], List[Tuple[UserProfile, Stream]]]
def bulk_remove_subscriptions(users: Iterable[UserProfile],
                              streams: Iterable[Stream],
                              acting_user: Optional[UserProfile]=None) -> SubAndRemovedT:

    users = list(users)
    streams = list(streams)

    stream_dict = {stream.id: stream for stream in streams}

    existing_subs_by_user = get_bulk_stream_subscriber_info(users, stream_dict)

    def get_non_subscribed_tups() -> List[Tuple[UserProfile, Stream]]:
        stream_ids = {stream.id for stream in streams}

        not_subscribed = []  # type: List[Tuple[UserProfile, Stream]]

        for user_profile in users:
            user_sub_stream_info = existing_subs_by_user[user_profile.id]

            subscribed_stream_ids = {
                stream.id
                for (sub, stream) in user_sub_stream_info
            }
            not_subscribed_stream_ids = stream_ids - subscribed_stream_ids

            for stream_id in not_subscribed_stream_ids:
                stream = stream_dict[stream_id]
                not_subscribed.append((user_profile, stream))

        return not_subscribed

    not_subscribed = get_non_subscribed_tups()

    subs_to_deactivate = []  # type: List[Tuple[Subscription, Stream]]
    sub_ids_to_deactivate = []  # type: List[int]

    # This loop just flattens out our data into big lists for
    # bulk operations.
    for tup_list in existing_subs_by_user.values():
        for (sub, stream) in tup_list:
            subs_to_deactivate.append((sub, stream))
            sub_ids_to_deactivate.append(sub.id)

    our_realm = users[0].realm

    # TODO: XXX: This transaction really needs to be done at the serializeable
    # transaction isolation level.
    with transaction.atomic():
        occupied_streams_before = list(get_occupied_streams(our_realm))
        Subscription.objects.filter(
            id__in=sub_ids_to_deactivate,
        ) .update(active=False)
        occupied_streams_after = list(get_occupied_streams(our_realm))

    # Log Subscription Activities in RealmAuditLog
    event_time = timezone_now()
    event_last_message_id = Message.objects.aggregate(Max('id'))['id__max']
    all_subscription_logs = []  # type: (List[RealmAuditLog])
    for (sub, stream) in subs_to_deactivate:
        all_subscription_logs.append(RealmAuditLog(realm=sub.user_profile.realm,
                                                   modified_user=sub.user_profile,
                                                   modified_stream=stream,
                                                   event_last_message_id=event_last_message_id,
                                                   event_type='subscription_deactivated',
                                                   event_time=event_time))
    # Now since we have all log objects generated we can do a bulk insert
    RealmAuditLog.objects.bulk_create(all_subscription_logs)

    new_vacant_streams = [stream for stream in
                          set(occupied_streams_before) - set(occupied_streams_after)]
    new_vacant_private_streams = [stream for stream in new_vacant_streams
                                  if stream.invite_only]
    new_vacant_public_streams = [stream for stream in new_vacant_streams
                                 if not stream.invite_only]
    if new_vacant_public_streams:
        event = dict(type="stream", op="vacate",
                     streams=[stream.to_dict()
                              for stream in new_vacant_public_streams])
        send_event(event, active_user_ids(our_realm.id))
    if new_vacant_private_streams:
        # Deactivate any newly-vacant private streams
        for stream in new_vacant_private_streams:
            do_deactivate_stream(stream)

    altered_user_dict = defaultdict(list)  # type: Dict[int, List[UserProfile]]
    streams_by_user = defaultdict(list)  # type: Dict[int, List[Stream]]
    for (sub, stream) in subs_to_deactivate:
        streams_by_user[sub.user_profile_id].append(stream)
        altered_user_dict[stream.id].append(sub.user_profile)

    for user_profile in users:
        if len(streams_by_user[user_profile.id]) == 0:
            continue
        notify_subscriptions_removed(user_profile, streams_by_user[user_profile.id])

        event = {'type': 'mark_stream_messages_as_read',
                 'user_profile_id': user_profile.id,
                 'stream_ids': [stream.id for stream in streams]}
        queue_json_publish("deferred_work", event)

    all_subscribers_by_stream = get_user_ids_for_streams(streams=streams)

    for stream in streams:
        if stream.is_in_zephyr_realm and not stream.invite_only:
            continue

        altered_users = altered_user_dict[stream.id]
        altered_user_ids = [u.id for u in altered_users]

        subscribed_user_ids = all_subscribers_by_stream[stream.id]

        peer_user_ids = get_peer_user_ids_for_stream_change(
            stream=stream,
            altered_user_ids=altered_user_ids,
            subscribed_user_ids=subscribed_user_ids,
        )

        if peer_user_ids:
            for removed_user in altered_users:
                event = dict(type="subscription",
                             op="peer_remove",
                             subscriptions=[stream.name],
                             user_id=removed_user.id)
                send_event(event, peer_user_ids)

    return (
        [(sub.user_profile, stream) for (sub, stream) in subs_to_deactivate],
        not_subscribed,
    )

def log_subscription_property_change(user_email: Text, stream_name: Text, property: Text,
                                     value: Any) -> None:
    event = {'type': 'subscription_property',
             'property': property,
             'user': user_email,
             'stream_name': stream_name,
             'value': value}
    log_event(event)

def do_change_subscription_property(user_profile: UserProfile, sub: Subscription,
                                    stream: Stream, property_name: Text, value: Any
                                    ) -> None:
    setattr(sub, property_name, value)
    sub.save(update_fields=[property_name])
    log_subscription_property_change(user_profile.email, stream.name,
                                     property_name, value)

    event = dict(type="subscription",
                 op="update",
                 email=user_profile.email,
                 property=property_name,
                 value=value,
                 stream_id=stream.id,
                 name=stream.name)
    send_event(event, [user_profile.id])

def do_change_password(user_profile: UserProfile, password: Text, commit: bool=True,
                       hashed_password: bool=False) -> None:
    if hashed_password:
        # This is a hashed password, not the password itself.
        user_profile.set_password(password)
    else:
        user_profile.set_password(password)
    if commit:
        user_profile.save(update_fields=["password"])
    event_time = timezone_now()
    RealmAuditLog.objects.create(realm=user_profile.realm, acting_user=user_profile,
                                 modified_user=user_profile, event_type='user_change_password',
                                 event_time=event_time)

def do_change_full_name(user_profile: UserProfile, full_name: Text,
                        acting_user: Optional[UserProfile]) -> None:
    old_name = user_profile.full_name
    user_profile.full_name = full_name
    user_profile.save(update_fields=["full_name"])
    event_time = timezone_now()
    RealmAuditLog.objects.create(realm=user_profile.realm, acting_user=acting_user,
                                 modified_user=user_profile, event_type='user_full_name_changed',
                                 event_time=event_time, extra_data=old_name)
    payload = dict(email=user_profile.email,
                   user_id=user_profile.id,
                   full_name=user_profile.full_name)
    send_event(dict(type='realm_user', op='update', person=payload),
               active_user_ids(user_profile.realm_id))
    if user_profile.is_bot:
        send_event(dict(type='realm_bot', op='update', bot=payload),
                   bot_owner_user_ids(user_profile))

def check_change_full_name(user_profile: UserProfile, full_name_raw: Text,
                           acting_user: UserProfile) -> Text:
    """Verifies that the user's proposed full name is valid.  The caller
    is responsible for checking check permissions.  Returns the new
    full name, which may differ from what was passed in (because this
    function strips whitespace)."""
    new_full_name = check_full_name(full_name_raw)
    do_change_full_name(user_profile, new_full_name, acting_user)
    return new_full_name

def do_change_bot_owner(user_profile: UserProfile, bot_owner: UserProfile,
                        acting_user: UserProfile) -> None:
    previous_owner = user_profile.bot_owner
    if previous_owner == bot_owner:
        return

    user_profile.bot_owner = bot_owner
    user_profile.save()  # Can't use update_fields because of how the foreign key works.
    event_time = timezone_now()
    RealmAuditLog.objects.create(realm=user_profile.realm, acting_user=acting_user,
                                 modified_user=user_profile, event_type='bot_owner_changed',
                                 event_time=event_time)

    update_users = bot_owner_user_ids(user_profile)

    # For admins, update event is sent instead of delete/add
    # event. bot_data of admin contains all the
    # bots and none of them should be removed/(added again).

    # Delete the bot from previous owner's bot data.
    if previous_owner and not previous_owner.is_realm_admin:
        send_event(dict(type='realm_bot',
                        op="delete",
                        bot=dict(email=user_profile.email,
                                 user_id=user_profile.id,
                                 )),
                   {previous_owner.id, })
        # Do not send update event for previous bot owner.
        update_users = update_users - {previous_owner.id, }

    # Notify the new owner that the bot has been added.
    if not bot_owner.is_realm_admin:
        add_event = created_bot_event(user_profile)
        send_event(add_event, {bot_owner.id, })
        # Do not send update event for bot_owner.
        update_users = update_users - {bot_owner.id, }

    send_event(dict(type='realm_bot',
                    op='update',
                    bot=dict(email=user_profile.email,
                             user_id=user_profile.id,
                             owner_id=user_profile.bot_owner.id,
                             )),
               update_users)

def do_change_tos_version(user_profile: UserProfile, tos_version: Text) -> None:
    user_profile.tos_version = tos_version
    user_profile.save(update_fields=["tos_version"])
    event_time = timezone_now()
    RealmAuditLog.objects.create(realm=user_profile.realm, acting_user=user_profile,
                                 modified_user=user_profile, event_type='user_tos_version_changed',
                                 event_time=event_time)

def do_regenerate_api_key(user_profile: UserProfile, acting_user: UserProfile) -> None:
    user_profile.api_key = random_api_key()
    user_profile.save(update_fields=["api_key"])
    event_time = timezone_now()
    RealmAuditLog.objects.create(realm=user_profile.realm, acting_user=acting_user,
                                 modified_user=user_profile, event_type='user_api_key_changed',
                                 event_time=event_time)

    if user_profile.is_bot:
        send_event(dict(type='realm_bot',
                        op='update',
                        bot=dict(email=user_profile.email,
                                 user_id=user_profile.id,
                                 api_key=user_profile.api_key,
                                 )),
                   bot_owner_user_ids(user_profile))

def do_change_avatar_fields(user_profile: UserProfile, avatar_source: Text) -> None:
    user_profile.avatar_source = avatar_source
    user_profile.avatar_version += 1
    user_profile.save(update_fields=["avatar_source", "avatar_version"])
    event_time = timezone_now()
    RealmAuditLog.objects.create(realm=user_profile.realm, modified_user=user_profile,
                                 event_type='user_change_avatar_source',
                                 extra_data={'avatar_source': avatar_source},
                                 event_time=event_time)

    if user_profile.is_bot:
        send_event(dict(type='realm_bot',
                        op='update',
                        bot=dict(email=user_profile.email,
                                 user_id=user_profile.id,
                                 avatar_url=avatar_url(user_profile),
                                 )),
                   bot_owner_user_ids(user_profile))

    payload = dict(
        email=user_profile.email,
        avatar_source=user_profile.avatar_source,
        avatar_url=avatar_url(user_profile),
        avatar_url_medium=avatar_url(user_profile, medium=True),
        user_id=user_profile.id
    )

    send_event(dict(type='realm_user',
                    op='update',
                    person=payload),
               active_user_ids(user_profile.realm_id))


def do_change_icon_source(realm: Realm, icon_source: Text, log: bool=True) -> None:
    realm.icon_source = icon_source
    realm.icon_version += 1
    realm.save(update_fields=["icon_source", "icon_version"])

    if log:
        log_event({'type': 'realm_change_icon',
                   'realm': realm.string_id,
                   'icon_source': icon_source})

    send_event(dict(type='realm',
                    op='update_dict',
                    property="icon",
                    data=dict(icon_source=realm.icon_source,
                              icon_url=realm_icon_url(realm))),
               active_user_ids(realm.id))

def _default_stream_permision_check(user_profile: UserProfile, stream: Optional[Stream]) -> None:
    # Any user can have a None default stream
    if stream is not None:
        if user_profile.is_bot:
            user = user_profile.bot_owner
        else:
            user = user_profile
        if stream.invite_only and (user is None or not subscribed_to_stream(user, stream.id)):
            raise JsonableError(_('Insufficient permission'))

def do_change_default_sending_stream(user_profile: UserProfile, stream: Optional[Stream],
                                     log: bool=True) -> None:
    _default_stream_permision_check(user_profile, stream)

    user_profile.default_sending_stream = stream
    user_profile.save(update_fields=['default_sending_stream'])
    if log:
        log_event({'type': 'user_change_default_sending_stream',
                   'user': user_profile.email,
                   'stream': str(stream)})
    if user_profile.is_bot:
        if stream:
            stream_name = stream.name  # type: Optional[Text]
        else:
            stream_name = None
        send_event(dict(type='realm_bot',
                        op='update',
                        bot=dict(email=user_profile.email,
                                 user_id=user_profile.id,
                                 default_sending_stream=stream_name,
                                 )),
                   bot_owner_user_ids(user_profile))

def do_change_default_events_register_stream(user_profile: UserProfile,
                                             stream: Optional[Stream],
                                             log: bool=True) -> None:
    _default_stream_permision_check(user_profile, stream)

    user_profile.default_events_register_stream = stream
    user_profile.save(update_fields=['default_events_register_stream'])
    if log:
        log_event({'type': 'user_change_default_events_register_stream',
                   'user': user_profile.email,
                   'stream': str(stream)})
    if user_profile.is_bot:
        if stream:
            stream_name = stream.name  # type: Optional[Text]
        else:
            stream_name = None
        send_event(dict(type='realm_bot',
                        op='update',
                        bot=dict(email=user_profile.email,
                                 user_id=user_profile.id,
                                 default_events_register_stream=stream_name,
                                 )),
                   bot_owner_user_ids(user_profile))

def do_change_default_all_public_streams(user_profile: UserProfile, value: bool,
                                         log: bool=True) -> None:
    user_profile.default_all_public_streams = value
    user_profile.save(update_fields=['default_all_public_streams'])
    if log:
        log_event({'type': 'user_change_default_all_public_streams',
                   'user': user_profile.email,
                   'value': str(value)})
    if user_profile.is_bot:
        send_event(dict(type='realm_bot',
                        op='update',
                        bot=dict(email=user_profile.email,
                                 user_id=user_profile.id,
                                 default_all_public_streams=user_profile.default_all_public_streams,
                                 )),
                   bot_owner_user_ids(user_profile))

def do_change_is_admin(user_profile: UserProfile, value: bool,
                       permission: str='administer') -> None:
    if permission == "administer":
        user_profile.is_realm_admin = value
        user_profile.save(update_fields=["is_realm_admin"])
    elif permission == "api_super_user":
        user_profile.is_api_super_user = value
        user_profile.save(update_fields=["is_api_super_user"])
    else:
        raise Exception("Unknown permission")

    if permission == 'administer':
        event = dict(type="realm_user", op="update",
                     person=dict(email=user_profile.email,
                                 user_id=user_profile.id,
                                 is_admin=value))
        send_event(event, active_user_ids(user_profile.realm_id))

def do_change_bot_type(user_profile: UserProfile, value: int) -> None:
    user_profile.bot_type = value
    user_profile.save(update_fields=["bot_type"])

def do_change_stream_invite_only(stream: Stream, invite_only: bool) -> None:
    stream.invite_only = invite_only
    stream.save(update_fields=['invite_only'])

def do_rename_stream(stream: Stream, new_name: Text, log: bool=True) -> Dict[str, Text]:
    old_name = stream.name
    stream.name = new_name
    stream.save(update_fields=["name"])

    if log:
        log_event({'type': 'stream_name_change',
                   'realm': stream.realm.string_id,
                   'new_name': new_name})

    recipient = get_stream_recipient(stream.id)
    messages = Message.objects.filter(recipient=recipient).only("id")

    # Update the display recipient and stream, which are easy single
    # items to set.
    old_cache_key = get_stream_cache_key(old_name, stream.realm_id)
    new_cache_key = get_stream_cache_key(stream.name, stream.realm_id)
    if old_cache_key != new_cache_key:
        cache_delete(old_cache_key)
        cache_set(new_cache_key, stream)
    cache_set(display_recipient_cache_key(recipient.id), stream.name)

    # Delete cache entries for everything else, which is cheaper and
    # clearer than trying to set them. display_recipient is the out of
    # date field in all cases.
    cache_delete_many(
        to_dict_cache_key_id(message.id) for message in messages)
    new_email = encode_email_address(stream)

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
        send_event(event, can_access_stream_user_ids(stream))

    # Even though the token doesn't change, the web client needs to update the
    # email forwarding address to display the correctly-escaped new name.
    return {"email_address": new_email}

def do_change_stream_description(stream: Stream, new_description: Text) -> None:
    stream.description = new_description
    stream.save(update_fields=['description'])

    event = dict(
        type='stream',
        op='update',
        property='description',
        name=stream.name,
        stream_id=stream.id,
        value=new_description,
    )
    send_event(event, can_access_stream_user_ids(stream))

def do_create_realm(string_id: Text, name: Text, restricted_to_domain: Optional[bool]=None,
                    invite_required: Optional[bool]=None, org_type: Optional[int]=None
                    ) -> Realm:
    existing_realm = get_realm(string_id)
    if existing_realm is not None:
        raise AssertionError("Realm %s already exists!" % (string_id,))

    kwargs = {}  # type: Dict[str, Any]
    if restricted_to_domain is not None:
        kwargs['restricted_to_domain'] = restricted_to_domain
    if invite_required is not None:
        kwargs['invite_required'] = invite_required
    if org_type is not None:
        kwargs['org_type'] = org_type
    realm = Realm(string_id=string_id, name=name, **kwargs)
    realm.save()

    # Create stream once Realm object has been saved
    notifications_stream = ensure_stream(realm, Realm.DEFAULT_NOTIFICATION_STREAM_NAME)
    realm.notifications_stream = notifications_stream

    signup_notifications_stream = ensure_stream(
        realm, Realm.INITIAL_PRIVATE_STREAM_NAME, invite_only=True,
        stream_description="A private stream for core team members.")
    realm.signup_notifications_stream = signup_notifications_stream

    realm.save(update_fields=['notifications_stream', 'signup_notifications_stream'])

    # Log the event
    log_event({"type": "realm_created",
               "string_id": string_id,
               "restricted_to_domain": restricted_to_domain,
               "invite_required": invite_required,
               "org_type": org_type})

    # Send a notification to the admin realm (if configured)
    if settings.NOTIFICATION_BOT is not None:
        signup_message = "Signups enabled"
        admin_realm = get_system_bot(settings.NOTIFICATION_BOT).realm
        internal_send_message(admin_realm, settings.NOTIFICATION_BOT, "stream",
                              "signups", realm.display_subdomain, signup_message)
    return realm

def do_change_notification_settings(user_profile: UserProfile, name: str, value: bool,
                                    log: bool=True) -> None:
    """Takes in a UserProfile object, the name of a global notification
    preference to update, and the value to update to
    """

    notification_setting_type = UserProfile.notification_setting_types[name]
    assert isinstance(value, notification_setting_type), (
        'Cannot update %s: %s is not an instance of %s' % (
            name, value, notification_setting_type,))

    setattr(user_profile, name, value)

    # Disabling digest emails should clear a user's email queue
    if name == 'enable_digest_emails' and not value:
        clear_scheduled_emails(user_profile.id, ScheduledEmail.DIGEST)

    user_profile.save(update_fields=[name])
    event = {'type': 'update_global_notifications',
             'user': user_profile.email,
             'notification_name': name,
             'setting': value}
    if log:
        log_event(event)
    send_event(event, [user_profile.id])

def do_change_enter_sends(user_profile: UserProfile, enter_sends: bool) -> None:
    user_profile.enter_sends = enter_sends
    user_profile.save(update_fields=["enter_sends"])

def do_change_default_desktop_notifications(user_profile: UserProfile,
                                            default_desktop_notifications: bool) -> None:
    user_profile.default_desktop_notifications = default_desktop_notifications
    user_profile.save(update_fields=["default_desktop_notifications"])

def do_set_user_display_setting(user_profile: UserProfile,
                                setting_name: str,
                                setting_value: Union[bool, Text]) -> None:
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

    send_event(event, [user_profile.id])

    # Updates to the timezone display setting are sent to all users
    if setting_name == "timezone":
        payload = dict(email=user_profile.email,
                       user_id=user_profile.id,
                       timezone=user_profile.timezone)
        send_event(dict(type='realm_user', op='update', person=payload),
                   active_user_ids(user_profile.realm_id))

def lookup_default_stream_groups(default_stream_group_names: List[str],
                                 realm: Realm) -> List[DefaultStreamGroup]:
    default_stream_groups = []
    for group_name in default_stream_group_names:
        try:
            default_stream_group = DefaultStreamGroup.objects.get(
                name=group_name, realm=realm)
        except DefaultStreamGroup.DoesNotExist:
            raise JsonableError(_('Invalid default stream group %s' % (group_name,)))
        default_stream_groups.append(default_stream_group)
    return default_stream_groups

def set_default_streams(realm: Realm, stream_dict: Dict[Text, Dict[Text, Any]]) -> None:
    DefaultStream.objects.filter(realm=realm).delete()
    stream_names = []
    for name, options in stream_dict.items():
        stream_names.append(name)
        stream = ensure_stream(realm,
                               name,
                               invite_only = options.get("invite_only", False),
                               stream_description = options.get("description", ''))
        DefaultStream.objects.create(stream=stream, realm=realm)

    # Always include the realm's default notifications streams, if it exists
    if realm.notifications_stream is not None:
        DefaultStream.objects.get_or_create(stream=realm.notifications_stream, realm=realm)

    log_event({'type': 'default_streams',
               'realm': realm.string_id,
               'streams': stream_names})

def notify_default_streams(realm_id: int) -> None:
    event = dict(
        type="default_streams",
        default_streams=streams_to_dicts_sorted(get_default_streams_for_realm(realm_id))
    )
    send_event(event, active_user_ids(realm_id))

def notify_default_stream_groups(realm: Realm) -> None:
    event = dict(
        type="default_stream_groups",
        default_stream_groups=default_stream_groups_to_dicts_sorted(get_default_stream_groups(realm))
    )
    send_event(event, active_user_ids(realm.id))

def do_add_default_stream(stream: Stream) -> None:
    realm_id = stream.realm_id
    stream_id = stream.id
    if not DefaultStream.objects.filter(realm_id=realm_id, stream_id=stream_id).exists():
        DefaultStream.objects.create(realm_id=realm_id, stream_id=stream_id)
        notify_default_streams(realm_id)

def do_remove_default_stream(stream: Stream) -> None:
    realm_id = stream.realm_id
    stream_id = stream.id
    DefaultStream.objects.filter(realm_id=realm_id, stream_id=stream_id).delete()
    notify_default_streams(realm_id)

def do_create_default_stream_group(realm: Realm, group_name: Text,
                                   description: Text, streams: List[Stream]) -> None:
    default_streams = get_default_streams_for_realm(realm.id)
    for stream in streams:
        if stream in default_streams:
            raise JsonableError(_(
                "'%(stream_name)s' is a default stream and cannot be added to '%(group_name)s'")
                % {'stream_name': stream.name, 'group_name': group_name})

    check_default_stream_group_name(group_name)
    (group, created) = DefaultStreamGroup.objects.get_or_create(
        name=group_name, realm=realm, description=description)
    if not created:
        raise JsonableError(_("Default stream group '%(group_name)s' already exists")
                            % {'group_name': group_name})

    group.streams.set(streams)
    notify_default_stream_groups(realm)

def do_add_streams_to_default_stream_group(realm: Realm, group: DefaultStreamGroup,
                                           streams: List[Stream]) -> None:
    default_streams = get_default_streams_for_realm(realm.id)
    for stream in streams:
        if stream in default_streams:
            raise JsonableError(_(
                "'%(stream_name)s' is a default stream and cannot be added to '%(group_name)s'")
                % {'stream_name': stream.name, 'group_name': group.name})
        if stream in group.streams.all():
            raise JsonableError(_(
                "Stream '%(stream_name)s' is already present in default stream group '%(group_name)s'")
                % {'stream_name': stream.name, 'group_name': group.name})
        group.streams.add(stream)

    group.save()
    notify_default_stream_groups(realm)

def do_remove_streams_from_default_stream_group(realm: Realm, group: DefaultStreamGroup,
                                                streams: List[Stream]) -> None:
    for stream in streams:
        if stream not in group.streams.all():
            raise JsonableError(_(
                "Stream '%(stream_name)s' is not present in default stream group '%(group_name)s'")
                % {'stream_name': stream.name, 'group_name': group.name})
        group.streams.remove(stream)

    group.save()
    notify_default_stream_groups(realm)

def do_change_default_stream_group_name(realm: Realm, group: DefaultStreamGroup,
                                        new_group_name: Text) -> None:
    if group.name == new_group_name:
        raise JsonableError(_("This default stream group is already named '%s'") % (new_group_name,))

    if DefaultStreamGroup.objects.filter(name=new_group_name, realm=realm).exists():
        raise JsonableError(_("Default stream group '%s' already exists") % (new_group_name,))

    group.name = new_group_name
    group.save()
    notify_default_stream_groups(realm)

def do_change_default_stream_group_description(realm: Realm, group: DefaultStreamGroup,
                                               new_description: Text) -> None:
    group.description = new_description
    group.save()
    notify_default_stream_groups(realm)

def do_remove_default_stream_group(realm: Realm, group: DefaultStreamGroup) -> None:
    group.delete()
    notify_default_stream_groups(realm)

def get_default_streams_for_realm(realm_id: int) -> List[Stream]:
    return [default.stream for default in
            DefaultStream.objects.select_related("stream", "stream__realm").filter(
                realm_id=realm_id)]

def get_default_subs(user_profile: UserProfile) -> List[Stream]:
    # Right now default streams are realm-wide.  This wrapper gives us flexibility
    # to some day further customize how we set up default streams for new users.
    return get_default_streams_for_realm(user_profile.realm_id)

# returns default streams in json serializeable format
def streams_to_dicts_sorted(streams: List[Stream]) -> List[Dict[str, Any]]:
    return sorted([stream.to_dict() for stream in streams], key=lambda elt: elt["name"])

def default_stream_groups_to_dicts_sorted(groups: List[DefaultStreamGroup]) -> List[Dict[str, Any]]:
    return sorted([group.to_dict() for group in groups], key=lambda elt: elt["name"])

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
def do_update_user_activity(user_profile: UserProfile,
                            client: Client,
                            query: Text,
                            log_time: datetime.datetime) -> None:
    (activity, created) = UserActivity.objects.get_or_create(
        user_profile = user_profile,
        client = client,
        query = query,
        defaults={'last_visit': log_time, 'count': 0})

    activity.count += 1
    activity.last_visit = log_time
    activity.save(update_fields=["last_visit", "count"])

def send_presence_changed(user_profile: UserProfile, presence: UserPresence) -> None:
    presence_dict = presence.to_dict()
    event = dict(type="presence", email=user_profile.email,
                 server_timestamp=time.time(),
                 presence={presence_dict['client']: presence_dict})
    send_event(event, active_user_ids(user_profile.realm_id))

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
    (presence, created) = UserPresence.objects.get_or_create(
        user_profile = user_profile,
        client = client,
        defaults = {'timestamp': log_time,
                    'status': status})

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

    if not user_profile.realm.is_zephyr_mirror_realm and (created or became_online):
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

def do_update_pointer(user_profile: UserProfile, pointer: int, update_flags: bool=False) -> None:
    prev_pointer = user_profile.pointer
    user_profile.pointer = pointer
    user_profile.save(update_fields=["pointer"])

    if update_flags:
        # Until we handle the new read counts in the Android app
        # natively, this is a shim that will mark as read any messages
        # up until the pointer move
        UserMessage.objects.filter(user_profile=user_profile,
                                   message__id__gt=prev_pointer,
                                   message__id__lte=pointer,
                                   flags=~UserMessage.flags.read)        \
                           .update(flags=F('flags').bitor(UserMessage.flags.read))

    event = dict(type='pointer', pointer=pointer)
    send_event(event, [user_profile.id])

def do_mark_all_as_read(user_profile: UserProfile) -> int:
    log_statsd_event('bankruptcy')

    msgs = UserMessage.objects.filter(
        user_profile=user_profile
    ).extra(
        where=[UserMessage.where_unread()]
    )

    count = msgs.update(
        flags=F('flags').bitor(UserMessage.flags.read)
    )

    event = dict(
        type='update_message_flags',
        operation='add',
        flag='read',
        messages=[],  # we don't send messages, since the client reloads anyway
        all=True
    )
    send_event(event, [user_profile.id])

    statsd.incr("mark_all_as_read", count)
    return count

def do_mark_stream_messages_as_read(user_profile: UserProfile,
                                    stream: Optional[Stream],
                                    topic_name: Optional[Text]=None) -> int:
    log_statsd_event('mark_stream_as_read')

    msgs = UserMessage.objects.filter(
        user_profile=user_profile
    )

    recipient = get_stream_recipient(stream.id)
    msgs = msgs.filter(message__recipient=recipient)

    if topic_name:
        msgs = msgs.filter(message__subject__iexact=topic_name)

    msgs = msgs.extra(
        where=[UserMessage.where_unread()]
    )

    message_ids = list(msgs.values_list('message__id', flat=True))

    count = msgs.update(
        flags=F('flags').bitor(UserMessage.flags.read)
    )

    event = dict(
        type='update_message_flags',
        operation='add',
        flag='read',
        messages=message_ids,
        all=False,
    )
    send_event(event, [user_profile.id])

    statsd.incr("mark_stream_as_read", count)
    return count

def do_update_message_flags(user_profile: UserProfile,
                            operation: Text,
                            flag: Text,
                            messages: Optional[Sequence[int]]) -> int:
    flagattr = getattr(UserMessage.flags, flag)

    assert messages is not None
    msgs = UserMessage.objects.filter(user_profile=user_profile,
                                      message__id__in=messages)
    # Hack to let you star any message
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
    else:
        raise AssertionError("Invalid message flags operation")

    event = {'type': 'update_message_flags',
             'operation': operation,
             'flag': flag,
             'messages': messages,
             'all': False}
    send_event(event, [user_profile.id])

    statsd.incr("flags.%s.%s" % (flag, operation), count)
    return count

def subscribed_to_stream(user_profile: UserProfile, stream_id: int) -> bool:
    try:
        if Subscription.objects.get(user_profile=user_profile,
                                    active=True,
                                    recipient__type=Recipient.STREAM,
                                    recipient__type_id=stream_id):
            return True
        return False
    except Subscription.DoesNotExist:
        return False

def truncate_content(content: Text, max_length: int, truncation_message: Text) -> Text:
    if len(content) > max_length:
        content = content[:max_length - len(truncation_message)] + truncation_message
    return content

def truncate_body(body: Text) -> Text:
    return truncate_content(body, MAX_MESSAGE_LENGTH, "...")

def truncate_topic(topic: Text) -> Text:
    return truncate_content(topic, MAX_SUBJECT_LENGTH, "...")

MessageUpdateUserInfoResult = TypedDict('MessageUpdateUserInfoResult', {
    'message_user_ids': Set[int],
    'mention_user_ids': Set[int],
})

def get_user_info_for_message_updates(message_id: int) -> MessageUpdateUserInfoResult:

    # We exclude UserMessage.flags.historical rows since those
    # users did not receive the message originally, and thus
    # probably are not relevant for reprocessed alert_words,
    # mentions and similar rendering features.  This may be a
    # decision we change in the future.
    query = UserMessage.objects.filter(
        message=message_id,
        flags=~UserMessage.flags.historical
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
    changed_ums = set()  # type: Set[UserMessage]

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

def update_to_dict_cache(changed_messages: List[Message]) -> List[int]:
    """Updates the message as stored in the to_dict cache (for serving
    messages)."""
    items_for_remote_cache = {}
    message_ids = []
    for changed_message in changed_messages:
        message_ids.append(changed_message.id)
        key = to_dict_cache_key_id(changed_message.id)
        value = MessageDict.to_dict_uncached(changed_message)
        items_for_remote_cache[key] = (value,)

    cache_set_many(items_for_remote_cache)
    return message_ids

# We use transaction.atomic to support select_for_update in the attachment codepath.
@transaction.atomic
def do_update_embedded_data(user_profile: UserProfile,
                            message: Message,
                            content: Optional[Text],
                            rendered_content: Optional[Text]) -> None:
    event = {
        'type': 'update_message',
        'sender': user_profile.email,
        'message_id': message.id}  # type: Dict[str, Any]
    changed_messages = [message]

    ums = UserMessage.objects.filter(message=message.id)

    if content is not None:
        update_user_message_flags(message, ums)
        message.content = content
        message.rendered_content = rendered_content
        message.rendered_content_version = bugdown_version
        event["content"] = content
        event["rendered_content"] = rendered_content

    message.save(update_fields=["content", "rendered_content"])

    event['message_ids'] = update_to_dict_cache(changed_messages)

    def user_info(um: UserMessage) -> Dict[str, Any]:
        return {
            'id': um.user_profile_id,
            'flags': um.flags_list()
        }
    send_event(event, list(map(user_info, ums)))

# We use transaction.atomic to support select_for_update in the attachment codepath.
@transaction.atomic
def do_update_message(user_profile: UserProfile, message: Message, topic_name: Optional[Text],
                      propagate_mode: str, content: Optional[Text],
                      rendered_content: Optional[Text], prior_mention_user_ids: Set[int],
                      mention_user_ids: Set[int]) -> int:
    event = {'type': 'update_message',
             # TODO: We probably want to remove the 'sender' field
             # after confirming it isn't used by any consumers.
             'sender': user_profile.email,
             'user_id': user_profile.id,
             'message_id': message.id}  # type: Dict[str, Any]
    edit_history_event = {
        'user_id': user_profile.id,
    }  # type: Dict[str, Any]
    changed_messages = [message]

    if message.is_stream_message():
        stream_id = message.recipient.type_id
        event['stream_name'] = Stream.objects.get(id=stream_id).name

    ums = UserMessage.objects.filter(message=message.id)

    if content is not None:
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
        message.rendered_content_version = bugdown_version
        event["content"] = content
        event["rendered_content"] = rendered_content
        event['prev_rendered_content_version'] = message.rendered_content_version
        event['is_me_message'] = Message.is_status_message(content, rendered_content)

        prev_content = edit_history_event['prev_content']
        if Message.content_has_attachment(prev_content) or Message.content_has_attachment(message.content):
            check_attachment_reference_change(prev_content, message)

        if message.is_stream_message():
            if topic_name is not None:
                new_topic_name = topic_name
            else:
                new_topic_name = message.topic_name()

            stream_topic = StreamTopicTarget(
                stream_id=stream_id,
                topic_name=new_topic_name,
            )  # type: Optional[StreamTopicTarget]
        else:
            stream_topic = None

        # TODO: We may want a slightly leaner of this function for updates.
        info = get_recipient_info(
            recipient=message.recipient,
            sender_id=message.sender_id,
            stream_topic=stream_topic,
        )

        event['push_notify_user_ids'] = list(info['push_notify_user_ids'])
        event['stream_push_user_ids'] = list(info['stream_push_user_ids'])
        event['prior_mention_user_ids'] = list(prior_mention_user_ids)
        event['mention_user_ids'] = list(mention_user_ids)
        event['presence_idle_user_ids'] = filter_presence_idle_user_ids(info['active_user_ids'])

    if topic_name is not None:
        orig_topic_name = message.topic_name()
        topic_name = truncate_topic(topic_name)
        event["orig_subject"] = orig_topic_name
        event["propagate_mode"] = propagate_mode
        message.subject = topic_name
        event["stream_id"] = message.recipient.type_id
        event["subject"] = topic_name
        event['subject_links'] = bugdown.subject_links(message.sender.realm_id, topic_name)
        edit_history_event["prev_subject"] = orig_topic_name

        if propagate_mode in ["change_later", "change_all"]:
            propagate_query = Q(recipient = message.recipient, subject = orig_topic_name)
            # We only change messages up to 2 days in the past, to avoid hammering our
            # DB by changing an unbounded amount of messages
            if propagate_mode == 'change_all':
                before_bound = timezone_now() - datetime.timedelta(days=2)

                propagate_query = (propagate_query & ~Q(id = message.id) &
                                   Q(pub_date__range=(before_bound, timezone_now())))
            if propagate_mode == 'change_later':
                propagate_query = propagate_query & Q(id__gt = message.id)

            messages = Message.objects.filter(propagate_query).select_related()

            # Evaluate the query before running the update
            messages_list = list(messages)
            messages.update(subject=topic_name)

            for m in messages_list:
                # The cached ORM object is not changed by messages.update()
                # and the remote cache update requires the new value
                m.subject = topic_name

            changed_messages += messages_list

    message.last_edit_time = timezone_now()
    assert message.last_edit_time is not None  # assert needed because stubs for django are missing
    event['edit_timestamp'] = datetime_to_timestamp(message.last_edit_time)
    edit_history_event['timestamp'] = event['edit_timestamp']
    if message.edit_history is not None:
        edit_history = ujson.loads(message.edit_history)
        edit_history.insert(0, edit_history_event)
    else:
        edit_history = [edit_history_event]
    message.edit_history = ujson.dumps(edit_history)

    message.save(update_fields=["subject", "content", "rendered_content",
                                "rendered_content_version", "last_edit_time",
                                "edit_history"])

    event['message_ids'] = update_to_dict_cache(changed_messages)

    def user_info(um: UserMessage) -> Dict[str, Any]:
        return {
            'id': um.user_profile_id,
            'flags': um.flags_list()
        }
    send_event(event, list(map(user_info, ums)))
    return len(changed_messages)


def do_delete_message(user_profile: UserProfile, message: Message) -> None:
    message_type = "stream"
    if not message.is_stream_message():
        message_type = "private"

    event = {
        'type': 'delete_message',
        'sender': user_profile.email,
        'message_id': message.id,
        'message_type': message_type, }  # type: Dict[str, Any]
    if message_type == "stream":
        event['stream_id'] = message.recipient.type_id
        event['topic'] = message.subject
    else:
        event['recipient_user_ids'] = message.recipient.type_id

    ums = [{'id': um.user_profile_id} for um in
           UserMessage.objects.filter(message=message.id)]
    move_message_to_archive(message.id)
    send_event(event, ums)

def get_streams_traffic(streams: Optional[Iterable[Stream]]=None) -> Dict[int, int]:
    stat = COUNT_STATS['messages_in_stream:is_bot:day']
    traffic_from = timezone_now() - datetime.timedelta(days=28)

    query = StreamCount.objects.filter(property=stat.property,
                                       end_time__gt=traffic_from)
    if streams is not None:
        query = query.filter(stream__in=streams)

    traffic_list = query.values('stream_id').annotate(value=Sum('value'))
    traffic_dict = {}
    for traffic in traffic_list:
        traffic_dict[traffic["stream_id"]] = traffic["value"]

    return traffic_dict

def round_to_2_significant_digits(number: int) -> int:
    return int(round(number, 2 - len(str(number))))

def get_average_weekly_stream_traffic(stream_id: int, stream_date_created: datetime.datetime,
                                      recent_traffic: QuerySet) -> int:
    try:
        stream_traffic = recent_traffic[stream_id]
    except KeyError:
        return 0

    stream_age = (timezone_now().date() - stream_date_created.date()).days

    if stream_age >= 28:
        average_weekly_traffic = int(stream_traffic // 4)
    elif stream_age >= 7:
        average_weekly_traffic = int(stream_traffic // (stream_age // 7))
    else:
        average_weekly_traffic = stream_traffic

    return round_to_2_significant_digits(average_weekly_traffic)

def is_old_stream(stream_date_created: datetime.datetime) -> bool:
    return (datetime.date.today() - stream_date_created.date()).days >= 7

def encode_email_address(stream: Stream) -> Text:
    return encode_email_address_helper(stream.name, stream.email_token)

def encode_email_address_helper(name: Text, email_token: Text) -> Text:
    # Some deployments may not use the email gateway
    if settings.EMAIL_GATEWAY_PATTERN == '':
        return ''

    # Given the fact that we have almost no restrictions on stream names and
    # that what characters are allowed in e-mail addresses is complicated and
    # dependent on context in the address, we opt for a very simple scheme:
    #
    # Only encode the stream name (leave the + and token alone). Encode
    # everything that isn't alphanumeric plus _ as the percent-prefixed integer
    # ordinal of that character, padded with zeroes to the maximum number of
    # bytes of a UTF-8 encoded Unicode character.
    encoded_name = re.sub("\W", lambda x: "%" + str(ord(x.group(0))).zfill(4), name)
    encoded_token = "%s+%s" % (encoded_name, email_token)
    return settings.EMAIL_GATEWAY_PATTERN % (encoded_token,)

def get_email_gateway_message_string_from_address(address: Text) -> Optional[Text]:
    pattern_parts = [re.escape(part) for part in settings.EMAIL_GATEWAY_PATTERN.split('%s')]
    if settings.EMAIL_GATEWAY_EXTRA_PATTERN_HACK:
        # Accept mails delivered to any Zulip server
        pattern_parts[-1] = settings.EMAIL_GATEWAY_EXTRA_PATTERN_HACK
    match_email_re = re.compile("(.*?)".join(pattern_parts))
    match = match_email_re.match(address)

    if not match:
        return None

    msg_string = match.group(1)

    return msg_string

def decode_email_address(email: Text) -> Optional[Tuple[Text, Text]]:
    # Perform the reverse of encode_email_address. Returns a tuple of (streamname, email_token)
    msg_string = get_email_gateway_message_string_from_address(email)

    if msg_string is None:
        return None
    elif '.' in msg_string:
        # Workaround for Google Groups and other programs that don't accept emails
        # that have + signs in them (see Trac #2102)
        encoded_stream_name, token = msg_string.split('.')
    else:
        encoded_stream_name, token = msg_string.split('+')
    stream_name = re.sub("%\d{4}", lambda x: unichr(int(x.group(0)[1:])), encoded_stream_name)
    return stream_name, token

# In general, it's better to avoid using .values() because it makes
# the code pretty ugly, but in this case, it has significant
# performance impact for loading / for users with large numbers of
# subscriptions, so it's worth optimizing.
SubHelperT = Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]
def gather_subscriptions_helper(user_profile: UserProfile,
                                include_subscribers: bool=True) -> SubHelperT:
    sub_dicts = get_stream_subscriptions_for_user(user_profile).values(
        "recipient_id", "in_home_view", "color", "desktop_notifications",
        "audible_notifications", "push_notifications", "active", "pin_to_top"
    ).order_by("recipient_id")

    sub_dicts = list(sub_dicts)
    sub_recipient_ids = [
        sub['recipient_id']
        for sub in sub_dicts
    ]
    stream_recipient = StreamRecipientMap()
    stream_recipient.populate_for_recipient_ids(sub_recipient_ids)

    stream_ids = set()  # type: Set[int]
    recent_traffic = get_streams_traffic()
    for sub in sub_dicts:
        sub['stream_id'] = stream_recipient.stream_id_for(sub['recipient_id'])
        stream_ids.add(sub['stream_id'])

    all_streams = get_active_streams(user_profile.realm).select_related(
        "realm").values("id", "name", "invite_only", "realm_id",
                        "email_token", "description", "date_created")

    stream_dicts = [stream for stream in all_streams if stream['id'] in stream_ids]
    stream_hash = {}
    for stream in stream_dicts:
        stream_hash[stream["id"]] = stream

    all_streams_id = [stream["id"] for stream in all_streams]

    subscribed = []
    unsubscribed = []
    never_subscribed = []

    # Deactivated streams aren't in stream_hash.
    streams = [stream_hash[sub["stream_id"]] for sub in sub_dicts
               if sub["stream_id"] in stream_hash]
    streams_subscribed_map = dict((sub["stream_id"], sub["active"]) for sub in sub_dicts)

    # Add never subscribed streams to streams_subscribed_map
    streams_subscribed_map.update({stream['id']: False for stream in all_streams if stream not in streams})

    if include_subscribers:
        subscriber_map = bulk_get_subscriber_user_ids(
            all_streams,
            user_profile,
            streams_subscribed_map,
            stream_recipient
        )  # type: Mapping[int, Optional[List[int]]]
    else:
        # If we're not including subscribers, always return None,
        # which the below code needs to check for anyway.
        subscriber_map = defaultdict(lambda: None)

    sub_unsub_stream_ids = set()
    for sub in sub_dicts:
        sub_unsub_stream_ids.add(sub["stream_id"])
        stream = stream_hash.get(sub["stream_id"])
        if not stream:
            # This stream has been deactivated, don't include it.
            continue

        subscribers = subscriber_map[stream["id"]]  # type: Optional[List[int]]

        # Important: don't show the subscribers if the stream is invite only
        # and this user isn't on it anymore (or a realm administrator).
        if stream["invite_only"] and not (sub["active"] or user_profile.is_realm_admin):
            subscribers = None

        stream_dict = {'name': stream["name"],
                       'in_home_view': sub["in_home_view"],
                       'invite_only': stream["invite_only"],
                       'color': sub["color"],
                       'desktop_notifications': sub["desktop_notifications"],
                       'audible_notifications': sub["audible_notifications"],
                       'push_notifications': sub["push_notifications"],
                       'pin_to_top': sub["pin_to_top"],
                       'stream_id': stream["id"],
                       'description': stream["description"],
                       'is_old_stream': is_old_stream(stream["date_created"]),
                       'stream_weekly_traffic': get_average_weekly_stream_traffic(stream["id"],
                                                                                  stream["date_created"],
                                                                                  recent_traffic),
                       'email_address': encode_email_address_helper(stream["name"], stream["email_token"])}
        if subscribers is not None:
            stream_dict['subscribers'] = subscribers
        if sub["active"]:
            subscribed.append(stream_dict)
        else:
            unsubscribed.append(stream_dict)

    all_streams_id_set = set(all_streams_id)
    # Listing public streams are disabled for Zephyr mirroring realms.
    if user_profile.realm.is_zephyr_mirror_realm:
        never_subscribed_stream_ids = set()  # type: Set[int]
    else:
        never_subscribed_stream_ids = all_streams_id_set - sub_unsub_stream_ids
    never_subscribed_streams = [ns_stream_dict for ns_stream_dict in all_streams
                                if ns_stream_dict['id'] in never_subscribed_stream_ids]

    for stream in never_subscribed_streams:
        is_public = (not stream['invite_only'])
        if is_public or user_profile.is_realm_admin:
            stream_dict = {'name': stream['name'],
                           'invite_only': stream['invite_only'],
                           'stream_id': stream['id'],
                           'is_old_stream': is_old_stream(stream["date_created"]),
                           'stream_weekly_traffic': get_average_weekly_stream_traffic(stream["id"],
                                                                                      stream["date_created"],
                                                                                      recent_traffic),
                           'description': stream['description']}
            if is_public or user_profile.is_realm_admin:
                subscribers = subscriber_map[stream["id"]]
                if subscribers is not None:
                    stream_dict['subscribers'] = subscribers
            never_subscribed.append(stream_dict)

    return (sorted(subscribed, key=lambda x: x['name']),
            sorted(unsubscribed, key=lambda x: x['name']),
            sorted(never_subscribed, key=lambda x: x['name']))

def gather_subscriptions(user_profile: UserProfile) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    subscribed, unsubscribed, never_subscribed = gather_subscriptions_helper(user_profile)
    user_ids = set()
    for subs in [subscribed, unsubscribed, never_subscribed]:
        for sub in subs:
            if 'subscribers' in sub:
                for subscriber in sub['subscribers']:
                    user_ids.add(subscriber)
    email_dict = get_emails_from_user_ids(list(user_ids))

    for subs in [subscribed, unsubscribed]:
        for sub in subs:
            if 'subscribers' in sub:
                sub['subscribers'] = sorted([email_dict[user_id] for user_id in sub['subscribers']])

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
          to mentions or being PM'ed).
        * They are no longer "present" according to the
          UserPresence table.
    '''

    if realm.presence_disabled:
        return []

    is_pm = message_type == 'private'

    user_ids = set()
    for user_id in active_user_ids:
        flags = user_flags.get(user_id, [])  # type: Iterable[str]
        mentioned = 'mentioned' in flags
        private_message = is_pm and user_id != sender_id
        if mentioned or private_message:
            user_ids.add(user_id)

    return filter_presence_idle_user_ids(user_ids)

def filter_presence_idle_user_ids(user_ids: Set[int]) -> List[int]:
    if not user_ids:
        return []

    # 140 seconds is consistent with presence.js:OFFLINE_THRESHOLD_SECS
    recent = timezone_now() - datetime.timedelta(seconds=140)
    rows = UserPresence.objects.filter(
        user_profile_id__in=user_ids,
        status=UserPresence.ACTIVE,
        timestamp__gte=recent
    ).distinct('user_profile_id').values('user_profile_id')
    active_user_ids = {row['user_profile_id'] for row in rows}
    idle_user_ids = user_ids - active_user_ids
    return sorted(list(idle_user_ids))

def get_status_dict(requesting_user_profile: UserProfile) -> Dict[Text, Dict[Text, Dict[str, Any]]]:
    if requesting_user_profile.realm.presence_disabled:
        # Return an empty dict if presence is disabled in this realm
        return defaultdict(dict)

    return UserPresence.get_status_dict_by_realm(requesting_user_profile.realm_id)

def get_cross_realm_dicts() -> List[Dict[str, Any]]:
    users = bulk_get_users(list(settings.CROSS_REALM_BOT_EMAILS), None,
                           base_query=UserProfile.objects.filter(
                               realm__string_id=settings.SYSTEM_BOT_REALM)).values()
    return [{'email': user.email,
             'user_id': user.id,
             'is_admin': user.is_realm_admin,
             'is_bot': user.is_bot,
             'full_name': user.full_name}
            for user in users
            # Important: We filter here, is addition to in
            # `base_query`, because of how bulk_get_users shares its
            # cache with other UserProfile caches.
            if user.realm.string_id == settings.SYSTEM_BOT_REALM]

def do_send_confirmation_email(invitee: PreregistrationUser,
                               referrer: UserProfile) -> None:
    """
    Send the confirmation/welcome e-mail to an invited user.
    """
    activation_url = create_confirmation_link(invitee, referrer.realm.host, Confirmation.INVITATION)
    context = {'referrer': referrer, 'activate_url': activation_url,
               'referrer_realm_name': referrer.realm.name}
    from_name = "%s (via Zulip)" % (referrer.full_name,)
    send_email('zerver/emails/invitation', to_email=invitee.email, from_name=from_name,
               from_address=FromAddress.NOREPLY, context=context)

def email_not_system_bot(email: Text) -> None:
    if is_cross_realm_bot_email(email):
        raise ValidationError('%s is an email address reserved for system bots' % (email,))

def validate_email_for_realm(target_realm: Realm, email: Text) -> None:
    try:
        # Registering with a system bot's email is not allowed...
        email_not_system_bot(email)
    except ValidationError:
        # ... unless this is the first user with that email.  This
        # should be impossible in production, because these users are
        # created by initialize_voyager_db, but it happens in a test's
        # setup.  (This would be a good wrinkle to clean up.)
        if UserProfile.objects.filter(email__iexact=email).exists():
            raise

    try:
        existing_user_profile = get_user(email, target_realm)
    except UserProfile.DoesNotExist:
        return

    if existing_user_profile.is_mirror_dummy:
        # Mirror dummy users to be activated must be inactive
        if existing_user_profile.is_active:
            raise AssertionError("Mirror dummy user is already active!")
    else:
        # Other users should not already exist at all.
        raise ValidationError('%s already has an account' % (email,))

def validate_email(user_profile: UserProfile, email: Text) -> Tuple[Optional[str], Optional[str]]:
    try:
        validators.validate_email(email)
    except ValidationError:
        return _("Invalid address."), None

    try:
        email_allowed_for_realm(email, user_profile.realm)
    except DomainNotAllowedForRealmError:
        return _("Outside your domain."), None

    try:
        validate_email_for_realm(user_profile.realm, email)
    except ValidationError:
        return None, _("Already has an account.")

    return None, None

class InvitationError(JsonableError):
    code = ErrorCode.INVITATION_FAILED
    data_fields = ['errors', 'sent_invitations']

    def __init__(self, msg: Text, errors: List[Tuple[Text, str]], sent_invitations: bool) -> None:
        self._msg = msg  # type: Text
        self.errors = errors  # type: List[Tuple[Text, str]]
        self.sent_invitations = sent_invitations  # type: bool

def estimate_recent_invites(realms: Iterable[Realm], *, days: int) -> int:
    '''An upper bound on the number of invites sent in the last `days` days'''
    recent_invites = RealmCount.objects.filter(
        realm__in=realms,
        property='invites_sent::day',
        end_time__gte=timezone_now() - datetime.timedelta(days=days)
    ).aggregate(Sum('value'))['value__sum']
    if recent_invites is None:
        return 0
    return recent_invites

def check_invite_limit(user: UserProfile, num_invitees: int) -> None:
    '''Discourage using invitation emails as a vector for carrying spam.'''
    msg = _("You do not have enough remaining invites. "
            "Please contact %s to have your limit raised. "
            "No invitations were sent.") % (settings.ZULIP_ADMINISTRATOR,)
    if settings.OPEN_REALM_CREATION:
        recent_invites = estimate_recent_invites([user.realm], days=1)
        if num_invitees + recent_invites > user.realm.max_invites:
            raise InvitationError(msg, [], sent_invitations=False)

        default_max = settings.INVITES_DEFAULT_REALM_DAILY_MAX
        newrealm_age = datetime.timedelta(days=settings.INVITES_NEW_REALM_DAYS)
        if (user.realm.date_created > timezone_now() - newrealm_age
                and user.realm.max_invites <= default_max):
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
                    invite_as_admin: Optional[bool]=False) -> None:

    check_invite_limit(user_profile, len(invitee_emails))

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

    validated_emails = []  # type: List[Text]
    errors = []  # type: List[Tuple[Text, str]]
    skipped = []  # type: List[Tuple[Text, str]]
    for email in invitee_emails:
        if email == '':
            continue
        email_error, email_skipped = validate_email(user_profile, email)
        if not (email_error or email_skipped):
            validated_emails.append(email)
        elif email_error:
            errors.append((email, email_error))
        elif email_skipped:
            skipped.append((email, email_skipped))

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
                                          invited_as_admin=invite_as_admin,
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

def do_get_user_invites(user_profile: UserProfile) -> List[Dict[str, Any]]:
    days_to_activate = getattr(settings, 'ACCOUNT_ACTIVATION_DAYS', 7)
    active_value = getattr(confirmation_settings, 'STATUS_ACTIVE', 1)

    lowest_datetime = timezone_now() - datetime.timedelta(days=days_to_activate)
    prereg_users = PreregistrationUser.objects.exclude(status=active_value).filter(
        invited_at__gte=lowest_datetime,
        referred_by__realm=user_profile.realm)

    invites = []

    for invitee in prereg_users:
        invites.append(dict(email=invitee.email,
                            ref=invitee.referred_by.email,
                            invited=datetime_to_timestamp(invitee.invited_at),
                            id=invitee.id,
                            invited_as_admin=invitee.invited_as_admin))

    return invites

def do_create_multiuse_invite_link(referred_by: UserProfile, streams: Optional[List[Stream]]=[]) -> str:
    realm = referred_by.realm
    invite = MultiuseInvite.objects.create(realm=realm, referred_by=referred_by)
    if streams:
        invite.streams.set(streams)

    return create_confirmation_link(invite, realm.host, Confirmation.MULTIUSE_INVITE)

def do_revoke_user_invite(prereg_user: PreregistrationUser) -> None:
    email = prereg_user.email

    # Delete both the confirmation objects and the prereg_user object.
    # TODO: Probably we actaully want to set the confirmation objects
    # to a "revoked" status so that we can give the user a better
    # error message.
    content_type = ContentType.objects.get_for_model(PreregistrationUser)
    Confirmation.objects.filter(content_type=content_type,
                                object_id=prereg_user.id).delete()
    prereg_user.delete()
    clear_scheduled_invitation_emails(email)

def do_resend_user_invite_email(prereg_user: PreregistrationUser) -> int:
    check_invite_limit(prereg_user.referred_by, 1)

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
    send_event(event, active_user_ids(realm.id))

def check_add_realm_emoji(realm: Realm,
                          name: Text,
                          author: UserProfile,
                          image_file: File) -> Optional[RealmEmoji]:
    realm_emoji = RealmEmoji(realm=realm, name=name, author=author)
    realm_emoji.full_clean()
    realm_emoji.save()

    emoji_file_name = get_emoji_file_name(image_file.name, realm_emoji.id)
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

def do_remove_realm_emoji(realm: Realm, name: Text) -> None:
    emoji = RealmEmoji.objects.get(realm=realm, name=name, deactivated=False)
    emoji.deactivated = True
    emoji.save(update_fields=['deactivated'])
    notify_realm_emoji(realm)

def notify_alert_words(user_profile: UserProfile, words: Iterable[Text]) -> None:
    event = dict(type="alert_words", alert_words=words)
    send_event(event, [user_profile.id])

def do_add_alert_words(user_profile: UserProfile, alert_words: Iterable[Text]) -> None:
    words = add_user_alert_words(user_profile, alert_words)
    notify_alert_words(user_profile, words)

def do_remove_alert_words(user_profile: UserProfile, alert_words: Iterable[Text]) -> None:
    words = remove_user_alert_words(user_profile, alert_words)
    notify_alert_words(user_profile, words)

def do_set_alert_words(user_profile: UserProfile, alert_words: List[Text]) -> None:
    set_user_alert_words(user_profile, alert_words)
    notify_alert_words(user_profile, alert_words)

def do_mute_topic(user_profile: UserProfile, stream: Stream, recipient: Recipient, topic: str) -> None:
    add_topic_mute(user_profile, stream.id, recipient.id, topic)
    event = dict(type="muted_topics", muted_topics=get_topic_mutes(user_profile))
    send_event(event, [user_profile.id])

def do_unmute_topic(user_profile: UserProfile, stream: Stream, topic: str) -> None:
    remove_topic_mute(user_profile, stream.id, topic)
    event = dict(type="muted_topics", muted_topics=get_topic_mutes(user_profile))
    send_event(event, [user_profile.id])

def do_mark_hotspot_as_read(user: UserProfile, hotspot: str) -> None:
    UserHotspot.objects.get_or_create(user=user, hotspot=hotspot)
    event = dict(type="hotspots", hotspots=get_next_hotspots(user))
    send_event(event, [user.id])

def notify_realm_filters(realm: Realm) -> None:
    realm_filters = realm_filters_for_realm(realm.id)
    event = dict(type="realm_filters", realm_filters=realm_filters)
    send_event(event, active_user_ids(realm.id))

# NOTE: Regexes must be simple enough that they can be easily translated to JavaScript
# RegExp syntax. In addition to JS-compatible syntax, the following features are available:
#   * Named groups will be converted to numbered groups automatically
#   * Inline-regex flags will be stripped, and where possible translated to RegExp-wide flags
def do_add_realm_filter(realm: Realm, pattern: Text, url_format_string: Text) -> int:
    pattern = pattern.strip()
    url_format_string = url_format_string.strip()
    realm_filter = RealmFilter(
        realm=realm, pattern=pattern,
        url_format_string=url_format_string)
    realm_filter.full_clean()
    realm_filter.save()
    notify_realm_filters(realm)

    return realm_filter.id

def do_remove_realm_filter(realm: Realm, pattern: Optional[Text]=None,
                           id: Optional[int]=None) -> None:
    if pattern is not None:
        RealmFilter.objects.get(realm=realm, pattern=pattern).delete()
    else:
        RealmFilter.objects.get(realm=realm, pk=id).delete()
    notify_realm_filters(realm)

def get_emails_from_user_ids(user_ids: Sequence[int]) -> Dict[int, Text]:
    # We may eventually use memcached to speed this up, but the DB is fast.
    return UserProfile.emails_from_ids(user_ids)

def do_add_realm_domain(realm: Realm, domain: Text, allow_subdomains: bool) -> (RealmDomain):
    realm_domain = RealmDomain.objects.create(realm=realm, domain=domain,
                                              allow_subdomains=allow_subdomains)
    event = dict(type="realm_domains", op="add",
                 realm_domain=dict(domain=realm_domain.domain,
                                   allow_subdomains=realm_domain.allow_subdomains))
    send_event(event, active_user_ids(realm.id))
    return realm_domain

def do_change_realm_domain(realm_domain: RealmDomain, allow_subdomains: bool) -> None:
    realm_domain.allow_subdomains = allow_subdomains
    realm_domain.save(update_fields=['allow_subdomains'])
    event = dict(type="realm_domains", op="change",
                 realm_domain=dict(domain=realm_domain.domain,
                                   allow_subdomains=realm_domain.allow_subdomains))
    send_event(event, active_user_ids(realm_domain.realm_id))

def do_remove_realm_domain(realm_domain: RealmDomain) -> None:
    realm = realm_domain.realm
    domain = realm_domain.domain
    realm_domain.delete()
    if RealmDomain.objects.filter(realm=realm).count() == 0 and realm.restricted_to_domain:
        # If this was the last realm domain, we mark the realm as no
        # longer restricted to domain, because the feature doesn't do
        # anything if there are no domains, and this is probably less
        # confusing than the alternative.
        do_set_realm_property(realm, 'restricted_to_domain', False)
    event = dict(type="realm_domains", op="remove", domain=domain)
    send_event(event, active_user_ids(realm.id))

def get_occupied_streams(realm: Realm) -> QuerySet:
    # TODO: Make a generic stub for QuerySet
    """ Get streams with subscribers """
    subs_filter = Subscription.objects.filter(active=True, user_profile__realm=realm,
                                              user_profile__is_active=True).values('recipient_id')
    stream_ids = Recipient.objects.filter(
        type=Recipient.STREAM, id__in=subs_filter).values('type_id')

    return Stream.objects.filter(id__in=stream_ids, realm=realm, deactivated=False)

def do_get_streams(user_profile: UserProfile, include_public: bool=True,
                   include_subscribed: bool=True, include_all_active: bool=False,
                   include_default: bool=False) -> List[Dict[str, Any]]:
    if include_all_active and not user_profile.is_api_super_user:
        raise JsonableError(_("User not authorized for this query"))

    # Listing public streams are disabled for Zephyr mirroring realms.
    include_public = include_public and not user_profile.realm.is_zephyr_mirror_realm
    # Start out with all streams in the realm with subscribers
    query = get_occupied_streams(user_profile.realm)

    if not include_all_active:
        user_subs = get_stream_subscriptions_for_user(user_profile).filter(
            active=True,
        ).select_related('recipient')

        if include_subscribed:
            recipient_check = Q(id__in=[sub.recipient.type_id for sub in user_subs])
        if include_public:
            invite_only_check = Q(invite_only=False)

        if include_subscribed and include_public:
            query = query.filter(recipient_check | invite_only_check)
        elif include_public:
            query = query.filter(invite_only_check)
        elif include_subscribed:
            query = query.filter(recipient_check)
        else:
            # We're including nothing, so don't bother hitting the DB.
            query = []

    streams = [(row.to_dict()) for row in query]
    streams.sort(key=lambda elt: elt["name"])
    if include_default:
        is_default = {}
        default_streams = get_default_streams_for_realm(user_profile.realm_id)
        for default_stream in default_streams:
            is_default[default_stream.id] = True
        for stream in streams:
            stream['is_default'] = is_default.get(stream["stream_id"], False)

    return streams

def do_claim_attachments(message: Message) -> None:
    attachment_url_list = attachment_url_re.findall(message.content)

    for url in attachment_url_list:
        path_id = attachment_url_to_path_id(url)
        user_profile = message.sender
        is_message_realm_public = False
        if message.is_stream_message():
            is_message_realm_public = Stream.objects.get(id=message.recipient.type_id).is_public()

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
            logging.warning("User %s tried to share upload %s in message %s, but lacks permission" % (
                user_profile.id, path_id, message.id))
            continue

        claim_attachment(user_profile, path_id, message, is_message_realm_public)

def do_delete_old_unclaimed_attachments(weeks_ago: int) -> None:
    old_unclaimed_attachments = get_old_unclaimed_attachments(weeks_ago)

    for attachment in old_unclaimed_attachments:
        delete_message_image(attachment.path_id)
        attachment.delete()

def check_attachment_reference_change(prev_content: Text, message: Message) -> None:
    new_content = message.content
    prev_attachments = set(attachment_url_re.findall(prev_content))
    new_attachments = set(attachment_url_re.findall(new_content))

    to_remove = list(prev_attachments - new_attachments)
    path_ids = []
    for url in to_remove:
        path_id = attachment_url_to_path_id(url)
        path_ids.append(path_id)

    attachments_to_update = Attachment.objects.filter(path_id__in=path_ids).select_for_update()
    message.attachment_set.remove(*attachments_to_update)

    to_add = list(new_attachments - prev_attachments)
    if len(to_add) > 0:
        do_claim_attachments(message)

def notify_realm_custom_profile_fields(realm: Realm, operation: str) -> None:
    fields = custom_profile_fields_for_realm(realm.id)
    event = dict(type="custom_profile_fields",
                 op=operation,
                 fields=[f.as_dict() for f in fields])
    send_event(event, active_user_ids(realm.id))

def try_add_realm_custom_profile_field(realm: Realm, name: Text, field_type: int) -> CustomProfileField:
    field = CustomProfileField(realm=realm, name=name, field_type=field_type)
    field.save()
    notify_realm_custom_profile_fields(realm, 'add')
    return field

def do_remove_realm_custom_profile_field(realm: Realm, field: CustomProfileField) -> None:
    """
    Deleting a field will also delete the user profile data
    associated with it in CustomProfileFieldValue model.
    """
    field.delete()
    notify_realm_custom_profile_fields(realm, 'delete')

def try_update_realm_custom_profile_field(realm: Realm, field: CustomProfileField,
                                          name: Text) -> None:
    field.name = name
    field.save(update_fields=['name'])
    notify_realm_custom_profile_fields(realm, 'update')

def do_update_user_custom_profile_data(user_profile: UserProfile,
                                       data: List[Dict[str, Union[int, Text]]]) -> None:
    with transaction.atomic():
        update_or_create = CustomProfileFieldValue.objects.update_or_create
        for field in data:
            update_or_create(user_profile=user_profile,
                             field_id=field['id'],
                             defaults={'value': field['value']})
            payload = dict(user_id=user_profile.id, custom_profile_field=dict(id=field['id'],
                                                                              value=field['value']))
            event = dict(type="realm_user", op="update", person=payload)
            send_event(event, active_user_ids(user_profile.realm.id))

def do_send_create_user_group_event(user_group: UserGroup, members: List[UserProfile]) -> None:
    event = dict(type="user_group",
                 op="add",
                 group=dict(name=user_group.name,
                            members=[member.id for member in members],
                            description=user_group.description,
                            id=user_group.id,
                            ),
                 )
    send_event(event, active_user_ids(user_group.realm_id))

def check_add_user_group(realm: Realm, name: Text, initial_members: List[UserProfile],
                         description: Text) -> None:
    try:
        user_group = create_user_group(name, initial_members, realm, description=description)
        do_send_create_user_group_event(user_group, initial_members)
    except django.db.utils.IntegrityError:
        raise JsonableError(_("User group '%s' already exists." % (name,)))

def do_send_user_group_update_event(user_group: UserGroup, data: Dict[str, Any]) -> None:
    event = dict(type="user_group", op='update', group_id=user_group.id, data=data)
    send_event(event, active_user_ids(user_group.realm_id))

def do_update_user_group_name(user_group: UserGroup, name: Text) -> None:
    user_group.name = name
    user_group.save(update_fields=['name'])
    do_send_user_group_update_event(user_group, dict(name=name))

def do_update_user_group_description(user_group: UserGroup, description: Text) -> None:
    user_group.description = description
    user_group.save(update_fields=['description'])
    do_send_user_group_update_event(user_group, dict(description=description))

def do_update_outgoing_webhook_service(bot_profile: UserProfile,
                                       service_interface: int,
                                       service_payload_url: Text) -> None:
    # TODO: First service is chosen because currently one bot can only have one service.
    # Update this once multiple services are supported.
    service = get_bot_services(bot_profile.id)[0]
    service.base_url = service_payload_url
    service.interface = service_interface
    service.save()
    send_event(dict(type='realm_bot',
                    op='update',
                    bot=dict(email=bot_profile.email,
                             user_id=bot_profile.id,
                             services = [dict(base_url=service.base_url,
                                              interface=service.interface)],
                             ),
                    ),
               bot_owner_user_ids(bot_profile))

def do_update_bot_config_data(bot_profile: UserProfile,
                              config_data: Dict[Text, Text]) -> None:
    for key, value in config_data.items():
        set_bot_config(bot_profile, key, value)
    updated_config_data = get_bot_config(bot_profile)
    send_event(dict(type='realm_bot',
                    op='update',
                    bot=dict(email=bot_profile.email,
                             user_id=bot_profile.id,
                             services = [dict(config_data=updated_config_data)],
                             ),
                    ),
               bot_owner_user_ids(bot_profile))

def get_service_dicts_for_bot(user_profile_id: str) -> List[Dict[str, Any]]:
    user_profile = get_user_profile_by_id(user_profile_id)
    services = get_bot_services(user_profile_id)
    service_dicts = []  # type: List[Dict[Text, Any]]
    if user_profile.bot_type == UserProfile.OUTGOING_WEBHOOK_BOT:
        service_dicts = [{'base_url': service.base_url,
                          'interface': service.interface,
                          }
                         for service in services]
    elif user_profile.bot_type == UserProfile.EMBEDDED_BOT:
        try:
            service_dicts = [{'config_data': get_bot_config(user_profile),
                              'service_name': services[0].name
                              }]
        # A ConfigError just means that there are no config entries for user_profile.
        except ConfigError:
            pass
    return service_dicts

def get_service_dicts_for_bots(bot_profile_ids: List[int], realm: Realm) -> Dict[int, List[Dict[str, Any]]]:
    bot_profiles = user_ids_to_users(bot_profile_ids, realm)  # type: List[UserProfile]
    bot_services_by_uid = get_services_for_bots(bot_profiles)

    embedded_bot_profiles = [profile for profile in bot_profiles
                             if profile.bot_type == UserProfile.EMBEDDED_BOT]
    embedded_bot_configs = get_bot_configs(embedded_bot_profiles)

    service_dicts_by_uid = {}  # type: Dict[int, List[Dict[Text, Any]]]
    for bot_profile in bot_profiles:
        services = bot_services_by_uid[bot_profile.id]
        service_dicts = []  # type: List[Dict[Text, Any]]
        if bot_profile.bot_type == UserProfile.OUTGOING_WEBHOOK_BOT:
            service_dicts = [{'base_url': service.base_url,
                              'interface': service.interface,
                              }
                             for service in services]
        elif bot_profile.bot_type == UserProfile.EMBEDDED_BOT:
            if bot_profile.id in embedded_bot_configs.keys():
                bot_config = embedded_bot_configs[bot_profile.id]
                service_dicts = [{'config_data': bot_config,
                                  'service_name': services[0].name
                                  }]
        service_dicts_by_uid[bot_profile.id] = service_dicts
    return service_dicts_by_uid

def get_owned_bot_dicts(user_profile: UserProfile,
                        include_all_realm_bots_if_admin: bool=True) -> List[Dict[str, Any]]:
    if user_profile.is_realm_admin and include_all_realm_bots_if_admin:
        result = get_bot_dicts_in_realm(user_profile.realm)
    else:
        result = UserProfile.objects.filter(realm=user_profile.realm, is_bot=True,
                                            bot_owner=user_profile).values(*bot_dict_fields)
    bot_profile_ids = [botdict['id'] for botdict in result]
    services_by_ids = get_service_dicts_for_bots(bot_profile_ids, user_profile.realm)
    return [{'email': botdict['email'],
             'user_id': botdict['id'],
             'full_name': botdict['full_name'],
             'bot_type': botdict['bot_type'],
             'is_active': botdict['is_active'],
             'api_key': botdict['api_key'],
             'default_sending_stream': botdict['default_sending_stream__name'],
             'default_events_register_stream': botdict['default_events_register_stream__name'],
             'default_all_public_streams': botdict['default_all_public_streams'],
             'owner': botdict['bot_owner__email'],
             'avatar_url': avatar_url_from_dict(botdict),
             'services': services_by_ids[botdict['id']],
             }
            for botdict in result]

def do_send_user_group_members_update_event(event_name: Text,
                                            user_group: UserGroup,
                                            user_ids: List[int]) -> None:
    event = dict(type="user_group",
                 op=event_name,
                 group_id=user_group.id,
                 user_ids=user_ids)
    send_event(event, active_user_ids(user_group.realm_id))

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

def do_send_delete_user_group_event(user_group_id: int, realm_id: int) -> None:
    event = dict(type="user_group",
                 op="remove",
                 group_id=user_group_id)
    send_event(event, active_user_ids(realm_id))

def check_delete_user_group(user_group_id: int, user_profile: UserProfile) -> None:
    user_group = access_user_group_by_id(user_group_id, user_profile)
    user_group.delete()
    do_send_delete_user_group_event(user_group_id, user_profile.realm.id)
