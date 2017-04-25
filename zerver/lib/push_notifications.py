from __future__ import absolute_import

import random
import requests
from typing import Any, Dict, List, Optional, SupportsInt, Text

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

# APNS error codes
ERROR_CODES = {
    1: 'Processing error',
    2: 'Missing device token', # looks like token was empty?
    3: 'Missing topic', # topic is encoded in the certificate, looks like certificate is wrong. bail out.
    4: 'Missing payload', # bail out, our message looks like empty
    5: 'Invalid token size', # current token has wrong size, skip it and retry
    6: 'Invalid topic size', # can not happen, we do not send topic, it is part of certificate. bail out.
    7: 'Invalid payload size', # our payload is probably too big. bail out.
    8: 'Invalid token', # our device token is broken, skipt it and retry
    10: 'Shutdown', # server went into maintenance mode. reported token is the last success, skip it and retry.
    None: 'Unknown', # unknown error, for sure we try again, but user should limit number of retries
}

redis_client = get_redis_client()

# Maintain a long-lived Session object to avoid having to re-SSL-handshake
# for each request
connection = None

# We maintain an additional APNS connection for pushing to Zulip apps that have been signed
# by the Dropbox certs (and have an app id of com.dropbox.zulip)
dbx_connection = None

# `APNS_SANDBOX` should be a bool
assert isinstance(settings.APNS_SANDBOX, bool)

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
        except PushDeviceToken.DoesNotExist:
            pass

def get_connection(cert_file, key_file):
    # type: (str, str) -> APNs
    connection = APNs(use_sandbox=settings.APNS_SANDBOX,
                      cert_file=cert_file,
                      key_file=key_file,
                      enhanced=True)
    connection.gateway_server.register_response_listener(response_listener)
    return connection

if settings.APNS_CERT_FILE is not None and os.path.exists(settings.APNS_CERT_FILE):
    connection = get_connection(settings.APNS_CERT_FILE,
                                settings.APNS_KEY_FILE)

if settings.DBX_APNS_CERT_FILE is not None and os.path.exists(settings.DBX_APNS_CERT_FILE):
    dbx_connection = get_connection(settings.DBX_APNS_CERT_FILE,
                                    settings.DBX_APNS_KEY_FILE)

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
    if not apns_connection:
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
    # type: (int, List[PushDeviceToken], **Any) -> None
    if not connection and not dbx_connection:
        logging.warning("Attempting to send push notification, but no connection was found. "
                        "This may be because we could not find the APNS Certificate file.")
        return

    # Plain b64 token kept for debugging purposes
    tokens = [(b64_to_hex(device.token), device.ios_app_id, device.token)
              for device in devices]

    for conn, app_ids in [
            (connection, [settings.ZULIP_IOS_APP_ID, None]),
            (dbx_connection, [settings.DBX_IOS_APP_ID])]:

        valid_devices = [device for device in tokens if device[1] in app_ids]
        valid_tokens = [device[0] for device in valid_devices]
        if valid_tokens:
            logging.info("APNS: Sending apple push notification "
                         "to devices: %s" % (valid_devices,))
            zulip_message = APNsMessage(user_id, valid_tokens,
                                        alert=extra_data['zulip']['alert'],
                                        **extra_data)
            _do_push_to_apns_service(user_id, zulip_message, conn)
        else:
            logging.warn("APNS: Not sending notification because "
                         "tokens didn't match devices: %s" % (app_ids,))

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


if settings.ANDROID_GCM_API_KEY:
    gcm = GCM(settings.ANDROID_GCM_API_KEY)
else:
    gcm = None

def send_android_push_notification_to_user(user_profile, data):
    # type: (UserProfile, Dict[str, Any]) -> None
    devices = list(PushDeviceToken.objects.filter(user=user_profile,
                                                  kind=PushDeviceToken.GCM))
    send_android_push_notification(devices, data)

@statsd_increment("android_push_notification")
def send_android_push_notification(devices, data):
    # type: (List[PushDeviceToken], Dict[str, Any]) -> None
    if not gcm:
        logging.warning("Attempting to send a GCM push notification, but no API key was configured")
        return
    reg_ids = [device.token for device in devices]

    res = gcm.json_request(registration_ids=reg_ids, data=data)

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
            elif not PushDeviceToken.objects.filter(token=new_reg_id, kind=PushDeviceToken.GCM).count():
                # This case shouldn't happen; any time we get a canonical ref it should have been
                # previously registered in our system.
                #
                # That said, recovery is easy: just update the current PDT object to use the new ID.
                logging.warning(
                    "GCM: Got canonical ref %s replacing %s but new ID not registered! Updating." %
                    (new_reg_id, reg_id))
                PushDeviceToken.objects.filter(
                    token=reg_id, kind=PushDeviceToken.GCM).update(token=new_reg_id)
            else:
                # Since we know the new ID is registered in our system we can just drop the old one.
                logging.info("GCM: Got canonical ref %s, dropping %s" % (new_reg_id, reg_id))

                PushDeviceToken.objects.filter(token=reg_id, kind=PushDeviceToken.GCM).delete()

    if 'errors' in res:
        for error, reg_ids in res['errors'].items():
            if error in ['NotRegistered', 'InvalidRegistration']:
                for reg_id in reg_ids:
                    logging.info("GCM: Removing %s" % (reg_id,))

                    device = PushDeviceToken.objects.get(token=reg_id, kind=PushDeviceToken.GCM)
                    device.delete()
            else:
                for reg_id in reg_ids:
                    logging.warning("GCM: Delivery to %s failed: %s" % (reg_id, error))

    # python-gcm handles retrying of the unsent messages.
    # Ref: https://github.com/geeknam/python-gcm/blob/master/gcm/gcm.py#L497

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
        sender_str = message.sender.full_name

        android_devices = [device for device in
                           PushDeviceToken.objects.filter(user=user_profile,
                                                          kind=PushDeviceToken.GCM)]
        apple_devices = list(PushDeviceToken.objects.filter(user=user_profile,
                                                            kind=PushDeviceToken.APNS))

        if apple_devices or android_devices:
            # TODO: set badge count in a better way
            # Determine what alert string to display based on the missed messages
            if message.recipient.type == Recipient.HUDDLE:
                alert = "New private group message from %s" % (sender_str,)
            elif message.recipient.type == Recipient.PERSONAL:
                alert = "New private message from %s" % (sender_str,)
            elif message.recipient.type == Recipient.STREAM:
                alert = "New mention from %s" % (sender_str,)
            else:
                alert = "New Zulip mentions and private messages from %s" % (sender_str,)

            if apple_devices:
                apple_extra_data = {
                    'alert': alert,
                    'message_ids': [message.id],
                }
                send_apple_push_notification(user_profile.id, apple_devices,
                                             badge=1, zulip=apple_extra_data)

            if android_devices:
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
                    'sender_avatar_url': avatar_url(message.sender),
                }

                if message.recipient.type == Recipient.STREAM:
                    android_data['recipient_type'] = "stream"
                    android_data['stream'] = get_display_recipient(message.recipient)
                    android_data['topic'] = message.subject
                elif message.recipient.type in (Recipient.HUDDLE, Recipient.PERSONAL):
                    android_data['recipient_type'] = "private"

                send_android_push_notification(android_devices, android_data)

    except UserMessage.DoesNotExist:
        logging.error("Could not find UserMessage with message_id %s" % (missed_message['message_id'],))

def add_push_device_token(user_profile, token_str, kind, ios_app_id=None):
    # type: (UserProfile, str, int, Optional[str]) -> None

    # If we're sending things to the push notification bouncer
    # register this user with them here
    if settings.PUSH_NOTIFICATION_BOUNCER_URL is not None:
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
    if settings.PUSH_NOTIFICATION_BOUNCER_URL is not None:
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


def send_to_push_bouncer(method, endpoint, post_data):
    # type: (str, str, Dict[str, Any]) -> None
    url = urllib.parse.urljoin(settings.PUSH_NOTIFICATION_BOUNCER_URL,
                               '/api/v1/remotes/push/' + endpoint)
    api_auth = requests.auth.HTTPBasicAuth(settings.ZULIP_ORG_ID,
                                           settings.ZULIP_ORG_KEY)

    res = requests.request(method,
                           url,
                           data=ujson.dumps(post_data),
                           auth=api_auth,
                           timeout=30,
                           verify=True,
                           headers={"User-agent": "ZulipServer/%s" % (ZULIP_VERSION,)})

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
