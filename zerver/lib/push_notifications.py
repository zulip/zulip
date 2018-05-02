# -*- coding: utf-8 -*-

import base64
import binascii
from functools import partial
import logging
import lxml.html as LH
import os
import re
import time
import random

from typing import Any, Dict, List, Optional, SupportsInt, Text, Tuple, Type, Union

from apns2.client import APNsClient
from apns2.payload import Payload as APNsPayload
from django.conf import settings
from django.utils.timezone import now as timezone_now
from django.utils.translation import ugettext as _
from gcm import GCM
from hyper.http20.exceptions import HTTP20Error
import requests
import urllib
import ujson

from zerver.decorator import statsd_increment
from zerver.lib.avatar import absolute_avatar_url
from zerver.lib.exceptions import ErrorCode, JsonableError
from zerver.lib.message import access_message, huddle_users
from zerver.lib.queue import retry_event
from zerver.lib.timestamp import datetime_to_timestamp, timestamp_to_datetime
from zerver.lib.utils import generate_random_token
from zerver.models import PushDeviceToken, Message, Recipient, UserProfile, \
    UserMessage, get_display_recipient, receives_offline_push_notifications, \
    receives_online_notifications, receives_stream_notifications, get_user_profile_by_id
from version import ZULIP_VERSION

if settings.ZILENCER_ENABLED:
    from zilencer.models import RemotePushDeviceToken
else:  # nocoverage  -- Not convenient to add test for this.
    from mock import Mock
    RemotePushDeviceToken = Mock()  # type: ignore # https://github.com/JukkaL/mypy/issues/1188

DeviceToken = Union[PushDeviceToken, RemotePushDeviceToken]

# We store the token as b64, but apns-client wants hex strings
def b64_to_hex(data: bytes) -> Text:
    return binascii.hexlify(base64.b64decode(data)).decode('utf-8')

def hex_to_b64(data: Text) -> bytes:
    return base64.b64encode(binascii.unhexlify(data.encode('utf-8')))

#
# Sending to APNs, for iOS
#

_apns_client = None  # type: Optional[APNsClient]
_apns_client_initialized = False

def get_apns_client() -> APNsClient:
    global _apns_client, _apns_client_initialized
    if not _apns_client_initialized:
        # NB if called concurrently, this will make excess connections.
        # That's a little sloppy, but harmless unless a server gets
        # hammered with a ton of these all at once after startup.
        if settings.APNS_CERT_FILE is not None:
            _apns_client = APNsClient(credentials=settings.APNS_CERT_FILE,
                                      use_sandbox=settings.APNS_SANDBOX)
        _apns_client_initialized = True
    return _apns_client

def apns_enabled() -> bool:
    client = get_apns_client()
    return client is not None

def modernize_apns_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    '''Take a payload in an unknown Zulip version's format, and return in current format.'''
    # TODO this isn't super robust as is -- if a buggy remote server
    # sends a malformed payload, we are likely to raise an exception.
    if 'message_ids' in data:
        # The format sent by 1.6.0, from the earliest pre-1.6.0
        # version with bouncer support up until 613d093d7 pre-1.7.0:
        #   'alert': str,              # just sender, and text about PM/group-PM/mention
        #   'message_ids': List[int],  # always just one
        return {
            'alert': data['alert'],
            'badge': 0,
            'custom': {
                'zulip': {
                    'message_ids': data['message_ids'],
                },
            },
        }
    else:
        # Something already compatible with the current format.
        # `alert` may be a string, or a dict with `title` and `body`.
        # In 1.7.0 and 1.7.1, before 0912b5ba8 pre-1.8.0, the only
        # item in `custom.zulip` is `message_ids`.
        return data

APNS_MAX_RETRIES = 3

@statsd_increment("apple_push_notification")
def send_apple_push_notification(user_id: int, devices: List[DeviceToken],
                                 payload_data: Dict[str, Any]) -> None:
    client = get_apns_client()
    if client is None:
        logging.warning("APNs: Dropping a notification because nothing configured.  "
                        "Set PUSH_NOTIFICATION_BOUNCER_URL (or APNS_CERT_FILE).")
        return
    logging.info("APNs: Sending notification for user %d to %d devices",
                 user_id, len(devices))
    payload = APNsPayload(**modernize_apns_payload(payload_data))
    expiration = int(time.time() + 24 * 3600)
    retries_left = APNS_MAX_RETRIES
    for device in devices:
        # TODO obviously this should be made to actually use the async

        def attempt_send() -> Optional[str]:
            stream_id = client.send_notification_async(
                device.token, payload, topic='org.zulip.Zulip',
                expiration=expiration)
            try:
                return client.get_notification_result(stream_id)
            except HTTP20Error as e:
                logging.warning("APNs: HTTP error sending for user %d to device %s: %s",
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
            logging.warning("APNs: Failed to send for user %d to device %s: %s",
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

def gcm_enabled() -> bool:  # nocoverage
    return gcm is not None

def send_android_push_notification_to_user(user_profile: UserProfile, data: Dict[str, Any]) -> None:
    devices = list(PushDeviceToken.objects.filter(user=user_profile,
                                                  kind=PushDeviceToken.GCM))
    send_android_push_notification(devices, data)

@statsd_increment("android_push_notification")
def send_android_push_notification(devices: List[DeviceToken], data: Dict[str, Any],
                                   remote: bool=False) -> None:
    if not gcm:
        logging.warning("Skipping sending a GCM push notification since "
                        "PUSH_NOTIFICATION_BOUNCER_URL and ANDROID_GCM_API_KEY are both unset")
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
                    # We remove all entries for this token (There
                    # could be multiple for different Zulip servers).
                    DeviceTokenClass.objects.filter(token=reg_id, kind=DeviceTokenClass.GCM).delete()
            else:
                for reg_id in reg_ids:
                    logging.warning("GCM: Delivery to %s failed: %s" % (reg_id, error))

    # python-gcm handles retrying of the unsent messages.
    # Ref: https://github.com/geeknam/python-gcm/blob/master/gcm/gcm.py#L497

#
# Sending to a bouncer
#

def uses_notification_bouncer() -> bool:
    return settings.PUSH_NOTIFICATION_BOUNCER_URL is not None

def send_notifications_to_bouncer(user_profile_id: int,
                                  apns_payload: Dict[str, Any],
                                  gcm_payload: Dict[str, Any]) -> None:
    post_data = {
        'user_id': user_profile_id,
        'apns_payload': apns_payload,
        'gcm_payload': gcm_payload,
    }
    # Calls zilencer.views.remote_server_notify_push
    send_json_to_push_bouncer('POST', 'notify', post_data)

def send_json_to_push_bouncer(method: str, endpoint: str, post_data: Dict[str, Any]) -> None:
    send_to_push_bouncer(
        method,
        endpoint,
        ujson.dumps(post_data),
        extra_headers={"Content-type": "application/json"},
    )

class PushNotificationBouncerException(Exception):
    pass

def send_to_push_bouncer(method: str,
                         endpoint: str,
                         post_data: Union[Text, Dict[str, Any]],
                         extra_headers: Optional[Dict[str, Any]]=None) -> None:
    """While it does actually send the notice, this function has a lot of
    code and comments around error handling for the push notifications
    bouncer.  There are several classes of failures, each with its own
    potential solution:

    * Network errors with requests.request.  We let those happen normally.

    * 500 errors from the push bouncer or other unexpected responses;
      we don't try to parse the response, but do make clear the cause.

    * 400 errors from the push bouncer.  Here there are 2 categories:
      Our server failed to connect to the push bouncer (should throw)
      vs. client-side errors like and invalid token.

    """
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

    if res.status_code >= 500:
        # 500s should be resolved by the people who run the push
        # notification bouncer service, since they'll get an email
        # too.  For now we email the server admin, but we'll likely
        # want to do some sort of retry logic eventually.
        raise PushNotificationBouncerException(
            _("Received 500 from push notification bouncer"))
    elif res.status_code >= 400:
        # If JSON parsing errors, just let that exception happen
        result_dict = ujson.loads(res.content)
        msg = result_dict['msg']
        if 'code' in result_dict and result_dict['code'] == 'INVALID_ZULIP_SERVER':
            # Invalid Zulip server credentials should email this server's admins
            raise PushNotificationBouncerException(
                _("Push notifications bouncer error: %s") % (msg,))
        else:
            # But most other errors coming from the push bouncer
            # server are client errors (e.g. never-registered token)
            # and should be handled as such.
            raise JsonableError(msg)
    elif res.status_code != 200:
        # Anything else is unexpected and likely suggests a bug in
        # this version of Zulip, so we throw an exception that will
        # email the server admins.
        raise PushNotificationBouncerException(
            "Push notification bouncer returned unexpected status code %s" % (res.status_code,))

    # If we don't throw an exception, it's a successful bounce!

#
# Managing device tokens
#

def num_push_devices_for_user(user_profile: UserProfile, kind: Optional[int]=None) -> PushDeviceToken:
    if kind is None:
        return PushDeviceToken.objects.filter(user=user_profile).count()
    else:
        return PushDeviceToken.objects.filter(user=user_profile, kind=kind).count()

def add_push_device_token(user_profile: UserProfile,
                          token_str: bytes,
                          kind: int,
                          ios_app_id: Optional[str]=None) -> None:

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
        # Calls zilencer.views.remote_server_register_push.
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

def remove_push_device_token(user_profile: UserProfile, token_str: bytes, kind: int) -> None:

    # If we're sending things to the push notification bouncer
    # unregister this user with them here
    if uses_notification_bouncer():
        # TODO: Make this a remove item
        post_data = {
            'server_uuid': settings.ZULIP_ORG_ID,
            'user_id': user_profile.id,
            'token': token_str,
            'token_kind': kind,
        }
        # Calls zilencer.views.remote_server_unregister_push.
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

def push_notifications_enabled() -> bool:
    '''True just if this server has configured a way to send push notifications.'''
    if (uses_notification_bouncer()
            and settings.ZULIP_ORG_KEY is not None
            and settings.ZULIP_ORG_ID is not None):  # nocoverage
        # We have the needed configuration to send push notifications through
        # the bouncer.  Better yet would be to confirm that this config actually
        # works -- e.g., that we have ever successfully sent to the bouncer --
        # but this is a good start.
        return True
    if apns_enabled() and gcm_enabled():  # nocoverage
        # We have the needed configuration to send through APNs and GCM directly
        # (i.e., we are the bouncer, presumably.)  Again, assume it actually works.
        return True
    return False

def get_alert_from_message(message: Message) -> Text:
    """
    Determine what alert string to display based on the missed messages.
    """
    sender_str = message.sender.full_name
    if message.recipient.type == Recipient.HUDDLE and message.trigger == 'private_message':
        return "New private group message from %s" % (sender_str,)
    elif message.recipient.type == Recipient.PERSONAL and message.trigger == 'private_message':
        return "New private message from %s" % (sender_str,)
    elif message.is_stream_message() and message.trigger == 'mentioned':
        return "New mention from %s" % (sender_str,)
    elif (message.is_stream_message() and
            (message.trigger == 'stream_push_notify' and message.stream_name)):
        return "New stream message from %s in %s" % (sender_str, message.stream_name,)
    else:
        return "New Zulip mentions and private messages from %s" % (sender_str,)

def get_mobile_push_content(rendered_content: Text) -> Text:
    def get_text(elem: LH.HtmlElement) -> Text:
        # Convert default emojis to their unicode equivalent.
        classes = elem.get("class", "")
        if "emoji" in classes:
            match = re.search("emoji-(?P<emoji_code>\S+)", classes)
            if match:
                emoji_code = match.group('emoji_code')
                char_repr = ""
                for codepoint in emoji_code.split('-'):
                    char_repr += chr(int(codepoint, 16))
                return char_repr
        # Handles realm emojis, avatars etc.
        if elem.tag == "img":
            return elem.get("alt", "")
        if elem.tag == 'blockquote':
            return ''  # To avoid empty line before quote text
        return elem.text or ''

    def format_as_quote(quote_text: Text) -> Text:
        quote_text_list = filter(None, quote_text.split('\n'))  # Remove empty lines
        quote_text = '\n'.join(map(lambda x: "> "+x, quote_text_list))
        quote_text += '\n'
        return quote_text

    def process(elem: LH.HtmlElement) -> Text:
        plain_text = get_text(elem)
        sub_text = ''
        for child in elem:
            sub_text += process(child)
        if elem.tag == 'blockquote':
            sub_text = format_as_quote(sub_text)
        plain_text += sub_text
        plain_text += elem.tail or ""
        return plain_text

    if settings.PUSH_NOTIFICATION_REDACT_CONTENT:
        return "***REDACTED***"
    else:
        elem = LH.fromstring(rendered_content)
        plain_text = process(elem)
        return plain_text

def truncate_content(content: Text) -> Tuple[Text, bool]:
    # We use unicode character 'HORIZONTAL ELLIPSIS' (U+2026) instead
    # of three dots as this saves two extra characters for textual
    # content. This function will need to be updated to handle unicode
    # combining characters and tags when we start supporting themself.
    if len(content) <= 200:
        return content, False
    return content[:200] + "…", True

def get_common_payload(message: Message) -> Dict[str, Any]:
    data = {}  # type: Dict[str, Any]

    # These will let the app support logging into multiple realms and servers.
    data['server'] = settings.EXTERNAL_HOST
    data['realm_id'] = message.sender.realm.id

    # `sender_id` is preferred, but some existing versions use `sender_email`.
    data['sender_id'] = message.sender.id
    data['sender_email'] = message.sender.email

    if message.recipient.type == Recipient.STREAM:
        data['recipient_type'] = "stream"
        data['stream'] = get_display_recipient(message.recipient)
        data['topic'] = message.subject
    elif message.recipient.type == Recipient.HUDDLE:
        data['recipient_type'] = "private"
        data['pm_users'] = huddle_users(message.recipient.id)
    else:  # Recipient.PERSONAL
        data['recipient_type'] = "private"

    return data

def get_apns_payload(message: Message) -> Dict[str, Any]:
    zulip_data = get_common_payload(message)
    zulip_data.update({
        'message_ids': [message.id],
    })

    content, _ = truncate_content(get_mobile_push_content(message.rendered_content))
    apns_data = {
        'alert': {
            'title': get_alert_from_message(message),
            'body': content,
        },
        'badge': 0,  # TODO: set badge count in a better way
        'custom': {'zulip': zulip_data},
    }
    return apns_data

def get_gcm_payload(user_profile: UserProfile, message: Message) -> Dict[str, Any]:
    data = get_common_payload(message)
    content, truncated = truncate_content(get_mobile_push_content(message.rendered_content))
    data.update({
        'user': user_profile.email,
        'event': 'message',
        'alert': get_alert_from_message(message),
        'zulip_message_id': message.id,  # message_id is reserved for CCS
        'time': datetime_to_timestamp(message.pub_date),
        'content': content,
        'content_truncated': truncated,
        'sender_full_name': message.sender.full_name,
        'sender_avatar_url': absolute_avatar_url(message.sender),
    })
    return data

@statsd_increment("push_notifications")
def handle_push_notification(user_profile_id: int, missed_message: Dict[str, Any]) -> None:
    """
    missed_message is the event received by the
    zerver.worker.queue_processors.PushNotificationWorker.consume function.
    """
    user_profile = get_user_profile_by_id(user_profile_id)
    if not (receives_offline_push_notifications(user_profile) or
            receives_online_notifications(user_profile)):
        return

    user_profile = get_user_profile_by_id(user_profile_id)
    (message, user_message) = access_message(user_profile, missed_message['message_id'])
    if user_message is not None:
        # If ther user has read the message already, don't push-notify.
        #
        # TODO: It feels like this is already handled when things are
        # put in the queue; maybe we should centralize this logic with
        # the `zerver/tornado/event_queue.py` logic?
        if user_message.flags.read:
            return
    else:
        # Users should only be getting push notifications into this
        # queue for messages they haven't received if they're
        # long-term idle; anything else is likely a bug.
        if not user_profile.long_term_idle:
            logging.error("Could not find UserMessage with message_id %s and user_id %s" % (
                missed_message['message_id'], user_profile_id))
            return

    message.trigger = missed_message['trigger']
    message.stream_name = missed_message.get('stream_name', None)

    apns_payload = get_apns_payload(message)
    gcm_payload = get_gcm_payload(user_profile, message)
    logging.info("Sending push notification to user %s" % (user_profile_id,))

    if uses_notification_bouncer():
        try:
            send_notifications_to_bouncer(user_profile_id,
                                          apns_payload,
                                          gcm_payload)
        except requests.ConnectionError:
            def failure_processor(event: Dict[str, Any]) -> None:
                logging.warning(
                    "Maximum retries exceeded for trigger:%s event:push_notification" % (
                        event['user_profile_id']))
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
