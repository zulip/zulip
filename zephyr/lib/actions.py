from django.conf import settings
from django.contrib.sessions.models import Session
from zephyr.lib.context_managers import lockfile
from zephyr.models import Realm, Stream, UserProfile, UserActivity, \
    Subscription, Recipient, Message, UserMessage, valid_stream_name, \
    DefaultStream, StreamColor, UserPresence, MAX_SUBJECT_LENGTH, \
    MAX_MESSAGE_LENGTH, get_client, get_stream, get_recipient, get_huddle, \
    get_user_profile_by_id
from django.db import transaction, IntegrityError
from django.db.models import F
from django.core.exceptions import ValidationError
from django.utils.importlib import import_module
session_engine = import_module(settings.SESSION_ENGINE)

from zephyr.lib.initial_password import initial_password
from zephyr.lib.timestamp import timestamp_to_datetime, datetime_to_timestamp
from zephyr.lib.cache_helpers import cache_save_message
from zephyr.lib.queue import queue_json_publish
from django.utils import timezone
from zephyr.lib.create_user import create_user
from zephyr.lib import bugdown
from zephyr.lib.cache import cache_with_key, user_profile_by_id_cache_key, \
    user_profile_by_email_cache_key
from zephyr.decorator import get_user_profile_by_email, json_to_list, JsonableError
from zephyr.lib.event_queue import request_event_queue, get_user_events

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
                   active=True):
    log_event({'type': 'user_created',
               'timestamp': time.time(),
               'full_name': full_name,
               'short_name': short_name,
               'user': email,
               'domain': realm.domain})
    user_profile = create_user(email, password, realm, full_name, short_name, active)

    notice = dict(event=dict(type="realm_user", op="add",
                             person=dict(email=user_profile.user.email,
                                         full_name=user_profile.full_name)),
                  users=[up.id for up in
                         UserProfile.objects.select_related().filter(realm=user_profile.realm,
                                                                     user__is_active=True)])
    tornado_callbacks.send_notification(notice)
    return user_profile

def user_sessions(user):
    return [s for s in Session.objects.all() if s.get_decoded().get('_auth_user_id') == user.id]

def delete_session(session):
    return session_engine.SessionStore(session.session_key).delete()

def delete_user_sessions(user_profile):
    for session in Session.objects.all():
        if session.get_decoded().get('_auth_user_id') == user_profile.user.id:
            delete_session(session)

def delete_realm_sessions(realm):
    realm_user_ids = [u.user.id for u in
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

    user_profile.user.set_unusable_password()
    user_profile.user.is_active = False
    user_profile.user.save(update_fields=["is_active", "password"])

    delete_user_sessions(user_profile)

    log_event({'type': 'user_deactivated',
               'timestamp': time.time(),
               'user': user_profile.user.email,
               'domain': user_profile.realm.domain})

    notice = dict(event=dict(type="realm_user", op="remove",
                             person=dict(email=user_profile.user.email,
                                         full_name=user_profile.full_name)),
                  users=[up.id for up in
                         UserProfile.objects.select_related().filter(realm=user_profile.realm,
                                                                     user__is_active=True)])
    tornado_callbacks.send_notification(notice)


def do_change_user_email(user_profile, new_email):
    old_email = user_profile.user.email

    user_profile.email = new_email
    user_profile.save(update_fields=["email"])

    user_profile.user.email = new_email
    user_profile.user.save(update_fields=["email"])

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

def do_send_message(message, rendered_content=None, no_log=False,
                    stream=None):
    # Log the message to our message log for populate_db to refill
    if not no_log:
        log_message(message)

    if message.recipient.type == Recipient.PERSONAL:
        recipients = list(set([get_user_profile_by_id(message.recipient.type_id),
                               get_user_profile_by_id(message.sender_id)]))
        # For personals, you send out either 1 or 2 copies of the message, for
        # personals to yourself or to someone else, respectively.
        assert((len(recipients) == 1) or (len(recipients) == 2))
    elif (message.recipient.type == Recipient.STREAM or
          message.recipient.type == Recipient.HUDDLE):
        recipients = [s.user_profile for
                      s in Subscription.objects.select_related(
                "user_profile", "user_profile__user").filter(recipient=message.recipient, active=True)]
    else:
        raise ValueError('Bad recipient type')

    # Save the message receipts in the database
    with transaction.commit_on_success():
        message.save()
        ums_to_create = [UserMessage(user_profile=user_profile, message=message)
                         for user_profile in recipients
                         if user_profile.user.is_active]
        for um in ums_to_create:
            sent_by_human = message.sending_client.name.lower() in \
                                ['website', 'iphone', 'android']
            if um.user_profile == message.sender and sent_by_human:
                um.flags |= UserMessage.flags.read
        UserMessage.objects.bulk_create(ums_to_create)

    cache_save_message(message)

    # We can only publish messages to longpolling clients if the Tornado server is running.
    if settings.TORNADO_SERVER:
        # Render Markdown etc. here and store (automatically) in
        # memcached, so that the single-threaded Tornado server
        # doesn't have to.
        message.to_dict(apply_markdown=True, rendered_content=rendered_content)
        message.to_dict(apply_markdown=False)
        data = dict(
            type     = 'new_message',
            message  = message.id,
            users    = [user.id for user in recipients])
        if message.recipient.type == Recipient.STREAM:
            # Note: This is where authorization for single-stream
            # get_updates happens! We only attach stream data to the
            # notify new_message request if it's a public stream,
            # ensuring that in the tornado server, non-public stream
            # messages are only associated to their subscribed users.
            if stream is None:
                stream = Stream.objects.select_related("realm").get(id=message.recipient.type_id)
            if stream.is_public():
                data['realm_id'] = stream.realm.id
                data['stream_name'] = stream.name
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
def check_send_message(sender, client, message_type_name, message_to,
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
    elif message_type_name == 'private':
        not_forged_zephyr_mirror = client and client.name == "zephyr_mirror" and not forged
        try:
            recipient = recipient_for_emails(message_to, not_forged_zephyr_mirror,
                                             forwarder_user_profile, sender)
        except ValidationError, e:
            return e.messages[0]
    else:
        return "Invalid message type"

    rendered_content = bugdown.convert(message_content)
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
        return None

    do_send_message(message, rendered_content=rendered_content,
                    stream=stream)

    return None

def internal_send_message(sender_email, recipient_type_name, recipients,
                          subject, content, realm=None):
    if len(content) > MAX_MESSAGE_LENGTH:
        content = content[0:3900] + "\n\n[message was too long and has been truncated]"

    sender = get_user_profile_by_email(sender_email)
    if realm is None:
        realm = sender.realm
    parsed_recipients = extract_recipients(recipients)
    if recipient_type_name == "stream":
        stream, _ = create_stream_if_needed(realm, parsed_recipients[0])

    ret = check_send_message(sender, get_client("Internal"), recipient_type_name,
                             parsed_recipients, subject, content, realm)
    if ret is not None:
        logging.error("Error sending internal message by %s: %s" % (sender_email, ret))

def get_stream_colors(user_profile):
    return [(sub["name"], sub["color"]) for sub in gather_subscriptions(user_profile)]

def pick_color(user_profile):
    # These colors are shared with the palette in subs.js.
    stream_assignment_colors = [
        "#76ce90", "#fae589", "#a6c7e5", "#e79ab5",
        "#bfd56f", "#f4ae55", "#b0a5fd", "#addfe5",
        "#f5ce6e", "#c2726a", "#94c849", "#bd86e5",
        "#ee7e4a", "#a6dcbf", "#95a5fd", "#53a063",
        "#9987e1", "#e4523d", "#c2c2c2", "#4f8de4",
        "#c6a8ad", "#e7cc4d", "#c8bebf", "#a47462"]
    used_colors = [elt[1] for elt in get_stream_colors(user_profile) if elt[1]]
    available_colors = filter(lambda x: x not in used_colors,
                              stream_assignment_colors)

    if available_colors:
        return available_colors[0]
    else:
        return stream_assignment_colors[len(used_colors) % len(stream_assignment_colors)]

def get_subscription(stream_name, user_profile):
    stream = get_stream(stream_name, user_profile.realm)
    recipient = get_recipient(Recipient.STREAM, stream.id)
    return Subscription.objects.filter(user_profile=user_profile,
                                       recipient=recipient, active=True)

def set_stream_color(user_profile, stream_name, color=None):
    subscription = get_subscription(stream_name, user_profile)
    stream_color, _ = StreamColor.objects.get_or_create(subscription=subscription[0])
    # TODO: sanitize color.
    if not color:
        color = pick_color(user_profile)
    stream_color.color = color
    stream_color.save(update_fields=["color"])
    return color

def do_add_subscription(user_profile, stream, no_log=False):
    recipient = get_recipient(Recipient.STREAM, stream.id)
    (subscription, created) = Subscription.objects.get_or_create(
        user_profile=user_profile, recipient=recipient,
        defaults={'active': True})
    did_subscribe = created
    if not subscription.active:
        did_subscribe = True
        subscription.active = True
        subscription.save(update_fields=["active"])
    color = set_stream_color(user_profile, stream.name)
    if did_subscribe:
        if not no_log:
            log_event({'type': 'subscription_added',
                       'user': user_profile.user.email,
                       'name': stream.name,
                       'domain': stream.realm.domain})

        notice = dict(event=dict(type="subscription", op="add",
                                 subscription=dict(name=stream.name,
                                                   in_home_view=subscription.in_home_view,
                                                   invite_only=stream.invite_only,
                                                   color=color)),
                      users=[user_profile.id])
        tornado_callbacks.send_notification(notice)

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
                       'user': user_profile.user.email,
                       'name': stream.name,
                       'domain': stream.realm.domain})

        notice = dict(event=dict(type="subscription", op="remove",
                                 subscription=dict(name=stream.name)),
                      users=[user_profile.id])
        tornado_callbacks.send_notification(notice)

    return did_remove

def log_subscription_property_change(user_email, property, property_dict):
    event = {'type': 'subscription_property',
             'property': property,
             'user': user_email}
    event.update(property_dict)
    log_event(event)

def do_activate_user(user_profile, log=True, join_date=timezone.now()):
    user = user_profile.user

    user_profile.is_active = True
    user_profile.set_password(initial_password(user_profile.email))
    user_profile.date_joined = join_date
    user_profile.save(update_fields=["is_active", "date_joined", "password"])

    user.is_active = True
    user.set_password(initial_password(user.email))
    user.date_joined = join_date
    user.save(update_fields=["is_active", "date_joined", "password"])

    if log:
        domain = user_profile.realm.domain
        log_event({'type': 'user_activated',
                   'user': user.email,
                   'domain': domain})

def do_change_password(user_profile, password, log=True, commit=True,
                       hashed_password=False):
    user = user_profile.user
    if hashed_password:
        # This is a hashed password, not the password itself.
        user.password = password
        user_profile.set_password(password)
    else:
        user.set_password(password)
        user_profile.set_password(password)
    if commit:
        user.save(update_fields=["password"])
        user_profile.save(update_fields=["password"])
    if log:
        log_event({'type': 'user_change_password',
                   'user': user.email,
                   'pwhash': user.password})

def do_change_full_name(user_profile, full_name, log=True):
    user_profile.full_name = full_name
    user_profile.save(update_fields=["full_name"])
    if log:
        log_event({'type': 'user_change_full_name',
                   'user': user_profile.user.email,
                   'full_name': full_name})

def do_create_realm(domain, replay=False):
    realm, created = Realm.objects.get_or_create(domain=domain)
    if created and not replay:
        # Log the event
        log_event({"type": "realm_created",
                   "domain": domain})

        internal_send_message("humbug+signups@humbughq.com", "stream",
                              "signups", domain, "Signups enabled.")
    return (realm, created)

def do_change_enable_desktop_notifications(user_profile, enable_desktop_notifications, log=True):
    user_profile.enable_desktop_notifications = enable_desktop_notifications
    user_profile.save(update_fields=["enable_desktop_notifications"])
    if log:
        log_event({'type': 'enable_desktop_notifications_changed',
                   'user': user_profile.user.email,
                   'enable_desktop_notifications': enable_desktop_notifications})

def do_change_enter_sends(user_profile, enter_sends):
    user_profile.enter_sends = enter_sends
    user_profile.save(update_fields=["enter_sends"])

def set_default_streams(realm, stream_names):
    DefaultStream.objects.filter(realm=realm).delete()
    for stream_name in stream_names:
        stream, _ = create_stream_if_needed(realm, stream_name)
        DefaultStream.objects.create(stream=stream, realm=realm)

def add_default_subs(user_profile):
    for default in DefaultStream.objects.filter(realm=user_profile.realm):
        do_add_subscription(user_profile, default.stream)

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
    presence.timestamp = log_time
    presence.status = status
    presence.save(update_fields=["timestamp", "status"])

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

    return True

def update_flags_externally(op, flag, user_profile, until_id):
    args = ['python', os.path.join(os.path.dirname(__file__), '../..', 'manage.py'),
            'set_message_flags', '--for-real', '-o', op, '-f', flag, '-m', user_profile.user.email,
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

def gather_subscriptions(user_profile):
    # This is a little awkward because the StreamColor table has foreign keys
    # to Subscription, but not vice versa, and not all Subscriptions have a
    # StreamColor.
    #
    # We could do this with a single OUTER JOIN query but Django's ORM does
    # not provide a simple way to specify one.

    # For now, don't display the subscription for your ability to receive personals.
    subs = Subscription.objects.filter(
        user_profile    = user_profile,
        active          = True,
        recipient__type = Recipient.STREAM)
    with_color = StreamColor.objects.filter(subscription__in = subs).select_related()
    no_color   = subs.exclude(id__in = with_color.values('subscription_id')).select_related()

    stream_ids = [sc.subscription.recipient.type_id for sc in with_color] + \
        [sub.recipient.type_id for sub in no_color]

    stream_hash = {}
    for stream in Stream.objects.filter(id__in=stream_ids):
        stream_hash[stream.id] = (stream.name, stream.invite_only)

    result = []
    for sc in with_color:
        (stream_name, invite_only) = stream_hash[sc.subscription.recipient.type_id]
        result.append({'name': stream_name,
                       'in_home_view': sc.subscription.in_home_view,
                       'invite_only': invite_only,
                       'color': sc.color})
    for sub in no_color:
        (stream_name, invite_only) = stream_hash[sub.recipient.type_id]
        result.append({'name': stream_name,
                       'in_home_view': sub.in_home_view,
                       'invite_only': invite_only,
                       'color': StreamColor.DEFAULT_STREAM_COLOR})

    return sorted(result)

def do_events_register(user_profile, apply_markdown=True, event_types=None):
    queue_id = request_event_queue(user_profile, apply_markdown, event_types)
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
        ret['realm_users'] = [{'email'     : profile.user.email,
                               'full_name' : profile.full_name}
                              for profile in
                              UserProfile.objects.select_related().filter(realm=user_profile.realm,
                                                                          user__is_active=True)]
    if event_types is None or "subscription" in event_types:
        ret['subscriptions'] = gather_subscriptions(user_profile)

    # Apply events that came in while we were fetching initial data
    events = get_user_events(user_profile, queue_id, -1)
    for event in events:
        if event['type'] == "message":
            ret['max_message_id'] = max(ret['max_message_id'], event['message']['id'])
        elif event['type'] == "pointer":
            ret['pointer'] = max(ret['pointer'], event['pointer'])
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

    if events:
        ret['last_event_id'] = events[-1]['id']
    else:
        ret['last_event_id'] = -1

    return ret
