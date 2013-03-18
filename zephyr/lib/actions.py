from django.conf import settings
from django.contrib.sessions.models import Session
from zephyr.lib.context_managers import lockfile
from zephyr.models import Realm, Stream, UserProfile, UserActivity, \
    Subscription, Recipient, Message, UserMessage, \
    DefaultStream, StreamColor, UserPresence, \
    MAX_MESSAGE_LENGTH, get_client, get_stream, get_recipient
from django.db import transaction, IntegrityError
from django.db.models import F
from zephyr.lib.initial_password import initial_password
from zephyr.lib.timestamp import timestamp_to_datetime, datetime_to_timestamp
from zephyr.lib.cache_helpers import cache_save_message
from zephyr.lib.queue import SimpleQueueClient
from django.utils import timezone
from zephyr.lib.create_user import create_user
from zephyr.lib.bulk_create import batch_bulk_create
from zephyr.lib import bugdown

import subprocess
import simplejson
import time
import traceback
import re
import requests
import datetime
import os
import platform
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
    return create_user(email, password, realm, full_name, short_name, active)

def user_sessions(user):
    return [s for s in Session.objects.all() if s.get_decoded().get('_auth_user_id') == user.id]

def do_deactivate(user_profile):
    user_profile.user.set_unusable_password()
    user_profile.user.is_active = False
    user_profile.user.save()

    for session in user_sessions(user_profile.user):
        session.delete()

    log_event({'type': 'user_deactivated',
               'timestamp': time.time(),
               'user': user_profile.user.email,
               'domain': user_profile.realm.domain})

def do_change_user_email(user, new_email):
    old_email = user.email
    user.email = new_email
    user.save()

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

@transaction.commit_on_success
def create_mit_user_if_needed(realm, email):
    try:
        return UserProfile.objects.get(user__email__iexact=email)
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
            return UserProfile.objects.get(user__email__iexact=email)

def log_message(message):
    if not message.sending_client.name.startswith("test:"):
        log_event(message.to_log_dict())

user_hash = {}
def get_user_profile_by_id(uid):
    if uid in user_hash:
        return user_hash[uid]
    return UserProfile.objects.select_related().get(id=uid)

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
        batch_bulk_create(UserMessage, ums_to_create)

    cache_save_message(message)

    # We can only publish messages to longpolling clients if the Tornado server is running.
    if settings.TORNADO_SERVER:
        # Render Markdown etc. here and store (automatically) in
        # memcached, so that the single-threaded Tornado server
        # doesn't have to.
        message.to_dict(apply_markdown=True, rendered_content=rendered_content)
        message.to_dict(apply_markdown=False)
        data = dict(
            secret   = settings.SHARED_SECRET,
            message  = message.id,
            users    = simplejson.dumps([str(user.id) for user in recipients]))
        if message.recipient.type == Recipient.STREAM:
            # Note: This is where authorization for single-stream
            # get_updates happens! We only attach stream data to the
            # notify_new_message request if it's a public stream,
            # ensuring that in the tornado server, non-public stream
            # messages are only associated to their subscribed users.
            if stream is None:
                stream = Stream.objects.select_related("realm").get(id=message.recipient.type_id)
            if stream.is_public():
                data['realm_id'] = stream.realm.id
                data['stream_name'] = stream.name
        requests.post(settings.TORNADO_SERVER + '/notify_new_message', data=data)

def create_stream_if_needed(realm, stream_name, invite_only=False):
    (stream, created) = Stream.objects.get_or_create(
        realm=realm, name__iexact=stream_name,
        defaults={'name': stream_name, 'invite_only': invite_only})
    if created:
        Recipient.objects.create(type_id=stream.id, type=Recipient.STREAM)
    return stream, created

def internal_send_message(sender_email, recipient_type, recipient,
                          subject, content, realm=None):
    stream = None
    if len(content) > MAX_MESSAGE_LENGTH:
        content = content[0:3900] + "\n\n[message was too long and has been truncated]"

    rendered_content = bugdown.convert(content)
    if rendered_content is None:
        rendered_content = "<p>[Message could not be rendered by bugdown!]</p>"

    message = Message()
    message.sender = UserProfile.objects.get(user__email__iexact=sender_email)

    if recipient_type == Recipient.STREAM:
        if realm is None:
            realm = message.sender.realm
        stream, _ = create_stream_if_needed(realm, recipient)
        type_id = stream.id
    else:
        type_id = UserProfile.objects.get(user__email__iexact=recipient).id

    message.recipient = get_recipient(recipient_type, type_id)

    message.subject = subject
    message.content = content
    message.pub_date = timezone.now()
    message.sending_client = get_client("Internal")

    do_send_message(message, rendered_content=rendered_content, stream=stream)

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
    stream_color.save()

def do_add_subscription(user_profile, stream, no_log=False):
    recipient = get_recipient(Recipient.STREAM, stream.id)
    (subscription, created) = Subscription.objects.get_or_create(
        user_profile=user_profile, recipient=recipient,
        defaults={'active': True})
    did_subscribe = created
    if not subscription.active:
        did_subscribe = True
        subscription.active = True
        subscription.save()
    if did_subscribe and not no_log:
        log_event({'type': 'subscription_added',
                   'user': user_profile.user.email,
                   'name': stream.name,
                   'domain': stream.realm.domain})
    set_stream_color(user_profile, stream.name)
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
    subscription.save()
    if did_remove and not no_log:
        log_event({'type': 'subscription_removed',
                   'user': user_profile.user.email,
                   'name': stream.name,
                   'domain': stream.realm.domain})
    return did_remove

def log_subscription_property_change(user_email, property, property_dict):
    event = {'type': 'subscription_property',
             'property': property,
             'user': user_email}
    event.update(property_dict)
    log_event(event)

def do_activate_user(user, log=True, join_date=timezone.now()):
    user.is_active = True
    user.set_password(initial_password(user.email))
    user.date_joined = join_date
    user.save()

    if log:
        domain = UserProfile.objects.get(user=user).realm.domain
        log_event({'type': 'user_activated',
                   'user': user.email,
                   'domain': domain})

def do_change_password(user, password, log=True, commit=True):
    user.set_password(password)
    if commit:
        user.save()
    if log:
        log_event({'type': 'user_change_password',
                   'user': user.email,
                   'pwhash': user.password})

def do_change_full_name(user_profile, full_name, log=True):
    user_profile.full_name = full_name
    user_profile.save()
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

        internal_send_message("humbug+signups@humbughq.com", Recipient.STREAM,
                              "signups", domain, "Signups enabled.")
    return (realm, created)

def do_change_enable_desktop_notifications(user_profile, enable_desktop_notifications, log=True):
    user_profile.enable_desktop_notifications = enable_desktop_notifications
    user_profile.save()
    if log:
        log_event({'type': 'enable_desktop_notifications_changed',
                   'user': user_profile.user.email,
                   'enable_desktop_notifications': enable_desktop_notifications})

def do_change_enter_sends(user_profile, enter_sends):
    user_profile.enter_sends = enter_sends
    user_profile.save()

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
    activity.save()

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
    presence.save()

if settings.USING_RABBITMQ or settings.TEST_SUITE:
    # RabbitMQ is required for idle and unread functionality
    if settings.USING_RABBITMQ:
        actions_queue = SimpleQueueClient()

    def update_user_presence(user_profile, client, log_time, status):
        event={'type': 'user_presence',
               'user_profile_id': user_profile.id,
               'status': status,
               'time': datetime_to_timestamp(log_time),
               'client': client.name}

        if settings.USING_RABBITMQ:
            actions_queue.json_publish("user_activity", event)
        elif settings.TEST_SUITE:
            process_user_presence_event(event)

    def update_message_flags(user_profile, operation, flag, messages, all):
        event = {'type':            'update_message',
                 'user_profile_id': user_profile.id,
                 'operation':       operation,
                 'flag':            flag,
                 'messages':        messages,
                 'all':             all}
        if settings.USING_RABBITMQ:
            actions_queue.json_publish("user_activity", event)
        else:
            return process_update_message_flags(event)
else:
    update_user_presence = lambda user_profile, client, log_time, status: None
    update_message_flags = lambda user_profile, operation, flag, messages, all: None

def process_user_presence_event(event):
    user_profile = UserProfile.objects.get(id=event["user_profile_id"])
    client = get_client(event["client"])
    log_time = timestamp_to_datetime(event["time"])
    status = event["status"]
    return do_update_user_presence(user_profile, client, log_time, status)

def process_update_message_flags(event):
    user_profile = UserProfile.objects.get(id=event["user_profile_id"])
    try:
        msg_ids = event["messages"]
        flag = getattr(UserMessage.flags, event["flag"])
        op = event["operation"]
    except (KeyError, AttributeError):
        return False

    if event["all"] == True:
        messages = UserMessage.objects.filter(user_profile=user_profile)
    else:
        messages = UserMessage.objects.filter(user_profile=user_profile,
                                              message__id__in=msg_ids)

    if op == "add":
        messages.update(flags=F('flags') | flag)
    elif op == "remove":
        messages.update(flags=F('flags') & ~flag)

    return True

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
