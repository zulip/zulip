from __future__ import absolute_import

from django.conf import settings
from django.utils.timezone import now

from zerver.models import Message, UserProfile, \
    Recipient, get_user_profile_by_id

from zerver.decorator import JsonableError
from zerver.lib.cache import cache_get_many, message_cache_key, \
    user_profile_by_id_cache_key, cache_save_user_profile
from zerver.lib.cache_helpers import cache_with_key
from zerver.lib.queue import queue_json_publish
from zerver.lib.event_queue import get_client_descriptors_for_user,\
    get_client_descriptors_for_realm_all_streams
from zerver.lib.timestamp import timestamp_to_datetime

import time
import logging
import requests
import ujson
import datetime

# Send email notifications to idle users
# after they are idle for 1 hour
NOTIFY_AFTER_IDLE_HOURS = 1

def update_pointer(user_profile_id, new_pointer):
    event = dict(type='pointer', pointer=new_pointer)
    for client in get_client_descriptors_for_user(user_profile_id):
        if client.accepts_event(event):
            client.add_event(event.copy())

def build_offline_notification_event(user_profile_id, message_id):
    return {"user_profile_id": user_profile_id,
            "message_id": message_id,
            "timestamp": time.time()}

def missedmessage_hook(user_profile_id, queue, last_for_client):
    # Only process missedmessage hook when the last queue for a
    # client has been garbage collected
    if not last_for_client:
        return

    message_ids = []
    for event in queue.event_queue.contents():
        if not event['type'] == 'message' or not event['flags']:
            continue

        if 'mentioned' in event['flags'] and not 'read' in event['flags']:
            message_ids.append(event['message']['id'])

    for msg_id in message_ids:
        event = build_offline_notification_event(user_profile_id, msg_id)
        queue_json_publish("missedmessage_emails", event, lambda event: None)
        queue_json_publish("missedmessage_mobile_notifications", event, lambda event: None)

@cache_with_key(message_cache_key, timeout=3600*24)
def get_message_by_id_dbwarn(message_id):
    if not settings.TEST_SUITE:
        logging.warning("Tornado failed to load message from memcached when delivering!")
    return Message.objects.select_related().get(id=message_id)

def receiver_is_idle(user_profile_id, realm_presences):
    # If a user has no message-receiving event queues, they've got no open zulip
    # session so we notify them
    all_client_descriptors = get_client_descriptors_for_user(user_profile_id)
    message_event_queues = [client for client in all_client_descriptors if client.accepts_messages()]
    off_zulip = len(message_event_queues) == 0

    # It's possible a recipient is not in the realm of a sender. We don't have
    # presence information in this case (and it's hard to get without an additional
    # db query) so we simply don't try to guess if this cross-realm recipient
    # has been idle for too long
    if realm_presences is None or not user_profile_id in realm_presences:
        return off_zulip

    # If the most recent online status from a user is >1hr in the past, we notify
    # them regardless of whether or not they have an open window
    user_presence = realm_presences[user_profile_id]
    idle_too_long = False
    newest = None
    for client, status in user_presence.iteritems():
        if newest is None or status['timestamp'] > newest['timestamp']:
            newest = status

    update_time = timestamp_to_datetime(newest['timestamp'])
    if now() - update_time > datetime.timedelta(hours=NOTIFY_AFTER_IDLE_HOURS):
        idle_too_long = True

    return off_zulip or idle_too_long

def process_new_message(data):
    message = get_message_by_id_dbwarn(data['message'])

    realm_presences = data['presences']
    sender_queue_id = data.get('sender_queue_id', None)

    message_dict_markdown = message.to_dict(True)
    message_dict_no_markdown = message.to_dict(False)

    # To remove duplicate clients: Maps queue ID to {'client': Client, 'flags': flags}
    send_to_clients = dict()

    if 'stream_name' in data and not data.get("invite_only"):
        for client in get_client_descriptors_for_realm_all_streams(data['realm_id']):
            send_to_clients[client.event_queue.id] = {'client': client, 'flags': None}
            if sender_queue_id is not None and client.event_queue.id == sender_queue_id:
                send_to_clients[client.event_queue.id]['is_sender'] = True

    for user_data in data['users']:
        user_profile_id = user_data['id']
        flags = user_data.get('flags', [])

        for client in get_client_descriptors_for_user(user_profile_id):
            send_to_clients[client.event_queue.id] = {'client': client, 'flags': flags}
            if sender_queue_id is not None and client.event_queue.id == sender_queue_id:
                send_to_clients[client.event_queue.id]['is_sender'] = True

        # If the recipient was offline and the message was a single or group PM to him
        # or she was @-notified potentially notify more immediately
        received_pm = message.recipient.type in (Recipient.PERSONAL, Recipient.HUDDLE) and \
                        user_profile_id != message.sender.id
        mentioned = 'mentioned' in flags
        idle = receiver_is_idle(user_profile_id, realm_presences)
        always_push_notify = user_data.get('always_push_notify', False)
        if (received_pm or mentioned) and (idle or always_push_notify):
            event = build_offline_notification_event(user_profile_id, message.id)

            # Don't send missed message emails if always_push_notify is True
            if idle:
                # We require RabbitMQ to do this, as we can't call the email handler
                # from the Tornado process. So if there's no rabbitmq support do nothing
                queue_json_publish("missedmessage_emails", event, lambda event: None)
            queue_json_publish("missedmessage_mobile_notifications", event, lambda event: None)

    for client_data in send_to_clients.itervalues():
        client = client_data['client']
        flags = client_data['flags']
        is_sender = client_data.get('is_sender', False)

        if not client.accepts_messages():
            # The actual check is the accepts_event() check below;
            # this line is just an optimization to avoid copying
            # message data unnecessarily
            continue

        if client.apply_markdown:
            message_dict = message_dict_markdown
        else:
            message_dict = message_dict_no_markdown

        # Make sure Zephyr mirroring bots know whether stream is invite-only
        if "mirror" in client.client_type.name and data.get("invite_only"):
            message_dict = message_dict.copy()
            message_dict["invite_only_stream"] = True

        event = dict(type='message', message=message_dict, flags=flags)

        if is_sender:
            local_message_id = data.get('local_id', None)
            if local_message_id is not None:
                event["local_message_id"] = local_message_id

        if not client.accepts_event(event):
            continue

        # The below prevents (Zephyr) mirroring loops.
        if ('mirror' in message.sending_client.name and
            message.sending_client == client.client_type):
            continue
        client.add_event(event)

def process_event(data):
    event = data['event']
    for user_profile_id in data['users']:
        for client in get_client_descriptors_for_user(user_profile_id):
            if client.accepts_event(event):
                client.add_event(event.copy())

def process_update_message(data):
    event = data['event']
    for user in data['users']:
        user_profile_id = user['id']
        user_event = event.copy() # shallow, but deep enough for our needs
        user_event['flags'] = user['flags']

        for client in get_client_descriptors_for_user(user_profile_id):
            if client.accepts_event(user_event):
                client.add_event(user_event)

def process_notification(data):
    if 'type' not in data:
        # Generic event that doesn't need special handling
        process_event(data)
    elif data['type'] == 'new_message':
        process_new_message(data)
    elif data['type'] == 'update_message':
        process_update_message(data)
    elif data['type'] == 'pointer_update':
        update_pointer(data['user'], data['new_pointer'])
    else:
        raise JsonableError('bad notification type ' + data['type'])

# Runs in the Django process to send a notification to Tornado.
#
# We use JSON rather than bare form parameters, so that we can represent
# different types and for compatibility with non-HTTP transports.

def send_notification_http(data):
    if settings.TORNADO_SERVER and not settings.RUNNING_INSIDE_TORNADO:
        requests.post(settings.TORNADO_SERVER + '/notify_tornado', data=dict(
                data   = ujson.dumps(data),
                secret = settings.SHARED_SECRET))
    else:
        process_notification(data)

def send_notification(data):
    return queue_json_publish("notify_tornado", data, send_notification_http)
