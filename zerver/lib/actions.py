from __future__ import absolute_import

from django.conf import settings
from django.core import validators
from django.contrib.sessions.models import Session
from zerver.lib.context_managers import lockfile
from zerver.models import Realm, RealmEmoji, Stream, UserProfile, UserActivity, \
    Subscription, Recipient, Message, UserMessage, valid_stream_name, \
    DefaultStream, UserPresence, Referral, MAX_SUBJECT_LENGTH, \
    MAX_MESSAGE_LENGTH, get_client, get_stream, get_recipient, get_huddle, \
    get_user_profile_by_id, PreregistrationUser, get_display_recipient, \
    to_dict_cache_key, get_realm, stringify_message_dict, bulk_get_recipients, \
    email_to_domain, email_to_username, display_recipient_cache_key, \
    get_stream_cache_key, to_dict_cache_key_id, is_super_user, \
    get_active_user_profiles_by_realm, UserActivityInterval

from django.db import transaction, IntegrityError
from django.db.models import F, Q
from django.core.exceptions import ValidationError
from django.utils.importlib import import_module
from django.template import loader
from django.core.mail import EmailMultiAlternatives, EmailMessage
from django.utils.timezone import utc, is_naive, now

from confirmation.models import Confirmation

session_engine = import_module(settings.SESSION_ENGINE)

from zerver.lib.initial_password import initial_password
from zerver.lib.timestamp import timestamp_to_datetime, datetime_to_timestamp
from zerver.lib.cache_helpers import cache_save_message
from zerver.lib.queue import queue_json_publish
from django.utils import timezone
from zerver.lib.create_user import create_user
from zerver.lib import bugdown
from zerver.lib.cache import cache_with_key, cache_set, \
    user_profile_by_email_cache_key, cache_set_many, \
    cache_delete, cache_delete_many, message_cache_key
from zerver.decorator import get_user_profile_by_email, json_to_list, JsonableError, \
     statsd_increment
from zerver.lib.event_queue import request_event_queue, get_user_events
from zerver.lib.utils import log_statsd_event, statsd
from zerver.lib.html_diff import highlight_html_differences
from zerver.lib.alert_words import user_alert_words, add_user_alert_words, \
    remove_user_alert_words, set_user_alert_words

import confirmation.settings

from zerver import tornado_callbacks

import DNS
import ujson
import time
import traceback
import re
import datetime
import os
import platform
import logging
from collections import defaultdict
from os import path

# Store an event in the log for re-importing messages
def log_event(event):
    if "timestamp" not in event:
        event["timestamp"] = time.time()

    if not path.exists(settings.EVENT_LOG_DIR):
        os.mkdir(settings.EVENT_LOG_DIR)

    template = path.join(settings.EVENT_LOG_DIR,
        '%s.' + platform.node()
        + datetime.datetime.now().strftime('.%Y-%m-%d'))

    with lockfile(template % ('lock',)):
        with open(template % ('events',), 'a') as log:
            log.write(ujson.dumps(event) + '\n')

def active_user_ids(realm):
    return [up.id for up in get_active_user_profiles_by_realm(realm)]

def notify_created_user(user_profile):
    notice = dict(event=dict(type="realm_user", op="add",
                             person=dict(email=user_profile.email,
                                         full_name=user_profile.full_name)),
                  users=active_user_ids(user_profile.realm))
    tornado_callbacks.send_notification(notice)

def do_create_user(email, password, realm, full_name, short_name,
                   active=True, bot=False, bot_owner=None,
                   avatar_source=UserProfile.AVATAR_FROM_GRAVATAR):
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

    user_profile = create_user(email, password, realm, full_name, short_name,
                               active, bot, bot_owner, avatar_source)

    notify_created_user(user_profile)
    return user_profile

def user_sessions(user_profile):
    return [s for s in Session.objects.all()
            if s.get_decoded().get('_auth_user_id') == user_profile.id]

def delete_session(session):
    return session_engine.SessionStore(session.session_key).delete()

def delete_user_sessions(user_profile):
    for session in Session.objects.all():
        if session.get_decoded().get('_auth_user_id') == user_profile.id:
            delete_session(session)

def delete_realm_user_sessions(realm):
    realm_user_ids = [user_profile.id for user_profile in
                      UserProfile.objects.filter(realm=realm)]
    for session in Session.objects.filter(expire_date__gte=datetime.datetime.now()):
        if session.get_decoded().get('_auth_user_id') in realm_user_ids:
            delete_session(session)

def delete_all_user_sessions():
    for session in Session.objects.all():
        delete_session(session)

def do_deactivate(user_profile, log=True, _cascade=True):
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

    notice = dict(event=dict(type="realm_user", op="remove",
                             person=dict(email=user_profile.email,
                                         full_name=user_profile.full_name)),
                  users=active_user_ids(user_profile.realm))
    tornado_callbacks.send_notification(notice)

    if _cascade:
        bot_profiles = UserProfile.objects.filter(is_bot=True, is_active=True,
                                                  bot_owner=user_profile)
        for profile in bot_profiles:
            do_deactivate(profile, _cascade=False)

def do_change_user_email(user_profile, new_email):
    old_email = user_profile.email
    user_profile.email = new_email
    user_profile.save(update_fields=["email"])

    log_event({'type': 'user_email_changed',
               'old_email': old_email,
               'new_email': new_email})

def compute_mit_user_fullname(email):
    try:
        # Input is either e.g. starnine@mit.edu or user|CROSSREALM.INVALID@mit.edu
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

@cache_with_key(lambda realm, email: user_profile_by_email_cache_key(email),
                timeout=3600*24*7)
@transaction.commit_on_success
def create_mit_user_if_needed(realm, email):
    try:
        return get_user_profile_by_email(email)
    except UserProfile.DoesNotExist:
        try:
            # Forge a user for this person
            return create_user(email, initial_password(email), realm,
                               compute_mit_user_fullname(email), email_to_username(email),
                               active=False)
        except IntegrityError:
            # Unless we raced with another thread doing the same
            # thing, in which case we should get the user they made
            transaction.commit()
            return get_user_profile_by_email(email)

def log_message(message):
    if not message.sending_client.name.startswith("test:"):
        log_event(message.to_log_dict())

# Helper function. Defaults here are overriden by those set in do_send_messages
def do_send_message(message, rendered_content = None, no_log = False, stream = None):
    return do_send_messages([{'message': message,
                              'rendered_content': rendered_content,
                              'no_log': no_log,
                              'stream': stream}])[0]

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
            query = Subscription.objects.select_related("user_profile").only(
                "id", "user_profile__id", "user_profile__is_active").filter(
                recipient=message['message'].recipient, active=True)
            message['recipients'] = [s.user_profile for s in query]
        else:
            raise ValueError('Bad recipient type')

        message['message'].maybe_render_content(None)

    # Save the message receipts in the database
    user_message_flags = defaultdict(dict)
    with transaction.commit_on_success():
        Message.objects.bulk_create([message['message'] for message in messages])
        ums = []
        for message in messages:
            ums_to_create = [UserMessage(user_profile=user_profile, message=message['message'])
                             for user_profile in message['recipients']
                             if user_profile.is_active]

            # These properties on the Message are set via
            # Message.render_markdown by code in the bugdown inline patterns
            wildcard = message['message'].mentions_wildcard
            mentioned_ids = message['message'].mentions_user_ids
            ids_with_alert_words = message['message'].user_ids_with_alert_words

            for um in ums_to_create:
                sent_by_human = (message['message'].sending_client.name.lower() in \
                                    ['website', 'iphone', 'android']) or \
                                ('desktop app' in message['message'].sending_client.name.lower())
                if um.user_profile.id == message['message'].sender.id and sent_by_human:
                    um.flags |= UserMessage.flags.read
                if wildcard:
                    um.flags |= UserMessage.flags.wildcard_mentioned
                if um.user_profile_id in mentioned_ids:
                    um.flags |= UserMessage.flags.mentioned
                if um.user_profile_id in ids_with_alert_words:
                    um.flags |= UserMessage.flags.has_alert_word
                user_message_flags[message['message'].id][um.user_profile_id] = um.flags_list()
            ums.extend(ums_to_create)
        UserMessage.objects.bulk_create(ums)

    for message in messages:
        cache_save_message(message['message'])
        # Render Markdown etc. here and store (automatically) in
        # memcached, so that the single-threaded Tornado server
        # doesn't have to.
        message['message'].to_dict(apply_markdown=True)
        message['message'].to_dict(apply_markdown=False)
        user_flags = user_message_flags.get(message['message'].id, {})
        sender = message['message'].sender
        recipient_emails = [user.email for user in message['recipients']]
        user_presences = get_status_dict(sender)
        presences = {}
        for email in recipient_emails:
            if email in user_presences:
                presences[email] = user_presences[email]

        data = dict(
            type         = 'new_message',
            message      = message['message'].id,
            presences    = user_presences,
            users        = [{'id': user.id, 'flags': user_flags.get(user.id, [])}
                             for user in message['recipients']])
        if message['message'].recipient.type == Recipient.STREAM:
            # Note: This is where authorization for single-stream
            # get_updates happens! We only attach stream data to the
            # notify new_message request if it's a public stream,
            # ensuring that in the tornado server, non-public stream
            # messages are only associated to their subscribed users.
            if message['stream'] is None:
                message['stream'] = Stream.objects.select_related("realm").get(id=message['message'].recipient.type_id)
            if message['stream'].is_public():
                data['realm_id'] = message['stream'].realm.id
                data['stream_name'] = message['stream'].name
            if message['stream'].invite_only:
                data['invite_only'] = True
        tornado_callbacks.send_notification(data)

    # Note that this does not preserve the order of message ids
    # returned.  In practice, this shouldn't matter, as we only
    # mirror single zephyr messages at a time and don't otherwise
    # intermingle sending zephyr messages with other messages.
    return already_sent_ids + [message['message'].id for message in messages]

def create_stream_if_needed(realm, stream_name, invite_only=False):
    (stream, created) = Stream.objects.get_or_create(
        realm=realm, name__iexact=stream_name,
        defaults={'name': stream_name, 'invite_only': invite_only})
    if created:
        Recipient.objects.create(type_id=stream.id, type=Recipient.STREAM)
    return stream, created

def recipient_for_emails(emails, not_forged_zephyr_mirror, user_profile, sender):
    recipient_profile_ids = set()
    for email in emails:
        try:
            recipient_profile_ids.add(get_user_profile_by_email(email).id)
        except UserProfile.DoesNotExist:
            raise ValidationError("Invalid email '%s'" % (email,))

    if not_forged_zephyr_mirror and user_profile.id not in recipient_profile_ids:
        raise ValidationError("User not authorized for this query")

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

def extract_recipients(raw_recipients):
    try:
        recipients = json_to_list(raw_recipients)
    except ValueError:
        recipients = [raw_recipients]

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

# check_message:
# Returns message ready for sending with do_send_message on success or the error message (string) on error.
def check_message(sender, client, message_type_name, message_to,
                  subject_name, message_content, realm=None, forged=False,
                  forged_timestamp=None, forwarder_user_profile=None):
    stream = None
    if len(message_to) == 0:
        raise JsonableError("Message must have recipients")
    if len(message_content) > MAX_MESSAGE_LENGTH:
        raise JsonableError("Message too long")
    if len(message_content.strip()) == 0:
        raise JsonableError("Message must not be empty")

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
        if len(subject) > MAX_SUBJECT_LENGTH:
            raise JsonableError("Topic too long")
        ## FIXME: Commented out temporarily while we figure out what we want
        # if not valid_stream_name(subject):
        #     return json_error("Invalid subject name")

        stream = get_stream(stream_name, realm)

        if sender.is_bot:
            if stream:
                num_subscribers = len(maybe_get_subscribers(stream))

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
                    message = internal_prep_message("notification-bot@zulip.com", "private",
                                                    sender.bot_owner.email, "", content)
                    do_send_messages([message])

                    sender.last_reminder = timezone.now()
                    sender.save(update_fields=['last_reminder'])

        if stream is None:
            raise JsonableError("Stream does not exist")
        recipient = get_recipient(Recipient.STREAM, stream.id)

        if not stream.invite_only:
            # This is a public stream
            pass
        elif subscribed_to_stream(sender, stream):
            # Or it is private, but your are subscribed
            pass
        elif is_super_user(sender) or is_super_user(forwarder_user_profile):
            # Or this request is being done on behalf of a super user
            pass
        elif sender.is_bot and subscribed_to_stream(sender.bot_owner, stream):
            # Or you're a bot and your owner is subscribed.
            pass
        else:
            # All other cases are an error.
            raise JsonableError("Not authorized to send to stream '%s'" % (stream.name,))

    elif message_type_name == 'private':
        not_forged_zephyr_mirror = client and client.name == "zephyr_mirror" and not forged
        try:
            recipient = recipient_for_emails(message_to, not_forged_zephyr_mirror,
                                             forwarder_user_profile, sender)
        except ValidationError, e:
            assert isinstance(e.messages[0], basestring)
            raise JsonableError(e.messages[0])
    else:
        raise JsonableError("Invalid message type")

    message = Message()
    message.sender = sender
    message.content = message_content
    message.recipient = recipient
    if message_type_name == 'stream':
        message.subject = subject
    if forged:
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

    return {'message': message, 'stream': stream}

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
    except JsonableError, e:
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
    available_colors = filter(lambda x: x not in used_colors,
                              stream_assignment_colors)

    if available_colors:
        return available_colors[0]
    else:
        return stream_assignment_colors[len(used_colors) % len(stream_assignment_colors)]

def get_subscription(stream_name, user_profile):
    stream = get_stream(stream_name, user_profile.realm)
    recipient = get_recipient(Recipient.STREAM, stream.id)
    return Subscription.objects.get(user_profile=user_profile,
                                    recipient=recipient, active=True)

def get_subscribers_query(stream, realm, requesting_user):
    """ Build a query to get the subscribers list for a stream, raising a JsonableError if:
        * No stream by that name exists in the realm.
        * The realm is MIT and the stream is not invite only.
        * The stream is invite only, requesting_user is passed, and that user
          does not subscribe to the stream.

    'stream' can either be a string representing a stream name, or a Stream
    object. If it's a Stream object, 'realm' is optional.

    The caller can refine this query with select_related(), values(), etc. depending
    on whether it wants objects or just certain fields
    """

    try:
        # If a Stream object was passed, get the realm from that.
        realm = stream.realm
    except AttributeError:
        # Assume a stream name was passed. Get the corresponding Stream object.
        stream_name = stream
        stream = get_stream(stream_name, realm)
        if stream is None:
            raise JsonableError("Stream does not exist: %s" % stream_name)

    # requesting_user, if passed, shouldn't be on a different realm.
    if requesting_user is not None and requesting_user.realm != realm:
        raise ValidationError("Requesting user not on given realm")

    if realm.domain == "mit.edu" and not stream.invite_only:
        raise JsonableError("You cannot get subscribers for public streams in this realm")

    if (requesting_user is not None and stream.invite_only
            and not subscribed_to_stream(requesting_user, stream)):
        raise JsonableError("Unable to retrieve subscribers for invite-only stream")

    # Note that non-active users may still have "active" subscriptions, because we
    # want to be able to easily reactivate them with their old subscriptions.  This
    # is why the query here has to look at the UserProfile.is_active flag.
    subscriptions = Subscription.objects.filter(recipient__type=Recipient.STREAM,
                                                recipient__type_id=stream.id,
                                                user_profile__is_active=True,
                                                active=True)
    return subscriptions


def get_subscribers(stream, realm=None, requesting_user=None):
    subscriptions = get_subscribers_query(stream, realm, requesting_user).select_related()
    return [subscription.user_profile for subscription in subscriptions]

def get_subscriber_emails(stream, realm=None, requesting_user=None):
    subscriptions = get_subscribers_query(stream, realm, requesting_user)
    subscriptions = subscriptions.values('user_profile__email')
    return [subscription['user_profile__email'] for subscription in subscriptions]

def get_other_subscriber_ids(stream, user_profile_id):
    try:
        subscriptions = get_subscribers_query(stream, None, None)
    except JsonableError:
        return []

    rows = subscriptions.values('user_profile_id')
    ids = [row['user_profile_id'] for row in rows]
    return filter(lambda id: id != user_profile_id, ids)

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
    subscribes_to = {}
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

def notify_subscriptions_added(user_profile, sub_pairs, no_log=False):
    if not no_log:
        log_event({'type': 'subscription_added',
                   'user': user_profile.email,
                   'names': [stream.name for sub, stream in sub_pairs],
                   'domain': stream.realm.domain})

    # Send a notification to the user who subscribed.
    payload = [dict(name=stream.name,
                    in_home_view=subscription.in_home_view,
                    invite_only=stream.invite_only,
                    color=subscription.color,
                    email_address=encode_email_address(stream),
                    subscribers=maybe_get_subscriber_emails(stream))
            for (subscription, stream) in sub_pairs]
    notice = dict(event=dict(type="subscriptions", op="add",
                             subscriptions=payload),
                  users=[user_profile.id])
    tornado_callbacks.send_notification(notice)

def notify_peers(user_profile, sub_pairs):
    # For other users on each stream, if applicable, send a notification
    # with less info. To make this efficient in cases of bulk subscriptions,
    # we do a first pass computing which users get a notification regarding
    # which streams.
    streams = [stream for (_, stream) in sub_pairs]
    notifications_for = get_subscribers_to_streams(streams)

    for event_recipient, notifications in notifications_for.iteritems():
        # Don't send a peer subscription notice to yourself.
        if event_recipient == user_profile:
            continue

        stream_names = [stream.name for stream in notifications]
        notice = dict(event=dict(type="subscriptions", op="peer_add",
                                 subscriptions=stream_names,
                                 user_email=user_profile.email),
                      users=[event_recipient.id])
        tornado_callbacks.send_notification(notice)

def bulk_add_subscriptions(streams, users):
    recipients_map = bulk_get_recipients(Recipient.STREAM, [stream.id for stream in streams])
    recipients = [recipient.id for recipient in recipients_map.values()]

    stream_map = {}
    for stream in streams:
        stream_map[recipients_map[stream.id].id] = stream

    subs_by_user = defaultdict(list)
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
                                  color=color, recipient_id=recipient_id)
        subs_by_user[user_profile.id].append(sub_to_add)
        subs_to_add.append((sub_to_add, stream))
    Subscription.objects.bulk_create([sub for (sub, stream) in subs_to_add])
    Subscription.objects.filter(id__in=[sub.id for (sub, stream_name) in subs_to_activate]).update(active=True)

    sub_tuples_by_user = defaultdict(list)
    for (sub, stream) in subs_to_add + subs_to_activate:
        sub_tuples_by_user[sub.user_profile.id].append((sub, stream))

    for user_profile in users:
        if len(sub_tuples_by_user[user_profile.id]) == 0:
            continue
        sub_pairs = sub_tuples_by_user[user_profile.id]
        notify_subscriptions_added(user_profile, sub_pairs)
        notify_peers(user_profile, sub_pairs)

    return ([(user_profile, stream_name) for (user_profile, recipient_id, stream_name) in new_subs] +
            [(sub.user_profile, stream_name) for (sub, stream_name) in subs_to_activate],
            already_subscribed)

# When changing this, also change bulk_add_subscriptions
def do_add_subscription(user_profile, stream, no_log=False):
    recipient = get_recipient(Recipient.STREAM, stream.id)
    color = pick_color(user_profile)
    (subscription, created) = Subscription.objects.get_or_create(
        user_profile=user_profile, recipient=recipient,
        defaults={'active': True, 'color': color})
    did_subscribe = created
    if not subscription.active:
        did_subscribe = True
        subscription.active = True
        subscription.save(update_fields=["active"])

    if did_subscribe:
        notify_subscriptions_added(user_profile, [(subscription, stream)], no_log)

        user_ids = get_other_subscriber_ids(stream, user_profile.id)
        notice = dict(event=dict(type="subscriptions", op="peer_add",
                                 subscriptions=[stream.name],
                                 user_email=user_profile.email),
                      users=user_ids)
        tornado_callbacks.send_notification(notice)

    return did_subscribe

def notify_subscriptions_removed(user_profile, streams, no_log=False):
    if not no_log:
        log_event({'type': 'subscription_removed',
                   'user': user_profile.email,
                   'names': [stream.name for stream in streams],
                   'domain': stream.realm.domain})

    payload = [dict(name=stream.name) for stream in streams]
    notice = dict(event=dict(type="subscriptions", op="remove",
                             subscriptions=payload),
                  users=[user_profile.id])
    tornado_callbacks.send_notification(notice)

    # As with a subscription add, send a 'peer subscription' notice to other
    # subscribers so they know the user unsubscribed.
    # FIXME: This code is mostly a copy-paste from notify_subscriptions_added.
    notifications_for = get_subscribers_to_streams(streams)

    for event_recipient, notifications in notifications_for.iteritems():
        # Don't send a peer subscription notice to yourself.
        if event_recipient == user_profile:
            continue

        stream_names = [stream.name for stream in notifications]
        notice = dict(event=dict(type="subscriptions", op="peer_remove",
                                 subscriptions=stream_names,
                                 user_email=user_profile.email),
                      users=[event_recipient.id])
        tornado_callbacks.send_notification(notice)


def bulk_remove_subscriptions(users, streams):
    recipients_map = bulk_get_recipients(Recipient.STREAM,
                                         [stream.id for stream in streams])
    stream_map = {}
    for stream in streams:
        stream_map[recipients_map[stream.id].id] = stream

    subs_by_user = dict((user_profile.id, []) for user_profile in users)
    for sub in Subscription.objects.select_related("user_profile").filter(user_profile__in=users,
                                                                          recipient__in=recipients_map.values(),
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

    Subscription.objects.filter(id__in=[sub.id for (sub, stream_name) in
                                        subs_to_deactivate]).update(active=False)

    streams_by_user = defaultdict(list)
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
    subscription.save(update_fields=["active"])
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

    notice = dict(event=dict(type="subscriptions",
                             op="update",
                             email=user_profile.email,
                             property=property_name,
                             value=value,
                             name=stream_name,),
                  users=[user_profile.id])
    tornado_callbacks.send_notification(notice)

def do_activate_user(user_profile, log=True, join_date=timezone.now()):
    user_profile.is_active = True
    user_profile.set_password(initial_password(user_profile.email))
    user_profile.date_joined = join_date
    user_profile.save(update_fields=["is_active", "date_joined", "password"])

    if log:
        domain = user_profile.realm.domain
        log_event({'type': 'user_activated',
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

    notice = dict(event=dict(type="realm_user", op="update",
                             person=dict(email=user_profile.email,
                                         full_name=user_profile.full_name)),
                  users=active_user_ids(user_profile.realm))
    tornado_callbacks.send_notification(notice)

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

    notice = dict(event=dict(type="subscriptions", op="update", property="name",
                             name=old_name, value=new_name),
                  users=active_user_ids(realm))

    tornado_callbacks.send_notification(notice)

    # Even though the token doesn't change, the web client needs to update the
    # email forwarding address to display the correctly-escaped new name.
    return {"email_address": encode_email_address(stream)}

def do_create_realm(domain, restricted_to_domain=True):
    realm = get_realm(domain)
    created = not realm
    if created:
        realm = Realm(domain=domain, restricted_to_domain=restricted_to_domain)
        realm.save()
        # Log the event
        log_event({"type": "realm_created",
                   "domain": domain,
                   "restricted_to_domain": restricted_to_domain})

        signup_message = "Signups enabled"
        if not restricted_to_domain:
            signup_message += " (open realm)"
        internal_send_message("new-user-bot@zulip.com", "stream",
                              "signups", domain, signup_message)
    return (realm, created)

def do_change_enable_desktop_notifications(user_profile, enable_desktop_notifications, log=True):
    user_profile.enable_desktop_notifications = enable_desktop_notifications
    user_profile.save(update_fields=["enable_desktop_notifications"])
    if log:
        log_event({'type': 'enable_desktop_notifications_changed',
                   'user': user_profile.email,
                   'enable_desktop_notifications': enable_desktop_notifications})

def do_change_enable_sounds(user_profile, enable_sounds, log=True):
    user_profile.enable_sounds = enable_sounds
    user_profile.save(update_fields=["enable_sounds"])
    if log:
        log_event({'type': 'enable_sounds_changed',
                   'user': user_profile.email,
                   'enable_sounds': enable_sounds})

def do_change_enable_offline_email_notifications(user_profile, offline_email_notifications, log=True):
    user_profile.enable_offline_email_notifications = offline_email_notifications
    user_profile.save(update_fields=["enable_offline_email_notifications"])
    if log:
        log_event({'type': 'enable_offline_email_notifications_changed',
                   'user': user_profile.email,
                   'enable_offline_email_notifications': offline_email_notifications})

def do_change_enter_sends(user_profile, enter_sends):
    user_profile.enter_sends = enter_sends
    user_profile.save(update_fields=["enter_sends"])

def set_default_streams(realm, stream_names):
    DefaultStream.objects.filter(realm=realm).delete()
    for stream_name in stream_names:
        stream, _ = create_stream_if_needed(realm, stream_name)
        DefaultStream.objects.create(stream=stream, realm=realm)

def get_default_subs(user_profile):
    return [default.stream for default in
            DefaultStream.objects.select_related("stream").filter(realm=user_profile.realm)]

@statsd_increment('user_activity')
@transaction.commit_on_success
def do_update_user_activity(user_profile, client, query, log_time):
    try:
        (activity, created) = UserActivity.objects.get_or_create(
            user_profile = user_profile,
            client = client,
            query = query,
            defaults={'last_visit': log_time, 'count': 0})
    except IntegrityError:
        transaction.commit()
        activity = UserActivity.objects.get(user_profile = user_profile,
                                            client = client,
                                            query = query)
    activity.count += 1
    activity.last_visit = log_time
    activity.save(update_fields=["last_visit", "count"])

def process_user_activity_event(event):
    user_profile = get_user_profile_by_id(event["user_profile_id"])
    client = get_client(event["client"])
    log_time = timestamp_to_datetime(event["time"])
    query = event["query"]
    return do_update_user_activity(user_profile, client, query, log_time)

def send_presence_changed(user_profile, presence):
    presence_dict = presence.to_dict()
    notice = dict(event=dict(type="presence", email=user_profile.email,
                             server_timestamp=time.time(),
                             presence={presence_dict['client']: presence.to_dict()}),
                  users=active_user_ids(user_profile.realm))
    tornado_callbacks.send_notification(notice)

@statsd_increment('user_presence')
@transaction.commit_on_success
def do_update_user_presence(user_profile, client, log_time, status):
    try:
        (presence, created) = UserPresence.objects.get_or_create(
            user_profile = user_profile,
            client = client,
            defaults = {'timestamp': log_time,
                        'status': status})
    except IntegrityError:
        transaction.commit()
        presence = UserPresence.objects.get(user_profile = user_profile,
                                            client = client)
        created = False

    stale_status = (log_time - presence.timestamp) > datetime.timedelta(minutes=1, seconds=10)
    was_idle = presence.status == UserPresence.IDLE
    became_online = (status == UserPresence.ACTIVE) and (stale_status or was_idle)

    if not created:
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
    event={'type': 'user_activity_interval',
           'user_profile_id': user_profile.id,
           'time': datetime_to_timestamp(log_time)}
    queue_json_publish("user_activity", event, process_user_activity_interval_event)

def update_user_presence(user_profile, client, log_time, status,
                         new_user_input):
    event={'type': 'user_presence',
           'user_profile_id': user_profile.id,
           'status': status,
           'time': datetime_to_timestamp(log_time),
           'client': client.name}

    queue_json_publish("user_activity", event, process_user_presence_event)

    if new_user_input:
        update_user_activity_interval(user_profile, log_time)

def do_update_message_flags(user_profile, operation, flag, messages, all):
    flagattr = getattr(UserMessage.flags, flag)

    if all:
        log_statsd_event('bankruptcy')
        msgs = UserMessage.objects.filter(user_profile=user_profile)
    else:
        msgs = UserMessage.objects.filter(user_profile=user_profile,
                                          message__id__in=messages)

    if operation == 'add':
        count = msgs.update(flags=F('flags').bitor(flagattr))
    elif operation == 'remove':
        count = msgs.update(flags=F('flags').bitand(~flagattr))

    event = {'type': 'update_message_flags',
             'operation': operation,
             'flag': flag,
             'messages': messages,
             'all': all}
    log_event(event)
    notice = dict(event=event, users=[user_profile.id])
    tornado_callbacks.send_notification(notice)

    statsd.incr("flags.%s.%s" % (flag, operation), count)

def process_user_presence_event(event):
    user_profile = get_user_profile_by_id(event["user_profile_id"])
    client = get_client(event["client"])
    log_time = timestamp_to_datetime(event["time"])
    status = event["status"]
    return do_update_user_presence(user_profile, client, log_time, status)

def process_user_activity_interval_event(event):
    user_profile = get_user_profile_by_id(event["user_profile_id"])
    log_time = timestamp_to_datetime(event["time"])

    effective_end = log_time + datetime.timedelta(minutes=15)
    try:
        last = UserActivityInterval.objects.filter(user_profile=user_profile).order_by("-end")[0]
        if log_time < last.end:
            last.end = effective_end
            last.save(update_fields=["end"])
            return
    except IndexError:
        pass

    UserActivityInterval.objects.create(user_profile=user_profile, start=log_time,
                                        end=effective_end)

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

def do_update_onboarding_steps(user_profile, steps):
    user_profile.onboarding_steps = ujson.dumps(steps)
    user_profile.save(update_fields=["onboarding_steps"])

    log_event({'type': 'update_onboarding',
               'user': user_profile.email,
               'steps': steps})

    notice = dict(event=dict(type="onboarding_steps", steps=steps),
                  users=[user_profile.id])
    tornado_callbacks.send_notification(notice)

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

    if message.sender != user_profile:
        if not (message.subject == "(no topic)" and content is None):
            raise JsonableError("Message was not sent by you")

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

    if content is not None:
        if len(content.strip()) == 0:
            content = "(deleted)"
        if len(content) > MAX_MESSAGE_LENGTH:
            raise JsonableError("Message too long")
        rendered_content = message.render_markdown(content)
        if not rendered_content:
            raise JsonableError("We were unable to render your updated message")

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

        if len(subject) > MAX_SUBJECT_LENGTH:
            raise JsonableError("Topic too long")
        event["orig_subject"] = orig_subject
        message.subject = subject
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
                # and the memcached update requires the new value
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

    # Update the message as stored in both the (deprecated) message
    # cache (for shunting the message over to Tornado in the old
    # get_messages API) and also the to_dict caches.
    items_for_memcached = {}
    event['message_ids'] = []
    for changed_message in changed_messages:
        event['message_ids'].append(changed_message.id)
        items_for_memcached[message_cache_key(changed_message.id)] = (changed_message,)
        items_for_memcached[to_dict_cache_key(changed_message, True)] = \
            (stringify_message_dict(changed_message.to_dict_uncached(apply_markdown=True)),)
        items_for_memcached[to_dict_cache_key(changed_message, False)] = \
            (stringify_message_dict(changed_message.to_dict_uncached(apply_markdown=False)),)
    cache_set_many(items_for_memcached)

    recipients = [um.user_profile_id for um in UserMessage.objects.filter(message=message_id)]
    notice = dict(event=event, users=recipients)
    tornado_callbacks.send_notification(notice)

def encode_email_address(stream):
    # Given the fact that we have almost no restrictions on stream names and
    # that what characters are allowed in e-mail addresses is complicated and
    # dependent on context in the address, we opt for a very simple scheme:
    #
    # Only encode the stream name (leave the + and token alone). Encode
    # everything that isn't alphanumeric plus _ as the percent-prefixed integer
    # ordinal of that character, padded with zeroes to the maximum number of
    # bytes of a UTF-8 encoded Unicode character.
    encoded_name = re.sub("\W", lambda x: "%" + str(ord(x.group(0))).zfill(4),
                          stream.name)
    return "%s+%s@streams.zulip.com" % (encoded_name, stream.email_token)

def decode_email_address(email):
    # Perform the reverse of encode_email_address. Only the stream name will be
    # transformed.
    return re.sub("%\d{4}", lambda x: unichr(int(x.group(0)[1:])), email)

def gather_subscriptions(user_profile):
    # For now, don't display subscriptions for private messages.
    subs = Subscription.objects.select_related().filter(
        user_profile    = user_profile,
        recipient__type = Recipient.STREAM)

    stream_ids = [sub.recipient.type_id for sub in subs]

    stream_hash = {}
    for stream in Stream.objects.filter(id__in=stream_ids):
        stream_hash[stream.id] = stream

    subscribed = []
    unsubscribed = []

    for sub in subs:
        stream = stream_hash[sub.recipient.type_id]
        try:
            subscribers = get_subscriber_emails(stream)
        except JsonableError:
            subscribers = None

        # Important: don't show the subscribers if the stream is invite only
        # and this user isn't on it anymore.
        if stream.invite_only and not sub.active:
            subscribers = None

        stream = {'name': stream.name,
                  'in_home_view': sub.in_home_view,
                  'invite_only': stream.invite_only,
                  'color': sub.color,
                  'notifications': sub.notifications,
                  'email_address': encode_email_address(stream)}
        if subscribers is not None:
            stream['subscribers'] = subscribers
        if sub.active:
            subscribed.append(stream)
        else:
            unsubscribed.append(stream)

    return (sorted(subscribed), sorted(unsubscribed))

def get_status_dict(requesting_user_profile):
    # Return no status info for MIT
    if requesting_user_profile.realm.domain == 'mit.edu':
        return defaultdict(dict)

    return UserPresence.get_status_dict_by_realm(requesting_user_profile.realm_id)


def do_events_register(user_profile, user_client, apply_markdown=True,
                       event_types=None, queue_lifespan_secs=0):
    queue_id = request_event_queue(user_profile, user_client, apply_markdown,
                                   queue_lifespan_secs, event_types)
    if queue_id is None:
        raise JsonableError("Could not allocate event queue")

    ret = {'queue_id': queue_id}
    if event_types is not None:
        event_types = set(event_types)

    # Fetch initial data.  When event_types is not specified, clients
    # want all event types.
    if event_types is None or "message" in event_types:
        # The client should use get_old_messages() to fetch messages
        # starting with the max_message_id.  They will get messages
        # newer than that ID via get_events()
        messages = Message.objects.filter(usermessage__user_profile=user_profile).order_by('-id')[:1]
        if messages:
            ret['max_message_id'] = messages[0].id
        else:
            ret['max_message_id'] = -1
    if event_types is None or "pointer" in event_types:
        ret['pointer'] = user_profile.pointer
    if event_types is None or "realm_user" in event_types:
        ret['realm_users'] = [{'email'     : profile.email,
                               'is_bot'    : profile.is_bot,
                               'full_name' : profile.full_name}
                              for profile in get_active_user_profiles_by_realm(user_profile.realm)]
    if event_types is None or "onboarding_steps" in event_types:
        ret['onboarding_steps'] = [{'email' : profile.email,
                                    'steps' : profile.onboarding_steps}]
    if event_types is None or "subscription" in event_types:
        subs = gather_subscriptions(user_profile)
        ret['subscriptions'] = subs[0]
        ret['unsubscribed'] = subs[1]
    if event_types is None or "presence" in event_types:
        ret['presences'] = get_status_dict(user_profile)
    if event_types is None or "referral" in event_types:
        ret['referrals'] = {'granted': user_profile.invites_granted,
                            'used': user_profile.invites_used}
    if event_types is None or "update_message_flags" in event_types:
        # There's no initial data for message flag updates, client will
        # get any updates during a session from get_events()
        pass
    if event_types is None or "realm_emoji" in event_types:
        ret['realm_emoji'] = user_profile.realm.get_emoji()
    if event_types is None or "alert_words" in event_types:
        ret['alert_words'] = user_alert_words(user_profile)

    # Apply events that came in while we were fetching initial data
    events = get_user_events(user_profile, queue_id, -1)
    for event in events:
        if event['type'] == "message":
            ret['max_message_id'] = max(ret['max_message_id'], event['message']['id'])
        elif event['type'] == "pointer":
            ret['pointer'] = max(ret['pointer'], event['pointer'])
        elif event['type'] == "onboarding_steps":
            ret['onboarding_steps'] = event['steps']
        elif event['type'] == "realm_user":
            # We handle update by just removing the old value and
            # adding the new one.
            if event['op'] == "remove" or event['op'] == "update":
                person = event['person']
                ret['realm_users'] = filter(lambda p: p['email'] != person['email'],
                                            ret['realm_users'])
            if event['op'] == "add" or event['op'] == "update":
                ret['realm_users'].append(event['person'])
        elif event['type'] == "subscriptions":
            if event['op'] in ["add", "remove"]:
                subscriptions_to_filter = set(sub.name.lower() for sub in event["subscriptions"])
            # We add the new subscriptions to the list of streams the
            # user is subscribed to, and also remove/add them from the
            # list of streams the user is not subscribed to (which we
            # are still sending on data about so that e.g. colors and
            # the in_home_view bit are properly available for those streams)
            #
            # And we do the opposite filtering process for unsubscribe events.
            if event['op'] == "add":
                ret['subscriptions'] += event['subscriptions']
                ret['unsubscribed'] = filter(lambda s: s['name'].lower() not in subscriptions_to_filter,
                                             ret['unsubscribed'])
            elif event['op'] == "remove":
                ret['unsubscribed'] += event['subscriptions']
                ret['subscriptions'] = filter(lambda s: s['name'].lower() not in subscriptions_to_filter,
                                              ret['subscriptions'])
            elif event['op'] == 'update':
                for sub in ret['subscriptions']:
                    if sub['name'].lower() == event['name'].lower():
                        sub[event['property']] = event['value']
            elif event['op'] == 'peer_add':
                for sub in ret['subscriptions']:
                    if (sub['name'] in event['subscriptions'] and
                            event['user_email'] not in sub['subscribers']):
                        sub['subscribers'].append(event['user_email'])
            elif event['op'] == 'peer_remove':
                for sub in ret['subscriptions']:
                    if (sub['name'] in event['subscriptions'] and
                            event['user_email'] in sub['subscribers']):
                        sub['subscribers'].remove(event['user_email'])
        elif event['type'] == "presence":
            ret['presences'][event['email']] = event['presence']
        elif event['type'] == "update_message":
            # The client will get the updated message directly
            pass
        elif event['type'] == "referral":
            ret['referrals'] = event['referrals']
        elif event['type'] == "update_message_flags":
            # The client will get the message with the updated flags directly
            pass
        elif event['type'] == "realm_emoji":
            ret['realm_emoji'] = event['realm_emoji']
        elif event['type'] == "alert_words":
            ret['alert_words'] = event['alert_words']
        else:
            raise ValueError("Unexpected event type %s" % (event['type'],))

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
    Confirmation.objects.send_confirmation(
        invitee, invitee.email, additional_context={'referrer': referrer},
        subject_template_path='confirmation/invite_email_subject.txt',
        body_template_path='confirmation/invite_email_body.txt')

def build_message_list(user_profile, messages):
    """
    Builds the message list object for the missed message email template.
    The messages are collapsed into per-recipient and per-sender blocks, like
    our web interface
    """
    messages_to_render = []

    def sender_string(message):
        sender = ''
        if message.recipient.type in (Recipient.STREAM, Recipient.HUDDLE):
            sender = message.sender.full_name
        return sender

    def build_message_payload(message):
        return {'plain': message.content,
                'html': message.rendered_content}

    def build_sender_payload(message):
        sender = sender_string(message)
        return {'sender': sender,
                'content': [build_message_payload(message)]}

    def message_header(user_profile, message):
        disp_recipient = get_display_recipient(message.recipient)
        if message.recipient.type == Recipient.PERSONAL:
            header = "You and %s" % (message.sender.full_name)
        elif message.recipient.type == Recipient.HUDDLE:
            other_recipients = [r['full_name'] for r in disp_recipient
                                    if r['email'] != user_profile.email]
            header = "You and %s" % (", ".join(other_recipients),)
        else:
            header = "%s > %s" % (disp_recipient, message.subject)
        return header

    # # Collapse message list to
    # [
    #    {
    #       "header":"xxx",
    #       "senders":[
    #          {
    #             "sender":"sender_name",
    #             "content":[
    #                {
    #                   "plain":"content",
    #                   "html":"htmlcontent"
    #                }
    #                {
    #                   "plain":"content",
    #                   "html":"htmlcontent"
    #                }
    #             ]
    #          }
    #       ]
    #    },
    # ]

    for message in messages:
        header = message_header(user_profile, message)

        # If we want to collapse into the previous recipient block
        if len(messages_to_render) > 0 and messages_to_render[-1]['header'] == header:
            sender = sender_string(message)
            sender_block = messages_to_render[-1]['senders']

            # Same message sender, collapse again
            if sender_block[-1]['sender'] == sender:
                sender_block[-1]['content'].append(build_message_payload(message))
            else:
                # Start a new sender block
                sender_block.append(build_sender_payload(message))
        else:
            # New recipient and sender block
            recipient_block = {'header': header,
                               'senders': [build_sender_payload(message)]}

            messages_to_render.append(recipient_block)

    return messages_to_render

@statsd_increment("missed_message_reminders")
def do_send_missedmessage_email(user_profile, missed_messages):
    """
    Send a reminder email to a user if she's missed some PMs by being offline

    `user_profile` is the user to send the reminder to
    `missed_messages` is a list of Message objects to remind about
    """
    template_payload = {'name': user_profile.full_name,
                        'messages': build_message_list(user_profile, missed_messages),
                        'message_count': len(missed_messages),
                        'url': 'https://zulip.com',
                        'reply_warning': False}

    senders = set(m.sender.full_name for m in missed_messages)
    sender_str = ", ".join(senders)

    headers = {}
    if all(msg.recipient.type in (Recipient.HUDDLE, Recipient.PERSONAL)
            for msg in missed_messages):
        # If we have one huddle, set a reply-to to all of the members
        # of the huddle except the user herself
        disp_recipients = [", ".join(recipient['email']
                                for recipient in get_display_recipient(msg.recipient)
                                    if recipient['email'] != user_profile.email)
                                 for msg in missed_messages]
        if all(msg.recipient.type == Recipient.HUDDLE for msg in missed_messages) and \
            len(set(disp_recipients)) == 1:
            headers['Reply-To'] = disp_recipients[0]
        elif len(senders) == 1:
            headers['Reply-To'] = missed_messages[0].sender.email
        else:
            template_payload['reply_warning'] = True
    else:
        # There are some @-mentions mixed in with personals
        template_payload['mention'] = True
        template_payload['reply_warning'] = True
        headers['Reply-To'] = "Nobody <noreply@zulip.com>"

    subject = "Missed Zulip%s from %s" % ('s' if len(senders) > 1 else '', sender_str)
    from_email = "%s (via Zulip) <noreply@zulip.com>" % (sender_str)

    text_content = loader.render_to_string('zerver/missed_message_email.txt', template_payload)
    html_content = loader.render_to_string('zerver/missed_message_email_html.txt', template_payload)

    msg = EmailMultiAlternatives(subject, text_content, from_email, [user_profile.email],
                                 headers = headers)
    msg.attach_alternative(html_content, "text/html")
    msg.send()

    user_profile.last_reminder = datetime.datetime.now()
    user_profile.save(update_fields=['last_reminder'])

def handle_missedmessage_emails(user_profile_id, missed_email_events):
    message_ids = [event.get('message_id') for event in missed_email_events]
    timestamp = timestamp_to_datetime(event.get('timestamp'))

    user_profile = get_user_profile_by_id(user_profile_id)
    messages = [um.message for um in UserMessage.objects.filter(user_profile=user_profile,
                                                                message__id__in=message_ids,
                                                                flags=~UserMessage.flags.read)]

    last_reminder = user_profile.last_reminder_tzaware()

    waitperiod = datetime.timedelta(hours=UserProfile.EMAIL_REMINDER_WAITPERIOD)
    if len(messages) == 0 or (last_reminder and \
                              timestamp - last_reminder < waitperiod):
        # Don't spam the user, if we've sent an email in the last day
        return

    do_send_missedmessage_email(user_profile, messages)


def user_email_is_unique(value):
    try:
        get_user_profile_by_email(value)
        raise ValidationError(u'%s is already registered' % value)
    except UserProfile.DoesNotExist:
        pass

def do_invite_users(user_profile, invitee_emails, streams):
    new_prereg_users = []
    errors = []
    skipped = []

    ret_error = None
    ret_error_data = {}

    for email in invitee_emails:
        if email == '':
            continue

        try:
            validators.validate_email(email)
        except ValidationError:
            errors.append((email, "Invalid address."))
            continue

        if user_profile.realm.restricted_to_domain and \
                email_to_domain(email).lower() != user_profile.realm.domain.lower():
            errors.append((email, "Outside your domain."))
            continue

        # Redundant check in case earlier validation preventing MIT users from
        # inviting people fails.
        if "@mit.edu" in email:
            errors.append((email, "Invitations are not enabled for MIT at this time."))
            continue

        try:
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
    notice = dict(event=dict(type="referral",
                             referrals=dict(granted=user_profile.invites_granted,
                                            used=user_profile.invites_used)),
                  users=[user_profile.id])
    tornado_callbacks.send_notification(notice)

def do_refer_friend(user_profile, email):
    content = """Referrer: "%s" <%s>
Realm: %s
Referred: %s""" % (user_profile.full_name, user_profile.email, user_profile.realm.domain, email)
    subject = "Zulip referral: %s" % (email,)
    from_email = '"%s" <referral-bot@zulip.com>' % (user_profile.full_name,)
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
    notice = dict(event=dict(type="realm_emoji", op="update",
                             realm_emoji=realm.get_emoji()),
                  users=[up.id for up in get_active_user_profiles_by_realm(realm)])
    tornado_callbacks.send_notification(notice)

def do_add_realm_emoji(realm, name, img_url):
    RealmEmoji(realm=realm, name=name, img_url=img_url).save()
    notify_realm_emoji(realm)

def do_remove_realm_emoji(realm, name):
    RealmEmoji.objects.get(realm=realm, name=name).delete()
    notify_realm_emoji(realm)

def notify_alert_words(user_profile, words):
    notice = dict(event=dict(type="alert_words", alert_words=words),
                  users=[user_profile.id])
    tornado_callbacks.send_notification(notice)

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
    notice = dict(event=dict(type="muted_topics", muted_topics=muted_topics),
                  users=[user_profile.id])
    tornado_callbacks.send_notification(notice)
