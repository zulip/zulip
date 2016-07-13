from __future__ import absolute_import

from six import text_type
from typing import Any, Dict, Optional

from zerver.models import PushDeviceToken, UserProfile
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.decorator import statsd_increment
from zerver.lib.utils import generate_random_token
from zerver.lib.redis_utils import get_redis_client

from apns import APNs, Frame, Payload, SENT_BUFFER_QTY
import gcmclient

from django.conf import settings

import base64, binascii, logging, os, time
from collections import OrderedDict
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

# Android GCM
gcm = None

def get_apns_key(token):
    return 'apns:' + token

class APNsMessage(object):
    def __init__(self, user, tokens, alert=None, badge=None, sound=None,
            category=None, **kwargs):
        self.frame = Frame()
        self.tokens = tokens
        expiry = time.time() + 24 * 3600
        priority = 10
        payload = Payload(alert=alert, badge=badge, sound=sound,
                          category=category, custom=kwargs)
        for token in tokens:
            data = {'token': token, 'user': user}
            identifier = generate_random_token(32)
            key = get_apns_key(identifier)
            redis_client.hmset(key, data)
            redis_client.expire(key, expiry)
            self.frame.add_item(token, payload, identifier, expiry, priority)

    def get_frame(self):
        return self.frame

def response_listener(error_response, connection):
    identifier = error_response['identifier']
    key = get_apns_key(identifier)
    if not redis_client.exists(key):
        logging.warn("APNs key, {}, doesn't not exist.".format(key))
        return

    code = error_response['status']
    errmsg = ERROR_CODES[code]
    data = redis_client.hgetall(key)
    token = data['token']
    user = data['user']
    b64_token = hex_to_b64(token)

    logging.warning("APNS: Failed to deliver APNS notification to %s, reason: %s" % (b64_token, errmsg))
    if code == 8:
        # Invalid Token, remove from our database
        logging.warning("APNS: Removing token from database due to above failure")
        try:
            PushDeviceToken.objects.get(user=user, token=b64_token).delete()
        except PushDeviceToken.DoesNotExist:
            pass

if settings.APNS_CERT_FILE is not None and os.path.exists(settings.APNS_CERT_FILE):
    connection = APNs(use_sandbox=settings.APNS_SANDBOX,
                      cert_file=settings.APNS_CERT_FILE,
                      key_file=settings.APNS_KEY_FILE,
                      enhanced=True)
    connection.gateway_server.register_response_listener(
        partial(response_listener, connection=connection))

if settings.DBX_APNS_CERT_FILE is not None and os.path.exists(settings.DBX_APNS_CERT_FILE):
    dbx_connection = APNs(use_sandbox=settings.APNS_SANDBOX,
                      cert_file=settings.DBX_APNS_CERT_FILE,
                      key_file=settings.DBX_APNS_KEY_FILE,
                      enhanced=True)
    dbx_connection.gateway_server.register_response_listener(
        partial(response_listener, connection=dbx_connection))

if settings.ANDROID_GCM_API_KEY:
    gcm = gcmclient.GCM(settings.ANDROID_GCM_API_KEY)

def num_push_devices_for_user(user_profile, kind = None):
    # type: (UserProfile, Optional[int]) -> PushDeviceToken
    if kind is None:
        return PushDeviceToken.objects.filter(user=user_profile).count()
    else:
        return PushDeviceToken.objects.filter(user=user_profile, kind=kind).count()

# We store the token as b64, but apns-client wants hex strings
def b64_to_hex(data):
    # type: (bytes) -> text_type
    return binascii.hexlify(base64.b64decode(data)).decode('utf-8')

def hex_to_b64(data):
    # type: (text_type) -> bytes
    return base64.b64encode(binascii.unhexlify(data.encode('utf-8')))

def _do_push_to_apns_service(user, message, apns_connection):
    # type: (UserProfile, APNsMessage, APNs) -> None
    if not apns_connection:
        logging.info("Not delivering APNS message %s to user %s due to missing connection" % (message, user))
        return

    frame = message.get_frame()
    apns_connection.gateway_server.send_notification_multiple(frame)

# Send a push notification to the desired clients
# extra_data is a dict that will be passed to the
# mobile app
@statsd_increment("apple_push_notification")
def send_apple_push_notification(user, alert, **extra_data):
    # type: (UserProfile, text_type, **Any) -> None
    if not connection and not dbx_connection:
        logging.error("Attempting to send push notification, but no connection was found. "
                      "This may be because we could not find the APNS Certificate file.")
        return

    devices = PushDeviceToken.objects.filter(user=user, kind=PushDeviceToken.APNS)
    # Plain b64 token kept for debugging purposes
    tokens = [(b64_to_hex(device.token), device.ios_app_id, device.token) for device in devices]

    logging.info("APNS: Sending apple push notification to devices: %s" % (tokens,))
    zulip_message = APNsMessage(user,
        [token[0] for token in tokens if token[1] in (settings.ZULIP_IOS_APP_ID, None)],
        alert=alert, **extra_data)

    dbx_message = APNsMessage(user,
        [token[0] for token in tokens if token[1] in (settings.DBX_IOS_APP_ID,)],
        alert=alert, **extra_data)

    _do_push_to_apns_service(user, zulip_message, connection)
    _do_push_to_apns_service(user, dbx_message, dbx_connection)

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

        PushDeviceToken.objects.filter(token=hex_to_b64(token), last_updates__lt=since_date,
                                       type=PushDeviceToken.APNS).delete()
    logging.info("Finished checking feedback for stale tokens")

@statsd_increment("android_push_notification")
def send_android_push_notification(user, data):
    # type: (UserProfile, Dict[str, Any]) -> None
    if not gcm:
        logging.error("Attempting to send a GCM push notification, but no API key was configured")
        return

    reg_ids = [device.token for device in
        PushDeviceToken.objects.filter(user=user, kind=PushDeviceToken.GCM)]

    msg = gcmclient.JSONMessage(reg_ids, data)
    res = gcm.send(msg)

    for reg_id, msg_id in res.success.items():
        logging.info("GCM: Sent %s as %s" % (reg_id, msg_id))

    # res.canonical will contain results when there are duplicate registrations for the same
    # device. The "canonical" registration is the latest registration made by the device.
    # Ref: http://developer.android.com/google/gcm/adv.html#canonical
    for reg_id, new_reg_id in res.canonical.items():
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

    for reg_id in res.not_registered:
        logging.info("GCM: Removing %s" % (reg_id,))

        device = PushDeviceToken.objects.get(token=reg_id, kind=PushDeviceToken.GCM)
        device.delete()

    for reg_id, err_code in res.failed.items():
        logging.warning("GCM: Delivery to %s failed: %s" % (reg_id, err_code))

    if res.needs_retry():
        # TODO
        logging.warning("GCM: delivery needs a retry but ignoring")

