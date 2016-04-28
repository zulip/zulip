from __future__ import absolute_import
from __future__ import print_function
from typing import Tuple

from django.conf import settings
from django.core import validators
from django.contrib.sessions.models import Session
from zerver.lib.cache import flush_user_profile
from zerver.lib.context_managers import lockfile
from zerver.models import Realm, RealmEmoji, Stream, UserProfile, UserActivity, \
    Subscription, Recipient, Message, UserMessage, valid_stream_name, \
    DefaultStream, UserPresence, Referral, PushDeviceToken, MAX_SUBJECT_LENGTH, \
    MAX_MESSAGE_LENGTH, get_client, get_stream, get_recipient, get_huddle, \
    get_user_profile_by_id, PreregistrationUser, get_display_recipient, \
    to_dict_cache_key, get_realm, stringify_message_dict, bulk_get_recipients, \
    email_allowed_for_realm, email_to_username, display_recipient_cache_key, \
    get_user_profile_by_email, get_stream_cache_key, to_dict_cache_key_id, \
    UserActivityInterval, get_active_user_dicts_in_realm, get_active_streams, \
    realm_filters_for_domain, RealmFilter, receives_offline_notifications, \
    ScheduledJob, realm_filters_for_domain, get_active_bot_dicts_in_realm

from zerver.lib.avatar import get_avatar_url, avatar_url

from django.db import transaction, IntegrityError
from django.db.models import F, Q
from django.core.exceptions import ValidationError
from django.utils.importlib import import_module
from django.core.mail import EmailMessage
from django.utils.timezone import now

from confirmation.models import Confirmation
import six
from six.moves import filter
from six.moves import map
from six.moves import range

session_engine = import_module(settings.SESSION_ENGINE)

from zerver.lib.create_user import random_api_key
from zerver.lib.timestamp import timestamp_to_datetime, datetime_to_timestamp
from zerver.lib.cache_helpers import cache_save_message
from zerver.lib.queue import queue_json_publish
from django.utils import timezone
from zerver.lib.create_user import create_user
from zerver.lib import bugdown
from zerver.lib.cache import cache_with_key, cache_set, \
    user_profile_by_email_cache_key, cache_set_many, \
    cache_delete, cache_delete_many, message_cache_key
from zerver.decorator import JsonableError, statsd_increment
from zerver.lib.event_queue import request_event_queue, get_user_events, send_event
from zerver.lib.utils import log_statsd_event, statsd
from zerver.lib.html_diff import highlight_html_differences
from zerver.lib.alert_words import user_alert_words, add_user_alert_words, \
    remove_user_alert_words, set_user_alert_words
from zerver.lib.push_notifications import num_push_devices_for_user, \
     send_apple_push_notification, send_android_push_notification
from zerver.lib.notifications import clear_followup_emails_queue
from zerver.lib.narrow import check_supported_events_narrow_filter
from zerver.lib.session_user import get_session_user

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

# Store an event in the log for re-importing messages
def log_event(event):
    if settings.EVENT_LOG_DIR is None:
        return

    if "timestamp" not in event:
        event["timestamp"] = time.time()

    if not os.path.exists(settings.EVENT_LOG_DIR):
        os.mkdir(settings.EVENT_LOG_DIR)

    template = os.path.join(settings.EVENT_LOG_DIR,
        '%s.' + platform.node()
        + datetime.datetime.now().strftime('.%Y-%m-%d'))

    with lockfile(template % ('lock',)):
        with open(template % ('events',), 'a') as log:
            log.write(ujson.dumps(event) + u'\n')

def active_user_ids(realm):
    return [userdict['id'] for userdict in get_active_user_dicts_in_realm(realm)]

def stream_user_ids(stream):
    subscriptions = Subscription.objects.filter(recipient__type=Recipient.STREAM,
                                                recipient__type_id=stream.id)
    if stream.invite_only:
        subscriptions = subscriptions.filter(active=True)

    return [sub['user_profile_id'] for sub in subscriptions.values('user_profile_id')]

def bot_owner_userids(user_profile):
    is_private_bot = (
        user_profile.default_sending_stream and user_profile.default_sending_stream.invite_only or
        user_profile.default_events_register_stream and user_profile.default_events_register_stream.invite_only)
    if is_private_bot:
        return (user_profile.bot_owner_id,)
    else:
        return active_user_ids(user_profile.realm)

def realm_user_count(realm):
    return UserProfile.objects.filter(realm=realm, is_active=True, is_bot=False).count()

def send_signup_message(sender, signups_stream, user_profile,
                        internal=False, realm=None):
    if internal:
        # When this is done using manage.py vs. the web interface
        internal_blurb = " **INTERNAL SIGNUP** "
    else:
        internal_blurb = " "

    user_count = realm_user_count(user_profile.realm)
    # Send notification to realm notifications stream if it exists
    # Don't send notification for the first user in a realm
    if user_profile.realm.notifications_stream is not None and user_count > 1:
        internal_send_message(sender, "stream",
                              user_profile.realm.notifications_stream.name,
                              "New users", "%s just signed up for Zulip. Say hello!" % \
                                (user_profile.full_name,),
                              realm=user_profile.realm)

    internal_send_message(sender,
            "stream", signups_stream, user_profile.realm.domain,
            "%s <`%s`> just signed up for Zulip!%s(total: **%i**)" % (
                user_profile.full_name,
                user_profile.email,
                internal_blurb,
                user_count,
                )
            )

def notify_new_user(user_profile, internal=False):
    if settings.NEW_USER_BOT is not None:
        send_signup_message(settings.NEW_USER_BOT, "signups", user_profile, internal)
    statsd.gauge("users.signups.%s" % (user_profile.realm.domain.replace('.', '_')), 1, delta=True)

# Does the processing for a new user account:
# * Subscribes to default/invitation streams
# * Fills in some recent historical messages
# * Notifies other users in realm and Zulip about the signup
# * Deactivates PreregistrationUser objects
# * subscribe the user to newsletter if newsletter_data is specified
def process_new_human_user(user_profile, prereg_user=None, newsletter_data=None):
    mit_beta_user = user_profile.realm.domain == "mit.edu"
    try:
        streams = prereg_user.streams.all()
    except AttributeError:
        # This will catch both the case where prereg_user is None and where it
        # is a MitUser.
        streams = []

    # If the user's invitation didn't explicitly list some streams, we
    # add the default streams
    if len(streams) == 0:
        streams = get_default_subs(user_profile)
    bulk_add_subscriptions(streams, [user_profile])

    # Give you the last 100 messages on your public streams, so you have
    # something to look at in your home view once you finish the
    # tutorial.
    one_week_ago = now() - datetime.timedelta(weeks=1)
    recipients = Recipient.objects.filter(type=Recipient.STREAM,
                                          type_id__in=[stream.id for stream in streams
                                                       if not stream.invite_only])
    messages = Message.objects.filter(recipient_id__in=recipients, pub_date__gt=one_week_ago).order_by("-id")[0:100]
    if len(messages) > 0:
        ums_to_create = [UserMessage(user_profile=user_profile, message=message,
                                     flags=UserMessage.flags.read)
                         for message in messages]

        UserMessage.objects.bulk_create(ums_to_create)

    # mit_beta_users don't have a referred_by field
    if not mit_beta_user and prereg_user is not None and prereg_user.referred_by is not None \
            and settings.NOTIFICATION_BOT is not None:
        # This is a cross-realm private message.
        internal_send_message(settings.NOTIFICATION_BOT,
                "private", prereg_user.referred_by.email, user_profile.realm.domain,
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

    if newsletter_data is not None:
        # If the user was created automatically via the API, we may
        # not want to register them for the newsletter
        queue_json_publish(
            "signups",
            {
                'EMAIL': user_profile.email,
                'merge_vars': {
                    'NAME': user_profile.full_name,
                    'REALM': user_profile.realm.domain,
                    'OPTIN_IP': newsletter_data["IP"],
                    'OPTIN_TIME': datetime.datetime.isoformat(datetime.datetime.now()),
                },
            },
        lambda event: None)

def notify_created_user(user_profile):
    event = dict(type="realm_user", op="add",
                 person=dict(email=user_profile.email,
                             is_admin=user_profile.is_realm_admin,
                             full_name=user_profile.full_name,
                             is_bot=user_profile.is_bot))
    send_event(event, active_user_ids(user_profile.realm))

def notify_created_bot(user_profile):

    def stream_name(stream):
        if not stream:
            return None
        return stream.name

    default_sending_stream_name = stream_name(user_profile.default_sending_stream)
    default_events_register_stream_name = stream_name(user_profile.default_events_register_stream)

    event = dict(type="realm_bot", op="add",
                 bot=dict(email=user_profile.email,
                          full_name=user_profile.full_name,
                          api_key=user_profile.api_key,
                          default_sending_stream=default_sending_stream_name,
                          default_events_register_stream=default_events_register_stream_name,
                          default_all_public_streams=user_profile.default_all_public_streams,
                          avatar_url=avatar_url(user_profile),
                          owner=user_profile.bot_owner.email,
                         ))
    send_event(event, bot_owner_userids(user_profile))

def do_create_user(email, password, realm, full_name, short_name,
                   active=True, bot=False, bot_owner=None,
                   avatar_source=UserProfile.AVATAR_FROM_GRAVATAR,
                   default_sending_stream=None, default_events_register_stream=None,
                   default_all_public_streams=None, prereg_user=None,
                   newsletter_data=None):
    event = {'type': 'user_created',
             'timestamp': time.time(),
             'full_name': full_name,
             'short_name': short_name,
             'user': email,
             'domain': realm.domain,
             'bot': bot}
    if bot:
        event['bot_owner'] = bot_owner.email
    log_event(event)

    user_profile = create_user(email=email, password=password, realm=realm,
                               full_name=full_name, short_name=short_name,
                               active=active, bot=bot, bot_owner=bot_owner,
                               avatar_source=avatar_source,
                               default_sending_stream=default_sending_stream,
                               default_events_register_stream=default_events_register_stream,
                               default_all_public_streams=default_all_public_streams)

    notify_created_user(user_profile)
    if bot:
        notify_created_bot(user_profile)
    else:
        process_new_human_user(user_profile, prereg_user=prereg_user,
                               newsletter_data=newsletter_data)
    return user_profile

def user_sessions(user_profile):
    return [s for s in Session.objects.all()
            if get_session_user(s) == user_profile.id]

def delete_session(session):
    return session_engine.SessionStore(session.session_key).delete()

def delete_user_sessions(user_profile):
    for session in Session.objects.all():
        if get_session_user(session) == user_profile.id:
            delete_session(session)

def delete_realm_user_sessions(realm):
    realm_user_ids = [user_profile.id for user_profile in
                      UserProfile.objects.filter(realm=realm)]
    for session in Session.objects.filter(expire_date__gte=datetime.datetime.now()):
        if get_session_user(session) in realm_user_ids:
            delete_session(session)

def delete_all_user_sessions():
    for session in Session.objects.all():
        delete_session(session)

def active_humans_in_realm(realm):
    return UserProfile.objects.filter(realm=realm, is_active=True, is_bot=False)

def do_set_realm_name(realm, name):
    realm.name = name
    realm.save(update_fields=['name'])
    event = dict(
        type="realm",
        op="update",
        property='name',
        value=name,
    )
    send_event(event, active_user_ids(realm))
    return {}

def do_set_realm_restricted_to_domain(realm, restricted):
    realm.restricted_to_domain = restricted
    realm.save(update_fields=['restricted_to_domain'])
    event = dict(
        type="realm",
        op="update",
        property='restricted_to_domain',
        value=restricted,
    )
    send_event(event, active_user_ids(realm))
    return {}

def do_set_realm_invite_required(realm, invite_required):
    realm.invite_required = invite_required
    realm.save(update_fields=['invite_required'])
    event = dict(
        type="realm",
        op="update",
        property='invite_required',
        value=invite_required,
    )
    send_event(event, active_user_ids(realm))
    return {}

def do_set_realm_invite_by_admins_only(realm, invite_by_admins_only):
    realm.invite_by_admins_only = invite_by_admins_only
    realm.save(update_fields=['invite_by_admins_only'])
    event = dict(
        type="realm",
        op="update",
        property='invite_by_admins_only',
        value=invite_by_admins_only,
    )
    send_event(event, active_user_ids(realm))
    return {}

def do_deactivate_realm(realm):
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

def do_reactivate_realm(realm):
    realm.deactivated = False
    realm.save(update_fields=["deactivated"])

def do_deactivate_user(user_profile, log=True, _cascade=True):
    if not user_profile.is_active:
        return

    user_profile.is_active = False;
    user_profile.save(update_fields=["is_active"])

    delete_user_sessions(user_profile)

    if log:
        log_event({'type': 'user_deactivated',
                   'timestamp': time.time(),
                   'user': user_profile.email,
                   'domain': user_profile.realm.domain})

    event = dict(type="realm_user", op="remove",
                 person=dict(email=user_profile.email,
                             full_name=user_profile.full_name))
    send_event(event, active_user_ids(user_profile.realm))

    if user_profile.is_bot:
        event = dict(type="realm_bot", op="remove",
                     bot=dict(email=user_profile.email,
                              full_name=user_profile.full_name))
        send_event(event, bot_owner_userids(user_profile))

    if _cascade:
        bot_profiles = UserProfile.objects.filter(is_bot=True, is_active=True,
                                                  bot_owner=user_profile)
        for profile in bot_profiles:
            do_deactivate_user(profile, _cascade=False)

def do_deactivate_stream(stream, log=True):
    user_profiles = UserProfile.objects.filter(realm=stream.realm)
    for user_profile in user_profiles:
        do_remove_subscription(user_profile, stream)

    was_invite_only = stream.invite_only
    stream.deactivated = True
    stream.invite_only = True
    # Preserve as much as possible the original stream name while giving it a
    # special prefix that both indicates that the stream is deactivated and
    # frees up the original name for reuse.
    old_name = stream.name
    new_name = ("!DEACTIVATED:" + old_name)[:Stream.MAX_NAME_LENGTH]
    for i in range(20):
        existing_deactivated_stream = get_stream(new_name, stream.realm)
        if existing_deactivated_stream:
            # This stream has alrady been deactivated, keep prepending !s until
            # we have a unique stream name or you've hit a rename limit.
            new_name = ("!" + new_name)[:Stream.MAX_NAME_LENGTH]
        else:
            break

    # If you don't have a unique name at this point, this will fail later in the
    # code path.

    stream.name = new_name[:Stream.MAX_NAME_LENGTH]
    stream.save()

    # Remove the old stream information from remote cache.
    old_cache_key = get_stream_cache_key(old_name, stream.realm)
    cache_delete(old_cache_key)

    if not was_invite_only:
        stream_dict = stream.to_dict()
        stream_dict.update(dict(name=old_name, invite_only=was_invite_only))
        event = dict(type="stream", op="delete",
                     streams=[stream_dict])
        send_event(event, active_user_ids(stream.realm))

    return

def do_change_user_email(user_profile, new_email):
    old_email = user_profile.email
    user_profile.email = new_email
    user_profile.save(update_fields=["email"])

    log_event({'type': 'user_email_changed',
               'old_email': old_email,
               'new_email': new_email})

def compute_irc_user_fullname(email):
    return email.split("@")[0] + " (IRC)"

def compute_jabber_user_fullname(email):
    return email.split("@")[0] + " (XMPP)"

def compute_mit_user_fullname(email):
    try:
        # Input is either e.g. username@mit.edu or user|CROSSREALM.INVALID@mit.edu
        match_user = re.match(r'^([a-zA-Z0-9_.-]+)(\|.+)?@mit\.edu$', email.lower())
        if match_user and match_user.group(2) is None:
            answer = DNS.dnslookup(
                "%s.passwd.ns.athena.mit.edu" % (match_user.group(1),),
                DNS.Type.TXT)
            hesiod_name = answer[0][0].split(':')[4].split(',')[0].strip()
            if hesiod_name != "":
                return hesiod_name
        elif match_user:
            return match_user.group(1).lower() + "@" + match_user.group(2).upper()[1:]
    except DNS.Base.ServerError:
        pass
    except:
        print ("Error getting fullname for %s:" % (email,))
        traceback.print_exc()
    return email.lower()

@cache_with_key(lambda realm, email, f: user_profile_by_email_cache_key(email),
                timeout=3600*24*7)
def create_mirror_user_if_needed(realm, email, email_to_fullname):
    try:
        return get_user_profile_by_email(email)
    except UserProfile.DoesNotExist:
        try:
            # Forge a user for this person
            return create_user(email, None, realm,
                               email_to_fullname(email), email_to_username(email),
                               active=False, is_mirror_dummy=True)
        except IntegrityError:
            return get_user_profile_by_email(email)

def log_message(message):
    if not message.sending_client.name.startswith("test:"):
        log_event(message.to_log_dict())

def always_push_notify(user):
    # robinhood.io asked to get push notifications for **all** notifyable
    # messages, regardless of idle status
    return user.realm.domain in ['robinhood.io']

# Helper function. Defaults here are overriden by those set in do_send_messages
def do_send_message(message, rendered_content = None, no_log = False, stream = None, local_id = None):
    return do_send_messages([{'message': message,
                              'rendered_content': rendered_content,
                              'no_log': no_log,
                              'stream': stream,
                              'local_id': local_id}])[0]

def do_send_messages(messages):
    # Filter out messages which didn't pass internal_prep_message properly
    messages = [message for message in messages if message is not None]

    # Filter out zephyr mirror anomalies where the message was already sent
    already_sent_ids = []
    new_messages = []
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
        message['no_log'] = message.get('no_log', False)
        message['stream'] = message.get('stream', None)
        message['local_id'] = message.get('local_id', None)
        message['sender_queue_id'] = message.get('sender_queue_id', None)

    # Log the message to our message log for populate_db to refill
    for message in messages:
        if not message['no_log']:
            log_message(message['message'])

    for message in messages:
        if message['message'].recipient.type == Recipient.PERSONAL:
            message['recipients'] = list(set([get_user_profile_by_id(message['message'].recipient.type_id),
                                              get_user_profile_by_id(message['message'].sender_id)]))
            # For personals, you send out either 1 or 2 copies of the message, for
            # personals to yourself or to someone else, respectively.
            assert((len(message['recipients']) == 1) or (len(message['recipients']) == 2))
        elif (message['message'].recipient.type == Recipient.STREAM or
              message['message'].recipient.type == Recipient.HUDDLE):
            # We use select_related()/only() here, while the PERSONAL case above uses
            # get_user_profile_by_id() to get UserProfile objects from cache.  Streams will
            # typically have more recipients than PMs, so get_user_profile_by_id() would be
            # a bit more expensive here, given that we need to hit the DB anyway and only
            # care about the email from the user profile.
            fields = [
                'user_profile__id',
                'user_profile__email',
                'user_profile__is_active',
                'user_profile__realm__domain'
            ]
            query = Subscription.objects.select_related("user_profile", "user_profile__realm").only(*fields).filter(
                recipient=message['message'].recipient, active=True)
            message['recipients'] = [s.user_profile for s in query]
        else:
            raise ValueError('Bad recipient type')

        # Only deliver the message to active user recipients
        message['active_recipients'] = [user_profile for user_profile in message['recipients'] if user_profile.is_active]
        message['message'].maybe_render_content(None)
        message['message'].update_calculated_fields()

    # Save the message receipts in the database
    user_message_flags = defaultdict(dict) # type: Dict[int, Dict[int, List[str]]]
    with transaction.atomic():
        Message.objects.bulk_create([message['message'] for message in messages])
        ums = []
        for message in messages:
            ums_to_create = [UserMessage(user_profile=user_profile, message=message['message'])
                             for user_profile in message['active_recipients']]

            # These properties on the Message are set via
            # Message.render_markdown by code in the bugdown inline patterns
            wildcard = message['message'].mentions_wildcard
            mentioned_ids = message['message'].mentions_user_ids
            ids_with_alert_words = message['message'].user_ids_with_alert_words
            is_me_message = message['message'].is_me_message

            for um in ums_to_create:
                if um.user_profile.id == message['message'].sender.id and \
                        message['message'].sent_by_human():
                    um.flags |= UserMessage.flags.read
                if wildcard:
                    um.flags |= UserMessage.flags.wildcard_mentioned
                if um.user_profile_id in mentioned_ids:
                    um.flags |= UserMessage.flags.mentioned
                if um.user_profile_id in ids_with_alert_words:
                    um.flags |= UserMessage.flags.has_alert_word
                if is_me_message:
                    um.flags |= UserMessage.flags.is_me_message
                user_message_flags[message['message'].id][um.user_profile_id] = um.flags_list()
            ums.extend(ums_to_create)
        UserMessage.objects.bulk_create(ums)

    for message in messages:
        cache_save_message(message['message'])
        # Render Markdown etc. here and store (automatically) in
        # remote cache, so that the single-threaded Tornado server
        # doesn't have to.
        user_flags = user_message_flags.get(message['message'].id, {})
        sender = message['message'].sender
        user_presences = get_status_dict(sender)
        presences = {}
        for user_profile in message['active_recipients']:
            if user_profile.email in user_presences:
                presences[user_profile.id] = user_presences[user_profile.email]

        event = dict(
            type         = 'message',
            message      = message['message'].id,
            message_dict_markdown = message['message'].to_dict(apply_markdown=True),
            message_dict_no_markdown = message['message'].to_dict(apply_markdown=False),
            presences    = presences)
        users = [{'id': user.id,
                  'flags': user_flags.get(user.id, []),
                  'always_push_notify': always_push_notify(user)}
                 for user in message['active_recipients']]
        if message['message'].recipient.type == Recipient.STREAM:
            # Note: This is where authorization for single-stream
            # get_updates happens! We only attach stream data to the
            # notify new_message request if it's a public stream,
            # ensuring that in the tornado server, non-public stream
            # messages are only associated to their subscribed users.
            if message['stream'] is None:
                message['stream'] = Stream.objects.select_related("realm").get(id=message['message'].recipient.type_id)
            if message['stream'].is_public():
                event['realm_id'] = message['stream'].realm.id
                event['stream_name'] = message['stream'].name
            if message['stream'].invite_only:
                event['invite_only'] = True
        if message['local_id'] is not None:
            event['local_id'] = message['local_id']
        if message['sender_queue_id'] is not None:
            event['sender_queue_id'] = message['sender_queue_id']
        send_event(event, users)
        if (settings.ENABLE_FEEDBACK and
            message['message'].recipient.type == Recipient.PERSONAL and
            settings.FEEDBACK_BOT in [up.email for up in message['recipients']]):
            queue_json_publish(
                    'feedback_messages',
                    message['message'].to_dict(apply_markdown=False),
                    lambda x: None
            )

    # Note that this does not preserve the order of message ids
    # returned.  In practice, this shouldn't matter, as we only
    # mirror single zephyr messages at a time and don't otherwise
    # intermingle sending zephyr messages with other messages.
    return already_sent_ids + [message['message'].id for message in messages]

def do_create_stream(realm, stream_name):
    # This is used by a management command now, mostly to facilitate testing.  It
    # doesn't simulate every single aspect of creating a subscription; for example,
    # we don't send Zulips to users to tell them they have been subscribed.
    stream = Stream()
    stream.realm = realm
    stream.name = stream_name
    stream.save()
    Recipient.objects.create(type_id=stream.id, type=Recipient.STREAM)
    subscribers = UserProfile.objects.filter(realm=realm, is_active=True, is_bot=False)
    bulk_add_subscriptions([stream], subscribers)

def create_stream_if_needed(realm, stream_name, invite_only=False):
    (stream, created) = Stream.objects.get_or_create(
        realm=realm, name__iexact=stream_name,
        defaults={'name': stream_name, 'invite_only': invite_only})
    if created:
        Recipient.objects.create(type_id=stream.id, type=Recipient.STREAM)
        if not invite_only:
            event = dict(type="stream", op="create",
                         streams=[stream.to_dict()])
            send_event(event, active_user_ids(realm))
    return stream, created

def recipient_for_emails(emails, not_forged_mirror_message,
                         user_profile, sender):
    recipient_profile_ids = set()
    normalized_emails = set()
    realm_domains = set()
    normalized_emails.add(sender.email)
    realm_domains.add(sender.realm.domain)

    for email in emails:
        try:
            user_profile = get_user_profile_by_email(email)
        except UserProfile.DoesNotExist:
            raise ValidationError("Invalid email '%s'" % (email,))
        if (not user_profile.is_active and not user_profile.is_mirror_dummy) or \
                user_profile.realm.deactivated:
            raise ValidationError("'%s' is no longer using Zulip." % (email,))
        recipient_profile_ids.add(user_profile.id)
        normalized_emails.add(user_profile.email)
        realm_domains.add(user_profile.realm.domain)

    if not_forged_mirror_message and user_profile.id not in recipient_profile_ids:
        raise ValidationError("User not authorized for this query")

    # Prevent cross realm private messages unless it is between only two realms
    # and one of users is a zuliper
    if len(realm_domains) == 2:
        # I'm assuming that cross-realm PMs with the "admin realm" are rare, and therefore can be slower
        admin_realm = get_realm(settings.ADMIN_DOMAIN)
        admin_realm_admin_emails = {u.email for u in admin_realm.get_admin_users()}
        # We allow settings.CROSS_REALM_BOT_EMAILS for the hardcoded emails for the feedback and notification bots
        if not (normalized_emails & admin_realm_admin_emails or normalized_emails & settings.CROSS_REALM_BOT_EMAILS):
            raise ValidationError("You can't send private messages outside of your organization.")
    if len(realm_domains) > 2:
        raise ValidationError("You can't send private messages outside of your organization.")

    # If the private message is just between the sender and
    # another person, force it to be a personal internally
    if (len(recipient_profile_ids) == 2
        and sender.id in recipient_profile_ids):
        recipient_profile_ids.remove(sender.id)

    if len(recipient_profile_ids) > 1:
        # Make sure the sender is included in huddle messages
        recipient_profile_ids.add(sender.id)
        huddle = get_huddle(list(recipient_profile_ids))
        return get_recipient(Recipient.HUDDLE, huddle.id)
    else:
        return get_recipient(Recipient.PERSONAL, list(recipient_profile_ids)[0])

def already_sent_mirrored_message_id(message):
    if message.recipient.type == Recipient.HUDDLE:
        # For huddle messages, we use a 10-second window because the
        # timestamps aren't guaranteed to actually match between two
        # copies of the same message.
        time_window = datetime.timedelta(seconds=10)
    else:
        time_window = datetime.timedelta(seconds=0)

    messages =  Message.objects.filter(
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
    # We try to accept multiple incoming formats for recipients.
    # See test_extract_recipients() for examples of what we allow.
    try:
        data = ujson.loads(s)
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
def check_send_message(*args, **kwargs):
    message = check_message(*args, **kwargs)
    return do_send_messages([message])[0]

def check_stream_name(stream_name):
    if stream_name == "":
        raise JsonableError("Stream can't be empty")
    if len(stream_name) > Stream.MAX_NAME_LENGTH:
        raise JsonableError("Stream name too long")
    if not valid_stream_name(stream_name):
        raise JsonableError("Invalid stream name")

def send_pm_if_empty_stream(sender, stream, stream_name):
    if sender.realm.domain == 'mit.edu' or sender.realm.deactivated:
        return

    if sender.is_bot and sender.bot_owner is not None:
        # Don't send these notifications for cross-realm bot messages
        # (e.g. from EMAIL_GATEWAY_BOT) since the owner for
        # EMAIL_GATEWAY_BOT is probably the server administrator, not
        # the owner of the bot who could potentially fix the problem.
        if stream.realm != sender.realm:
            return

        if stream:
            num_subscribers = stream.num_subscribers()

        if stream is None or num_subscribers == 0:
            # Warn a bot's owner if they are sending a message to a stream
            # that does not exist, or has no subscribers
            # We warn the user once every 5 minutes to avoid a flood of
            # PMs on a misconfigured integration, re-using the
            # UserProfile.last_reminder field, which is not used for bots.
            last_reminder = sender.last_reminder_tzaware()
            waitperiod = datetime.timedelta(minutes=UserProfile.BOT_OWNER_STREAM_ALERT_WAITPERIOD)
            if not last_reminder or timezone.now() - last_reminder > waitperiod:
                if stream is None:
                    error_msg = "that stream does not yet exist. To create it, "
                elif num_subscribers == 0:
                    error_msg = "there are no subscribers to that stream. To join it, "

                content = ("Hi there! We thought you'd like to know that your bot **%s** just "
                           "tried to send a message to stream `%s`, but %s"
                           "click the gear in the left-side stream list." %
                           (sender.full_name, stream_name, error_msg))
                message = internal_prep_message(settings.NOTIFICATION_BOT, "private",
                                                sender.bot_owner.email, "", content)
                do_send_messages([message])

                sender.last_reminder = timezone.now()
                sender.save(update_fields=['last_reminder'])

# check_message:
# Returns message ready for sending with do_send_message on success or the error message (string) on error.
def check_message(sender, client, message_type_name, message_to,
                  subject_name, message_content, realm=None, forged=False,
                  forged_timestamp=None, forwarder_user_profile=None, local_id=None,
                  sender_queue_id=None):
    stream = None
    if not message_to and message_type_name == 'stream' and sender.default_sending_stream:
        # Use the users default stream
        message_to = [sender.default_sending_stream.name]
    elif len(message_to) == 0:
        raise JsonableError("Message must have recipients")
    if len(message_content.strip()) == 0:
        raise JsonableError("Message must not be empty")
    message_content = truncate_body(message_content)

    if realm is None:
        realm = sender.realm

    if message_type_name == 'stream':
        if len(message_to) > 1:
            raise JsonableError("Cannot send to multiple streams")

        stream_name = message_to[0].strip()
        check_stream_name(stream_name)

        if subject_name is None:
            raise JsonableError("Missing topic")
        subject = subject_name.strip()
        if subject == "":
            raise JsonableError("Topic can't be empty")
        subject = truncate_topic(subject)
        ## FIXME: Commented out temporarily while we figure out what we want
        # if not valid_stream_name(subject):
        #     return json_error("Invalid subject name")

        stream = get_stream(stream_name, realm)

        send_pm_if_empty_stream(sender, stream, stream_name)

        if stream is None:
            raise JsonableError("Stream does not exist")
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
        elif sender.is_bot and subscribed_to_stream(sender.bot_owner, stream):
            # Or you're a bot and your owner is subscribed.
            pass
        else:
            # All other cases are an error.
            raise JsonableError("Not authorized to send to stream '%s'" % (stream.name,))

    elif message_type_name == 'private':
        mirror_message = client and client.name in ["zephyr_mirror", "irc_mirror", "jabber_mirror", "JabberMirror"]
        not_forged_mirror_message = mirror_message and not forged
        try:
            recipient = recipient_for_emails(message_to, not_forged_mirror_message,
                                             forwarder_user_profile, sender)
        except ValidationError as e:
            assert isinstance(e.messages[0], six.string_types)
            raise JsonableError(e.messages[0])
    else:
        raise JsonableError("Invalid message type")

    message = Message()
    message.sender = sender
    message.content = message_content
    message.recipient = recipient
    if message_type_name == 'stream':
        message.subject = subject
    if forged and forged_timestamp is not None:
        # Forged messages come with a timestamp
        message.pub_date = timestamp_to_datetime(forged_timestamp)
    else:
        message.pub_date = timezone.now()
    message.sending_client = client

    if not message.maybe_render_content(realm.domain):
        raise JsonableError("Unable to render message")

    if client.name == "zephyr_mirror":
        id = already_sent_mirrored_message_id(message)
        if id is not None:
            return {'message': id}

    return {'message': message, 'stream': stream, 'local_id': local_id, 'sender_queue_id': sender_queue_id}

def internal_prep_message(sender_email, recipient_type_name, recipients,
                          subject, content, realm=None):
    """
    Create a message object and checks it, but doesn't send it or save it to the database.
    The internal function that calls this can therefore batch send a bunch of created
    messages together as one database query.
    Call do_send_messages with a list of the return values of this method.
    """
    if len(content) > MAX_MESSAGE_LENGTH:
        content = content[0:3900] + "\n\n[message was too long and has been truncated]"

    sender = get_user_profile_by_email(sender_email)
    if realm is None:
        realm = sender.realm
    parsed_recipients = extract_recipients(recipients)
    if recipient_type_name == "stream":
        stream, _ = create_stream_if_needed(realm, parsed_recipients[0])

    try:
        return check_message(sender, get_client("Internal"), recipient_type_name,
                             parsed_recipients, subject, content, realm)
    except JsonableError as e:
        logging.error("Error queueing internal message by %s: %s" % (sender_email, str(e)))

    return None

def internal_send_message(sender_email, recipient_type_name, recipients,
                          subject, content, realm=None):
    msg = internal_prep_message(sender_email, recipient_type_name, recipients,
                                subject, content, realm)

    # internal_prep_message encountered an error
    if msg is None:
        return

    do_send_messages([msg])

def pick_color(user_profile):
    subs = Subscription.objects.filter(user_profile=user_profile,
                                       active=True,
                                       recipient__type=Recipient.STREAM)
    return pick_color_helper(user_profile, subs)

def pick_color_helper(user_profile, subs):
    # These colors are shared with the palette in subs.js.
    stream_assignment_colors = [
        "#76ce90", "#fae589", "#a6c7e5", "#e79ab5",
        "#bfd56f", "#f4ae55", "#b0a5fd", "#addfe5",
        "#f5ce6e", "#c2726a", "#94c849", "#bd86e5",
        "#ee7e4a", "#a6dcbf", "#95a5fd", "#53a063",
        "#9987e1", "#e4523d", "#c2c2c2", "#4f8de4",
        "#c6a8ad", "#e7cc4d", "#c8bebf", "#a47462"]
    used_colors = [sub.color for sub in subs if sub.active]
    available_colors = [x for x in stream_assignment_colors if x not in used_colors]

    if available_colors:
        return available_colors[0]
    else:
        return stream_assignment_colors[len(used_colors) % len(stream_assignment_colors)]

def get_subscription(stream_name, user_profile):
    stream = get_stream(stream_name, user_profile.realm)
    recipient = get_recipient(Recipient.STREAM, stream.id)
    return Subscription.objects.get(user_profile=user_profile,
                                    recipient=recipient, active=True)

def validate_user_access_to_subscribers(user_profile, stream):
    """ Validates whether the user can view the subscribers of a stream.  Raises a JsonableError if:
        * The user and the stream are in different realms
        * The realm is MIT and the stream is not invite only.
        * The stream is invite only, requesting_user is passed, and that user
          does not subscribe to the stream.
    """
    return validate_user_access_to_subscribers_helper(
        user_profile,
        {"realm__domain": stream.realm.domain,
         "realm_id": stream.realm_id,
         "invite_only": stream.invite_only},
        # We use a lambda here so that we only compute whether the
        # user is subscribed if we have to
        lambda: subscribed_to_stream(user_profile, stream))

def validate_user_access_to_subscribers_helper(user_profile, stream_dict, check_user_subscribed):
    """ Helper for validate_user_access_to_subscribers that doesn't require a full stream object
    * check_user_subscribed is a function that when called with no
      arguments, will report whether the user is subscribed to the stream
    """
    if user_profile is not None and user_profile.realm_id != stream_dict["realm_id"]:
        raise ValidationError("Requesting user not on given realm")

    if stream_dict["realm__domain"] == "mit.edu" and not stream_dict["invite_only"]:
        raise JsonableError("You cannot get subscribers for public streams in this realm")

    if (user_profile is not None and stream_dict["invite_only"] and
        not check_user_subscribed()):
        raise JsonableError("Unable to retrieve subscribers for invite-only stream")

# sub_dict is a dictionary mapping stream_id => whether the user is subscribed to that stream
def bulk_get_subscriber_user_ids(stream_dicts, user_profile, sub_dict):
    target_stream_dicts = []
    for stream_dict in stream_dicts:
        try:
            validate_user_access_to_subscribers_helper(user_profile, stream_dict,
                                                       lambda: sub_dict[stream_dict["id"]])
        except JsonableError:
            continue
        target_stream_dicts.append(stream_dict)

    subscriptions = Subscription.objects.select_related("recipient").filter(
        recipient__type=Recipient.STREAM,
        recipient__type_id__in=[stream["id"] for stream in target_stream_dicts],
        user_profile__is_active=True,
        active=True).values("user_profile_id", "recipient__type_id")

    result = dict((stream["id"], []) for stream in stream_dicts) # type: Dict[int, List[int]]
    for sub in subscriptions:
        result[sub["recipient__type_id"]].append(sub["user_profile_id"])

    return result

def get_subscribers_query(stream, requesting_user):
    """ Build a query to get the subscribers list for a stream, raising a JsonableError if:

    'stream' can either be a string representing a stream name, or a Stream
    object. If it's a Stream object, 'realm' is optional.

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
    subscriptions = get_subscribers_query(stream, requesting_user).select_related()
    return [subscription.user_profile for subscription in subscriptions]

def get_subscriber_emails(stream, requesting_user=None):
    subscriptions = get_subscribers_query(stream, requesting_user)
    subscriptions = subscriptions.values('user_profile__email')
    return [subscription['user_profile__email'] for subscription in subscriptions]

def get_subscriber_ids(stream):
    try:
        subscriptions = get_subscribers_query(stream, None)
    except JsonableError:
        return []

    rows = subscriptions.values('user_profile_id')
    ids = [row['user_profile_id'] for row in rows]
    return ids

def get_other_subscriber_ids(stream, user_profile_id):
    ids = get_subscriber_ids(stream)
    return [id for id in ids if id != user_profile_id]

def maybe_get_subscriber_emails(stream):
    """ Alternate version of get_subscriber_emails that takes a Stream object only
    (not a name), and simply returns an empty list if unable to get a real
    subscriber list (because we're on the MIT realm). """
    try:
        subscribers = get_subscriber_emails(stream)
    except JsonableError:
        subscribers = []
    return subscribers

def set_stream_color(user_profile, stream_name, color=None):
    subscription = get_subscription(stream_name, user_profile)
    if not color:
        color = pick_color(user_profile)
    subscription.color = color
    subscription.save(update_fields=["color"])
    return color

def get_subscribers_to_streams(streams):
    """ Return a dict where the keys are user profiles, and the values are
    arrays of all the streams within 'streams' to which that user is
    subscribed.
    """
    subscribes_to = {} # type: Dict[str, List[Stream]]
    for stream in streams:
        try:
            subscribers = get_subscribers(stream)
        except JsonableError:
            # We can't get a subscriber list for this stream. Probably MIT.
            continue

        for subscriber in subscribers:
            if subscriber not in subscribes_to:
                subscribes_to[subscriber] = []
            subscribes_to[subscriber].append(stream)

    return subscribes_to

def notify_subscriptions_added(user_profile, sub_pairs, stream_emails, no_log=False):
    if not no_log:
        log_event({'type': 'subscription_added',
                   'user': user_profile.email,
                   'names': [stream.name for sub, stream in sub_pairs],
                   'domain': user_profile.realm.domain})

    # Send a notification to the user who subscribed.
    payload = [dict(name=stream.name,
                    stream_id=stream.id,
                    in_home_view=subscription.in_home_view,
                    invite_only=stream.invite_only,
                    color=subscription.color,
                    email_address=encode_email_address(stream),
                    desktop_notifications=subscription.desktop_notifications,
                    audible_notifications=subscription.audible_notifications,
                    description=stream.description,
                    subscribers=stream_emails(stream))
            for (subscription, stream) in sub_pairs]
    event = dict(type="subscription", op="add",
                 subscriptions=payload)
    send_event(event, [user_profile.id])

def bulk_add_subscriptions(streams, users):
    recipients_map = bulk_get_recipients(Recipient.STREAM, [stream.id for stream in streams])
    recipients = [recipient.id for recipient in recipients_map.values()]

    stream_map = {}
    for stream in streams:
        stream_map[recipients_map[stream.id].id] = stream

    subs_by_user = defaultdict(list) # type: Dict[int, List[Subscription]]
    all_subs_query = Subscription.objects.select_related("user_profile")
    for sub in all_subs_query.filter(user_profile__in=users,
                                     recipient__type=Recipient.STREAM):
        subs_by_user[sub.user_profile_id].append(sub)

    already_subscribed = []
    subs_to_activate = []
    new_subs = []
    for user_profile in users:
        needs_new_sub = set(recipients)
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

    subs_to_add = []
    for (user_profile, recipient_id, stream) in new_subs:
        color = pick_color_helper(user_profile, subs_by_user[user_profile.id])
        sub_to_add = Subscription(user_profile=user_profile, active=True,
                                  color=color, recipient_id=recipient_id,
                                  desktop_notifications=user_profile.enable_stream_desktop_notifications,
                                  audible_notifications=user_profile.enable_stream_sounds)
        subs_by_user[user_profile.id].append(sub_to_add)
        subs_to_add.append((sub_to_add, stream))

    # TODO: XXX: This transaction really needs to be done at the serializeable
    # transaction isolation level.
    with transaction.atomic():
        occupied_streams_before = list(get_occupied_streams(user_profile.realm))
        Subscription.objects.bulk_create([sub for (sub, stream) in subs_to_add])
        Subscription.objects.filter(id__in=[sub.id for (sub, stream_name) in subs_to_activate]).update(active=True)
        occupied_streams_after = list(get_occupied_streams(user_profile.realm))

    new_occupied_streams = [stream for stream in
                            set(occupied_streams_after) - set(occupied_streams_before)
                            if not stream.invite_only]
    if new_occupied_streams:
        event = dict(type="stream", op="occupy",
                     streams=[stream.to_dict()
                              for stream in new_occupied_streams])
        send_event(event, active_user_ids(user_profile.realm))

    # Notify all existing users on streams that users have joined

    # First, get all users subscribed to the streams that we care about
    # We fetch all subscription information upfront, as it's used throughout
    # the following code and we want to minize DB queries
    all_subs = Subscription.objects.filter(recipient__type=Recipient.STREAM,
                                           recipient__type_id__in=[stream.id for stream in streams],
                                           user_profile__is_active=True,
                                           active=True).select_related('recipient', 'user_profile')

    all_subs_by_stream = defaultdict(list) # type: Dict[int, List[UserProfile]]
    emails_by_stream = defaultdict(list) # type: Dict[int, List[str]]
    for sub in all_subs:
        all_subs_by_stream[sub.recipient.type_id].append(sub.user_profile)
        emails_by_stream[sub.recipient.type_id].append(sub.user_profile.email)

    def fetch_stream_subscriber_emails(stream):
        if stream.realm.domain == "mit.edu" and not stream.invite_only:
            return []
        return emails_by_stream[stream.id]

    sub_tuples_by_user = defaultdict(list) # type: Dict[int, List[Tuple[Subscription, Stream]]]
    new_streams = set()
    for (sub, stream) in subs_to_add + subs_to_activate:
        sub_tuples_by_user[sub.user_profile.id].append((sub, stream))
        new_streams.add((sub.user_profile.id, stream.id))

    for user_profile in users:
        if len(sub_tuples_by_user[user_profile.id]) == 0:
            continue
        sub_pairs = sub_tuples_by_user[user_profile.id]
        notify_subscriptions_added(user_profile, sub_pairs, fetch_stream_subscriber_emails)

    for stream in streams:
        if stream.realm.domain == "mit.edu" and not stream.invite_only:
            continue

        new_users = [user for user in users if (user.id, stream.id) in new_streams]
        new_user_ids = [user.id for user in new_users]
        all_subscribed_ids = [user.id for user in all_subs_by_stream[stream.id]]
        other_user_ids = set(all_subscribed_ids) - set(new_user_ids)
        if other_user_ids:
            for user_profile in new_users:
                event = dict(type="subscription", op="peer_add",
                             subscriptions=[stream.name],
                             user_email=user_profile.email)
                send_event(event, other_user_ids)

    return ([(user_profile, stream_name) for (user_profile, recipient_id, stream_name) in new_subs] +
            [(sub.user_profile, stream_name) for (sub, stream_name) in subs_to_activate],
            already_subscribed)

# When changing this, also change bulk_add_subscriptions
def do_add_subscription(user_profile, stream, no_log=False):
    recipient = get_recipient(Recipient.STREAM, stream.id)
    color = pick_color(user_profile)
    # TODO: XXX: This transaction really needs to be done at the serializeable
    # transaction isolation level.
    with transaction.atomic():
        vacant_before = stream.num_subscribers() == 0
        (subscription, created) = Subscription.objects.get_or_create(
            user_profile=user_profile, recipient=recipient,
            defaults={'active': True, 'color': color,
                      'notifications': user_profile.default_desktop_notifications})
        did_subscribe = created
        if not subscription.active:
            did_subscribe = True
            subscription.active = True
            subscription.save(update_fields=["active"])

    if vacant_before and did_subscribe and not stream.invite_only:
        event = dict(type="stream", op="occupy",
                     streams=[stream.to_dict()])
        send_event(event, active_user_ids(user_profile.realm))

    if did_subscribe:
        emails_by_stream = {stream.id: maybe_get_subscriber_emails(stream)}
        notify_subscriptions_added(user_profile, [(subscription, stream)], lambda stream: emails_by_stream[stream.id], no_log)

        user_ids = get_other_subscriber_ids(stream, user_profile.id)
        event = dict(type="subscription", op="peer_add",
                     subscriptions=[stream.name],
                     user_email=user_profile.email)
        send_event(event, user_ids)

    return did_subscribe

def notify_subscriptions_removed(user_profile, streams, no_log=False):
    if not no_log:
        log_event({'type': 'subscription_removed',
                   'user': user_profile.email,
                   'names': [stream.name for stream in streams],
                   'domain': user_profile.realm.domain})

    payload = [dict(name=stream.name, stream_id=stream.id) for stream in streams]
    event = dict(type="subscription", op="remove",
                 subscriptions=payload)
    send_event(event, [user_profile.id])

    # As with a subscription add, send a 'peer subscription' notice to other
    # subscribers so they know the user unsubscribed.
    # FIXME: This code was mostly a copy-paste from notify_subscriptions_added.
    #        We have since streamlined how we do notifications for adds, and
    #        we should do the same for removes.
    notifications_for = get_subscribers_to_streams(streams)

    for event_recipient, notifications in six.iteritems(notifications_for):
        # Don't send a peer subscription notice to yourself.
        if event_recipient == user_profile:
            continue

        stream_names = [stream.name for stream in notifications]
        event = dict(type="subscription", op="peer_remove",
                     subscriptions=stream_names,
                     user_email=user_profile.email)
        send_event(event, [event_recipient.id])

def bulk_remove_subscriptions(users, streams):
    recipients_map = bulk_get_recipients(Recipient.STREAM,
                                         [stream.id for stream in streams])
    stream_map = {}
    for stream in streams:
        stream_map[recipients_map[stream.id].id] = stream

    subs_by_user = dict((user_profile.id, []) for user_profile in users) # type: Dict[int, List[Subscription]]
    for sub in Subscription.objects.select_related("user_profile").filter(user_profile__in=users,
                                                                          recipient__in=list(recipients_map.values()),
                                                                          active=True):
        subs_by_user[sub.user_profile_id].append(sub)

    subs_to_deactivate = []
    not_subscribed = []
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

    new_vacant_streams = [stream for stream in
                          set(occupied_streams_before) - set(occupied_streams_after)
                          if not stream.invite_only]
    if new_vacant_streams:
        event = dict(type="stream", op="vacate",
                     streams=[stream.to_dict()
                              for stream in new_vacant_streams])
        send_event(event, active_user_ids(user_profile.realm))

    streams_by_user = defaultdict(list) # type: Dict[int, List[Stream]]
    for (sub, stream) in subs_to_deactivate:
        streams_by_user[sub.user_profile_id].append(stream)

    for user_profile in users:
        if len(streams_by_user[user_profile.id]) == 0:
            continue
        notify_subscriptions_removed(user_profile, streams_by_user[user_profile.id])

    return ([(sub.user_profile, stream) for (sub, stream) in subs_to_deactivate],
            not_subscribed)

def do_remove_subscription(user_profile, stream, no_log=False):
    recipient = get_recipient(Recipient.STREAM, stream.id)
    maybe_sub = Subscription.objects.filter(user_profile=user_profile,
                                            recipient=recipient)
    if len(maybe_sub) == 0:
        return False
    subscription = maybe_sub[0]
    did_remove = subscription.active
    subscription.active = False
    with transaction.atomic():
        subscription.save(update_fields=["active"])
        vacant_after = stream.num_subscribers() == 0

    if vacant_after and did_remove and not stream.invite_only:
        event = dict(type="stream", op="vacate",
                     streams=[stream.to_dict()])
        send_event(event, active_user_ids(user_profile.realm))

    if did_remove:
        notify_subscriptions_removed(user_profile, [stream], no_log)

    return did_remove

def log_subscription_property_change(user_email, stream_name, property, value):
    event = {'type': 'subscription_property',
             'property': property,
             'user': user_email,
             'stream_name': stream_name,
             'value': value}
    log_event(event)

def do_change_subscription_property(user_profile, sub, stream_name,
                                    property_name, value):
    setattr(sub, property_name, value)
    sub.save(update_fields=[property_name])
    log_subscription_property_change(user_profile.email, stream_name,
                                     property_name, value)

    event = dict(type="subscription",
                 op="update",
                 email=user_profile.email,
                 property=property_name,
                 value=value,
                 name=stream_name)
    send_event(event, [user_profile.id])

def do_activate_user(user_profile, log=True, join_date=timezone.now()):
    user_profile.is_active = True
    user_profile.is_mirror_dummy = False
    user_profile.set_unusable_password()
    user_profile.date_joined = join_date
    user_profile.save(update_fields=["is_active", "date_joined", "password",
                                     "is_mirror_dummy"])

    if log:
        domain = user_profile.realm.domain
        log_event({'type': 'user_activated',
                   'user': user_profile.email,
                   'domain': domain})

    notify_created_user(user_profile)

def do_reactivate_user(user_profile):
    # Unlike do_activate_user, this is meant for re-activating existing users,
    # so it doesn't reset their password, etc.
    user_profile.is_active = True
    user_profile.save(update_fields=["is_active"])

    domain = user_profile.realm.domain
    log_event({'type': 'user_reactivated',
               'user': user_profile.email,
               'domain': domain})

    notify_created_user(user_profile)

def do_change_password(user_profile, password, log=True, commit=True,
                       hashed_password=False):
    if hashed_password:
        # This is a hashed password, not the password itself.
        user_profile.set_password(password)
    else:
        user_profile.set_password(password)
    if commit:
        user_profile.save(update_fields=["password"])
    if log:
        log_event({'type': 'user_change_password',
                   'user': user_profile.email,
                   'pwhash': user_profile.password})

def do_change_full_name(user_profile, full_name, log=True):
    user_profile.full_name = full_name
    user_profile.save(update_fields=["full_name"])
    if log:
        log_event({'type': 'user_change_full_name',
                   'user': user_profile.email,
                   'full_name': full_name})

    payload = dict(email=user_profile.email,
                   full_name=user_profile.full_name)
    send_event(dict(type='realm_user', op='update', person=payload),
               active_user_ids(user_profile.realm))
    if user_profile.is_bot:
        send_event(dict(type='realm_bot', op='update', bot=payload),
                   bot_owner_userids(user_profile))

def do_regenerate_api_key(user_profile, log=True):
    user_profile.api_key = random_api_key()
    user_profile.save(update_fields=["api_key"])

    if log:
        log_event({'type': 'user_change_api_key',
                   'user': user_profile.email})

    if user_profile.is_bot:
        send_event(dict(type='realm_bot',
                        op='update',
                        bot=dict(email=user_profile.email,
                                api_key=user_profile.api_key,)),
                    bot_owner_userids(user_profile))

def do_change_avatar_source(user_profile, avatar_source, log=True):
    user_profile.avatar_source = avatar_source
    user_profile.save(update_fields=["avatar_source"])

    if log:
        log_event({'type': 'user_change_avatar_source',
                   'user': user_profile.email,
                   'avatar_source': avatar_source})

    if user_profile.is_bot:
        send_event(dict(type='realm_bot',
                        op='update',
                        bot=dict(email=user_profile.email,
                                avatar_url=avatar_url(user_profile),)),
                    bot_owner_userids(user_profile))

def _default_stream_permision_check(user_profile, stream):
    # Any user can have a None default stream
    if stream is not None:
        if user_profile.is_bot:
            user = user_profile.bot_owner
        else:
            user = user_profile
        if stream.invite_only and not subscribed_to_stream(user, stream):
            raise JsonableError('Insufficient permission')

def do_change_default_sending_stream(user_profile, stream, log=True):
    _default_stream_permision_check(user_profile, stream)

    user_profile.default_sending_stream = stream
    user_profile.save(update_fields=['default_sending_stream'])
    if log:
        log_event({'type': 'user_change_default_sending_stream',
                   'user': user_profile.email,
                   'stream': str(stream)})
    if user_profile.is_bot:
        if stream:
            stream_name = stream.name
        else:
            stream_name = None
        send_event(dict(type='realm_bot',
                        op='update',
                        bot=dict(email=user_profile.email,
                                default_sending_stream=stream_name,)),
                    bot_owner_userids(user_profile))

def do_change_default_events_register_stream(user_profile, stream, log=True):
    _default_stream_permision_check(user_profile, stream)

    user_profile.default_events_register_stream = stream
    user_profile.save(update_fields=['default_events_register_stream'])
    if log:
        log_event({'type': 'user_change_default_events_register_stream',
                   'user': user_profile.email,
                   'stream': str(stream)})
    if user_profile.is_bot:
        if stream:
            stream_name = stream.name
        else:
            stream_name = None
        send_event(dict(type='realm_bot',
                        op='update',
                        bot=dict(email=user_profile.email,
                                 default_events_register_stream=stream_name,)),
                    bot_owner_userids(user_profile))

def do_change_default_all_public_streams(user_profile, value, log=True):
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
                                default_all_public_streams=user_profile.default_all_public_streams,)),
                    bot_owner_userids(user_profile))

def do_change_is_admin(user_profile, value, permission='administer'):
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
                                 is_admin=value))
        send_event(event, active_user_ids(user_profile.realm))

def do_make_stream_public(user_profile, realm, stream_name):
    stream_name = stream_name.strip()
    stream = get_stream(stream_name, realm)

    if not stream:
        raise JsonableError('Unknown stream "%s"' % (stream_name,))

    if not subscribed_to_stream(user_profile, stream):
        raise JsonableError('You are not invited to this stream.')

    stream.invite_only = False
    stream.save(update_fields=['invite_only'])
    return {}

def do_make_stream_private(realm, stream_name):
    stream_name = stream_name.strip()
    stream = get_stream(stream_name, realm)

    if not stream:
        raise JsonableError('Unknown stream "%s"' % (stream_name,))

    stream.invite_only = True
    stream.save(update_fields=['invite_only'])
    return {}

def do_rename_stream(realm, old_name, new_name, log=True):
    old_name = old_name.strip()
    new_name = new_name.strip()

    stream = get_stream(old_name, realm)

    if not stream:
        raise JsonableError('Unknown stream "%s"' % (old_name,))

    # Will raise if there's an issue.
    check_stream_name(new_name)

    if get_stream(new_name, realm) and old_name.lower() != new_name.lower():
        raise JsonableError('Stream name "%s" is already taken' % (new_name,))

    old_name = stream.name
    stream.name = new_name
    stream.save(update_fields=["name"])

    if log:
        log_event({'type': 'stream_name_change',
                   'domain': realm.domain,
                   'new_name': new_name})

    recipient = get_recipient(Recipient.STREAM, stream.id)
    messages = Message.objects.filter(recipient=recipient).only("id")

    # Update the display recipient and stream, which are easy single
    # items to set.
    old_cache_key = get_stream_cache_key(old_name, realm)
    new_cache_key = get_stream_cache_key(stream.name, realm)
    if old_cache_key != new_cache_key:
        cache_delete(old_cache_key)
        cache_set(new_cache_key, stream)
    cache_set(display_recipient_cache_key(recipient.id), stream.name)

    # Delete cache entries for everything else, which is cheaper and
    # clearer than trying to set them. display_recipient is the out of
    # date field in all cases.
    cache_delete_many(message_cache_key(message.id) for message in messages)
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
            name=old_name
        )
        send_event(event, stream_user_ids(stream))

    # Even though the token doesn't change, the web client needs to update the
    # email forwarding address to display the correctly-escaped new name.
    return {"email_address": new_email}

def do_change_stream_description(realm, stream_name, new_description):
    stream = get_stream(stream_name, realm)
    stream.description = new_description
    stream.save(update_fields=['description'])

    event = dict(type='stream', op='update',
                 property='description', name=stream_name,
                 value=new_description)
    send_event(event, stream_user_ids(stream))
    return {}

def do_create_realm(domain, name, restricted_to_domain=True):
    realm = get_realm(domain)
    created = not realm
    if created:
        realm = Realm(domain=domain, name=name,
                      restricted_to_domain=restricted_to_domain)
        realm.save()

        # Create stream once Realm object has been saved
        notifications_stream, _ = create_stream_if_needed(realm, Realm.DEFAULT_NOTIFICATION_STREAM_NAME)
        realm.notifications_stream = notifications_stream
        realm.save(update_fields=['notifications_stream'])

        # Include a welcome message in this notifications stream
        product_name = "Zulip"
        content = """Hello, and welcome to %s!

This is a message on stream `%s` with the topic `welcome`. We'll use this stream for system-generated notifications.""" % (product_name, notifications_stream.name,)
        msg = internal_prep_message(settings.WELCOME_BOT, 'stream',
                                     notifications_stream.name, "welcome",
                                     content, realm=realm)
        do_send_messages([msg])

        # Log the event
        log_event({"type": "realm_created",
                   "domain": domain,
                   "restricted_to_domain": restricted_to_domain})

        if settings.NEW_USER_BOT is not None:
            signup_message = "Signups enabled"
            if not restricted_to_domain:
                signup_message += " (open realm)"
            internal_send_message(settings.NEW_USER_BOT, "stream",
                                  "signups", domain, signup_message)
    return (realm, created)

def do_change_enable_stream_desktop_notifications(user_profile,
                                                  enable_stream_desktop_notifications,
                                                  log=True):
    user_profile.enable_stream_desktop_notifications = enable_stream_desktop_notifications
    user_profile.save(update_fields=["enable_stream_desktop_notifications"])
    event = {'type': 'update_global_notifications',
             'user': user_profile.email,
             'notification_name': 'enable_stream_desktop_notifications',
             'setting': enable_stream_desktop_notifications}
    if log:
        log_event(event)
    send_event(event, [user_profile.id])

def do_change_enable_stream_sounds(user_profile, enable_stream_sounds, log=True):
    user_profile.enable_stream_sounds = enable_stream_sounds
    user_profile.save(update_fields=["enable_stream_sounds"])
    event = {'type': 'update_global_notifications',
             'user': user_profile.email,
             'notification_name': 'enable_stream_sounds',
             'setting': enable_stream_sounds}
    if log:
        log_event(event)
    send_event(event, [user_profile.id])

def do_change_enable_desktop_notifications(user_profile, enable_desktop_notifications, log=True):
    user_profile.enable_desktop_notifications = enable_desktop_notifications
    user_profile.save(update_fields=["enable_desktop_notifications"])
    event = {'type': 'update_global_notifications',
             'user': user_profile.email,
             'notification_name': 'enable_desktop_notifications',
             'setting': enable_desktop_notifications}
    if log:
        log_event(event)
    send_event(event, [user_profile.id])

def do_change_enable_sounds(user_profile, enable_sounds, log=True):
    user_profile.enable_sounds = enable_sounds
    user_profile.save(update_fields=["enable_sounds"])
    event = {'type': 'update_global_notifications',
             'user': user_profile.email,
             'notification_name': 'enable_sounds',
             'setting': enable_sounds}
    if log:
        log_event(event)
    send_event(event, [user_profile.id])

def do_change_enable_offline_email_notifications(user_profile, offline_email_notifications, log=True):
    user_profile.enable_offline_email_notifications = offline_email_notifications
    user_profile.save(update_fields=["enable_offline_email_notifications"])
    event = {'type': 'update_global_notifications',
             'user': user_profile.email,
             'notification_name': 'enable_offline_email_notifications',
             'setting': offline_email_notifications}
    if log:
        log_event(event)
    send_event(event, [user_profile.id])

def do_change_enable_offline_push_notifications(user_profile, offline_push_notifications, log=True):
    user_profile.enable_offline_push_notifications = offline_push_notifications
    user_profile.save(update_fields=["enable_offline_push_notifications"])
    event = {'type': 'update_global_notifications',
             'user': user_profile.email,
             'notification_name': 'enable_offline_push_notifications',
             'setting': offline_push_notifications}
    if log:
        log_event(event)
    send_event(event, [user_profile.id])

def do_change_enable_digest_emails(user_profile, enable_digest_emails, log=True):
    user_profile.enable_digest_emails = enable_digest_emails
    user_profile.save(update_fields=["enable_digest_emails"])

    if not enable_digest_emails:
        # Remove any digest emails that have been enqueued.
        clear_followup_emails_queue(user_profile.email)

    event = {'type': 'update_global_notifications',
             'user': user_profile.email,
             'notification_name': 'enable_digest_emails',
             'setting': enable_digest_emails}
    if log:
        log_event(event)
    send_event(event, [user_profile.id])

def do_change_autoscroll_forever(user_profile, autoscroll_forever, log=True):
    user_profile.autoscroll_forever = autoscroll_forever
    user_profile.save(update_fields=["autoscroll_forever"])

    if log:
        log_event({'type': 'autoscroll_forever',
                   'user': user_profile.email,
                   'autoscroll_forever': autoscroll_forever})

def do_change_enter_sends(user_profile, enter_sends):
    user_profile.enter_sends = enter_sends
    user_profile.save(update_fields=["enter_sends"])

def do_change_default_desktop_notifications(user_profile, default_desktop_notifications):
    user_profile.default_desktop_notifications = default_desktop_notifications
    user_profile.save(update_fields=["default_desktop_notifications"])

def do_change_twenty_four_hour_time(user_profile, setting_value, log=True):
    user_profile.twenty_four_hour_time = setting_value
    user_profile.save(update_fields=["twenty_four_hour_time"])
    event = {'type': 'update_display_settings',
             'user': user_profile.email,
             'setting_name': 'twenty_four_hour_time',
             'setting': setting_value}
    if log:
        log_event(event)
    send_event(event, [user_profile.id])

def do_change_left_side_userlist(user_profile, setting_value, log=True):
    user_profile.left_side_userlist = setting_value
    user_profile.save(update_fields=["left_side_userlist"])
    event = {'type': 'update_display_settings',
             'user': user_profile.email,
             'setting_name':'left_side_userlist',
             'setting': setting_value}
    if log:
        log_event(event)
    send_event(event, [user_profile.id])

def set_default_streams(realm, stream_names):
    DefaultStream.objects.filter(realm=realm).delete()
    for stream_name in stream_names:
        stream, _ = create_stream_if_needed(realm, stream_name)
        DefaultStream.objects.create(stream=stream, realm=realm)

    # Always include the realm's default notifications streams, if it exists
    if realm.notifications_stream is not None:
        DefaultStream.objects.get_or_create(stream=realm.notifications_stream, realm=realm)

    log_event({'type': 'default_streams',
               'domain': realm.domain,
               'streams': stream_names})

def do_add_default_stream(realm, stream_name):
    stream, _ = create_stream_if_needed(realm, stream_name)
    if DefaultStream.objects.filter(realm=realm, stream=stream).exists():
        return {}
    DefaultStream.objects.create(realm=realm, stream=stream)
    return {}

def do_remove_default_stream(realm, stream_name):
    stream = get_stream(stream_name, realm)
    if stream is None:
        raise JsonableError("Stream does not exist")
    DefaultStream.objects.filter(realm=realm, stream=stream).delete()
    return {}

def get_default_streams_for_realm(realm):
    return [default.stream for default in
            DefaultStream.objects.select_related("stream", "stream__realm").filter(realm=realm)]

def get_default_subs(user_profile):
    # Right now default streams are realm-wide.  This wrapper gives us flexibility
    # to some day further customize how we set up default streams for new users.
    return get_default_streams_for_realm(user_profile.realm)

def do_update_user_activity_interval(user_profile, log_time):
    effective_end = log_time + datetime.timedelta(minutes=15)

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
    (activity, created) = UserActivity.objects.get_or_create(
        user_profile = user_profile,
        client = client,
        query = query,
        defaults={'last_visit': log_time, 'count': 0})

    activity.count += 1
    activity.last_visit = log_time
    activity.save(update_fields=["last_visit", "count"])

def send_presence_changed(user_profile, presence):
    presence_dict = presence.to_dict()
    event = dict(type="presence", email=user_profile.email,
                 server_timestamp=time.time(),
                 presence={presence_dict['client']: presence.to_dict()})
    send_event(event, active_user_ids(user_profile.realm))

def consolidate_client(client):
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

    if not user_profile.realm.domain == "mit.edu" and (created or became_online):
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
    event={'user_profile_id': user_profile.id,
           'time': datetime_to_timestamp(log_time)}
    queue_json_publish("user_activity_interval", event,
                       lambda e: do_update_user_activity_interval(user_profile, log_time))

def update_user_presence(user_profile, client, log_time, status,
                         new_user_input):
    event={'user_profile_id': user_profile.id,
           'status': status,
           'time': datetime_to_timestamp(log_time),
           'client': client.name}

    queue_json_publish("user_presence", event,
                       lambda e: do_update_user_presence(user_profile, client,
                                                         log_time, status))

    if new_user_input:
        update_user_activity_interval(user_profile, log_time)

def do_update_pointer(user_profile, pointer, update_flags=False):
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

def do_update_message_flags(user_profile, operation, flag, messages, all):
    flagattr = getattr(UserMessage.flags, flag)

    if all:
        log_statsd_event('bankruptcy')
        msgs = UserMessage.objects.filter(user_profile=user_profile)
    else:
        msgs = UserMessage.objects.filter(user_profile=user_profile,
                                          message__id__in=messages)
        # Hack to let you star any message
        if msgs.count() == 0:
            if not len(messages) == 1:
                raise JsonableError("Invalid message(s)")
            if flag != "starred":
                raise JsonableError("Invalid message(s)")
            # Check that the user could have read the relevant message
            try:
                message = Message.objects.get(id=messages[0])
            except Message.DoesNotExist:
                raise JsonableError("Invalid message(s)")
            recipient = Recipient.objects.get(id=message.recipient_id)
            if recipient.type != Recipient.STREAM:
                raise JsonableError("Invalid message(s)")
            stream = Stream.objects.select_related("realm").get(id=recipient.type_id)
            if not stream.is_public():
                raise JsonableError("Invalid message(s)")

            # OK, this is a message that you legitimately have access
            # to via narrowing to the stream it is on, even though you
            # didn't actually receive it.  So we create a historical,
            # read UserMessage message row for you to star.
            UserMessage.objects.create(user_profile=user_profile,
                                       message=message,
                                       flags=UserMessage.flags.historical | UserMessage.flags.read)

    # The filter() statements below prevent postgres from doing a lot of
    # unnecessary work, which is a big deal for users updating lots of
    # flags (e.g. bankruptcy).  This patch arose from seeing slow calls
    # to POST /json/messages/flags in the logs.  The filter() statements
    # are kind of magical; they are actually just testing the one bit.
    if operation == 'add':
        msgs = msgs.filter(flags=~flagattr)
        count = msgs.update(flags=F('flags').bitor(flagattr))
    elif operation == 'remove':
        msgs = msgs.filter(flags=flagattr)
        count = msgs.update(flags=F('flags').bitand(~flagattr))

    event = {'type': 'update_message_flags',
             'operation': operation,
             'flag': flag,
             'messages': messages,
             'all': all}
    log_event(event)
    send_event(event, [user_profile.id])

    statsd.incr("flags.%s.%s" % (flag, operation), count)

def subscribed_to_stream(user_profile, stream):
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
    if len(content) > max_length:
        content = content[:max_length - len(truncation_message)] + truncation_message
    return content

def truncate_body(body):
    return truncate_content(body, MAX_MESSAGE_LENGTH, "...")

def truncate_topic(topic):
    return truncate_content(topic, MAX_SUBJECT_LENGTH, "...")


def update_user_message_flags(message, ums):
    wildcard = message.mentions_wildcard
    mentioned_ids = message.mentions_user_ids
    ids_with_alert_words = message.user_ids_with_alert_words
    changed_ums = set()

    def update_flag(um, should_set, flag):
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


def do_update_message(user_profile, message_id, subject, propagate_mode, content):
    try:
        message = Message.objects.select_related().get(id=message_id)
    except Message.DoesNotExist:
        raise JsonableError("Unknown message id")

    event = {'type': 'update_message',
             'sender': user_profile.email,
             'message_id': message_id}
    edit_history_event = {}
    changed_messages = [message]

    # You can only edit a message if:
    # 1. You sent it, OR:
    # 2. This is a topic-only edit for a (no topic) message, OR:
    # 3. This is a topic-only edit and you are an admin.
    if message.sender == user_profile:
        pass
    elif (content is None) and ((message.subject == "(no topic)") or
                                user_profile.is_realm_admin):
        pass
    else:
        raise JsonableError("You don't have permission to edit this message")

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

    ums = UserMessage.objects.filter(message=message_id)

    if content is not None:
        if len(content.strip()) == 0:
            content = "(deleted)"
        content = truncate_body(content)
        rendered_content = message.render_markdown(content)

        if not rendered_content:
            raise JsonableError("We were unable to render your updated message")

        update_user_message_flags(message, ums)

        # We are turning off diff highlighting everywhere until ticket #1532 is addressed.
        if False:
            # Don't highlight message edit diffs on prod
            rendered_content = highlight_html_differences(first_rendered_content, rendered_content)

        event['orig_content'] = message.content
        event['orig_rendered_content'] = message.rendered_content
        edit_history_event["prev_content"] = message.content
        edit_history_event["prev_rendered_content"] = message.rendered_content
        edit_history_event["prev_rendered_content_version"] = message.rendered_content_version
        message.content = content
        message.set_rendered_content(rendered_content)
        event["content"] = content
        event["rendered_content"] = rendered_content

    if subject is not None:
        orig_subject = message.subject
        subject = subject.strip()
        if subject == "":
            raise JsonableError("Topic can't be empty")
        subject = truncate_topic(subject)
        event["orig_subject"] = orig_subject
        event["propagate_mode"] = propagate_mode
        message.subject = subject
        event["stream_id"] = message.recipient.type_id
        event["subject"] = subject
        event['subject_links'] = bugdown.subject_links(message.sender.realm.domain.lower(), subject)
        edit_history_event["prev_subject"] = orig_subject


        if propagate_mode in ["change_later", "change_all"]:
            propagate_query = Q(recipient = message.recipient, subject = orig_subject)
            # We only change messages up to 2 days in the past, to avoid hammering our
            # DB by changing an unbounded amount of messages
            if propagate_mode == 'change_all':
                before_bound = now() - datetime.timedelta(days=2)

                propagate_query = propagate_query & ~Q(id = message.id) & \
                                                     Q(pub_date__range=(before_bound, now()))
            if propagate_mode == 'change_later':
                propagate_query = propagate_query & Q(id__gt = message.id)

            messages = Message.objects.filter(propagate_query).select_related();

            # Evaluate the query before running the update
            messages_list = list(messages)
            messages.update(subject=subject)

            for m in messages_list:
                # The cached ORM object is not changed by messages.update()
                # and the remote cache update requires the new value
                m.subject = subject

            changed_messages += messages_list

    message.last_edit_time = timezone.now()
    event['edit_timestamp'] = datetime_to_timestamp(message.last_edit_time)
    edit_history_event['timestamp'] = event['edit_timestamp']
    if message.edit_history is not None:
        edit_history.insert(0, edit_history_event)
    else:
        edit_history = [edit_history_event]
    message.edit_history = ujson.dumps(edit_history)

    log_event(event)
    message.save(update_fields=["subject", "content", "rendered_content",
                                "rendered_content_version", "last_edit_time",
                                "edit_history"])

    # Update the message as stored in the (deprecated) message
    # cache (for shunting the message over to Tornado in the old
    # get_messages API) and also the to_dict caches.
    items_for_remote_cache = {}
    event['message_ids'] = []
    for changed_message in changed_messages:
        event['message_ids'].append(changed_message.id)
        items_for_remote_cache[message_cache_key(changed_message.id)] = (changed_message,)
        items_for_remote_cache[to_dict_cache_key(changed_message, True)] = \
            (stringify_message_dict(changed_message.to_dict_uncached(apply_markdown=True)),)
        items_for_remote_cache[to_dict_cache_key(changed_message, False)] = \
            (stringify_message_dict(changed_message.to_dict_uncached(apply_markdown=False)),)
    cache_set_many(items_for_remote_cache)

    def user_info(um):
        return {
            'id': um.user_profile_id,
            'flags': um.flags_list()
        }
    send_event(event, list(map(user_info, ums)))

def encode_email_address(stream):
    return encode_email_address_helper(stream.name, stream.email_token)

def encode_email_address_helper(name, email_token):
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
    pattern_parts = [re.escape(part) for part in settings.EMAIL_GATEWAY_PATTERN.split('%s')]
    if settings.ZULIP_COM:
        # Accept mails delivered to any Zulip server
        pattern_parts[-1] = r'@[\w-]*\.zulip\.net'
    match_email_re = re.compile("(.*?)".join(pattern_parts))
    match = match_email_re.match(address)

    if not match:
        return None

    msg_string = match.group(1)

    return msg_string

def decode_email_address(email):
    # Perform the reverse of encode_email_address. Returns a tuple of (streamname, email_token)
    msg_string = get_email_gateway_message_string_from_address(email)

    if '.' in msg_string:
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
def gather_subscriptions_helper(user_profile):
    sub_dicts = Subscription.objects.select_related("recipient").filter(
        user_profile    = user_profile,
        recipient__type = Recipient.STREAM).values(
        "recipient__type_id", "in_home_view", "color", "desktop_notifications",
        "audible_notifications", "active")

    stream_ids = [sub["recipient__type_id"] for sub in sub_dicts]

    stream_dicts = get_active_streams(user_profile.realm).select_related(
        "realm").filter(id__in=stream_ids).values(
        "id", "name", "invite_only", "realm_id", "realm__domain", "email_token", "description")
    stream_hash = {}
    for stream in stream_dicts:
        stream_hash[stream["id"]] = stream

    subscribed = []
    unsubscribed = []

    # Deactivated streams aren't in stream_hash.
    streams = [stream_hash[sub["recipient__type_id"]] for sub in sub_dicts \
                   if sub["recipient__type_id"] in stream_hash]
    streams_subscribed_map = dict((sub["recipient__type_id"], sub["active"]) for sub in sub_dicts)
    subscriber_map = bulk_get_subscriber_user_ids(streams, user_profile, streams_subscribed_map)

    for sub in sub_dicts:
        stream = stream_hash.get(sub["recipient__type_id"])
        if not stream:
            # This stream has been deactivated, don't include it.
            continue

        subscribers = subscriber_map[stream["id"]]

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
                       'stream_id': stream["id"],
                       'description': stream["description"],
                       'email_address': encode_email_address_helper(stream["name"], stream["email_token"])}
        if subscribers is not None:
            stream_dict['subscribers'] = subscribers
        if sub["active"]:
            subscribed.append(stream_dict)
        else:
            unsubscribed.append(stream_dict)

    user_ids = set()
    for subs in [subscribed, unsubscribed]:
        for sub in subs:
            if 'subscribers' in sub:
                for subscriber in sub['subscribers']:
                    user_ids.add(subscriber)
    email_dict = get_emails_from_user_ids(list(user_ids))
    return (sorted(subscribed, key=lambda x: x['name']),
            sorted(unsubscribed, key=lambda x: x['name']),
            email_dict)

def gather_subscriptions(user_profile):
    subscribed, unsubscribed, email_dict = gather_subscriptions_helper(user_profile)
    for subs in [subscribed, unsubscribed]:
        for sub in subs:
            if 'subscribers' in sub:
                sub['subscribers'] = [email_dict[user_id] for user_id in sub['subscribers']]

    return (subscribed, unsubscribed)

def get_status_dict(requesting_user_profile):
    # Return no status info for MIT
    if requesting_user_profile.realm.domain == 'mit.edu':
        return defaultdict(dict)

    return UserPresence.get_status_dict_by_realm(requesting_user_profile.realm_id)


def get_realm_user_dicts(user_profile):
    # Due to our permission model, it is advantageous to find the admin users in bulk.
    admins = user_profile.realm.get_admin_users()
    admin_emails = set([up.email for up in admins])
    return [{'email'     : userdict['email'],
             'is_admin'  : userdict['email'] in admin_emails,
             'is_bot'    : userdict['is_bot'],
             'full_name' : userdict['full_name']}
            for userdict in get_active_user_dicts_in_realm(user_profile.realm)]

def get_realm_bot_dicts(user_profile):
    return [{'email': botdict['email'],
             'full_name': botdict['full_name'],
             'api_key': botdict['api_key'],
             'default_sending_stream': botdict['default_sending_stream__name'],
             'default_events_register_stream': botdict['default_events_register_stream__name'],
             'default_all_public_streams': botdict['default_all_public_streams'],
             'owner': botdict['bot_owner__email'],
             'avatar_url': get_avatar_url(botdict['avatar_source'], botdict['email']),
            }
            for botdict in get_active_bot_dicts_in_realm(user_profile.realm)]

# Fetch initial data.  When event_types is not specified, clients want
# all event types.  Whenever you add new code to this function, you
# should also add corresponding events for changes in the data
# structures and new code to apply_events (and add a test in EventsRegisterTest).
def fetch_initial_state_data(user_profile, event_types, queue_id):
    state = {'queue_id': queue_id}

    if event_types is None:
        want = lambda msg_type: True
    else:
        want = set(event_types).__contains__

    if want('alert_words'):
        state['alert_words'] = user_alert_words(user_profile)

    if want('message'):
        # The client should use get_old_messages() to fetch messages
        # starting with the max_message_id.  They will get messages
        # newer than that ID via get_events()
        messages = Message.objects.filter(usermessage__user_profile=user_profile).order_by('-id')[:1]
        if messages:
            state['max_message_id'] = messages[0].id
        else:
            state['max_message_id'] = -1

    if want('muted_topics'):
        state['muted_topics'] = ujson.loads(user_profile.muted_topics)

    if want('pointer'):
        state['pointer'] = user_profile.pointer

    if want('presence'):
        state['presences'] = get_status_dict(user_profile)

    if want('realm'):
        state['realm_name'] = user_profile.realm.name
        state['realm_restricted_to_domain'] = user_profile.realm.restricted_to_domain
        state['realm_invite_required'] = user_profile.realm.invite_required
        state['realm_invite_by_admins_only'] = user_profile.realm.invite_by_admins_only

    if want('realm_domain'):
        state['realm_domain'] = user_profile.realm.domain

    if want('realm_emoji'):
        state['realm_emoji'] = user_profile.realm.get_emoji()

    if want('realm_filters'):
        state['realm_filters'] = realm_filters_for_domain(user_profile.realm.domain)

    if want('realm_user'):
        state['realm_users'] = get_realm_user_dicts(user_profile)

    if want('realm_bot'):
        state['realm_bots'] = get_realm_bot_dicts(user_profile)

    if want('referral'):
        state['referrals'] = {'granted': user_profile.invites_granted,
                              'used': user_profile.invites_used}

    if want('subscription'):
        subscriptions, unsubscribed, email_dict = gather_subscriptions_helper(user_profile)
        state['subscriptions'] = subscriptions
        state['unsubscribed'] = unsubscribed
        state['email_dict'] = email_dict

    if want('update_message_flags'):
        # There's no initial data for message flag updates, client will
        # get any updates during a session from get_events()
        pass

    if want('stream'):
        state['streams'] = do_get_streams(user_profile)

    if want('update_display_settings'):
        state['twenty_four_hour_time'] = user_profile.twenty_four_hour_time
        state['left_side_userlist'] = user_profile.left_side_userlist

    return state

def apply_events(state, events, user_profile):
    for event in events:
        if event['type'] == "message":
            state['max_message_id'] = max(state['max_message_id'], event['message']['id'])
        elif event['type'] == "pointer":
            state['pointer'] = max(state['pointer'], event['pointer'])
        elif event['type'] == "realm_user":
            person = event['person']

            def our_person(p):
                return p['email'] == person['email']

            if event['op'] == "add":
                state['realm_users'].append(person)
            elif event['op'] == "remove":
                state['realm_users'] = [x for x in state['realm_users'] if not our_person(x)]
            elif event['op'] == 'update':
                for p in state['realm_users']:
                    if our_person(p):
                        p.update(person)

        elif event['type'] == 'realm_bot':
            if event['op'] == 'add':
                state['realm_bots'].append(event['bot'])

            if event['op'] == 'remove':
                email = event['bot']['email']
                state['realm_bots'] = [b for b in state['realm_bots'] if b['email'] != email]

            if event['op'] == 'update':
                for bot in state['realm_bots']:
                    if bot['email'] == event['bot']['email']:
                        bot.update(event['bot'])

        elif event['type'] == 'stream':
            if event['op'] == 'update':
                # For legacy reasons, we call stream data 'subscriptions' in
                # the state var here, for the benefit of the JS code.
                for obj in state['subscriptions']:
                    if obj['name'].lower() == event['name'].lower():
                        obj[event['property']] = event['value']
                # Also update the pure streams data
                for stream in state['streams']:
                    if stream['name'].lower() == event['name'].lower():
                        prop = event['property']
                        if prop in stream:
                            stream[prop] = event['value']
            elif event['op'] == "occupy":
                state['streams'] += event['streams']
            elif event['op'] == "vacate":
                stream_ids = [s["stream_id"] for s in event['streams']]
                state['streams'] = [s for s in state['streams'] if s["stream_id"] not in stream_ids]
        elif event['type'] == 'realm':
            field = 'realm_' + event['property']
            state[field] = event['value']
        elif event['type'] == "subscription":
            if event['op'] in ["add"]:
                # Convert the user_profile IDs to emails since that's what register() returns
                # TODO: Clean up this situation
                for item in event["subscriptions"]:
                    item["subscribers"] = [get_user_profile_by_email(email).id for email in item["subscribers"]]

            def name(sub):
                return sub['name'].lower()

            if event['op'] == "add":
                added_names = set(map(name, event["subscriptions"]))
                was_added = lambda s: name(s) in added_names

                # add the new subscriptions
                state['subscriptions'] += event['subscriptions']

                # remove them from unsubscribed if they had been there
                state['unsubscribed'] = [x for x in state['unsubscribed'] if not was_added(x)]

            elif event['op'] == "remove":
                removed_names = set(map(name, event["subscriptions"]))
                was_removed = lambda s: name(s) in removed_names

                # Find the subs we are affecting.
                removed_subs = list(filter(was_removed, state['subscriptions']))

                # Remove our user from the subscribers of the removed subscriptions.
                for sub in removed_subs:
                    sub['subscribers'] = [id for id in sub['subscribers'] if id != user_profile.id]

                # We must effectively copy the removed subscriptions from subscriptions to
                # unsubscribe, since we only have the name in our data structure.
                state['unsubscribed'] += removed_subs

                # Now filter out the removed subscriptions from subscriptions.
                state['subscriptions'] = [x for x in state['subscriptions'] if not was_removed(x)]

            elif event['op'] == 'update':
                for sub in state['subscriptions']:
                    if sub['name'].lower() == event['name'].lower():
                        sub[event['property']] = event['value']
            elif event['op'] == 'peer_add':
                user_id = get_user_profile_by_email(event['user_email']).id
                for sub in state['subscriptions']:
                    if (sub['name'] in event['subscriptions'] and
                        user_id not in sub['subscribers']):
                        sub['subscribers'].append(user_id)
            elif event['op'] == 'peer_remove':
                user_id = get_user_profile_by_email(event['user_email']).id
                for sub in state['subscriptions']:
                    if (sub['name'] in event['subscriptions'] and
                        user_id in sub['subscribers']):
                        sub['subscribers'].remove(user_id)
        elif event['type'] == "presence":
            state['presences'][event['email']] = event['presence']
        elif event['type'] == "update_message":
            # The client will get the updated message directly
            pass
        elif event['type'] == "referral":
            state['referrals'] = event['referrals']
        elif event['type'] == "update_message_flags":
            # The client will get the message with the updated flags directly
            pass
        elif event['type'] == "realm_emoji":
            state['realm_emoji'] = event['realm_emoji']
        elif event['type'] == "alert_words":
            state['alert_words'] = event['alert_words']
        elif event['type'] == "muted_topics":
            state['muted_topics'] = event["muted_topics"]
        elif event['type'] == "realm_filters":
            state['realm_filters'] = event["realm_filters"]
        elif event['type'] == "update_display_settings":
            if event['setting_name'] == "twenty_four_hour_time":
                state['twenty_four_hour_time'] = event["setting"]
            if event['setting_name'] == 'left_side_userlist':
                state['left_side_userlist'] = event["setting"]
        else:
            raise ValueError("Unexpected event type %s" % (event['type'],))

def do_events_register(user_profile, user_client, apply_markdown=True,
                       event_types=None, queue_lifespan_secs=0, all_public_streams=False,
                       narrow=[]):
    # Technically we don't need to check this here because
    # build_narrow_filter will check it, but it's nicer from an error
    # handling perspective to do it before contacting Tornado
    check_supported_events_narrow_filter(narrow)
    queue_id = request_event_queue(user_profile, user_client, apply_markdown,
                                   queue_lifespan_secs, event_types, all_public_streams,
                                   narrow=narrow)
    if queue_id is None:
        raise JsonableError("Could not allocate event queue")
    if event_types is not None:
        event_types = set(event_types)

    ret = fetch_initial_state_data(user_profile, event_types, queue_id)

    # Apply events that came in while we were fetching initial data
    events = get_user_events(user_profile, queue_id, -1)
    apply_events(ret, events, user_profile)
    if events:
        ret['last_event_id'] = events[-1]['id']
    else:
        ret['last_event_id'] = -1
    return ret

def do_send_confirmation_email(invitee, referrer):
    """
    Send the confirmation/welcome e-mail to an invited user.

    `invitee` is a PreregistrationUser.
    `referrer` is a UserProfile.
    """
    subject_template_path = 'confirmation/invite_email_subject.txt'
    body_template_path = 'confirmation/invite_email_body.txt'
    context = {'referrer': referrer,
               'support_email': settings.ZULIP_ADMINISTRATOR,
               'voyager': settings.VOYAGER}

    if referrer.realm.domain == 'mit.edu':
        subject_template_path = 'confirmation/mituser_invite_email_subject.txt'
        body_template_path = 'confirmation/mituser_invite_email_body.txt'

    Confirmation.objects.send_confirmation(
        invitee, invitee.email, additional_context=context,
        subject_template_path=subject_template_path,
        body_template_path=body_template_path)

@statsd_increment("push_notifications")
def handle_push_notification(user_profile_id, missed_message):
    try:
        user_profile = get_user_profile_by_id(user_profile_id)
        if not receives_offline_notifications(user_profile):
            return

        umessage = UserMessage.objects.get(user_profile=user_profile,
                                           message__id=missed_message['message_id'])
        message = umessage.message
        if umessage.flags.read:
            return
        sender_str = message.sender.full_name

        apple = num_push_devices_for_user(user_profile, kind=PushDeviceToken.APNS)
        android = num_push_devices_for_user(user_profile, kind=PushDeviceToken.GCM)

        if apple or android:
            #TODO: set badge count in a better way
            # Determine what alert string to display based on the missed messages
            if message.recipient.type == Recipient.HUDDLE:
                alert = "New private group message from %s" % (sender_str,)
            elif message.recipient.type == Recipient.PERSONAL:
                alert = "New private message from %s" % (sender_str,)
            elif message.recipient.type == Recipient.STREAM:
                alert = "New mention from %s" % (sender_str,)
            else:
                alert = "New Zulip mentions and private messages from %s" % (sender_str,)

            if apple:
                apple_extra_data = {'message_ids': [message.id]}
                send_apple_push_notification(user_profile, alert, badge=1, zulip=apple_extra_data)

            if android:
                content = message.content
                content_truncated = (len(content) > 200)
                if content_truncated:
                    content = content[:200] + "..."

                android_data = {
                    'user': user_profile.email,
                    'event': 'message',
                    'alert': alert,
                    'zulip_message_id': message.id, # message_id is reserved for CCS
                    'time': datetime_to_timestamp(message.pub_date),
                    'content': content,
                    'content_truncated': content_truncated,
                    'sender_email': message.sender.email,
                    'sender_full_name': message.sender.full_name,
                    'sender_avatar_url': get_avatar_url(message.sender.avatar_source, message.sender.email),
                }

                if message.recipient.type == Recipient.STREAM:
                    android_data['recipient_type'] = "stream"
                    android_data['stream'] = get_display_recipient(message.recipient)
                    android_data['topic'] = message.subject
                elif message.recipient.type in (Recipient.HUDDLE, Recipient.PERSONAL):
                    android_data['recipient_type'] = "private"

                send_android_push_notification(user_profile, android_data)

    except UserMessage.DoesNotExist:
        logging.error("Could not find UserMessage with message_id %s" %(missed_message['message_id'],))

def is_inactive(email):
    try:
        if get_user_profile_by_email(email).is_active:
            raise ValidationError(u'%s is already active' % (email,))
    except UserProfile.DoesNotExist:
        pass

def user_email_is_unique(email):
    try:
        get_user_profile_by_email(email)
        raise ValidationError(u'%s is already registered' % (email,))
    except UserProfile.DoesNotExist:
        pass

def do_invite_users(user_profile, invitee_emails, streams):
    new_prereg_users = []
    errors = []
    skipped = []

    ret_error = None
    ret_error_data = {} # type: Dict[str, List[Tuple[str, str]]]

    for email in invitee_emails:
        if email == '':
            continue

        try:
            validators.validate_email(email)
        except ValidationError:
            errors.append((email, "Invalid address."))
            continue

        if not email_allowed_for_realm(email, user_profile.realm):
            errors.append((email, "Outside your domain."))
            continue

        try:
            existing_user_profile = get_user_profile_by_email(email)
        except UserProfile.DoesNotExist:
            existing_user_profile = None
        try:
            if existing_user_profile is not None and existing_user_profile.is_mirror_dummy:
                # Mirror dummy users to be activated must be inactive
                is_inactive(email)
            else:
                # Other users should not already exist at all.
                user_email_is_unique(email)
        except ValidationError:
            skipped.append((email, "Already has an account."))
            continue

        # The logged in user is the referrer.
        prereg_user = PreregistrationUser(email=email, referred_by=user_profile)

        # We save twice because you cannot associate a ManyToMany field
        # on an unsaved object.
        prereg_user.save()
        prereg_user.streams = streams
        prereg_user.save()

        new_prereg_users.append(prereg_user)

    if errors:
        ret_error = "Some emails did not validate, so we didn't send any invitations."
        ret_error_data = {'errors': errors}

    if skipped and len(skipped) == len(invitee_emails):
        # All e-mails were skipped, so we didn't actually invite anyone.
        ret_error = "We weren't able to invite anyone."
        ret_error_data = {'errors': skipped}
        return ret_error, ret_error_data

    # If we encounter an exception at any point before now, there are no unwanted side-effects,
    # since it is totally fine to have duplicate PreregistrationUsers
    for user in new_prereg_users:
        event = {"email": user.email, "referrer_email": user_profile.email}
        queue_json_publish("invites", event,
                           lambda event: do_send_confirmation_email(user, user_profile))

    if skipped:
        ret_error = "Some of those addresses are already using Zulip, \
so we didn't send them an invitation. We did send invitations to everyone else!"
        ret_error_data = {'errors': skipped}

    return ret_error, ret_error_data

def send_referral_event(user_profile):
    event = dict(type="referral",
                 referrals=dict(granted=user_profile.invites_granted,
                                used=user_profile.invites_used))
    send_event(event, [user_profile.id])

def do_refer_friend(user_profile, email):
    content = """Referrer: "%s" <%s>
Realm: %s
Referred: %s""" % (user_profile.full_name, user_profile.email, user_profile.realm.domain, email)
    subject = "Zulip referral: %s" % (email,)
    from_email = '"%s" <%s>' % (user_profile.full_name, 'referrals@zulip.com')
    to_email = '"Zulip Referrals" <zulip+referrals@zulip.com>'
    headers = {'Reply-To' : '"%s" <%s>' % (user_profile.full_name, user_profile.email,)}
    msg = EmailMessage(subject, content, from_email, [to_email], headers=headers)
    msg.send()

    referral = Referral(user_profile=user_profile, email=email)
    referral.save()
    user_profile.invites_used += 1
    user_profile.save(update_fields=['invites_used'])

    send_referral_event(user_profile)

def notify_realm_emoji(realm):
    event = dict(type="realm_emoji", op="update",
                 realm_emoji=realm.get_emoji())
    user_ids = [userdict['id'] for userdict in get_active_user_dicts_in_realm(realm)]
    send_event(event, user_ids)

def check_add_realm_emoji(realm, name, img_url):
    emoji = RealmEmoji(realm=realm, name=name, img_url=img_url)
    emoji.full_clean()
    emoji.save()
    notify_realm_emoji(realm)

def do_remove_realm_emoji(realm, name):
    RealmEmoji.objects.get(realm=realm, name=name).delete()
    notify_realm_emoji(realm)

def notify_alert_words(user_profile, words):
    event = dict(type="alert_words", alert_words=words)
    send_event(event, [user_profile.id])

def do_add_alert_words(user_profile, alert_words):
    words = add_user_alert_words(user_profile, alert_words)
    notify_alert_words(user_profile, words)

def do_remove_alert_words(user_profile, alert_words):
    words = remove_user_alert_words(user_profile, alert_words)
    notify_alert_words(user_profile, words)

def do_set_alert_words(user_profile, alert_words):
    set_user_alert_words(user_profile, alert_words)
    notify_alert_words(user_profile, alert_words)

def do_set_muted_topics(user_profile, muted_topics):
    user_profile.muted_topics = ujson.dumps(muted_topics)
    user_profile.save(update_fields=['muted_topics'])
    event = dict(type="muted_topics", muted_topics=muted_topics)
    send_event(event, [user_profile.id])

def notify_realm_filters(realm):
    realm_filters = realm_filters_for_domain(realm.domain)
    user_ids = [userdict['id'] for userdict in get_active_user_dicts_in_realm(realm)]
    event = dict(type="realm_filters", realm_filters=realm_filters)
    send_event(event, user_ids)

# NOTE: Regexes must be simple enough that they can be easily translated to JavaScript
# RegExp syntax. In addition to JS-compatible syntax, the following features are available:
#   * Named groups will be converted to numbered groups automatically
#   * Inline-regex flags will be stripped, and where possible translated to RegExp-wide flags
def do_add_realm_filter(realm, pattern, url_format_string):
    RealmFilter(realm=realm, pattern=pattern,
                url_format_string=url_format_string).save()
    notify_realm_filters(realm)

def do_remove_realm_filter(realm, pattern):
    RealmFilter.objects.get(realm=realm, pattern=pattern).delete()
    notify_realm_filters(realm)

def get_emails_from_user_ids(user_ids):
    # We may eventually use memcached to speed this up, but the DB is fast.
    return UserProfile.emails_from_ids(user_ids)

def realm_aliases(realm):
    return [alias.domain for alias in realm.realmalias_set.all()]

def get_occupied_streams(realm):
    """ Get streams with subscribers """
    subs_filter = Subscription.objects.filter(active=True, user_profile__realm=realm,
                                              user_profile__is_active=True).values('recipient_id')
    stream_ids = Recipient.objects.filter(
        type=Recipient.STREAM, id__in=subs_filter).values('type_id')

    return Stream.objects.filter(id__in=stream_ids, realm=realm, deactivated=False)

def do_get_streams(user_profile, include_public=True, include_subscribed=True,
                   include_all_active=False):
    if include_all_active and not user_profile.is_api_super_user:
        raise JsonableError("User not authorized for this query")

    # Listing public streams are disabled for the mit.edu realm.
    include_public = include_public and user_profile.realm.domain != "mit.edu"
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

    def make_dict(row):
        return dict(
            stream_id = row.id,
            name = row.name,
            description = row.description,
            invite_only = row.invite_only,
        )

    streams = [make_dict(row) for row in query]
    streams.sort(key=lambda elt: elt["name"])

    return streams
