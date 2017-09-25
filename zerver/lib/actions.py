from __future__ import absolute_import
from __future__ import print_function
from typing import (
    AbstractSet, Any, AnyStr, Callable, Dict, Iterable, List, Mapping, MutableMapping,
    Optional, Sequence, Set, Text, Tuple, TypeVar, Union, cast
)
from mypy_extensions import TypedDict

from django.utils.html import escape
from django.utils.translation import ugettext as _
from django.conf import settings
from django.core import validators
from analytics.lib.counts import COUNT_STATS, do_increment_logging_stat
from zerver.lib.bugdown import (
    BugdownRenderingException,
    version as bugdown_version,
    url_embed_preview_enabled_for_realm
)
from zerver.lib.addressee import (
    Addressee,
    user_profiles_from_unvalidated_emails,
)
from zerver.lib.cache import (
    delete_user_profile_caches,
    to_dict_cache_key,
    to_dict_cache_key_id,
)
from zerver.lib.context_managers import lockfile
from zerver.lib.emoji import emoji_name_to_emoji_code
from zerver.lib.hotspots import get_next_hotspots
from zerver.lib.message import (
    access_message,
    MessageDict,
    message_to_dict,
    render_markdown,
)
from zerver.lib.realm_icon import realm_icon_url
from zerver.lib.retention import move_message_to_archive
from zerver.lib.send_email import send_email, FromAddress
from zerver.lib.topic_mutes import (
    get_topic_mutes,
    add_topic_mute,
    remove_topic_mute,
)
from zerver.models import Realm, RealmEmoji, Stream, UserProfile, UserActivity, \
    RealmDomain, \
    Subscription, Recipient, Message, Attachment, UserMessage, RealmAuditLog, \
    UserHotspot, \
    Client, DefaultStream, UserPresence, PushDeviceToken, ScheduledEmail, \
    MAX_SUBJECT_LENGTH, \
    MAX_MESSAGE_LENGTH, get_client, get_stream, get_recipient, get_huddle, \
    get_user_profile_by_id, PreregistrationUser, get_display_recipient, \
    get_realm, bulk_get_recipients, \
    email_allowed_for_realm, email_to_username, display_recipient_cache_key, \
    get_user_profile_by_email, get_user, get_stream_cache_key, \
    UserActivityInterval, active_user_ids, get_active_streams, \
    realm_filters_for_realm, RealmFilter, receives_offline_notifications, \
    get_owned_bot_dicts, stream_name_in_use, \
    get_old_unclaimed_attachments, get_cross_realm_emails, \
    Reaction, EmailChangeStatus, CustomProfileField, \
    custom_profile_fields_for_realm, \
    CustomProfileFieldValue, validate_attachment_request, get_system_bot, \
    get_display_recipient_by_id, query_for_ids

from zerver.lib.alert_words import alert_words_in_realm
from zerver.lib.avatar import avatar_url
from zerver.lib.stream_recipient import StreamRecipientMap

from django.db import transaction, IntegrityError, connection
from django.db.models import F, Q, Max
from django.db.models.query import QuerySet
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.utils.timezone import now as timezone_now

from confirmation.models import Confirmation, create_confirmation_link
import six
from six.moves import filter
from six.moves import map
from six.moves import range
from six import unichr

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
from zerver.lib.alert_words import user_alert_words, add_user_alert_words, \
    remove_user_alert_words, set_user_alert_words
from zerver.lib.notifications import clear_scheduled_emails, \
    clear_scheduled_invitation_emails, enqueue_welcome_emails
from zerver.lib.narrow import check_supported_events_narrow_filter
from zerver.lib.exceptions import JsonableError, ErrorCode
from zerver.lib.sessions import delete_user_sessions
from zerver.lib.upload import attachment_url_re, attachment_url_to_path_id, \
    claim_attachment, delete_message_image
from zerver.lib.str_utils import NonBinaryStr, force_str
from zerver.tornado.event_queue import request_event_queue, send_event

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
def log_event(event):
    # type: (MutableMapping[str, Any]) -> None
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
            log.write(force_str(ujson.dumps(event) + u'\n'))

def can_access_stream_user_ids(stream):
    # type: (Stream) -> Set[int]

    # return user ids of users who can access the attributes of
    # a stream, such as its name/description
    if stream.is_public():
        return set(active_user_ids(stream.realm_id))
    else:
        return private_stream_user_ids(stream)

def private_stream_user_ids(stream):
    # type: (Stream) -> Set[int]

    # TODO: Find similar queries elsewhere and de-duplicate this code.
    subscriptions = Subscription.objects.filter(
        recipient__type=Recipient.STREAM,
        recipient__type_id=stream.id,
        active=True)

    return {sub['user_profile_id'] for sub in subscriptions.values('user_profile_id')}

def bot_owner_userids(user_profile):
    # type: (UserProfile) -> Set[int]
    is_private_bot = (
        user_profile.default_sending_stream and user_profile.default_sending_stream.invite_only or
        user_profile.default_events_register_stream and user_profile.default_events_register_stream.invite_only)
    if is_private_bot:
        return {user_profile.bot_owner_id, }
    else:
        users = {user.id for user in user_profile.realm.get_admin_users()}
        users.add(user_profile.bot_owner_id)
        return users

def realm_user_count(realm):
    # type: (Realm) -> int
    return UserProfile.objects.filter(realm=realm, is_active=True, is_bot=False).count()

def get_topic_history_for_stream(user_profile, recipient):
    # type: (UserProfile, Recipient) -> List[Dict[str, Any]]

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
    cursor = connection.cursor()
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

def send_signup_message(sender, signups_stream, user_profile,
                        internal=False, realm=None):
    # type: (UserProfile, Text, UserProfile, bool, Optional[Realm]) -> None
    if internal:
        # When this is done using manage.py vs. the web interface
        internal_blurb = " **INTERNAL SIGNUP** "
    else:
        internal_blurb = " "

    user_count = realm_user_count(user_profile.realm)
    notifications_stream = user_profile.realm.get_notifications_stream()
    # Send notification to realm notifications stream if it exists
    # Don't send notification for the first user in a realm
    if notifications_stream is not None and user_count > 1:
        internal_send_message(
            user_profile.realm,
            sender,
            "stream",
            notifications_stream.name,
            "New users", "%s just signed up for Zulip. Say hello!" % (
                user_profile.full_name,)
        )

    # We also send a notification to the Zulip administrative realm
    admin_realm = get_system_bot(sender).realm
    try:
        # Check whether the stream exists
        get_stream(signups_stream, admin_realm)
    except Stream.DoesNotExist:
        # If the signups stream hasn't been created in the admin
        # realm, don't auto-create it to send to it; just do nothing.
        return
    internal_send_message(
        admin_realm,
        sender,
        "stream",
        signups_stream,
        user_profile.realm.string_id,
        "%s <`%s`> just signed up for Zulip!%s(total: **%i**)" % (
            user_profile.full_name,
            user_profile.email,
            internal_blurb,
            user_count,
        )
    )

def notify_new_user(user_profile, internal=False):
    # type: (UserProfile, bool) -> None
    if settings.NEW_USER_BOT is not None:
        send_signup_message(settings.NEW_USER_BOT, "signups", user_profile, internal)
    statsd.gauge("users.signups.%s" % (user_profile.realm.string_id), 1, delta=True)

    # We also clear any scheduled invitation emails to prevent them
    # from being sent after the user is created.
    clear_scheduled_invitation_emails(user_profile.email)

def add_new_user_history(user_profile, streams):
    # type: (UserProfile, Iterable[Stream]) -> None
    """Give you the last 1000 messages on your public streams, so you have
    something to look at in your home view once you finish the
    tutorial."""
    one_week_ago = timezone_now() - datetime.timedelta(weeks=1)
    recipients = Recipient.objects.filter(type=Recipient.STREAM,
                                          type_id__in=[stream.id for stream in streams
                                                       if not stream.invite_only])
    recent_messages = Message.objects.filter(recipient_id__in=recipients,
                                             pub_date__gt=one_week_ago).order_by("-id")
    message_ids_to_use = list(reversed(recent_messages.values_list('id', flat=True)[0:1000]))
    if len(message_ids_to_use) == 0:
        return

    # Handle the race condition where a message arrives between
    # bulk_add_subscriptions above and the Message query just above
    already_ids = set(UserMessage.objects.filter(message_id__in=message_ids_to_use,
                                                 user_profile=user_profile).values_list("message_id", flat=True))
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
def process_new_human_user(user_profile, prereg_user=None, newsletter_data=None):
    # type: (UserProfile, Optional[PreregistrationUser], Optional[Dict[str, str]]) -> None
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
    enqueue_welcome_emails(user_profile)

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

def notify_created_user(user_profile):
    # type: (UserProfile) -> None
    event = dict(type="realm_user", op="add",
                 person=dict(email=user_profile.email,
                             user_id=user_profile.id,
                             is_admin=user_profile.is_realm_admin,
                             full_name=user_profile.full_name,
                             avatar_url=avatar_url(user_profile),
                             timezone=user_profile.timezone,
                             is_bot=user_profile.is_bot))
    send_event(event, active_user_ids(user_profile.realm_id))

def notify_created_bot(user_profile):
    # type: (UserProfile) -> None

    def stream_name(stream):
        # type: (Optional[Stream]) -> Optional[Text]
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
               )

    # Set the owner key only when the bot has an owner.
    # The default bots don't have an owner. So don't
    # set the owner key while reactivating them.
    if user_profile.bot_owner is not None:
        bot['owner'] = user_profile.bot_owner.email

    event = dict(type="realm_bot", op="add", bot=bot)
    send_event(event, bot_owner_userids(user_profile))

def do_create_user(email, password, realm, full_name, short_name,
                   active=True, is_realm_admin=False, bot_type=None, bot_owner=None, tos_version=None,
                   timezone=u"", avatar_source=UserProfile.AVATAR_FROM_GRAVATAR,
                   default_sending_stream=None, default_events_register_stream=None,
                   default_all_public_streams=None, prereg_user=None,
                   newsletter_data=None):
    # type: (Text, Optional[Text], Realm, Text, Text, bool, bool, Optional[int], Optional[UserProfile], Optional[Text], Text, Text, Optional[Stream], Optional[Stream], bool, Optional[PreregistrationUser], Optional[Dict[str, str]]) -> UserProfile
    user_profile = create_user(email=email, password=password, realm=realm,
                               full_name=full_name, short_name=short_name,
                               active=active, is_realm_admin=is_realm_admin,
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
                               newsletter_data=newsletter_data)
    return user_profile

def active_humans_in_realm(realm):
    # type: (Realm) -> Sequence[UserProfile]
    return UserProfile.objects.filter(realm=realm, is_active=True, is_bot=False)


def do_set_realm_property(realm, name, value):
    # type: (Realm, str, Union[Text, bool, int]) -> None
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


def do_set_realm_authentication_methods(realm, authentication_methods):
    # type: (Realm, Dict[str, bool]) -> None
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


def do_set_realm_message_editing(realm, allow_message_editing, message_content_edit_limit_seconds):
    # type: (Realm, bool, int) -> None
    realm.allow_message_editing = allow_message_editing
    realm.message_content_edit_limit_seconds = message_content_edit_limit_seconds
    realm.save(update_fields=['allow_message_editing', 'message_content_edit_limit_seconds'])
    event = dict(
        type="realm",
        op="update_dict",
        property="default",
        data=dict(allow_message_editing=allow_message_editing,
                  message_content_edit_limit_seconds=message_content_edit_limit_seconds),
    )
    send_event(event, active_user_ids(realm.id))

def do_set_realm_notifications_stream(realm, stream, stream_id):
    # type: (Realm, Stream, int) -> None
    realm.notifications_stream = stream
    realm.save(update_fields=['notifications_stream'])
    event = dict(
        type="realm",
        op="update",
        property="notifications_stream_id",
        value=stream_id
    )
    send_event(event, active_user_ids(realm.id))

def do_deactivate_realm(realm):
    # type: (Realm) -> None
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

    for user in active_humans_in_realm(realm):
        # Don't deactivate the users, but do delete their sessions so they get
        # bumped to the login screen, where they'll get a realm deactivation
        # notice when they try to log in.
        delete_user_sessions(user)
        clear_scheduled_emails(user.id)

def do_reactivate_realm(realm):
    # type: (Realm) -> None
    realm.deactivated = False
    realm.save(update_fields=["deactivated"])

def do_deactivate_user(user_profile, acting_user=None, _cascade=True):
    # type: (UserProfile, Optional[UserProfile], bool) -> None
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
        send_event(event, bot_owner_userids(user_profile))

    if _cascade:
        bot_profiles = UserProfile.objects.filter(is_bot=True, is_active=True,
                                                  bot_owner=user_profile)
        for profile in bot_profiles:
            do_deactivate_user(profile, acting_user=acting_user, _cascade=False)

def do_deactivate_stream(stream, log=True):
    # type: (Stream, bool) -> None

    # Get the affected user ids *before* we deactivate everybody.
    affected_user_ids = can_access_stream_user_ids(stream)

    Subscription.objects.select_related('user_profile').filter(
        recipient__type=Recipient.STREAM,
        recipient__type_id=stream.id,
        active=True).update(active=False)

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

def do_change_user_email(user_profile, new_email):
    # type: (UserProfile, Text) -> None
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

def do_start_email_change_process(user_profile, new_email):
    # type: (UserProfile, Text) -> None
    old_email = user_profile.email
    user_profile.email = new_email
    obj = EmailChangeStatus.objects.create(new_email=new_email, old_email=old_email,
                                           user_profile=user_profile, realm=user_profile.realm)

    activation_url = create_confirmation_link(obj, user_profile.realm.host, Confirmation.EMAIL_CHANGE)
    context = {'realm': user_profile.realm, 'old_email': old_email, 'new_email': new_email,
               'activate_url': activation_url}
    send_email('zerver/emails/confirm_new_email', to_email=new_email,
               from_name='Zulip Account Security', from_address=FromAddress.NOREPLY,
               context=context)

def compute_irc_user_fullname(email):
    # type: (NonBinaryStr) -> NonBinaryStr
    return email.split("@")[0] + " (IRC)"

def compute_jabber_user_fullname(email):
    # type: (NonBinaryStr) -> NonBinaryStr
    return email.split("@")[0] + " (XMPP)"

def compute_mit_user_fullname(email):
    # type: (NonBinaryStr) -> NonBinaryStr
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
def create_mirror_user_if_needed(realm, email, email_to_fullname):
    # type: (Realm, Text, Callable[[Text], Text]) -> UserProfile
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

def render_incoming_message(message, content, user_ids, realm):
    # type: (Message, Text, Set[int], Realm) -> Text
    realm_alert_words = alert_words_in_realm(realm)
    try:
        rendered_content = render_markdown(
            message=message,
            content=content,
            realm=realm,
            realm_alert_words=realm_alert_words,
            user_ids=user_ids,
        )
    except BugdownRenderingException:
        raise JsonableError(_('Unable to render message'))
    return rendered_content

def get_typing_user_profiles(recipient, sender_id):
    # type: (Recipient, int) -> List[UserProfile]
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
        user_ids = Subscription.objects.filter(
            recipient=recipient,
            active=True,
        ).order_by('user_profile_id').values_list('user_profile_id', flat=True)

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
    'service_bot_tuples': List[Tuple[int, int]],
})

def get_recipient_info(recipient, sender_id):
    # type: (Recipient, int) -> RecipientInfoResult
    stream_push_user_ids = set()  # type: Set[int]

    if recipient.type == Recipient.PERSONAL:
        # The sender and recipient may be the same id, so
        # de-duplicate using a set.
        user_ids = list({recipient.type_id, sender_id})
        assert(len(user_ids) in [1, 2])

    elif recipient.type == Recipient.STREAM:
        subscription_rows = Subscription.objects.filter(
            recipient=recipient,
            active=True,
        ).values(
            'user_profile_id',
            'push_notifications',
        ).order_by('user_profile_id')
        user_ids = [
            row['user_profile_id']
            for row in subscription_rows
        ]
        stream_push_user_ids = {
            row['user_profile_id']
            for row in subscription_rows
            if row['push_notifications']
        }

    elif recipient.type == Recipient.HUDDLE:
        user_ids = Subscription.objects.filter(
            recipient=recipient,
            active=True,
        ).order_by('user_profile_id').values_list('user_profile_id', flat=True)

    else:
        raise ValueError('Bad recipient type')

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
            user_ids=user_ids,
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

    active_user_ids = {
        row['id']
        for row in rows
    }

    def get_ids_for(f):
        # type: (Callable[[Dict[str, Any]], bool]) -> Set[int]
        return {
            row['id']
            for row in rows
            if f(row)
        }

    def is_service_bot(row):
        # type: (Dict[str, Any]) -> bool
        return row['is_bot'] and (row['bot_type'] in UserProfile.SERVICE_BOT_TYPES)

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
        service_bot_tuples=service_bot_tuples
    )  # type: RecipientInfoResult
    return info

def do_send_messages(messages_maybe_none):
    # type: (Sequence[Optional[MutableMapping[str, Any]]]) -> List[int]
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

    # For consistency, changes to the default values for these gets should also be applied
    # to the default args in do_send_message
    for message in messages:
        message['rendered_content'] = message.get('rendered_content', None)
        message['stream'] = message.get('stream', None)
        message['local_id'] = message.get('local_id', None)
        message['sender_queue_id'] = message.get('sender_queue_id', None)
        message['realm'] = message.get('realm', message['message'].sender.realm)

    for message in messages:
        info = get_recipient_info(message['message'].recipient,
                                  message['message'].sender_id)

        message['active_user_ids'] = info['active_user_ids']
        message['push_notify_user_ids'] = info['push_notify_user_ids']
        message['stream_push_user_ids'] = info['stream_push_user_ids']
        message['um_eligible_user_ids'] = info['um_eligible_user_ids']
        message['long_term_idle_user_ids'] = info['long_term_idle_user_ids']
        message['service_bot_tuples'] = info['service_bot_tuples']

    links_for_embed = set()  # type: Set[Text]
    # Render our messages.
    for message in messages:
        assert message['message'].rendered_content is None
        rendered_content = render_incoming_message(
            message['message'],
            message['message'].content,
            message['active_user_ids'],
            message['realm'])
        message['message'].rendered_content = rendered_content
        message['message'].rendered_content_version = bugdown_version
        links_for_embed |= message['message'].links_for_preview

    for message in messages:
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

            # Prepare to collect service queue events triggered by the message.
            message['message'].service_queue_events = defaultdict(list)

            # Avoid infinite loops by preventing messages sent by bots from generating
            # Service events.
            sender = message['message'].sender
            if sender.is_bot:
                continue

            # TODO: Right now, service bots need to be subscribed to a stream in order to
            # receive messages when mentioned; we will want to change that structure.
            for user_profile_id, bot_type in message['service_bot_tuples']:
                if bot_type == UserProfile.OUTGOING_WEBHOOK_BOT:
                    queue_name = 'outgoing_webhooks'
                elif bot_type == UserProfile.EMBEDDED_BOT:
                    queue_name = 'embedded_bots'
                else:
                    logging.error(
                        'Unexpected bot_type for Service bot id=%s: %s' %
                        (user_profile_id, bot_type))
                    continue

                # Mention triggers, primarily for stream messages
                if user_profile_id in mentioned_user_ids:
                    trigger = 'mention'
                # PM triggers for personal and huddle messsages
                elif message['message'].recipient.type != Recipient.STREAM:
                    trigger = 'private_message'
                else:
                    continue

                message['message'].service_queue_events[queue_name].append({
                    'trigger': trigger,
                    'user_profile_id': user_profile_id,
                })

        bulk_insert_ums(ums)

        # Claim attachments in message
        for message in messages:
            if Message.content_has_attachment(message['message'].content):
                do_claim_attachments(message['message'])

    for message in messages:
        # Deliver events to the real-time push system, as well as
        # enqueuing any additional processing triggered by the message.
        message_dict_markdown = message_to_dict(message['message'], apply_markdown=True)
        message_dict_no_markdown = message_to_dict(message['message'], apply_markdown=False)

        user_flags = user_message_flags.get(message['message'].id, {})
        sender = message['message'].sender
        message_type = message_dict_no_markdown['type']

        missed_message_userids = get_userids_for_missed_messages(
            realm=sender.realm,
            sender_id=sender.id,
            message_type=message_type,
            active_user_ids=message['active_user_ids'],
            user_flags=user_flags,
        )

        event = dict(
            type='message',
            message=message['message'].id,
            message_dict_markdown=message_dict_markdown,
            message_dict_no_markdown=message_dict_no_markdown,
            missed_message_userids=missed_message_userids,
        )

        users = [
            dict(
                id=user_id,
                flags=user_flags.get(user_id, []),
                always_push_notify=(user_id in message['push_notify_user_ids']),
                stream_push_notify=(user_id in message['stream_push_user_ids']),
            )
            for user_id in message['active_user_ids']
        ]

        if message['message'].recipient.type == Recipient.STREAM:
            # Note: This is where authorization for single-stream
            # get_updates happens! We only attach stream data to the
            # notify new_message request if it's a public stream,
            # ensuring that in the tornado server, non-public stream
            # messages are only associated to their subscribed users.
            if message['stream'] is None:
                message['stream'] = Stream.objects.select_related("realm").get(id=message['message'].recipient.type_id)
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
            queue_json_publish('embed_links', event_data, lambda x: None)

        if (settings.ENABLE_FEEDBACK and settings.FEEDBACK_BOT and
                message['message'].recipient.type == Recipient.PERSONAL):

            feedback_bot_id = get_user_profile_by_email(email=settings.FEEDBACK_BOT).id
            if feedback_bot_id in message['active_user_ids']:
                queue_json_publish(
                    'feedback_messages',
                    message_to_dict(message['message'], apply_markdown=False),
                    lambda x: None
                )

        for queue_name, events in message['message'].service_queue_events.items():
            for event in events:
                queue_json_publish(
                    queue_name,
                    {
                        "message": message_to_dict(message['message'], apply_markdown=False),
                        "trigger": event['trigger'],
                        "user_profile_id": event["user_profile_id"],
                        "failed_tries": 0,
                    },
                    lambda x: None
                )

    # Note that this does not preserve the order of message ids
    # returned.  In practice, this shouldn't matter, as we only
    # mirror single zephyr messages at a time and don't otherwise
    # intermingle sending zephyr messages with other messages.
    return already_sent_ids + [message['message'].id for message in messages]

class UserMessageLite(object):
    '''
    The Django ORM is too slow for bulk operations.  This class
    is optimized for the simple use case of inserting a bunch of
    rows into zerver_usermessage.
    '''
    def __init__(self, user_profile_id, message_id):
        # type: (int, int) -> None
        self.user_profile_id = user_profile_id
        self.message_id = message_id
        self.flags = 0

    def flags_list(self):
        # type: () -> List[str]
        return UserMessage.flags_list_for_flags(self.flags)

def create_user_messages(message, um_eligible_user_ids, long_term_idle_user_ids, mentioned_user_ids):
    # type: (Message, Set[int], Set[int], Set[int]) -> List[UserMessageLite]
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
                message.recipient.type == Recipient.STREAM and
                int(um.flags) == 0):
            continue
        user_messages.append(um)

    return user_messages

def bulk_insert_ums(ums):
    # type: (List[UserMessageLite]) -> None
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

def notify_reaction_update(user_profile, message, reaction, op):
    # type: (UserProfile, Message, Reaction, Text) -> None
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

def do_add_reaction(user_profile, message, emoji_name):
    # type: (UserProfile, Message, Text) -> None
    (emoji_code, reaction_type) = emoji_name_to_emoji_code(user_profile.realm, emoji_name)
    reaction = Reaction(user_profile=user_profile, message=message,
                        emoji_name=emoji_name, emoji_code=emoji_code,
                        reaction_type=reaction_type)
    reaction.save()
    notify_reaction_update(user_profile, message, reaction, "add")

def do_remove_reaction(user_profile, message, emoji_name):
    # type: (UserProfile, Message, Text) -> None
    reaction = Reaction.objects.filter(user_profile=user_profile,
                                       message=message,
                                       emoji_name=emoji_name).get()
    reaction.delete()
    notify_reaction_update(user_profile, message, reaction, "remove")

def do_send_typing_notification(notification):
    # type: (Dict[str, Any]) -> None
    recipient_user_profiles = get_typing_user_profiles(notification['recipient'],
                                                       notification['sender'].id)
    # Only deliver the notification to active user recipients
    user_ids_to_notify = [profile.id for profile in recipient_user_profiles if profile.is_active]
    sender_dict = {'user_id': notification['sender'].id, 'email': notification['sender'].email}
    # Include a list of recipients in the event body to help identify where the typing is happening
    recipient_dicts = [{'user_id': profile.id, 'email': profile.email} for profile in recipient_user_profiles]
    event = dict(
        type            = 'typing',
        op              = notification['op'],
        sender          = sender_dict,
        recipients      = recipient_dicts)

    send_event(event, user_ids_to_notify)

# check_send_typing_notification:
# Checks the typing notification and sends it
def check_send_typing_notification(sender, notification_to, operator):
    # type: (UserProfile, Sequence[Text], Text) -> None
    typing_notification = check_typing_notification(sender, notification_to, operator)
    do_send_typing_notification(typing_notification)

# check_typing_notification:
# Returns typing notification ready for sending with do_send_typing_notification on success
# or the error message (string) on error.
def check_typing_notification(sender, notification_to, operator):
    # type: (UserProfile, Sequence[Text], Text) -> Dict[str, Any]
    if len(notification_to) == 0:
        raise JsonableError(_('Missing parameter: \'to\' (recipient)'))
    elif operator not in ('start', 'stop'):
        raise JsonableError(_('Invalid \'op\' value (should be start or stop)'))
    else:
        try:
            recipient = recipient_for_emails(notification_to, False,
                                             sender, sender)
        except ValidationError as e:
            assert isinstance(e.messages[0], six.string_types)
            raise JsonableError(e.messages[0])
    if recipient.type == Recipient.STREAM:
        raise ValueError('Forbidden recipient type')
    return {'sender': sender, 'recipient': recipient, 'op': operator}

def stream_welcome_message(stream):
    # type: (Stream) -> Text
    content = _('Welcome to #**%s**.') % (stream.name,)

    if stream.description:
        content += '\n\n**' + _('Description') + '**: '
        content += stream.description

    return content

def prep_stream_welcome_message(stream):
    # type: (Stream) -> Optional[Dict[str, Any]]
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

def send_stream_creation_event(stream, user_ids):
    # type: (Stream, List[int]) -> None
    event = dict(type="stream", op="create",
                 streams=[stream.to_dict()])
    send_event(event, user_ids)

def create_stream_if_needed(realm, stream_name, invite_only=False, stream_description = ""):
    # type: (Realm, Text, bool, Text) -> Tuple[Stream, bool]
    (stream, created) = Stream.objects.get_or_create(
        realm=realm, name__iexact=stream_name,
        defaults={'name': stream_name,
                  'description': stream_description,
                  'invite_only': invite_only})
    if created:
        Recipient.objects.create(type_id=stream.id, type=Recipient.STREAM)
        if stream.is_public():
            send_stream_creation_event(stream, active_user_ids(stream.realm_id))
    return stream, created

def create_streams_if_needed(realm, stream_dicts):
    # type: (Realm, List[Mapping[str, Any]]) -> Tuple[List[Stream], List[Stream]]
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


def get_recipient_from_user_ids(recipient_profile_ids, not_forged_mirror_message, forwarder_user_profile, sender):
    # type: (Set[int], bool, Optional[UserProfile], UserProfile) -> Recipient

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
        huddle = get_huddle(list(recipient_profile_ids))
        return get_recipient(Recipient.HUDDLE, huddle.id)
    else:
        return get_recipient(Recipient.PERSONAL, list(recipient_profile_ids)[0])

def validate_recipient_user_profiles(user_profiles, sender):
    # type: (List[UserProfile], UserProfile) -> Set[int]
    recipient_profile_ids = set()

    # We exempt cross-realm bots from the check that all the recipients
    # are in the same realm.
    realms = set()
    exempt_emails = get_cross_realm_emails()
    if sender.email not in exempt_emails:
        realms.add(sender.realm_id)

    for user_profile in user_profiles:
        if (not user_profile.is_active and not user_profile.is_mirror_dummy) or \
                user_profile.realm.deactivated:
            raise ValidationError(_("'%s' is no longer using Zulip.") % (user_profile.email,))
        recipient_profile_ids.add(user_profile.id)
        if user_profile.email not in exempt_emails:
            realms.add(user_profile.realm_id)

    if len(realms) > 1:
        raise ValidationError(_("You can't send private messages outside of your organization."))

    return recipient_profile_ids

def recipient_for_emails(emails, not_forged_mirror_message,
                         forwarder_user_profile, sender):
    # type: (Iterable[Text], bool, Optional[UserProfile], UserProfile) -> Recipient

    user_profiles = user_profiles_from_unvalidated_emails(emails, sender.realm)

    return recipient_for_user_profiles(
        user_profiles=user_profiles,
        not_forged_mirror_message=not_forged_mirror_message,
        forwarder_user_profile=forwarder_user_profile,
        sender=sender
    )

def recipient_for_user_profiles(user_profiles, not_forged_mirror_message,
                                forwarder_user_profile, sender):
    # type: (List[UserProfile], bool, Optional[UserProfile], UserProfile) -> Recipient

    recipient_profile_ids = validate_recipient_user_profiles(user_profiles, sender)

    return get_recipient_from_user_ids(recipient_profile_ids, not_forged_mirror_message,
                                       forwarder_user_profile, sender)

def already_sent_mirrored_message_id(message):
    # type: (Message) -> Optional[int]
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

def extract_recipients(s):
    # type: (Union[str, Iterable[Text]]) -> List[Text]
    # We try to accept multiple incoming formats for recipients.
    # See test_extract_recipients() for examples of what we allow.
    try:
        data = ujson.loads(s)  # type: ignore # This function has a super weird union argument.
    except ValueError:
        data = s

    if isinstance(data, six.string_types):
        data = data.split(',')

    if not isinstance(data, list):
        raise ValueError("Invalid data type for recipients")

    recipients = data

    # Strip recipients, and then remove any duplicates and any that
    # are the empty string after being stripped.
    recipients = [recipient.strip() for recipient in recipients]
    return list(set(recipient for recipient in recipients if recipient))

# check_send_message:
# Returns the id of the sent message.  Has same argspec as check_message.
def check_send_message(sender, client, message_type_name, message_to,
                       subject_name, message_content, realm=None, forged=False,
                       forged_timestamp=None, forwarder_user_profile=None, local_id=None,
                       sender_queue_id=None):
    # type: (UserProfile, Client, Text, Sequence[Text], Optional[Text], Text, Optional[Realm], bool, Optional[float], Optional[UserProfile], Optional[Text], Optional[Text]) -> int

    addressee = Addressee.legacy_build(
        sender,
        message_type_name,
        message_to,
        subject_name)

    message = check_message(sender, client, addressee,
                            message_content, realm, forged, forged_timestamp,
                            forwarder_user_profile, local_id, sender_queue_id)
    return do_send_messages([message])[0]

def check_stream_name(stream_name):
    # type: (Text) -> None
    if stream_name.strip() == "":
        raise JsonableError(_("Invalid stream name '%s'" % (stream_name)))
    if len(stream_name) > Stream.MAX_NAME_LENGTH:
        raise JsonableError(_("Stream name too long (limit: %s characters)" % (Stream.MAX_NAME_LENGTH)))
    for i in stream_name:
        if ord(i) == 0:
            raise JsonableError(_("Stream name '%s' contains NULL (0x00) characters." % (stream_name)))

def send_pm_if_empty_stream(sender, stream, stream_name, realm):
    # type: (UserProfile, Optional[Stream], Text, Realm) -> None
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
        num_subscribers = stream.num_subscribers()
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
def check_message(sender, client, addressee,
                  message_content_raw, realm=None, forged=False,
                  forged_timestamp=None, forwarder_user_profile=None, local_id=None,
                  sender_queue_id=None):
    # type: (UserProfile, Client, Addressee, Text, Optional[Realm], bool, Optional[float], Optional[UserProfile], Optional[Text], Optional[Text]) -> Dict[str, Any]
    stream = None

    message_content = message_content_raw.rstrip()
    if len(message_content) == 0:
        raise JsonableError(_("Message must not be empty"))
    message_content = truncate_body(message_content)

    if realm is None:
        realm = sender.realm

    if addressee.is_stream():
        stream_name = addressee.stream_name()
        if stream_name is None:
            if sender.default_sending_stream:
                # Use the users default stream
                stream_name = sender.default_sending_stream.name
            else:
                raise JsonableError(_('Missing stream'))

        stream_name = stream_name.strip()
        check_stream_name(stream_name)

        subject_name = addressee.topic()
        if subject_name is None:
            raise JsonableError(_("Missing topic"))
        subject = subject_name.strip()
        if subject == "":
            raise JsonableError(_("Topic can't be empty"))
        subject = truncate_topic(subject)

        try:
            stream = get_stream(stream_name, realm)

            send_pm_if_empty_stream(sender, stream, stream_name, realm)

        except Stream.DoesNotExist:
            send_pm_if_empty_stream(sender, None, stream_name, realm)
            raise JsonableError(_("Stream '%(stream_name)s' does not exist") % {'stream_name': escape(stream_name)})
        recipient = get_recipient(Recipient.STREAM, stream.id)

        if not stream.invite_only:
            # This is a public stream
            pass
        elif subscribed_to_stream(sender, stream):
            # Or it is private, but your are subscribed
            pass
        elif sender.is_api_super_user or (forwarder_user_profile is not None and
                                          forwarder_user_profile.is_api_super_user):
            # Or this request is being done on behalf of a super user
            pass
        elif sender.is_bot and (sender.bot_owner is not None and
                                subscribed_to_stream(sender.bot_owner, stream)):
            # Or you're a bot and your owner is subscribed.
            pass
        elif sender.email == settings.WELCOME_BOT:
            # The welcome bot welcomes folks to the stream.
            pass
        else:
            # All other cases are an error.
            raise JsonableError(_("Not authorized to send to stream '%s'") % (stream.name,))

    elif addressee.is_private():
        user_profiles = addressee.user_profiles()

        if user_profiles is None or len(user_profiles) == 0:
            raise JsonableError(_("Message must have recipients"))

        mirror_message = client and client.name in ["zephyr_mirror", "irc_mirror", "jabber_mirror", "JabberMirror"]
        not_forged_mirror_message = mirror_message and not forged
        try:
            recipient = recipient_for_user_profiles(user_profiles, not_forged_mirror_message,
                                                    forwarder_user_profile, sender)
        except ValidationError as e:
            assert isinstance(e.messages[0], six.string_types)
            raise JsonableError(e.messages[0])
    else:
        raise JsonableError(_("Invalid message type"))

    message = Message()
    message.sender = sender
    message.content = message_content
    message.recipient = recipient
    if addressee.is_stream():
        message.subject = subject
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

def _internal_prep_message(realm, sender, addressee, content):
    # type: (Realm, UserProfile, Addressee, Text) -> Optional[Dict[str, Any]]
    """
    Create a message object and checks it, but doesn't send it or save it to the database.
    The internal function that calls this can therefore batch send a bunch of created
    messages together as one database query.
    Call do_send_messages with a list of the return values of this method.
    """
    if len(content) > MAX_MESSAGE_LENGTH:
        content = content[0:3900] + "\n\n[message was too long and has been truncated]"

    if realm is None:
        raise RuntimeError("None is not a valid realm for internal_prep_message!")

    if addressee.is_stream():
        stream, _ = create_stream_if_needed(realm, addressee.stream_name())

    try:
        return check_message(sender, get_client("Internal"), addressee,
                             content, realm=realm)
    except JsonableError as e:
        logging.error(u"Error queueing internal message by %s: %s" % (sender.email, e))

    return None

def internal_prep_message(realm, sender_email, recipient_type_name, recipients,
                          subject, content):
    # type: (Realm, Text, str, Text, Text, Text) -> Optional[Dict[str, Any]]
    """
    See _internal_prep_message for details of how this works.
    """
    sender = get_system_bot(sender_email)
    parsed_recipients = extract_recipients(recipients)

    addressee = Addressee.legacy_build(
        sender,
        recipient_type_name,
        parsed_recipients,
        subject,
        realm=realm)

    return _internal_prep_message(
        realm=realm,
        sender=sender,
        addressee=addressee,
        content=content,
    )

def internal_prep_stream_message(realm, sender, stream_name, topic, content):
    # type: (Realm, UserProfile, Text, Text, Text) -> Optional[Dict[str, Any]]
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

def internal_prep_private_message(realm, sender, recipient_user, content):
    # type: (Realm, UserProfile, UserProfile, Text) -> Optional[Dict[str, Any]]
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

def internal_send_message(realm, sender_email, recipient_type_name, recipients,
                          subject, content):
    # type: (Realm, Text, str, Text, Text, Text) -> None
    msg = internal_prep_message(realm, sender_email, recipient_type_name, recipients,
                                subject, content)

    # internal_prep_message encountered an error
    if msg is None:
        return

    do_send_messages([msg])

def internal_send_private_message(realm, sender, recipient_user, content):
    # type: (Realm, UserProfile, UserProfile, Text) -> None
    message = internal_prep_private_message(realm, sender, recipient_user, content)
    if message is None:
        return
    do_send_messages([message])

def pick_color(user_profile):
    # type: (UserProfile) -> Text
    subs = Subscription.objects.filter(user_profile=user_profile,
                                       active=True,
                                       recipient__type=Recipient.STREAM)
    return pick_color_helper(user_profile, subs)

def pick_color_helper(user_profile, subs):
    # type: (UserProfile, Iterable[Subscription]) -> Text
    # These colors are shared with the palette in subs.js.
    used_colors = [sub.color for sub in subs if sub.active]
    available_colors = [s for s in STREAM_ASSIGNMENT_COLORS if s not in used_colors]

    if available_colors:
        return available_colors[0]
    else:
        return STREAM_ASSIGNMENT_COLORS[len(used_colors) % len(STREAM_ASSIGNMENT_COLORS)]

def validate_user_access_to_subscribers(user_profile, stream):
    # type: (Optional[UserProfile], Stream) -> None
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
        lambda: subscribed_to_stream(cast(UserProfile, user_profile), stream))

def validate_user_access_to_subscribers_helper(user_profile, stream_dict, check_user_subscribed):
    # type: (Optional[UserProfile], Mapping[str, Any], Callable[[], bool]) -> None
    """ Helper for validate_user_access_to_subscribers that doesn't require a full stream object
    * check_user_subscribed is a function that when called with no
      arguments, will report whether the user is subscribed to the stream
    """
    if user_profile is None:
        raise ValidationError("Missing user to validate access for")

    if user_profile.realm_id != stream_dict["realm_id"]:
        raise ValidationError("Requesting user not in given realm")

    if user_profile.realm.is_zephyr_mirror_realm and not stream_dict["invite_only"]:
        raise JsonableError(_("You cannot get subscribers for public streams in this realm"))

    if (stream_dict["invite_only"] and not check_user_subscribed()):
        raise JsonableError(_("Unable to retrieve subscribers for invite-only stream"))

# sub_dict is a dictionary mapping stream_id => whether the user is subscribed to that stream
def bulk_get_subscriber_user_ids(stream_dicts, user_profile, sub_dict, stream_recipient):
    # type: (Iterable[Mapping[str, Any]], UserProfile, Mapping[int, bool], StreamRecipientMap) -> Dict[int, List[int]]
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

def get_subscribers_query(stream, requesting_user):
    # type: (Stream, Optional[UserProfile]) -> QuerySet
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
    subscriptions = Subscription.objects.filter(recipient__type=Recipient.STREAM,
                                                recipient__type_id=stream.id,
                                                user_profile__is_active=True,
                                                active=True)
    return subscriptions

def get_subscribers(stream, requesting_user=None):
    # type: (Stream, Optional[UserProfile]) -> List[UserProfile]
    subscriptions = get_subscribers_query(stream, requesting_user).select_related()
    return [subscription.user_profile for subscription in subscriptions]

def get_subscriber_emails(stream, requesting_user=None):
    # type: (Stream, Optional[UserProfile]) -> List[Text]
    subscriptions_query = get_subscribers_query(stream, requesting_user)
    subscriptions = subscriptions_query.values('user_profile__email')
    return [subscription['user_profile__email'] for subscription in subscriptions]

def maybe_get_subscriber_emails(stream, user_profile):
    # type: (Stream, UserProfile) -> List[Text]
    """ Alternate version of get_subscriber_emails that takes a Stream object only
    (not a name), and simply returns an empty list if unable to get a real
    subscriber list (because we're on the MIT realm). """
    try:
        subscribers = get_subscriber_emails(stream, requesting_user=user_profile)
    except JsonableError:
        subscribers = []
    return subscribers

def notify_subscriptions_added(user_profile, sub_pairs, stream_emails, no_log=False):
    # type: (UserProfile, Iterable[Tuple[Subscription, Stream]], Callable[[Stream], List[Text]], bool) -> None
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
                    subscribers=stream_emails(stream))
               for (subscription, stream) in sub_pairs]
    event = dict(type="subscription", op="add",
                 subscriptions=payload)
    send_event(event, [user_profile.id])

def get_peer_user_ids_for_stream_change(stream, altered_users, subscribed_users):
    # type: (Stream, Iterable[UserProfile], Iterable[UserProfile]) -> Set[int]
    '''
    altered_users is a list of users that we are adding/removing
    subscribed_users is the list of already subscribed users

    Based on stream policy, we notify the correct bystanders, while
    not notifying altered_users (who get subscribers via another event)
    '''

    altered_user_ids = [user.id for user in altered_users]

    if stream.invite_only:
        # PRIVATE STREAMS
        all_subscribed_ids = [user.id for user in subscribed_users]
        return set(all_subscribed_ids) - set(altered_user_ids)

    else:
        # PUBLIC STREAMS
        # We now do "peer_add" or "peer_remove" events even for streams
        # users were never subscribed to, in order for the neversubscribed
        # structure to stay up-to-date.
        return set(active_user_ids(stream.realm_id)) - set(altered_user_ids)

def query_all_subs_by_stream(streams):
    # type: (Iterable[Stream]) -> Dict[int, List[UserProfile]]
    all_subs = Subscription.objects.filter(recipient__type=Recipient.STREAM,
                                           recipient__type_id__in=[stream.id for stream in streams],
                                           user_profile__is_active=True,
                                           active=True).select_related('recipient', 'user_profile')

    all_subs_by_stream = defaultdict(list)  # type: Dict[int, List[UserProfile]]
    for sub in all_subs:
        all_subs_by_stream[sub.recipient.type_id].append(sub.user_profile)
    return all_subs_by_stream

def bulk_add_subscriptions(streams, users, from_stream_creation=False, acting_user=None):
    # type: (Iterable[Stream], Iterable[UserProfile], bool, Optional[UserProfile]) -> Tuple[List[Tuple[UserProfile, Stream]], List[Tuple[UserProfile, Stream]]]
    recipients_map = bulk_get_recipients(Recipient.STREAM, [stream.id for stream in streams])  # type: Mapping[int, Recipient]
    recipients = [recipient.id for recipient in recipients_map.values()]  # type: List[int]

    stream_map = {}  # type: Dict[int, Stream]
    for stream in streams:
        stream_map[recipients_map[stream.id].id] = stream

    subs_by_user = defaultdict(list)  # type: Dict[int, List[Subscription]]
    all_subs_query = Subscription.objects.select_related("user_profile")
    for sub in all_subs_query.filter(user_profile__in=users,
                                     recipient__type=Recipient.STREAM):
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
        Subscription.objects.filter(id__in=[sub.id for (sub, stream) in subs_to_activate]).update(active=True)
        occupied_streams_after = list(get_occupied_streams(user_profile.realm))

    # Log Subscription Activities in RealmAuditLog
    event_time = timezone_now()
    event_last_message_id = Message.objects.aggregate(Max('id'))['id__max']
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
    all_subs_by_stream = query_all_subs_by_stream(streams=streams)

    def fetch_stream_subscriber_emails(stream):
        # type: (Stream) -> List[Text]
        if stream.realm.is_zephyr_mirror_realm and not stream.invite_only:
            return []
        users = all_subs_by_stream[stream.id]
        return [u.email for u in users]

    sub_tuples_by_user = defaultdict(list)  # type: Dict[int, List[Tuple[Subscription, Stream]]]
    new_streams = set()  # type: Set[Tuple[int, int]]
    for (sub, stream) in subs_to_add + subs_to_activate:
        sub_tuples_by_user[sub.user_profile.id].append((sub, stream))
        new_streams.add((sub.user_profile.id, stream.id))

    # We now send several types of events to notify browsers.  The
    # first batch is notifications to users on invite-only streams
    # that the stream exists.
    for stream in streams:
        new_users = [user for user in users if (user.id, stream.id) in new_streams]

        # Users newly added to invite-only streams need a `create`
        # notification, since they didn't have the invite-only stream
        # in their browser yet.
        if not stream.is_public():
            send_stream_creation_event(stream, [user.id for user in new_users])

    # The second batch is events for the users themselves that they
    # were subscribed to the new streams.
    for user_profile in users:
        if len(sub_tuples_by_user[user_profile.id]) == 0:
            continue
        sub_pairs = sub_tuples_by_user[user_profile.id]
        notify_subscriptions_added(user_profile, sub_pairs, fetch_stream_subscriber_emails)

    # The second batch is events for other users who are tracking the
    # subscribers lists of streams in their browser; everyone for
    # public streams and only existing subscribers for private streams.
    for stream in streams:
        if stream.realm.is_zephyr_mirror_realm and not stream.invite_only:
            continue

        new_users = [user for user in users if (user.id, stream.id) in new_streams]

        peer_user_ids = get_peer_user_ids_for_stream_change(
            stream=stream,
            altered_users=new_users,
            subscribed_users=all_subs_by_stream[stream.id]
        )

        if peer_user_ids:
            for added_user in new_users:
                event = dict(type="subscription", op="peer_add",
                             subscriptions=[stream.name],
                             user_id=added_user.id)
                send_event(event, peer_user_ids)

    return ([(user_profile, stream) for (user_profile, recipient_id, stream) in new_subs] +
            [(sub.user_profile, stream) for (sub, stream) in subs_to_activate],
            already_subscribed)

def notify_subscriptions_removed(user_profile, streams, no_log=False):
    # type: (UserProfile, Iterable[Stream], bool) -> None
    if not no_log:
        log_event({'type': 'subscription_removed',
                   'user': user_profile.email,
                   'names': [stream.name for stream in streams],
                   'realm': user_profile.realm.string_id})

    payload = [dict(name=stream.name, stream_id=stream.id) for stream in streams]
    event = dict(type="subscription", op="remove",
                 subscriptions=payload)
    send_event(event, [user_profile.id])

def bulk_remove_subscriptions(users, streams, acting_user=None):
    # type: (Iterable[UserProfile], Iterable[Stream], Optional[UserProfile]) -> Tuple[List[Tuple[UserProfile, Stream]], List[Tuple[UserProfile, Stream]]]

    recipients_map = bulk_get_recipients(Recipient.STREAM,
                                         [stream.id for stream in streams])  # type: Mapping[int, Recipient]
    stream_map = {}  # type: Dict[int, Stream]
    for stream in streams:
        stream_map[recipients_map[stream.id].id] = stream

    subs_by_user = dict((user_profile.id, []) for user_profile in users)  # type: Dict[int, List[Subscription]]
    for sub in Subscription.objects.select_related("user_profile").filter(user_profile__in=users,
                                                                          recipient__in=list(recipients_map.values()),
                                                                          active=True):
        subs_by_user[sub.user_profile_id].append(sub)

    subs_to_deactivate = []  # type: List[Tuple[Subscription, Stream]]
    not_subscribed = []  # type: List[Tuple[UserProfile, Stream]]
    for user_profile in users:
        recipients_to_unsub = set([recipient.id for recipient in recipients_map.values()])
        for sub in subs_by_user[user_profile.id]:
            recipients_to_unsub.remove(sub.recipient_id)
            subs_to_deactivate.append((sub, stream_map[sub.recipient_id]))
        for recipient_id in recipients_to_unsub:
            not_subscribed.append((user_profile, stream_map[recipient_id]))

    # TODO: XXX: This transaction really needs to be done at the serializeable
    # transaction isolation level.
    with transaction.atomic():
        occupied_streams_before = list(get_occupied_streams(user_profile.realm))
        Subscription.objects.filter(id__in=[sub.id for (sub, stream_name) in
                                            subs_to_deactivate]).update(active=False)
        occupied_streams_after = list(get_occupied_streams(user_profile.realm))

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
        send_event(event, active_user_ids(user_profile.realm_id))
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

    all_subs_by_stream = query_all_subs_by_stream(streams=streams)

    for stream in streams:
        if stream.realm.is_zephyr_mirror_realm and not stream.invite_only:
            continue

        altered_users = altered_user_dict[stream.id]

        peer_user_ids = get_peer_user_ids_for_stream_change(
            stream=stream,
            altered_users=altered_users,
            subscribed_users=all_subs_by_stream[stream.id]
        )

        if peer_user_ids:
            for removed_user in altered_users:
                event = dict(type="subscription",
                             op="peer_remove",
                             subscriptions=[stream.name],
                             user_id=removed_user.id)
                send_event(event, peer_user_ids)

    return ([(sub.user_profile, stream) for (sub, stream) in subs_to_deactivate],
            not_subscribed)

def log_subscription_property_change(user_email, stream_name, property, value):
    # type: (Text, Text, Text, Any) -> None
    event = {'type': 'subscription_property',
             'property': property,
             'user': user_email,
             'stream_name': stream_name,
             'value': value}
    log_event(event)

def do_change_subscription_property(user_profile, sub, stream,
                                    property_name, value):
    # type: (UserProfile, Subscription, Stream, Text, Any) -> None
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

def do_activate_user(user_profile):
    # type: (UserProfile) -> None
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

def do_reactivate_user(user_profile, acting_user=None):
    # type: (UserProfile, Optional[UserProfile]) -> None
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

def do_change_password(user_profile, password, commit=True,
                       hashed_password=False):
    # type: (UserProfile, Text, bool, bool) -> None
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

def do_change_full_name(user_profile, full_name, acting_user):
    # type: (UserProfile, Text, UserProfile) -> None
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
                   bot_owner_userids(user_profile))

def do_change_bot_owner(user_profile, bot_owner, acting_user):
    # type: (UserProfile, UserProfile, UserProfile) -> None
    user_profile.bot_owner = bot_owner
    user_profile.save()
    event_time = timezone_now()
    RealmAuditLog.objects.create(realm=user_profile.realm, acting_user=acting_user,
                                 modified_user=user_profile, event_type='bot_owner_changed',
                                 event_time=event_time)
    send_event(dict(type='realm_bot',
                    op='update',
                    bot=dict(email=user_profile.email,
                             user_id=user_profile.id,
                             owner_id=user_profile.bot_owner.id,
                             )),
               bot_owner_userids(user_profile))

def do_change_tos_version(user_profile, tos_version):
    # type: (UserProfile, Text) -> None
    user_profile.tos_version = tos_version
    user_profile.save(update_fields=["tos_version"])
    event_time = timezone_now()
    RealmAuditLog.objects.create(realm=user_profile.realm, acting_user=user_profile,
                                 modified_user=user_profile, event_type='user_tos_version_changed',
                                 event_time=event_time)

def do_regenerate_api_key(user_profile, acting_user):
    # type: (UserProfile, UserProfile) -> None
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
                   bot_owner_userids(user_profile))

def do_change_avatar_fields(user_profile, avatar_source):
    # type: (UserProfile, Text) -> None
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
                   bot_owner_userids(user_profile))

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


def do_change_icon_source(realm, icon_source, log=True):
    # type: (Realm, Text, bool) -> None
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

def _default_stream_permision_check(user_profile, stream):
    # type: (UserProfile, Optional[Stream]) -> None
    # Any user can have a None default stream
    if stream is not None:
        if user_profile.is_bot:
            user = user_profile.bot_owner
        else:
            user = user_profile
        if stream.invite_only and (user is None or not subscribed_to_stream(user, stream)):
            raise JsonableError(_('Insufficient permission'))

def do_change_default_sending_stream(user_profile, stream, log=True):
    # type: (UserProfile, Optional[Stream], bool) -> None
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
                   bot_owner_userids(user_profile))

def do_change_default_events_register_stream(user_profile, stream, log=True):
    # type: (UserProfile, Optional[Stream], bool) -> None
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
                   bot_owner_userids(user_profile))

def do_change_default_all_public_streams(user_profile, value, log=True):
    # type: (UserProfile, bool, bool) -> None
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
                   bot_owner_userids(user_profile))

def do_change_is_admin(user_profile, value, permission='administer'):
    # type: (UserProfile, bool, str) -> None
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

def do_change_bot_type(user_profile, value):
    # type: (UserProfile, int) -> None
    user_profile.bot_type = value
    user_profile.save(update_fields=["bot_type"])

def do_change_stream_invite_only(stream, invite_only):
    # type: (Stream, bool) -> None
    stream.invite_only = invite_only
    stream.save(update_fields=['invite_only'])

def do_rename_stream(stream, new_name, log=True):
    # type: (Stream, Text, bool) -> Dict[str, Text]
    old_name = stream.name
    stream.name = new_name
    stream.save(update_fields=["name"])

    if log:
        log_event({'type': 'stream_name_change',
                   'realm': stream.realm.string_id,
                   'new_name': new_name})

    recipient = get_recipient(Recipient.STREAM, stream.id)
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
        to_dict_cache_key_id(message.id, True) for message in messages)
    cache_delete_many(
        to_dict_cache_key_id(message.id, False) for message in messages)
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

def do_change_stream_description(stream, new_description):
    # type: (Stream, Text) -> None
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

def do_create_realm(string_id, name, restricted_to_domain=None,
                    invite_required=None, org_type=None):
    # type: (Text, Text, Optional[bool], Optional[bool], Optional[int]) -> Realm
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
    notifications_stream, _ = create_stream_if_needed(realm, Realm.DEFAULT_NOTIFICATION_STREAM_NAME)
    realm.notifications_stream = notifications_stream
    realm.save(update_fields=['notifications_stream'])

    # Log the event
    log_event({"type": "realm_created",
               "string_id": string_id,
               "restricted_to_domain": restricted_to_domain,
               "invite_required": invite_required,
               "org_type": org_type})

    # Send a notification to the admin realm (if configured)
    if settings.NEW_USER_BOT is not None:
        signup_message = "Signups enabled"
        admin_realm = get_system_bot(settings.NEW_USER_BOT).realm
        internal_send_message(admin_realm, settings.NEW_USER_BOT, "stream",
                              "signups", string_id, signup_message)
    return realm

def do_change_notification_settings(user_profile, name, value, log=True):
    # type: (UserProfile, str, bool, bool) -> None
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

def do_change_autoscroll_forever(user_profile, autoscroll_forever, log=True):
    # type: (UserProfile, bool, bool) -> None
    user_profile.autoscroll_forever = autoscroll_forever
    user_profile.save(update_fields=["autoscroll_forever"])

    if log:
        log_event({'type': 'autoscroll_forever',
                   'user': user_profile.email,
                   'autoscroll_forever': autoscroll_forever})

def do_change_enter_sends(user_profile, enter_sends):
    # type: (UserProfile, bool) -> None
    user_profile.enter_sends = enter_sends
    user_profile.save(update_fields=["enter_sends"])

def do_change_default_desktop_notifications(user_profile, default_desktop_notifications):
    # type: (UserProfile, bool) -> None
    user_profile.default_desktop_notifications = default_desktop_notifications
    user_profile.save(update_fields=["default_desktop_notifications"])

def do_set_user_display_setting(user_profile, setting_name, setting_value):
    # type: (UserProfile, str, Union[bool, Text]) -> None
    property_type = UserProfile.property_types[setting_name]
    assert isinstance(setting_value, property_type)
    setattr(user_profile, setting_name, setting_value)
    user_profile.save(update_fields=[setting_name])
    event = {'type': 'update_display_settings',
             'user': user_profile.email,
             'setting_name': setting_name,
             'setting': setting_value}
    send_event(event, [user_profile.id])

    # Updates to the timezone display setting are sent to all users
    if setting_name == "timezone":
        payload = dict(email=user_profile.email,
                       user_id=user_profile.id,
                       timezone=user_profile.timezone)
        send_event(dict(type='realm_user', op='update', person=payload),
                   active_user_ids(user_profile.realm_id))

def set_default_streams(realm, stream_dict):
    # type: (Realm, Dict[Text, Dict[Text, Any]]) -> None
    DefaultStream.objects.filter(realm=realm).delete()
    stream_names = []
    for name, options in stream_dict.items():
        stream_names.append(name)
        stream, _ = create_stream_if_needed(realm,
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

def notify_default_streams(realm_id):
    # type: (int) -> None
    event = dict(
        type="default_streams",
        default_streams=streams_to_dicts_sorted(get_default_streams_for_realm(realm_id))
    )
    send_event(event, active_user_ids(realm_id))

def do_add_default_stream(stream):
    # type: (Stream) -> None
    realm_id = stream.realm_id
    stream_id = stream.id
    if not DefaultStream.objects.filter(realm_id=realm_id, stream_id=stream_id).exists():
        DefaultStream.objects.create(realm_id=realm_id, stream_id=stream_id)
        notify_default_streams(realm_id)

def do_remove_default_stream(stream):
    # type: (Stream) -> None
    realm_id = stream.realm_id
    stream_id = stream.id
    DefaultStream.objects.filter(realm_id=realm_id, stream_id=stream_id).delete()
    notify_default_streams(realm_id)

def get_default_streams_for_realm(realm_id):
    # type: (int) -> List[Stream]
    return [default.stream for default in
            DefaultStream.objects.select_related("stream", "stream__realm").filter(realm_id=realm_id)]

def get_default_subs(user_profile):
    # type: (UserProfile) -> List[Stream]
    # Right now default streams are realm-wide.  This wrapper gives us flexibility
    # to some day further customize how we set up default streams for new users.
    return get_default_streams_for_realm(user_profile.realm_id)

# returns default streams in json serializeable format
def streams_to_dicts_sorted(streams):
    # type: (List[Stream]) -> List[Dict[str, Any]]
    return sorted([stream.to_dict() for stream in streams], key=lambda elt: elt["name"])

def do_update_user_activity_interval(user_profile, log_time):
    # type: (UserProfile, datetime.datetime) -> None
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
def do_update_user_activity(user_profile, client, query, log_time):
    # type: (UserProfile, Client, Text, datetime.datetime) -> None
    (activity, created) = UserActivity.objects.get_or_create(
        user_profile = user_profile,
        client = client,
        query = query,
        defaults={'last_visit': log_time, 'count': 0})

    activity.count += 1
    activity.last_visit = log_time
    activity.save(update_fields=["last_visit", "count"])

def send_presence_changed(user_profile, presence):
    # type: (UserProfile, UserPresence) -> None
    presence_dict = presence.to_dict()
    event = dict(type="presence", email=user_profile.email,
                 server_timestamp=time.time(),
                 presence={presence_dict['client']: presence_dict})
    send_event(event, active_user_ids(user_profile.realm_id))

def consolidate_client(client):
    # type: (Client) -> Client
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
def do_update_user_presence(user_profile, client, log_time, status):
    # type: (UserProfile, Client, datetime.datetime, int) -> None
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

def update_user_activity_interval(user_profile, log_time):
    # type: (UserProfile, datetime.datetime) -> None
    event = {'user_profile_id': user_profile.id,
             'time': datetime_to_timestamp(log_time)}
    queue_json_publish("user_activity_interval", event,
                       lambda e: do_update_user_activity_interval(user_profile, log_time))

def update_user_presence(user_profile, client, log_time, status,
                         new_user_input):
    # type: (UserProfile, Client, datetime.datetime, int, bool) -> None
    event = {'user_profile_id': user_profile.id,
             'status': status,
             'time': datetime_to_timestamp(log_time),
             'client': client.name}

    queue_json_publish("user_presence", event,
                       lambda e: do_update_user_presence(user_profile, client,
                                                         log_time, status))

    if new_user_input:
        update_user_activity_interval(user_profile, log_time)

def do_update_pointer(user_profile, pointer, update_flags=False):
    # type: (UserProfile, int, bool) -> None
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

def do_mark_all_as_read(user_profile):
    # type: (UserProfile) -> int
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

def do_mark_stream_messages_as_read(user_profile, stream, topic_name=None):
    # type: (UserProfile, Optional[Stream], Optional[Text]) -> int
    log_statsd_event('mark_stream_as_read')

    msgs = UserMessage.objects.filter(
        user_profile=user_profile
    )

    recipient = get_recipient(Recipient.STREAM, stream.id)
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

def do_update_message_flags(user_profile, operation, flag, messages):
    # type: (UserProfile, Text, Text, Optional[Sequence[int]]) -> int
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

def subscribed_to_stream(user_profile, stream):
    # type: (UserProfile, Stream) -> bool
    try:
        if Subscription.objects.get(user_profile=user_profile,
                                    active=True,
                                    recipient__type=Recipient.STREAM,
                                    recipient__type_id=stream.id):
            return True
        return False
    except Subscription.DoesNotExist:
        return False

def truncate_content(content, max_length, truncation_message):
    # type: (Text, int, Text) -> Text
    if len(content) > max_length:
        content = content[:max_length - len(truncation_message)] + truncation_message
    return content

def truncate_body(body):
    # type: (Text) -> Text
    return truncate_content(body, MAX_MESSAGE_LENGTH, "...")

def truncate_topic(topic):
    # type: (Text) -> Text
    return truncate_content(topic, MAX_SUBJECT_LENGTH, "...")


def update_user_message_flags(message, ums):
    # type: (Message, Iterable[UserMessage]) -> None
    wildcard = message.mentions_wildcard
    mentioned_ids = message.mentions_user_ids
    ids_with_alert_words = message.user_ids_with_alert_words
    changed_ums = set()  # type: Set[UserMessage]

    def update_flag(um, should_set, flag):
        # type: (UserMessage, bool, int) -> None
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

def update_to_dict_cache(changed_messages):
    # type: (List[Message]) -> List[int]
    """Updates the message as stored in the to_dict cache (for serving
    messages)."""
    items_for_remote_cache = {}
    message_ids = []
    for changed_message in changed_messages:
        message_ids.append(changed_message.id)
        items_for_remote_cache[to_dict_cache_key(changed_message, True)] = \
            (MessageDict.to_dict_uncached(changed_message, apply_markdown=True),)
        items_for_remote_cache[to_dict_cache_key(changed_message, False)] = \
            (MessageDict.to_dict_uncached(changed_message, apply_markdown=False),)
    cache_set_many(items_for_remote_cache)
    return message_ids

# We use transaction.atomic to support select_for_update in the attachment codepath.
@transaction.atomic
def do_update_embedded_data(user_profile, message, content, rendered_content):
    # type: (UserProfile, Message, Optional[Text], Optional[Text]) -> None
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

    def user_info(um):
        # type: (UserMessage) -> Dict[str, Any]
        return {
            'id': um.user_profile_id,
            'flags': um.flags_list()
        }
    send_event(event, list(map(user_info, ums)))

# We use transaction.atomic to support select_for_update in the attachment codepath.
@transaction.atomic
def do_update_message(user_profile, message, subject, propagate_mode, content, rendered_content):
    # type: (UserProfile, Message, Optional[Text], str, Optional[Text], Optional[Text]) -> int
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

    # Set first_rendered_content to be the oldest version of the
    # rendered content recorded; which is the current version if the
    # content hasn't been edited before.  Note that because one could
    # have edited just the subject, not every edit history event
    # contains a prev_rendered_content element.
    first_rendered_content = message.rendered_content
    if message.edit_history is not None:
        edit_history = ujson.loads(message.edit_history)
        for old_edit_history_event in edit_history:
            if 'prev_rendered_content' in old_edit_history_event:
                first_rendered_content = old_edit_history_event['prev_rendered_content']

    ums = UserMessage.objects.filter(message=message.id)

    if content is not None:
        update_user_message_flags(message, ums)

        # We are turning off diff highlighting everywhere until ticket #1532 is addressed.
        if False:
            # Don't highlight message edit diffs on prod
            rendered_content = highlight_html_differences(first_rendered_content, rendered_content)

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

        prev_content = edit_history_event['prev_content']
        if Message.content_has_attachment(prev_content) or Message.content_has_attachment(message.content):
            check_attachment_reference_change(prev_content, message)

    if subject is not None:
        orig_subject = message.topic_name()
        subject = truncate_topic(subject)
        event["orig_subject"] = orig_subject
        event["propagate_mode"] = propagate_mode
        message.subject = subject
        event["stream_id"] = message.recipient.type_id
        event["subject"] = subject
        event['subject_links'] = bugdown.subject_links(message.sender.realm_id, subject)
        edit_history_event["prev_subject"] = orig_subject

        if propagate_mode in ["change_later", "change_all"]:
            propagate_query = Q(recipient = message.recipient, subject = orig_subject)
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
            messages.update(subject=subject)

            for m in messages_list:
                # The cached ORM object is not changed by messages.update()
                # and the remote cache update requires the new value
                m.subject = subject

            changed_messages += messages_list

    message.last_edit_time = timezone_now()
    assert message.last_edit_time is not None  # assert needed because stubs for django are missing
    event['edit_timestamp'] = datetime_to_timestamp(message.last_edit_time)
    edit_history_event['timestamp'] = event['edit_timestamp']
    if message.edit_history is not None:
        edit_history.insert(0, edit_history_event)
    else:
        edit_history = [edit_history_event]
    message.edit_history = ujson.dumps(edit_history)

    message.save(update_fields=["subject", "content", "rendered_content",
                                "rendered_content_version", "last_edit_time",
                                "edit_history"])

    event['message_ids'] = update_to_dict_cache(changed_messages)

    def user_info(um):
        # type: (UserMessage) -> Dict[str, Any]
        return {
            'id': um.user_profile_id,
            'flags': um.flags_list()
        }
    send_event(event, list(map(user_info, ums)))
    return len(changed_messages)


def do_delete_message(user_profile, message):
    # type: (UserProfile, Message) -> None
    event = {
        'type': 'delete_message',
        'sender': user_profile.email,
        'message_id': message.id}  # type: Dict[str, Any]
    ums = [{'id': um.user_profile_id} for um in
           UserMessage.objects.filter(message=message.id)]
    move_message_to_archive(message.id)
    send_event(event, ums)


def encode_email_address(stream):
    # type: (Stream) -> Text
    return encode_email_address_helper(stream.name, stream.email_token)

def encode_email_address_helper(name, email_token):
    # type: (Text, Text) -> Text
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

def get_email_gateway_message_string_from_address(address):
    # type: (Text) -> Optional[Text]
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

def decode_email_address(email):
    # type: (Text) -> Optional[Tuple[Text, Text]]
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
def gather_subscriptions_helper(user_profile, include_subscribers=True):
    # type: (UserProfile, bool) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]
    sub_dicts = Subscription.objects.filter(
        user_profile    = user_profile,
        recipient__type = Recipient.STREAM
    ).values(
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
    for sub in sub_dicts:
        sub['stream_id'] = stream_recipient.stream_id_for(sub['recipient_id'])
        stream_ids.add(sub['stream_id'])

    all_streams = get_active_streams(user_profile.realm).select_related(
        "realm").values("id", "name", "invite_only", "realm_id",
                        "email_token", "description")

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
        # and this user isn't on it anymore.
        if stream["invite_only"] and not sub["active"]:
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
                           'description': stream['description']}
            if is_public:
                subscribers = subscriber_map[stream["id"]]
                if subscribers is not None:
                    stream_dict['subscribers'] = subscribers
            never_subscribed.append(stream_dict)

    return (sorted(subscribed, key=lambda x: x['name']),
            sorted(unsubscribed, key=lambda x: x['name']),
            sorted(never_subscribed, key=lambda x: x['name']))

def gather_subscriptions(user_profile):
    # type: (UserProfile) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]
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

def get_userids_for_missed_messages(realm, sender_id, message_type, active_user_ids, user_flags):
    # type: (Realm, int, str, Set[int], Dict[int, List[str]]) -> List[int]
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

    if not user_ids:
        return []

    # 140 seconds is consistent with presence.js:OFFLINE_THRESHOLD_SECS
    recent = timezone_now() - datetime.timedelta(seconds=140)
    rows = UserPresence.objects.filter(
        user_profile_id__in=user_ids,
        timestamp__gte=recent
    ).distinct('user_profile_id').values('user_profile_id')
    active_user_ids = {row['user_profile_id'] for row in rows}
    idle_user_ids = user_ids - active_user_ids
    return sorted(list(idle_user_ids))

def get_status_dict(requesting_user_profile):
    # type: (UserProfile) -> Dict[Text, Dict[Text, Dict[str, Any]]]
    if requesting_user_profile.realm.presence_disabled:
        # Return an empty dict if presence is disabled in this realm
        return defaultdict(dict)

    return UserPresence.get_status_dict_by_realm(requesting_user_profile.realm_id)

def get_cross_realm_dicts():
    # type: () -> List[Dict[str, Any]]
    users = [get_system_bot(email) for email in get_cross_realm_emails()]
    return [{'email': user.email,
             'user_id': user.id,
             'is_admin': user.is_realm_admin,
             'is_bot': user.is_bot,
             'full_name': user.full_name}
            for user in users]

def do_send_confirmation_email(invitee, referrer, body):
    # type: (PreregistrationUser, UserProfile, Optional[str]) -> None
    """
    Send the confirmation/welcome e-mail to an invited user.

    `invitee` is a PreregistrationUser.
    `referrer` is a UserProfile.
    """
    activation_url = create_confirmation_link(invitee, referrer.realm.host, Confirmation.INVITATION)
    context = {'referrer': referrer, 'custom_body': body, 'activate_url': activation_url,
               'referrer_realm_name': referrer.realm.name}
    from_name = u"%s (via Zulip)" % (referrer.full_name,)
    send_email('zerver/emails/invitation', to_email=invitee.email, from_name=from_name,
               from_address=FromAddress.NOREPLY, context=context)

def user_email_is_unique(email):
    # type: (Text) -> None
    try:
        get_user_profile_by_email(email)
        raise ValidationError(u'%s already has an account' % (email,))
    except UserProfile.DoesNotExist:
        pass

def validate_email_for_realm(target_realm, email):
    # type: (Optional[Realm], Text) -> None
    try:
        existing_user_profile = get_user_profile_by_email(email)
    except UserProfile.DoesNotExist:
        existing_user_profile = None

    if existing_user_profile is not None and existing_user_profile.is_mirror_dummy:
        # Mirror dummy users to be activated must be inactive
        if existing_user_profile.is_active:
            raise ValidationError(u'%s already has an account' % (email,))
    elif existing_user_profile:
        # Other users should not already exist at all.
        raise ValidationError(u'%s already has an account' % (email,))

def validate_email(user_profile, email):
    # type: (UserProfile, Text) -> Tuple[Optional[str], Optional[str]]
    try:
        validators.validate_email(email)
    except ValidationError:
        return _("Invalid address."), None

    if not email_allowed_for_realm(email, user_profile.realm):
        return _("Outside your domain."), None

    try:
        validate_email_for_realm(user_profile.realm, email)
    except ValidationError:
        return None, _("Already has an account.")

    return None, None

class InvitationError(JsonableError):
    code = ErrorCode.INVITATION_FAILED
    data_fields = ['errors', 'sent_invitations']

    def __init__(self, msg, errors, sent_invitations):
        # type: (Text, List[Tuple[Text, str]], bool) -> None
        self._msg = msg  # type: Text
        self.errors = errors  # type: List[Tuple[Text, str]]
        self.sent_invitations = sent_invitations  # type: bool

def do_invite_users(user_profile, invitee_emails, streams, body=None):
    # type: (UserProfile, SizedTextIterable, Iterable[Stream], Optional[str]) -> None
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

    # Now that we are past all the possible errors, we actually create
    # the PreregistrationUser objects and trigger the email invitations.
    for email in validated_emails:
        # The logged in user is the referrer.
        prereg_user = PreregistrationUser(email=email, referred_by=user_profile)

        prereg_user.save()
        stream_ids = [stream.id for stream in streams]
        prereg_user.streams.set(stream_ids)

        event = {"email": prereg_user.email, "referrer_id": user_profile.id, "email_body": body}
        queue_json_publish("invites", event,
                           lambda event: do_send_confirmation_email(prereg_user, user_profile, body))

    if skipped:
        raise InvitationError(_("Some of those addresses are already using Zulip, "
                                "so we didn't send them an invitation. We did send "
                                "invitations to everyone else!"),
                              skipped, sent_invitations=True)

def notify_realm_emoji(realm):
    # type: (Realm) -> None
    event = dict(type="realm_emoji", op="update",
                 realm_emoji=realm.get_emoji())
    send_event(event, active_user_ids(realm.id))

def check_add_realm_emoji(realm, name, file_name, author=None):
    # type: (Realm, Text, Text, Optional[UserProfile]) -> None
    emoji = RealmEmoji(realm=realm, name=name, file_name=file_name, author=author)
    emoji.full_clean()
    emoji.save()
    notify_realm_emoji(realm)

def do_remove_realm_emoji(realm, name):
    # type: (Realm, Text) -> None
    emoji = RealmEmoji.objects.get(realm=realm, name=name)
    emoji.deactivated = True
    emoji.save(update_fields=['deactivated'])
    notify_realm_emoji(realm)

def notify_alert_words(user_profile, words):
    # type: (UserProfile, Iterable[Text]) -> None
    event = dict(type="alert_words", alert_words=words)
    send_event(event, [user_profile.id])

def do_add_alert_words(user_profile, alert_words):
    # type: (UserProfile, Iterable[Text]) -> None
    words = add_user_alert_words(user_profile, alert_words)
    notify_alert_words(user_profile, words)

def do_remove_alert_words(user_profile, alert_words):
    # type: (UserProfile, Iterable[Text]) -> None
    words = remove_user_alert_words(user_profile, alert_words)
    notify_alert_words(user_profile, words)

def do_set_alert_words(user_profile, alert_words):
    # type: (UserProfile, List[Text]) -> None
    set_user_alert_words(user_profile, alert_words)
    notify_alert_words(user_profile, alert_words)

def do_mute_topic(user_profile, stream, recipient, topic):
    # type: (UserProfile, Stream, Recipient, str) -> None
    add_topic_mute(user_profile, stream.id, recipient.id, topic)
    event = dict(type="muted_topics", muted_topics=get_topic_mutes(user_profile))
    send_event(event, [user_profile.id])

def do_unmute_topic(user_profile, stream, topic):
    # type: (UserProfile, Stream, str) -> None
    remove_topic_mute(user_profile, stream.id, topic)
    event = dict(type="muted_topics", muted_topics=get_topic_mutes(user_profile))
    send_event(event, [user_profile.id])

def do_mark_hotspot_as_read(user, hotspot):
    # type: (UserProfile, str) -> None
    UserHotspot.objects.get_or_create(user=user, hotspot=hotspot)
    event = dict(type="hotspots", hotspots=get_next_hotspots(user))
    send_event(event, [user.id])

def notify_realm_filters(realm):
    # type: (Realm) -> None
    realm_filters = realm_filters_for_realm(realm.id)
    event = dict(type="realm_filters", realm_filters=realm_filters)
    send_event(event, active_user_ids(realm.id))

# NOTE: Regexes must be simple enough that they can be easily translated to JavaScript
# RegExp syntax. In addition to JS-compatible syntax, the following features are available:
#   * Named groups will be converted to numbered groups automatically
#   * Inline-regex flags will be stripped, and where possible translated to RegExp-wide flags
def do_add_realm_filter(realm, pattern, url_format_string):
    # type: (Realm, Text, Text) -> int
    pattern = pattern.strip()
    url_format_string = url_format_string.strip()
    realm_filter = RealmFilter(
        realm=realm, pattern=pattern,
        url_format_string=url_format_string)
    realm_filter.full_clean()
    realm_filter.save()
    notify_realm_filters(realm)

    return realm_filter.id

def do_remove_realm_filter(realm, pattern=None, id=None):
    # type: (Realm, Optional[Text], Optional[int]) -> None
    if pattern is not None:
        RealmFilter.objects.get(realm=realm, pattern=pattern).delete()
    else:
        RealmFilter.objects.get(realm=realm, pk=id).delete()
    notify_realm_filters(realm)

def get_emails_from_user_ids(user_ids):
    # type: (Sequence[int]) -> Dict[int, Text]
    # We may eventually use memcached to speed this up, but the DB is fast.
    return UserProfile.emails_from_ids(user_ids)

def do_add_realm_domain(realm, domain, allow_subdomains):
    # type: (Realm, Text, bool) -> (RealmDomain)
    realm_domain = RealmDomain.objects.create(realm=realm, domain=domain,
                                              allow_subdomains=allow_subdomains)
    event = dict(type="realm_domains", op="add",
                 realm_domain=dict(domain=realm_domain.domain,
                                   allow_subdomains=realm_domain.allow_subdomains))
    send_event(event, active_user_ids(realm.id))
    return realm_domain

def do_change_realm_domain(realm_domain, allow_subdomains):
    # type: (RealmDomain, bool) -> None
    realm_domain.allow_subdomains = allow_subdomains
    realm_domain.save(update_fields=['allow_subdomains'])
    event = dict(type="realm_domains", op="change",
                 realm_domain=dict(domain=realm_domain.domain,
                                   allow_subdomains=realm_domain.allow_subdomains))
    send_event(event, active_user_ids(realm_domain.realm_id))

def do_remove_realm_domain(realm_domain):
    # type: (RealmDomain) -> None
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

def get_occupied_streams(realm):
    # type: (Realm) -> QuerySet
    # TODO: Make a generic stub for QuerySet
    """ Get streams with subscribers """
    subs_filter = Subscription.objects.filter(active=True, user_profile__realm=realm,
                                              user_profile__is_active=True).values('recipient_id')
    stream_ids = Recipient.objects.filter(
        type=Recipient.STREAM, id__in=subs_filter).values('type_id')

    return Stream.objects.filter(id__in=stream_ids, realm=realm, deactivated=False)

def do_get_streams(user_profile, include_public=True, include_subscribed=True,
                   include_all_active=False, include_default=False):
    # type: (UserProfile, bool, bool, bool, bool) -> List[Dict[str, Any]]
    if include_all_active and not user_profile.is_api_super_user:
        raise JsonableError(_("User not authorized for this query"))

    # Listing public streams are disabled for Zephyr mirroring realms.
    include_public = include_public and not user_profile.realm.is_zephyr_mirror_realm
    # Start out with all streams in the realm with subscribers
    query = get_occupied_streams(user_profile.realm)

    if not include_all_active:
        user_subs = Subscription.objects.select_related("recipient").filter(
            active=True, user_profile=user_profile,
            recipient__type=Recipient.STREAM)

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

def do_claim_attachments(message):
    # type: (Message) -> None
    attachment_url_list = attachment_url_re.findall(message.content)

    for url in attachment_url_list:
        path_id = attachment_url_to_path_id(url)
        user_profile = message.sender
        is_message_realm_public = False
        if message.recipient.type == Recipient.STREAM:
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

def do_delete_old_unclaimed_attachments(weeks_ago):
    # type: (int) -> None
    old_unclaimed_attachments = get_old_unclaimed_attachments(weeks_ago)

    for attachment in old_unclaimed_attachments:
        delete_message_image(attachment.path_id)
        attachment.delete()

def check_attachment_reference_change(prev_content, message):
    # type: (Text, Message) -> None
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

def notify_realm_custom_profile_fields(realm):
    # type: (Realm) -> None
    fields = custom_profile_fields_for_realm(realm.id)
    event = dict(type="custom_profile_fields",
                 fields=[f.as_dict() for f in fields])
    send_event(event, active_user_ids(realm.id))

def try_add_realm_custom_profile_field(realm, name, field_type):
    # type: (Realm, Text, int) -> CustomProfileField
    field = CustomProfileField(realm=realm, name=name, field_type=field_type)
    field.save()
    notify_realm_custom_profile_fields(realm)
    return field

def do_remove_realm_custom_profile_field(realm, field):
    # type: (Realm, CustomProfileField) -> None
    """
    Deleting a field will also delete the user profile data
    associated with it in CustomProfileFieldValue model.
    """
    field.delete()
    notify_realm_custom_profile_fields(realm)

def try_update_realm_custom_profile_field(realm, field, name):
    # type: (Realm, CustomProfileField, Text) -> None
    field.name = name
    field.save(update_fields=['name'])
    notify_realm_custom_profile_fields(realm)

def do_update_user_custom_profile_data(user_profile, data):
    # type: (UserProfile, List[Dict[str, Union[int, Text]]]) -> None
    with transaction.atomic():
        update_or_create = CustomProfileFieldValue.objects.update_or_create
        for field in data:
            update_or_create(user_profile=user_profile,
                             field_id=field['id'],
                             defaults={'value': field['value']})
