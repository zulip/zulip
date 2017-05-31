from __future__ import absolute_import

import random
import requests
from typing import Any, Dict, List, Optional, SupportsInt, Text, Union, Type

from version import ZULIP_VERSION
from zerver.models import PushDeviceToken, Message, Recipient, UserProfile, \
    UserMessage, get_display_recipient, receives_offline_notifications, \
    receives_online_notifications
from zerver.models import get_user_profile_by_id
from zerver.lib.avatar import avatar_url
from zerver.lib.request import JsonableError
from zerver.lib.timestamp import datetime_to_timestamp, timestamp_to_datetime
from zerver.decorator import statsd_increment
from zerver.lib.utils import generate_random_token
from zerver.lib.redis_utils import get_redis_client

from apns import APNs, Frame, Payload, SENT_BUFFER_QTY
from gcm import GCM

from django.conf import settings
from django.utils.timezone import now as timezone_now
from django.utils.translation import ugettext as _
from six.moves import urllib

import base64
import binascii
import logging
import os
import time
import ujson
from functools import partial

if settings.ZILENCER_ENABLED:
    from zilencer.models import RemotePushDeviceToken
else:  # nocoverage  -- Not convenient to add test for this.
    from mock import Mock
    RemotePushDeviceToken = Mock()  # type: ignore # https://github.com/JukkaL/mypy/issues/1188

DeviceToken = Union[PushDeviceToken, RemotePushDeviceToken]

# APNS error codes
ERROR_CODES = {
    1: 'Processing error',
    2: 'Missing device token',  # looks like token was empty?
    3: 'Missing topic',  # topic is encoded in the certificate, looks like certificate is wrong. bail out.
    4: 'Missing payload',  # bail out, our message looks like empty
    5: 'Invalid token size',  # current token has wrong size, skip it and retry
    6: 'Invalid topic size',  # can not happen, we do not send topic, it is part of certificate. bail out.
    7: 'Invalid payload size',  # our payload is probably too big. bail out.
    8: 'Invalid token',  # our device token is broken, skipt it and retry
    10: 'Shutdown',  # server went into maintenance mode. reported token is the last success, skip it and retry.
    None: 'Unknown',  # unknown error, for sure we try again, but user should limit number of retries
}

redis_client = get_redis_client()

# Maintain a long-lived Session object to avoid having to re-SSL-handshake
# for each request
connection = None

# `APNS_SANDBOX` should be a bool
assert isinstance(settings.APNS_SANDBOX, bool)

def uses_notification_bouncer():
    # type: () -> bool
    return settings.PUSH_NOTIFICATION_BOUNCER_URL is not None

def get_apns_key(identifer):
    # type: (SupportsInt) -> str
    return 'apns:' + str(identifer)

class APNsMessage(object):
    def __init__(self, user_id, tokens, alert=None, badge=None, sound=None,
                 category=None, **kwargs):
        # type: (int, List[Text], Text, int, Text, Text, **Any) -> None
        self.frame = Frame()
        self.tokens = tokens
        expiry = int(time.time() + 24 * 3600)
        priority = 10
        payload = Payload(alert=alert, badge=badge, sound=sound,
                          category=category, custom=kwargs)
        for token in tokens:
            data = {'token': token, 'user_id': user_id}
            identifier = random.getrandbits(32)
            key = get_apns_key(identifier)
            redis_client.hmset(key, data)
            redis_client.expire(key, expiry)
            self.frame.add_item(token, payload, identifier, expiry, priority)

    def get_frame(self):
        # type: () -> Frame
        return self.frame

def response_listener(error_response):
    # type: (Dict[str, SupportsInt]) -> None
    identifier = error_response['identifier']
    key = get_apns_key(identifier)
    if not redis_client.exists(key):
        logging.warn("APNs key, {}, doesn't not exist.".format(key))
        return

    code = error_response['status']
    assert isinstance(code, int)

    errmsg = ERROR_CODES[code]
    data = redis_client.hgetall(key)
    token = data['token']
    user = get_user_profile_by_id(int(data['user_id']))
    b64_token = hex_to_b64(token)

    logging.warn("APNS: Failed to deliver APNS notification to %s, reason: %s" % (b64_token, errmsg))
    if code == 8:
        # Invalid Token, remove from our database
        logging.warn("APNS: Removing token from database due to above failure")
        try:
            PushDeviceToken.objects.get(user=user, token=b64_token).delete()
            return  # No need to check RemotePushDeviceToken
        except PushDeviceToken.DoesNotExist:
            pass

        if settings.ZILENCER_ENABLED:
            # Trying to delete from both models is a bit inefficient than
            # deleting from only one model but this method is very simple.
            try:
                RemotePushDeviceToken.objects.get(user_id=user.id,
                                                  token=b64_token).delete()
            except RemotePushDeviceToken.DoesNotExist:
                pass

def get_connection(cert_file, key_file):
    # type: (str, str) -> APNs
    connection = APNs(use_sandbox=settings.APNS_SANDBOX,
                      cert_file=cert_file,
                      key_file=key_file,
                      enhanced=True)
    connection.gateway_server.register_response_listener(response_listener)
    return connection

if settings.APNS_CERT_FILE is not None and os.path.exists(settings.APNS_CERT_FILE):  # nocoverage
    connection = get_connection(settings.APNS_CERT_FILE,
                                settings.APNS_KEY_FILE)

def num_push_devices_for_user(user_profile, kind = None):
    # type: (UserProfile, Optional[int]) -> PushDeviceToken
    if kind is None:
        return PushDeviceToken.objects.filter(user=user_profile).count()
    else:
        return PushDeviceToken.objects.filter(user=user_profile, kind=kind).count()

# We store the token as b64, but apns-client wants hex strings
def b64_to_hex(data):
    # type: (bytes) -> Text
    return binascii.hexlify(base64.b64decode(data)).decode('utf-8')

def hex_to_b64(data):
    # type: (Text) -> bytes
    return base64.b64encode(binascii.unhexlify(data.encode('utf-8')))

def _do_push_to_apns_service(user_id, message, apns_connection):
    # type: (int, APNsMessage, APNs) -> None
    if not apns_connection:  # nocoverage
        logging.info("Not delivering APNS message %s to user %s due to missing connection" % (message, user_id))
        return

    frame = message.get_frame()
    apns_connection.gateway_server.send_notification_multiple(frame)

def send_apple_push_notification_to_user(user, alert, **extra_data):
    # type: (UserProfile, Text, **Any) -> None
    devices = PushDeviceToken.objects.filter(user=user, kind=PushDeviceToken.APNS)
    send_apple_push_notification(user.id, devices, zulip=dict(alert=alert),
                                 **extra_data)

# Send a push notification to the desired clients
# extra_data is a dict that will be passed to the
# mobile app
@statsd_increment("apple_push_notification")
def send_apple_push_notification(user_id, devices, **extra_data):
    # type: (int, List[DeviceToken], **Any) -> None
    if not connection:
        logging.warning("Attempting to send push notification, but no connection was found. "
                        "This may be because we could not find the APNS Certificate file.")
        return

    # Plain b64 token kept for debugging purposes
    tokens = [(b64_to_hex(device.token), device.ios_app_id, device.token)
              for device in devices]

    valid_devices = [device for device in tokens if device[1] in [settings.ZULIP_IOS_APP_ID, None]]
    valid_tokens = [device[0] for device in valid_devices]
    if valid_tokens:
        logging.info("APNS: Sending apple push notification "
                     "to devices: %s" % (valid_devices,))
        zulip_message = APNsMessage(user_id, valid_tokens,
                                    alert=extra_data['zulip']['alert'],
                                    **extra_data)
        _do_push_to_apns_service(user_id, zulip_message, connection)
    else:  # nocoverage
        logging.warn("APNS: Not sending notification because "
                     "tokens didn't match devices: %s/%s" % (tokens, settings.ZULIP_IOS_APP_ID,))

# NOTE: This is used by the check_apns_tokens manage.py command. Do not call it otherwise, as the
# feedback() call can take up to 15s
def check_apns_feedback():
    # type: () -> None
    feedback_connection = APNs(use_sandbox=settings.APNS_SANDBOX,
                               cert_file=settings.APNS_CERT_FILE,
                               key_file=settings.APNS_KEY_FILE)

    for token, since in feedback_connection.feedback_server.items():
        since_date = timestamp_to_datetime(since)
        logging.info("Found unavailable token %s, unavailable since %s" % (token, since_date))

        PushDeviceToken.objects.filter(token=hex_to_b64(token), last_updated__lt=since_date,
                                       kind=PushDeviceToken.APNS).delete()
    logging.info("Finished checking feedback for stale tokens")


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

def get_alert_from_message(message):
    # type: (Message) -> Text
    """
    Determine what alert string to display based on the missed messages.
    """
    sender_str = message.sender.full_name
    if message.recipient.type == Recipient.HUDDLE:
        return "New private group message from %s" % (sender_str,)
    elif message.recipient.type == Recipient.PERSONAL:
        return "New private message from %s" % (sender_str,)
    elif message.recipient.type == Recipient.STREAM:
        return "New mention from %s" % (sender_str,)
    else:
        return "New Zulip mentions and private messages from %s" % (sender_str,)

def get_apns_payload(message):
    # type: (Message) -> Dict[str, Any]
    return {
        'alert': get_alert_from_message(message),
        'message_ids': [message.id],
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
        'sender_avatar_url': avatar_url(message.sender),
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
    try:
        user_profile = get_user_profile_by_id(user_profile_id)
        if not (receives_offline_notifications(user_profile) or receives_online_notifications(user_profile)):
            return

        umessage = UserMessage.objects.get(user_profile=user_profile,
                                           message__id=missed_message['message_id'])
        message = umessage.message
        if umessage.flags.read:
            return

        apns_payload = get_apns_payload(message)
        gcm_payload = get_gcm_payload(user_profile, message)

        if uses_notification_bouncer():
            send_notifications_to_bouncer(user_profile_id,
                                          apns_payload,
                                          gcm_payload)
            return

        android_devices = list(PushDeviceToken.objects.filter(user=user_profile,
                                                              kind=PushDeviceToken.GCM))

        apple_devices = list(PushDeviceToken.objects.filter(user=user_profile,
                                                            kind=PushDeviceToken.APNS))

        # TODO: set badge count in a better way
        if apple_devices:
            send_apple_push_notification(user_profile.id, apple_devices,
                                         badge=1, zulip=apns_payload)

        if android_devices:
            send_android_push_notification(android_devices, gcm_payload)

    except UserMessage.DoesNotExist:
        logging.error("Could not find UserMessage with message_id %s" % (missed_message['message_id'],))

def send_notifications_to_bouncer(user_profile_id, apns_payload, gcm_payload):
    # type: (int, Dict[str, Any], Dict[str, Any]) -> None
    post_data = {
        'user_id': user_profile_id,
        'apns_payload': apns_payload,
        'gcm_payload': gcm_payload,
    }
    send_json_to_push_bouncer('POST', 'notify', post_data)

def add_push_device_token(user_profile, token_str, kind, ios_app_id=None):
    # type: (UserProfile, str, int, Optional[str]) -> None

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
        token.last_updated = timezone_now()
        token.save(update_fields=['last_updated'])

def remove_push_device_token(user_profile, token_str, kind):
    # type: (UserProfile, str, int) -> None

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
