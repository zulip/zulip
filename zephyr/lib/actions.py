from __future__ import absolute_import

from django.conf import settings
from django.contrib.sessions.models import Session
from zephyr.lib.context_managers import lockfile
from zephyr.models import Realm, Stream, UserProfile, UserActivity, \
    Subscription, Recipient, Message, UserMessage, valid_stream_name, \
    DefaultStream, UserPresence, MAX_SUBJECT_LENGTH, \
    MAX_MESSAGE_LENGTH, get_client, get_stream, get_recipient, get_huddle, \
    get_user_profile_by_id, PreregistrationUser, get_display_recipient, \
    to_dict_cache_key, get_realm
from django.db import transaction, IntegrityError
from django.db.models import F, Q
from django.core.exceptions import ValidationError
from django.utils.importlib import import_module
from django.template import loader
from django.core.mail import EmailMultiAlternatives

from confirmation.models import Confirmation

session_engine = import_module(settings.SESSION_ENGINE)

from zephyr.lib.initial_password import initial_password
from zephyr.lib.timestamp import timestamp_to_datetime, datetime_to_timestamp
from zephyr.lib.cache_helpers import cache_save_message
from zephyr.lib.queue import queue_json_publish
from django.utils import timezone
from zephyr.lib.create_user import create_user
from zephyr.lib import bugdown
from zephyr.lib.cache import cache_with_key, \
    user_profile_by_email_cache_key, status_dict_cache_key, cache_set_many
from zephyr.decorator import get_user_profile_by_email, json_to_list, JsonableError, \
     statsd_increment
from zephyr.lib.event_queue import request_event_queue, get_user_events
from zephyr.lib.utils import log_statsd_event, statsd
from zephyr.lib.html_diff import highlight_html_differences

import confirmation.settings

from zephyr import tornado_callbacks

import subprocess
import simplejson
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
            log.write(simplejson.dumps(event) + '\n')

def do_create_user(email, password, realm, full_name, short_name,
                   active=True, bot=False, bot_owner=None):
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
                               active, bot, bot_owner)

    notice = dict(event=dict(type="realm_user", op="add",
                             person=dict(email=user_profile.email,
                                         full_name=user_profile.full_name)),
                  users=[up.id for up in
                         UserProfile.objects.select_related().filter(realm=user_profile.realm,
                                                                     is_active=True)])
    tornado_callbacks.send_notification(notice)
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
    for session in Session.objects.all():
        if session.get_decoded().get('_auth_user_id') in realm_user_ids:
            delete_session(session)

def delete_all_user_sessions():
    for session in Session.objects.all():
        delete_session(session)

def do_deactivate(user_profile):
    user_profile.is_active = False;
    user_profile.set_unusable_password()
    user_profile.save(update_fields=["is_active", "password"])

    delete_user_sessions(user_profile)

    log_event({'type': 'user_deactivated',
               'timestamp': time.time(),
               'user': user_profile.email,
               'domain': user_profile.realm.domain})

    notice = dict(event=dict(type="realm_user", op="remove",
                             person=dict(email=user_profile.email,
                                         full_name=user_profile.full_name)),
                  users=[up.id for up in
                         UserProfile.objects.select_related().filter(realm=user_profile.realm,
                                                                     is_active=True)])
    tornado_callbacks.send_notification(notice)


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
            dns_query = "%s.passwd.ns.athena.mit.edu" % (match_user.group(1),)
            proc = subprocess.Popen(['host', '-t', 'TXT', dns_query],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            out, _err_unused = proc.communicate()
            if proc.returncode == 0:
                # Parse e.g. 'starnine:*:84233:101:Athena Consulting Exchange User,,,:/mit/starnine:/bin/bash'
                # for the 4th passwd entry field, aka the person's name.
                hesiod_name = out.split(':')[4].split(',')[0].strip()
                if hesiod_name == "":
                    return email
                return hesiod_name
        elif match_user:
            return match_user.group(1).lower() + "@" + match_user.group(2).upper()[1:]
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
                               compute_mit_user_fullname(email), email.split("@")[0],
                               active=False)
        except IntegrityError:
            # Unless we raced with another thread doing the same
            # thing, in which case we should get the user they made
            transaction.commit()
            return get_user_profile_by_email(email)

def log_message(message):
    if not message.sending_client.name.startswith("test:"):
        log_event(message.to_log_dict())

# Match multi-word string between @** ** or match any one-word
# sequences after @
find_mentions_re = re.compile(r'\B@(?:\*\*([^\*]+)\*\*)|@(\w+)')

def mentioned_in_message(message):
    # Determine what, if any, users are mentioned with an @-notification
    # in this message
    #
    # TODO(leo) There is a minor regression in that we no longer
    # match just-first-names or just-last-names
    wildcards = ['all', 'everyone']

    potential_mentions = find_mentions_re.findall(message.content)
    # Either the first or the second group matched something, take the
    # one that did (find_all returns a list with each item containing all groups)
    potential_mentions = map(lambda elem: elem[0] or elem[1], potential_mentions)

    users = set()
    for mention in potential_mentions:
        if mention in wildcards:
            return (True, set())

        attempts = [Q(full_name__iexact=mention), Q(short_name__iexact=mention)]
        found = False
        for attempt in attempts:
            ups = UserProfile.objects.filter(attempt, realm=message.sender.realm)
            for user in ups:
                users.add(user)
            found = len(ups) > 0
            break

        if found:
            continue

    return (False, users)

# Helper function. Defaults here are overriden by those set in do_send_messages
def do_send_message(message, rendered_content = None, no_log = False, stream = None):
    do_send_messages([{'message': message,
                       'rendered_content': rendered_content,
                       'no_log': no_log,
                       'stream': stream}])

def do_send_messages(messages):
    # Filter out messages which didn't pass internal_prep_message properly
    messages = [message for message in messages if message is not None]

    # Filter out zephyr mirror anomalies where the message was already sent
    messages = [message for message in messages if message['message'] is not None]

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
            message['recipients'] = [s.user_profile for
                                     s in Subscription.objects.select_related(
                    "user_profile").filter(recipient=message['message'].recipient, active=True)]
        else:
            raise ValueError('Bad recipient type')

    # Save the message receipts in the database
    user_message_flags = defaultdict(dict)
    with transaction.commit_on_success():
        Message.objects.bulk_create([message['message'] for message in messages])
        ums = []
        for message in messages:
            ums_to_create = [UserMessage(user_profile=user_profile, message=message['message'])
                             for user_profile in message['recipients']
                             if user_profile.is_active]
            for um in ums_to_create:
                wildcard, mentioned = mentioned_in_message(message['message'])
                sent_by_human = message['message'].sending_client.name.lower() in \
                                    ['website', 'iphone', 'android']
                if um.user_profile == message['message'].sender and sent_by_human:
                    um.flags |= UserMessage.flags.read
                if wildcard:
                    um.flags |= UserMessage.flags.wildcard_mentioned
                if um.user_profile in mentioned:
                    um.flags |= UserMessage.flags.mentioned
                user_message_flags[message['message'].id][um.user_profile] = um.flags_dict().get('flags')
            ums.extend(ums_to_create)
        UserMessage.objects.bulk_create(ums)

    for message in messages:
        cache_save_message(message['message'])

    # We can only publish messages to longpolling clients if the Tornado server is running.
    if settings.TORNADO_SERVER:
        for message in messages:
            # Render Markdown etc. here and store (automatically) in
            # memcached, so that the single-threaded Tornado server
            # doesn't have to.
            message['message'].to_dict(apply_markdown=True, rendered_content=message['rendered_content'])
            message['message'].to_dict(apply_markdown=False)
            user_flags = user_message_flags.get(message['message'].id, {})
            data = dict(
                type     = 'new_message',
                message  = message['message'].id,
                users    = [{'id': user.id, 'flags': user_flags.get(user, [])} for user in message['recipients']])
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
            tornado_callbacks.send_notification(data)

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

def already_sent_mirrored_message(message):
    if message.recipient.type == Recipient.HUDDLE:
        # For huddle messages, we use a 10-second window because the
        # timestamps aren't guaranteed to actually match between two
        # copies of the same message.
        time_window = datetime.timedelta(seconds=10)
    else:
        time_window = datetime.timedelta(seconds=0)

    # Since our database doesn't store timestamps with
    # better-than-second resolution, we should do our comparisons
    # using objects at second resolution
    pub_date_lowres = message.pub_date.replace(microsecond=0)
    return Message.objects.filter(
        sender=message.sender,
        recipient=message.recipient,
        content=message.content,
        subject=message.subject,
        sending_client=message.sending_client,
        pub_date__gte=pub_date_lowres - time_window,
        pub_date__lte=pub_date_lowres + time_window).exists()

def extract_recipients(raw_recipients):
    try:
        recipients = json_to_list(raw_recipients)
    except (simplejson.decoder.JSONDecodeError, ValueError):
        recipients = [raw_recipients]

    # Strip recipients, and then remove any duplicates and any that
    # are the empty string after being stripped.
    recipients = [recipient.strip() for recipient in recipients]
    return list(set(recipient for recipient in recipients if recipient))

# check_send_message:
# Returns None on success or the error message on error.
# has same argspec as check_message
def check_send_message(*args, **kwargs):
    message = check_message(*args, **kwargs)
    if(type(message) != dict):
        assert isinstance(message, basestring)
        return message
    do_send_messages([message])
    return None

# check_message:
# Returns message ready for sending with do_send_message on success or the error message (string) on error.
def check_message(sender, client, message_type_name, message_to,
                  subject_name, message_content, realm=None, forged=False,
                  forged_timestamp=None, forwarder_user_profile=None):
    stream = None
    if len(message_to) == 0:
        return "Message must have recipients."
    if len(message_content) > MAX_MESSAGE_LENGTH:
        return "Message too long."

    if realm is None:
        realm = sender.realm

    if message_type_name == 'stream':
        if len(message_to) > 1:
            return "Cannot send to multiple streams"

        stream_name = message_to[0].strip()
        if stream_name == "":
            return "Stream can't be empty"
        if len(stream_name) > Stream.MAX_NAME_LENGTH:
            return "Stream name too long"
        if not valid_stream_name(stream_name):
            return "Invalid stream name"

        if subject_name is None:
            return "Missing subject"
        subject = subject_name.strip()
        if subject == "":
            return "Subject can't be empty"
        if len(subject) > MAX_SUBJECT_LENGTH:
            return "Subject too long"
        ## FIXME: Commented out temporarily while we figure out what we want
        # if not valid_stream_name(subject):
        #     return json_error("Invalid subject name")

        stream = get_stream(stream_name, realm)
        if stream is None:
            return "Stream does not exist"
        recipient = get_recipient(Recipient.STREAM, stream.id)

        if (stream.invite_only
            and ((not sender.is_bot and not subscribed_to_stream(sender, stream))
                 or (sender.is_bot and not (subscribed_to_stream(sender.bot_owner, stream)
                                            or subscribed_to_stream(sender, stream))))):
            return "Not authorized to send to stream '%s'" % (stream.name,)
    elif message_type_name == 'private':
        not_forged_zephyr_mirror = client and client.name == "zephyr_mirror" and not forged
        try:
            recipient = recipient_for_emails(message_to, not_forged_zephyr_mirror,
                                             forwarder_user_profile, sender)
        except ValidationError, e:
            assert isinstance(e.messages[0], basestring)
            return e.messages[0]
    else:
        return "Invalid message type"

    rendered_content = bugdown.convert(message_content, sender.realm.domain)
    if rendered_content is None:
        return "We were unable to render your message"

    message = Message()
    message.sender = sender
    message.content = message_content
    message.rendered_content = rendered_content
    message.rendered_content_version = bugdown.version
    message.recipient = recipient
    if message_type_name == 'stream':
        message.subject = subject
    if forged:
        # Forged messages come with a timestamp
        message.pub_date = timestamp_to_datetime(forged_timestamp)
    else:
        message.pub_date = timezone.now()
    message.sending_client = client

    if client.name == "zephyr_mirror" and already_sent_mirrored_message(message):
        return {'message': None}

    return {'message': message, 'rendered_content': rendered_content,
            'stream': stream}

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

    ret = check_message(sender, get_client("Internal"), recipient_type_name,
                        parsed_recipients, subject, content, realm)
    if isinstance(ret, basestring):
        logging.error("Error queueing internal message by %s: %s" % (sender_email, ret))
    elif isinstance(ret, dict):
        return ret
    else:
        logging.error("Error queueing internal message; check message return unexpected type: %s" \
                      % (repr(ret),))

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

def set_stream_color(user_profile, stream_name, color=None):
    subscription = get_subscription(stream_name, user_profile)
    if not color:
        color = pick_color(user_profile)
    subscription.color = color
    subscription.save(update_fields=["color"])
    return color

def notify_new_subscription(user_profile, stream, subscription, no_log=False):
    if not no_log:
        log_event({'type': 'subscription_added',
                   'user': user_profile.email,
                   'name': stream.name,
                   'domain': stream.realm.domain})

    notice = dict(event=dict(type="subscription", op="add",
                             subscription=dict(name=stream.name,
                                               in_home_view=subscription.in_home_view,
                                               invite_only=stream.invite_only,
                                               color=subscription.color)),
                  users=[user_profile.id])
    tornado_callbacks.send_notification(notice)

# This function assumes that the users are known to not be subscribers
# of the stream (e.g. because the stream was created by this same query)
def bulk_add_subscriptions(stream, users):
    recipient = get_recipient(Recipient.STREAM, stream.id)
    all_subs = Subscription.objects.filter(user_profile__in=users,
                                           recipient__type=Recipient.STREAM)

    subs_by_user = defaultdict(list)
    for sub in all_subs:
        subs_by_user[sub.user_profile_id].append(sub)

    already_subscribed = []
    subs_to_activate = []
    users_needing_new_subs = []
    for user_profile in users:
        needs_new_sub = True
        for sub in subs_by_user[user_profile.id]:
            if sub.recipient_id == recipient.id:
                needs_new_sub = False
                if sub.active:
                    already_subscribed.append(user_profile)
                else:
                    subs_to_activate.append(sub)
        if needs_new_sub:
            users_needing_new_subs.append(user_profile)

    subs_to_add = []
    for user_profile in users_needing_new_subs:
        color = pick_color_helper(user_profile, subs_by_user[user_profile.id])
        subs_to_add.append(Subscription(user_profile=user_profile,
                                        active=True, color=color,
                                        recipient=recipient))
    Subscription.objects.bulk_create(subs_to_add)
    Subscription.objects.filter(id__in=[s.id for s in subs_to_activate]).update(active=True)

    for sub in subs_to_add + subs_to_activate:
        notify_new_subscription(sub.user_profile, stream, sub)
    return (users_needing_new_subs + [sub.user_profile for sub in subs_to_activate],
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
        notify_new_subscription(user_profile, stream, subscription, no_log)
    return did_subscribe

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
        if not no_log:
            log_event({'type': 'subscription_removed',
                       'user': user_profile.email,
                       'name': stream.name,
                       'domain': stream.realm.domain})

        notice = dict(event=dict(type="subscription", op="remove",
                                 subscription=dict(name=stream.name)),
                      users=[user_profile.id])
        tornado_callbacks.send_notification(notice)

    return did_remove

def log_subscription_property_change(user_email, stream_name, property, value):
    event = {'type': 'subscription_property',
             'property': property,
             'user': user_email,
             'stream_name': stream_name,
             'value': value}
    log_event(event)

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
        internal_send_message("humbug+signups@humbughq.com", "stream",
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
            DefaultStream.objects.filter(realm=user_profile.realm)]

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
    user_profile = UserProfile.objects.get(id=event["user_profile_id"])
    client = get_client(event["client"])
    log_time = timestamp_to_datetime(event["time"])
    query = event["query"]
    return do_update_user_activity(user_profile, client, query, log_time)

def send_presence_changed(user_profile, presence):
    presence_dict = presence.to_dict()
    notice = dict(event=dict(type="presence", email=user_profile.email,
                             server_timestamp=time.time(),
                             presence={presence_dict['client']: presence.to_dict()}),
                  users=[up.id for up in
                         UserProfile.objects.select_related()
                                            .filter(realm=user_profile.realm,
                                                    is_active=True)])
    tornado_callbacks.send_notification(notice)

@statsd_increment('user_presence')
@transaction.commit_on_success
def do_update_user_presence(user_profile, client, log_time, status):
    try:
        (presence, created) = UserPresence.objects.get_or_create(
            user_profile = user_profile,
            client = client,
            defaults = {'timestamp': log_time})
    except IntegrityError:
        transaction.commit()
        presence = UserPresence.objects.get(user_profile = user_profile,
                                            client = client)
        created = False

    stale_status = (log_time - presence.timestamp) > datetime.timedelta(minutes=10)
    was_idle = presence.status == UserPresence.IDLE
    became_online = (status == UserPresence.ACTIVE) and (stale_status or was_idle)

    presence.timestamp = log_time
    presence.status = status
    presence.save(update_fields=["timestamp", "status"])

    if not user_profile.realm.domain == "mit.edu" and (created or became_online):
        # Push event to all users in the realm so they see the new user
        # appear in the presence list immediately, or the newly online
        # user without delay
        send_presence_changed(user_profile, presence)

def update_user_presence(user_profile, client, log_time, status):
    event={'type': 'user_presence',
           'user_profile_id': user_profile.id,
           'status': status,
           'time': datetime_to_timestamp(log_time),
           'client': client.name}

    queue_json_publish("user_activity", event, process_user_presence_event)

def update_message_flags(user_profile, operation, flag, messages, all):
    rest_until = None

    if all:
        log_statsd_event('bankruptcy')

        # Do the first 450 message updates in-process, as this is a
        # bankruptcy request and the user is about to reload. We don't
        # want them to see a bunch of unread messages while we go about
        # doing the work
        first_batch = 450
        flagattr = getattr(UserMessage.flags, flag)

        all_ums = UserMessage.objects.filter(user_profile=user_profile)
        if operation == "add":
            umessages = all_ums.filter(flags=~flagattr)
        elif operation == "remove":
            umessages = all_ums.filter(flags=flagattr)

        mids = [m.id for m in umessages.order_by('-id')[:first_batch]]
        to_update = UserMessage.objects.filter(id__in=mids)

        if operation == "add":
            to_update.update(flags=F('flags').bitor(flagattr))
        elif operation == "remove":
            to_update.update(flags=F('flags').bitand(~flagattr))

        if len(mids) == 0:
            return True

        rest_until = mids[len(mids) - 1]

    event = {'type':            'update_message',
             'user_profile_id': user_profile.id,
             'operation':       operation,
             'flag':            flag,
             'messages':        messages,
             'until_id':        rest_until}
    queue_json_publish("user_activity", event, process_update_message_flags)

def process_user_presence_event(event):
    user_profile = UserProfile.objects.get(id=event["user_profile_id"])
    client = get_client(event["client"])
    log_time = timestamp_to_datetime(event["time"])
    status = event["status"]
    return do_update_user_presence(user_profile, client, log_time, status)

def process_update_message_flags(event):
    user_profile = UserProfile.objects.get(id=event["user_profile_id"])
    try:
        until_id = event["until_id"]
        messages = event["messages"]
        flag = event["flag"]
        op = event["operation"]
    except (KeyError, AttributeError):
        return False

    # Shell out bankruptcy requests as we split them up into many
    # pieces to avoid swamping the db
    if until_id and not settings.TEST_SUITE:
        update_flags_externally(op, flag, user_profile, until_id)
        return True

    flagattr = getattr(UserMessage.flags, flag)
    msgs = UserMessage.objects.filter(user_profile=user_profile,
                                      message__id__in=messages)

    # If we're running in the test suite, don't shell out to manage.py.
    # Updates that the manage.py command makes don't seem to be immediately
    # reflected in the next in-process sqlite queries.
    # TODO(leo) remove when tests switch to postgres
    if settings.TEST_SUITE and until_id:
        msgs = UserMessage.objects.filter(user_profile=user_profile,
                                          id__lte=until_id)

    if op == 'add':
        msgs.update(flags=F('flags').bitor(flagattr))
    elif op == 'remove':
        msgs.update(flags=F('flags').bitand(~flagattr))

    statsd.incr("flags.%s.%s" % (flag, op), len(msgs))

    return True

def update_flags_externally(op, flag, user_profile, until_id):
    args = ['python', os.path.join(os.path.dirname(__file__), '../..', 'manage.py'),
            'set_message_flags', '--for-real', '-o', op, '-f', flag, '-m', user_profile.email,
            '-u', str(until_id)]

    subprocess.Popen(args, stdin=subprocess.PIPE, stdout=None, stderr=None)

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
    user_profile.onboarding_steps = simplejson.dumps(steps)
    user_profile.save()

    log_event({'type': 'update_onboarding',
               'user': user_profile.email,
               'steps': steps})

    notice = dict(event=dict(type="onboarding_steps", steps=steps),
                  users=[user_profile.id])
    tornado_callbacks.send_notification(notice)

def do_update_message(user_profile, message_id, subject, content):
    try:
        message = Message.objects.select_related().get(id=message_id)
    except Message.DoesNotExist:
        raise JsonableError("Unknown message id")

    event = {'type': 'update_message',
             'sender': user_profile.email,
             'message_id': message_id}
    edit_history_event = {}

    if message.sender != user_profile:
        raise JsonableError("Message was not sent by you")

    # Set first_rendered_content to be the oldest version of the
    # rendered content recorded; which is the current version if the
    # content hasn't been edited before.  Note that because one could
    # have edited just the subject, not every edit history event
    # contains a prev_rendered_content element.
    first_rendered_content = message.rendered_content
    if message.edit_history is not None:
        edit_history = simplejson.loads(message.edit_history)
        for old_edit_history_event in edit_history:
            if 'prev_rendered_content' in old_edit_history_event:
                first_rendered_content = old_edit_history_event['prev_rendered_content']

    if content is not None:
        rendered_content = bugdown.convert(content, message.sender.realm.domain)
        if rendered_content is None:
            raise JsonableError("We were unable to render your updated message")

        if not settings.DEPLOYED or settings.STAGING_DEPLOYED:
            # Don't highlight message edit diffs on prod
            rendered_content = highlight_html_differences(first_rendered_content, rendered_content)

        event['orig_content'] = message.content
        event['orig_rendered_content'] = message.rendered_content
        edit_history_event["prev_content"] = message.content
        edit_history_event["prev_rendered_content"] = message.rendered_content
        edit_history_event["prev_rendered_content_version"] = message.rendered_content_version
        message.content = content
        message.rendered_content = rendered_content
        message.rendered_content_version = bugdown.version
        event["content"] = content
        event["rendered_content"] = rendered_content

    if subject is not None:
        event["orig_subject"] = message.subject
        message.subject = subject
        event["subject"] = subject
        edit_history_event["prev_subject"] = event['orig_subject']

    message.last_edit_time = timezone.now()
    event['edit_timestamp'] = datetime_to_timestamp(message.last_edit_time)
    edit_history_event['timestamp'] = event['edit_timestamp']
    if message.edit_history is not None:
        edit_history.insert(0, edit_history_event)
    else:
        edit_history = [edit_history_event]
    message.edit_history = simplejson.dumps(edit_history)

    log_event(event)
    message.save(update_fields=["subject", "content", "rendered_content",
                                "rendered_content_version", "last_edit_time",
                                "edit_history"])

    # Update the message as stored in both the (deprecated) message
    # cache (for shunting the message over to Tornado in the old
    # get_messages API) and also the to_dict caches.
    cache_save_message(message)
    items_for_memcached = {}
    items_for_memcached[to_dict_cache_key(message, True)] = \
        (message.to_dict_uncached(apply_markdown=True,
                                  rendered_content=message.rendered_content),)
    items_for_memcached[to_dict_cache_key(message, False)] = \
        (message.to_dict_uncached(apply_markdown=False),)
    cache_set_many(items_for_memcached)

    recipients = [um.user_profile_id for um in UserMessage.objects.filter(message=message_id)]
    notice = dict(event=event, users=recipients)
    tornado_callbacks.send_notification(notice)

def do_finish_tutorial(user_profile):
    user_profile.tutorial_status = UserProfile.TUTORIAL_FINISHED
    user_profile.save()

    # We want to add the default subs list iff there were no subs
    try:
        prereg_user = PreregistrationUser.objects.filter(email=user_profile.email,
                                                         status=confirmation.settings.STATUS_ACTIVE) \
                                                 .order_by('-id')[0]
        streams = prereg_user.streams.all()
    except IndexError:
        # If the user signed up via a mechanism other than
        # PreregistrationUser (e.g. Google Apps connect or MitUser),
        # just give them the default streams.
        streams = []

    if len(streams) == 0:
        streams = get_default_subs(user_profile)
    for stream in streams:
        do_add_subscription(user_profile, stream)

def gather_subscriptions(user_profile):
    # For now, don't display subscriptions for private messages.
    subs = Subscription.objects.select_related().filter(
        user_profile    = user_profile,
        recipient__type = Recipient.STREAM)

    stream_ids = [sub.recipient.type_id for sub in subs]

    stream_hash = {}
    for stream in Stream.objects.filter(id__in=stream_ids):
        stream_hash[stream.id] = (stream.name, stream.invite_only)

    subscribed = []
    unsubscribed = []

    for sub in subs:
        (stream_name, invite_only) = stream_hash[sub.recipient.type_id]
        stream = {'name': stream_name,
                       'in_home_view': sub.in_home_view,
                       'invite_only': invite_only,
                       'color': sub.color,
                       'notifications': sub.notifications}
        if sub.active:
            subscribed.append(stream)
        else:
            unsubscribed.append(stream)

    return (sorted(subscribed), sorted(unsubscribed))

@cache_with_key(status_dict_cache_key, timeout=60)
def get_status_dict(requesting_user_profile):
    user_statuses = defaultdict(dict)

    # Return no status info for MIT
    if requesting_user_profile.realm.domain == 'mit.edu':
        return user_statuses

    for presence in UserPresence.objects.filter(user_profile__realm=requesting_user_profile.realm,
                                                user_profile__is_active=True) \
                                        .select_related('user_profile', 'client'):
        user_statuses[presence.user_profile.email][presence.client.name] = presence.to_dict()

    return user_statuses


def do_events_register(user_profile, user_client, apply_markdown=True,
                       event_types=None):
    queue_id = request_event_queue(user_profile, user_client, apply_markdown,
                                   event_types)
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
                               'full_name' : profile.full_name}
                              for profile in
                              UserProfile.objects.select_related().filter(realm=user_profile.realm,
                                                                          is_active=True)]
    if event_types is None or "onboarding_steps" in event_types:
        ret['onboarding_steps'] = [{'email' : profile.email,
                                    'steps' : profile.onboarding_steps}]
    if event_types is None or "subscription" in event_types:
        subs = gather_subscriptions(user_profile)
        ret['subscriptions'] = subs[0]
        ret['unsubscribed'] = subs[1]
    if event_types is None or "presence" in event_types:
        ret['presences'] = get_status_dict(user_profile)

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
            if event['op'] == "add":
                ret['realm_users'].append(event['person'])
            elif event['op'] == "remove":
                person = event['person']
                ret['realm_users'] = filter(lambda p: p['email'] != person['email'],
                                            ret['realm_users'])
        elif event['type'] == "subscription":
            if event['op'] == "add":
                ret['subscriptions'].append(event['subscription'])
            elif event['op'] == "remove":
                sub = event['subscription']
                ret['subscriptions'] = filter(lambda s: s['name'] != sub['name'],
                                              ret['subscriptions'])
                ret['unsubscribed'].append(sub)
        elif event['type'] == "presence":
                ret['presences'][event['email']] = event['presence']
        elif event['type'] == "update_message":
            # The client will get the updated message directly
            pass
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
                        'url': 'https://humbughq.com',
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

    subject = "Missed Humbug%s from %s" % ('s' if len(senders) > 1 else '', sender_str)
    from_email = "%s (via Humbug) <noreply@humbughq.com>" % (sender_str)

    text_content = loader.render_to_string('zephyr/missed_message_email.txt', template_payload)
    html_content = loader.render_to_string('zephyr/missed_message_email_html.txt', template_payload)

    msg = EmailMultiAlternatives(subject, text_content, from_email, [user_profile.email],
                                 headers = headers)
    msg.attach_alternative(html_content, "text/html")
    msg.send()

    user_profile.last_reminder = datetime.datetime.now()
    user_profile.save(update_fields=['last_reminder'])

def handle_missedmessage_emails(user_profile_id, missed_email_events):
    message_ids = [event.get('message_id') for event in missed_email_events]
    timestamp = timestamp_to_datetime(event.get('timestamp'))

    user_profile = UserProfile.objects.get(id=user_profile_id)
    messages = [um.message for um in UserMessage.objects.filter(user_profile=user_profile,
                                                                message__id__in=message_ids,
                                                                flags=~UserMessage.flags.read)]

    waitperiod = datetime.timedelta(hours=UserProfile.EMAIL_REMINDER_WAITPERIOD)
    if len(messages) == 0 or (user_profile.last_reminder and \
                              timestamp - user_profile.last_reminder < waitperiod):
        # Don't spam the user, if we've sent an email in the last day
        return

    do_send_missedmessage_email(user_profile, messages)
