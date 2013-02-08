from django.conf import settings
from django.contrib.auth.models import User
from zephyr.lib.context_managers import lockfile
from zephyr.models import Realm, Stream, UserProfile, UserActivity, \
    Subscription, Recipient, Message, UserMessage, \
    DefaultStream, StreamColor, \
    MAX_MESSAGE_LENGTH, get_client, get_display_recipient, get_stream
from django.db import transaction, IntegrityError
from zephyr.lib.initial_password import initial_password
from zephyr.lib.cache import cache_with_key
from zephyr.lib.timestamp import timestamp_to_datetime
from zephyr.lib.message_cache import cache_save_message
from django.utils import timezone
from django.contrib.auth.models import UserManager

import subprocess
import simplejson
import time
import traceback
import re
import requests
import hashlib
import base64
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

# create_user_hack is the same as Django's User.objects.create_user,
# except that we don't save to the database so it can used in
# bulk_creates
def create_user_hack(username, password, email, active):
    now = timezone.now()
    email = UserManager.normalize_email(email)
    user = User(username=username, email=email,
                is_staff=False, is_active=active, is_superuser=False,
                last_login=now, date_joined=now)

    if active:
        user.set_password(password)
    else:
        user.set_unusable_password()
    return user

def create_user_base(email, password, active=True):
    # NB: the result of Base32 + truncation is not a valid Base32 encoding.
    # It's just a unique alphanumeric string.
    # Use base32 instead of base64 so we don't have to worry about mixed case.
    # Django imposes a limit of 30 characters on usernames.
    email_hash = hashlib.sha256(settings.HASH_SALT + email).digest()
    username = base64.b32encode(email_hash)[:30]
    return create_user_hack(username, password, email, active)

def create_user(email, password, realm, full_name, short_name,
                active=True):
    user = create_user_base(email=email, password=password,
                            active=active)
    user.save()
    return UserProfile.create(user, realm, full_name, short_name)

def do_create_user(email, password, realm, full_name, short_name,
                   active=True):
    log_event({'type': 'user_created',
               'timestamp': time.time(),
               'full_name': full_name,
               'short_name': short_name,
               'user': email,
               'domain': realm.domain})
    return create_user(email, password, realm, full_name, short_name, active)

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
        return UserProfile.objects.get(user__email=email)
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
            return UserProfile.objects.get(user__email=email)

def log_message(message):
    if not message.sending_client.name.startswith("test:"):
        log_event(message.to_log_dict())

user_hash = {}
def get_user_profile_by_id(uid):
    if uid in user_hash:
        return user_hash[uid]
    return UserProfile.objects.select_related().get(id=uid)

def do_send_message(message, no_log=False):
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
                      s in Subscription.objects.select_related().filter(recipient=message.recipient, active=True)]
    else:
        raise ValueError('Bad recipient type')

    # Save the message receipts in the database
    # TODO: Use bulk_create here
    with transaction.commit_on_success():
        message.save()
        for user_profile in recipients:
            # Only deliver messages to "active" user accounts
            if user_profile.user.is_active:
                UserMessage(user_profile=user_profile, message=message).save()

    cache_save_message(message)

    # We can only publish messages to longpolling clients if the Tornado server is running.
    if settings.TORNADO_SERVER:
        # Render Markdown etc. here and store (automatically) in
        # memcached, so that the single-threaded Tornado server
        # doesn't have to.
        message.to_dict(apply_markdown=True)
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
            stream = Stream.objects.get(id=message.recipient.type_id)
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
                          subject, content):
    if len(content) > MAX_MESSAGE_LENGTH:
        content = content[0:3900] + "\n\n[message was too long and has been truncated]"
    message = Message()
    message.sender = UserProfile.objects.get(user__email=sender_email)

    if recipient_type == Recipient.STREAM:
        stream, _ = create_stream_if_needed(message.sender.realm, recipient)
        type_id = stream.id
    else:
        type_id = UserProfile.objects.get(user__email=recipient).id

    message.recipient = Recipient.objects.get(type_id=type_id, type=recipient_type)

    message.subject = subject
    message.content = content
    message.pub_date = timezone.now()
    message.sending_client = get_client("Internal")

    do_send_message(message)

def do_add_subscription(user_profile, stream, no_log=False):
    recipient = Recipient.objects.get(type_id=stream.id,
                                      type=Recipient.STREAM)
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
    return did_subscribe

def do_remove_subscription(user_profile, stream, no_log=False):
    recipient = Recipient.objects.get(type_id=stream.id,
                                      type=Recipient.STREAM)
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

        # Sent a notification message
        message = Message()
        message.sender = UserProfile.objects.get(user__email="humbug+signups@humbughq.com")
        stream, _ = create_stream_if_needed(message.sender.realm, "signups")
        message.recipient = Recipient.objects.get(type_id=stream.id, type=Recipient.STREAM)
        message.subject = domain
        message.content = "Signups enabled."
        message.pub_date = timezone.now()
        message.sending_client = get_client("Internal")

        do_send_message(message)
    return (realm, created)

def do_change_enable_desktop_notifications(user_profile, enable_desktop_notifications, log=True):
    user_profile.enable_desktop_notifications = enable_desktop_notifications
    user_profile.save()
    if log:
        log_event({'type': 'enable_desktop_notifications_changed',
                   'user': user_profile.user.email,
                   'enable_desktop_notifications': enable_desktop_notifications})

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

    result = []
    for sc in with_color:
        stream_name = get_display_recipient(sc.subscription.recipient)
        result.append({'name': stream_name,
                       'in_home_view': sc.subscription.in_home_view,
                       'invite_only': get_stream(stream_name, user_profile.realm).invite_only,
                       'color': sc.color})
    for sub in no_color:
        stream_name = get_display_recipient(sub.recipient)
        result.append({'name': stream_name,
                       'in_home_view': sub.in_home_view,
                       'invite_only': get_stream(stream_name, user_profile.realm).invite_only,
                       'color': StreamColor.DEFAULT_STREAM_COLOR})

    return sorted(result)
