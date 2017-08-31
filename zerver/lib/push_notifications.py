from __future__ import absolute_import

import base64
import binascii
from functools import partial
import logging
import os
import time
import random
from typing import Any, Dict, List, Optional, SupportsInt, Text, Union, Type

from apns2.client import APNsClient
from apns2.payload import Payload as APNsPayload
from django.conf import settings
from django.utils.timezone import now as timezone_now
from django.utils.translation import ugettext as _
from gcm import GCM
from hyper.http20.exceptions import HTTP20Error
import requests
from six.moves import urllib
import ujson

from zerver.decorator import statsd_increment
from zerver.lib.avatar import absolute_avatar_url
from zerver.lib.queue import retry_event
from zerver.lib.request import JsonableError
from zerver.lib.timestamp import datetime_to_timestamp, timestamp_to_datetime
from zerver.lib.utils import generate_random_token
from zerver.models import PushDeviceToken, Message, Recipient, UserProfile, \
    UserMessage, get_display_recipient, receives_offline_notifications, \
    receives_online_notifications, receives_stream_notifications, get_user_profile_by_id
from version import ZULIP_VERSION

if settings.ZILENCER_ENABLED:
    from zilencer.models import RemotePushDeviceToken
else:  # nocoverage  -- Not convenient to add test for this.
    from mock import Mock
    RemotePushDeviceToken = Mock()  # type: ignore # https://github.com/JukkaL/mypy/issues/1188

DeviceToken = Union[PushDeviceToken, RemotePushDeviceToken]

# We store the token as b64, but apns-client wants hex strings
def b64_to_hex(data):
    # type: (bytes) -> Text
    return binascii.hexlify(base64.b64decode(data)).decode('utf-8')

def hex_to_b64(data):
    # type: (Text) -> bytes
    return base64.b64encode(binascii.unhexlify(data.encode('utf-8')))

#
# Sending to APNs, for iOS
#

_apns_client = None  # type: APNsClient

def get_apns_client():
    # type: () -> APNsClient
    global _apns_client
    if _apns_client is None:
        # NB if called concurrently, this will make excess connections.
        # That's a little sloppy, but harmless unless a server gets
        # hammered with a ton of these all at once after startup.
        _apns_client = APNsClient(credentials=settings.APNS_CERT_FILE,
                                  use_sandbox=settings.APNS_SANDBOX)
    return _apns_client

APNS_MAX_RETRIES = 3

@statsd_increment("apple_push_notification")
def send_apple_push_notification(user_id, devices, payload_data):
    # type: (int, List[DeviceToken], Dict[str, Any]) -> None
    if not devices:
        return
    logging.info("APNs: Sending notification for user %d to %d devices",
                 user_id, len(devices))
    payload = APNsPayload(**payload_data)
    expiration = int(time.time() + 24 * 3600)
    client = get_apns_client()
    retries_left = APNS_MAX_RETRIES
    for device in devices:
        # TODO obviously this should be made to actually use the async

        def attempt_send():
            # type: () -> Optional[str]
            stream_id = client.send_notification_async(
                device.token, payload, topic='org.zulip.Zulip',
                expiration=expiration)
            try:
                return client.get_notification_result(stream_id)
            except HTTP20Error as e:
                logging.warn("APNs: HTTP error sending for user %d to device %s: %s",
                             user_id, device.token, e.__class__.__name__)
                return None

        result = attempt_send()
        while result is None and retries_left > 0:
            retries_left -= 1
            result = attempt_send()
        if result is None:
            result = "HTTP error, retries exhausted"

        if result == 'Success':
            logging.info("APNs: Success sending for user %d to device %s",
                         user_id, device.token)
        else:
            logging.warn("APNs: Failed to send for user %d to device %s: %s",
                         user_id, device.token, result)
            # TODO delete token if status 410 (and timestamp isn't before
            #      the token we have)

#
# Sending to GCM, for Android
#

if settings.ANDROID_GCM_API_KEY:  # nocoverage
    gcm = GCM(settings.ANDROID_GCM_API_KEY)
else:
    gcm = None

def send_android_push_notification_to_user(user_profile, data):
    # type: (UserProfile, Dict[str, Any]) -> None
    devices = list(PushDeviceToken.objects.filter(user=user_profile,
                                                  kind=PushDeviceToken.GCM))
    send_android_push_notification(devices, data)

@statsd_increment("android_push_notification")
def send_android_push_notification(devices, data, remote=False):
    # type: (List[DeviceToken], Dict[str, Any], bool) -> None
    if not gcm:
        logging.warning("Attempting to send a GCM push notification, but no API key was configured")
        return
    reg_ids = [device.token for device in devices]

    if remote:
        DeviceTokenClass = RemotePushDeviceToken
    else:
        DeviceTokenClass = PushDeviceToken

    try:
        res = gcm.json_request(registration_ids=reg_ids, data=data, retries=10)
    except IOError as e:
        logging.warning(str(e))
        return

    if res and 'success' in res:
        for reg_id, msg_id in res['success'].items():
            logging.info("GCM: Sent %s as %s" % (reg_id, msg_id))

    # res.canonical will contain results when there are duplicate registrations for the same
    # device. The "canonical" registration is the latest registration made by the device.
    # Ref: http://developer.android.com/google/gcm/adv.html#canonical
    if 'canonical' in res:
        for reg_id, new_reg_id in res['canonical'].items():
            if reg_id == new_reg_id:
                # I'm not sure if this should happen. In any case, not really actionable.
                logging.warning("GCM: Got canonical ref but it already matches our ID %s!" % (reg_id,))
            elif not DeviceTokenClass.objects.filter(token=new_reg_id,
                                                     kind=DeviceTokenClass.GCM).count():
                # This case shouldn't happen; any time we get a canonical ref it should have been
                # previously registered in our system.
                #
                # That said, recovery is easy: just update the current PDT object to use the new ID.
                logging.warning(
                    "GCM: Got canonical ref %s replacing %s but new ID not registered! Updating." %
                    (new_reg_id, reg_id))
                DeviceTokenClass.objects.filter(
                    token=reg_id, kind=DeviceTokenClass.GCM).update(token=new_reg_id)
            else:
                # Since we know the new ID is registered in our system we can just drop the old one.
                logging.info("GCM: Got canonical ref %s, dropping %s" % (new_reg_id, reg_id))

                DeviceTokenClass.objects.filter(token=reg_id, kind=DeviceTokenClass.GCM).delete()

    if 'errors' in res:
        for error, reg_ids in res['errors'].items():
            if error in ['NotRegistered', 'InvalidRegistration']:
                for reg_id in reg_ids:
                    logging.info("GCM: Removing %s" % (reg_id,))

                    device = DeviceTokenClass.objects.get(token=reg_id, kind=DeviceTokenClass.GCM)
                    device.delete()
            else:
                for reg_id in reg_ids:
                    logging.warning("GCM: Delivery to %s failed: %s" % (reg_id, error))

    # python-gcm handles retrying of the unsent messages.
    # Ref: https://github.com/geeknam/python-gcm/blob/master/gcm/gcm.py#L497

#
# Sending to a bouncer
#

def uses_notification_bouncer():
    # type: () -> bool
    return settings.PUSH_NOTIFICATION_BOUNCER_URL is not None

def send_notifications_to_bouncer(user_profile_id, apns_payload, gcm_payload):
    # type: (int, Dict[str, Any], Dict[str, Any]) -> None
    post_data = {
        'user_id': user_profile_id,
        'apns_payload': apns_payload,
        'gcm_payload': gcm_payload,
    }
    send_json_to_push_bouncer('POST', 'notify', post_data)

def send_json_to_push_bouncer(method, endpoint, post_data):
    # type: (str, str, Dict[str, Any]) -> None
    send_to_push_bouncer(
        method,
        endpoint,
        ujson.dumps(post_data),
        extra_headers={"Content-type": "application/json"},
    )

def send_to_push_bouncer(method, endpoint, post_data, extra_headers=None):
    # type: (str, str, Union[Text, Dict[str, Any]], Optional[Dict[str, Any]]) -> None
    url = urllib.parse.urljoin(settings.PUSH_NOTIFICATION_BOUNCER_URL,
                               '/api/v1/remotes/push/' + endpoint)
    api_auth = requests.auth.HTTPBasicAuth(settings.ZULIP_ORG_ID,
                                           settings.ZULIP_ORG_KEY)

    headers = {"User-agent": "ZulipServer/%s" % (ZULIP_VERSION,)}
    if extra_headers is not None:
        headers.update(extra_headers)

    res = requests.request(method,
                           url,
                           data=post_data,
                           auth=api_auth,
                           timeout=30,
                           verify=True,
                           headers=headers)

    # TODO: Think more carefully about how this error hanlding should work.
    if res.status_code >= 500:
        raise JsonableError(_("Error received from push notification bouncer"))
    elif res.status_code >= 400:
        try:
            msg = ujson.loads(res.content)['msg']
        except Exception:
            raise JsonableError(_("Error received from push notification bouncer"))
        raise JsonableError(msg)
    elif res.status_code != 200:
        raise JsonableError(_("Error received from push notification bouncer"))

    # If we don't throw an exception, it's a successful bounce!

#
# Managing device tokens
#

def num_push_devices_for_user(user_profile, kind = None):
    # type: (UserProfile, Optional[int]) -> PushDeviceToken
    if kind is None:
        return PushDeviceToken.objects.filter(user=user_profile).count()
    else:
        return PushDeviceToken.objects.filter(user=user_profile, kind=kind).count()

def add_push_device_token(user_profile, token_str, kind, ios_app_id=None):
    # type: (UserProfile, bytes, int, Optional[str]) -> None

    logging.info("New push device: %d %r %d %r",
                 user_profile.id, token_str, kind, ios_app_id)

    # If we're sending things to the push notification bouncer
    # register this user with them here
    if uses_notification_bouncer():
        post_data = {
            'server_uuid': settings.ZULIP_ORG_ID,
            'user_id': user_profile.id,
            'token': token_str,
            'token_kind': kind,
        }

        if kind == PushDeviceToken.APNS:
            post_data['ios_app_id'] = ios_app_id

        logging.info("Sending new push device to bouncer: %r", post_data)
        send_to_push_bouncer('POST', 'register', post_data)
        return

    # If another user was previously logged in on the same device and didn't
    # properly log out, the token will still be registered to the wrong account
    PushDeviceToken.objects.filter(token=token_str).exclude(user=user_profile).delete()

    # Overwrite with the latest value
    token, created = PushDeviceToken.objects.get_or_create(user=user_profile,
                                                           token=token_str,
                                                           defaults=dict(
                                                               kind=kind,
                                                               ios_app_id=ios_app_id))
    if not created:
        logging.info("Existing push device updated.")
        token.last_updated = timezone_now()
        token.save(update_fields=['last_updated'])
    else:
        logging.info("New push device created.")

def remove_push_device_token(user_profile, token_str, kind):
    # type: (UserProfile, bytes, int) -> None

    # If we're sending things to the push notification bouncer
    # register this user with them here
    if uses_notification_bouncer():
        # TODO: Make this a remove item
        post_data = {
            'server_uuid': settings.ZULIP_ORG_ID,
            'user_id': user_profile.id,
            'token': token_str,
            'token_kind': kind,
        }
        send_to_push_bouncer("POST", "unregister", post_data)
        return

    try:
        token = PushDeviceToken.objects.get(token=token_str, kind=kind)
        token.delete()
    except PushDeviceToken.DoesNotExist:
        raise JsonableError(_("Token does not exist"))

#
# Push notifications in general
#

def get_alert_from_message(message):
    # type: (Message) -> Text
    """
    Determine what alert string to display based on the missed messages.
    """
    sender_str = message.sender.full_name
    if message.recipient.type == Recipient.HUDDLE and message.triggers['private_message']:
        return "New private group message from %s" % (sender_str,)
    elif message.recipient.type == Recipient.PERSONAL and message.triggers['private_message']:
        return "New private message from %s" % (sender_str,)
    elif message.recipient.type == Recipient.STREAM and message.triggers['mentioned']:
        return "New mention from %s" % (sender_str,)
    elif (message.recipient.type == Recipient.STREAM and
            (message.triggers['stream_push_notify'] and message.stream_name)):
        return "New stream message from %s in %s" % (sender_str, message.stream_name,)
    else:
        return "New Zulip mentions and private messages from %s" % (sender_str,)

def get_apns_payload(message):
    # type: (Message) -> Dict[str, Any]
    return {
        'alert': {
            'title': get_alert_from_message(message),
            'body': message.content[:200],
        },
        # TODO: set badge count in a better way
        'badge': 1,
        'custom': {
            'zulip': {
                'message_ids': [message.id],
            }
        }
    }

def get_gcm_payload(user_profile, message):
    # type: (UserProfile, Message) -> Dict[str, Any]
    content = message.content
    content_truncated = (len(content) > 200)
    if content_truncated:
        content = content[:200] + "..."

    android_data = {
        'user': user_profile.email,
        'event': 'message',
        'alert': get_alert_from_message(message),
        'zulip_message_id': message.id,  # message_id is reserved for CCS
        'time': datetime_to_timestamp(message.pub_date),
        'content': content,
        'content_truncated': content_truncated,
        'sender_email': message.sender.email,
        'sender_full_name': message.sender.full_name,
        'sender_avatar_url': absolute_avatar_url(message.sender),
    }

    if message.recipient.type == Recipient.STREAM:
        android_data['recipient_type'] = "stream"
        android_data['stream'] = get_display_recipient(message.recipient)
        android_data['topic'] = message.subject
    elif message.recipient.type in (Recipient.HUDDLE, Recipient.PERSONAL):
        android_data['recipient_type'] = "private"

    return android_data

@statsd_increment("push_notifications")
def handle_push_notification(user_profile_id, missed_message):
    # type: (int, Dict[str, Any]) -> None
    """
    missed_message is the event received by the
    zerver.worker.queue_processors.PushNotificationWorker.consume function.
    """
    try:
        user_profile = get_user_profile_by_id(user_profile_id)
        if not (receives_offline_notifications(user_profile) or
                receives_online_notifications(user_profile)):
            return

        umessage = UserMessage.objects.get(user_profile=user_profile,
                                           message__id=missed_message['message_id'])
        message = umessage.message
        triggers = missed_message['triggers']
        message.triggers = {
            'private_message': triggers['private_message'],
            'mentioned': triggers['mentioned'],
            'stream_push_notify': triggers['stream_push_notify'],
        }
        message.stream_name = missed_message.get('stream_name', None)

        if umessage.flags.read:
            return

        apns_payload = get_apns_payload(message)
        gcm_payload = get_gcm_payload(user_profile, message)
        logging.info("Sending push notification to user %s" % (user_profile_id,))

        if uses_notification_bouncer():
            try:
                send_notifications_to_bouncer(user_profile_id,
                                              apns_payload,
                                              gcm_payload)
            except requests.ConnectionError:
                if 'failed_tries' not in missed_message:
                    missed_message['failed_tries'] = 0

                def failure_processor(event):
                    # type: (Dict[str, Any]) -> None
                    logging.warning("Maximum retries exceeded for trigger:%s event:push_notification" % (event['user_profile_id']))
                retry_event('missedmessage_mobile_notifications', missed_message,
                            failure_processor)

            return

        android_devices = list(PushDeviceToken.objects.filter(user=user_profile,
                                                              kind=PushDeviceToken.GCM))

        apple_devices = list(PushDeviceToken.objects.filter(user=user_profile,
                                                            kind=PushDeviceToken.APNS))

        if apple_devices:
            send_apple_push_notification(user_profile.id, apple_devices,
                                         apns_payload)

        if android_devices:
            send_android_push_notification(android_devices, gcm_payload)

    except UserMessage.DoesNotExist:
        logging.error("Could not find UserMessage with message_id %s" % (missed_message['message_id'],))
