from __future__ import absolute_import

from zerver.models import PushDeviceToken
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.decorator import statsd_increment

from apnsclient import Session, Message, APNs
import gcmclient

from django.conf import settings

import base64, binascii, logging, os

# Maintain a long-lived Session object to avoid having to re-SSL-handshake
# for each request
session = Session()
connection = None
if settings.APNS_CERT_FILE is not None and os.path.exists(settings.APNS_CERT_FILE):
    connection = session.get_connection(settings.APNS_SANDBOX, cert_file=settings.APNS_CERT_FILE)

def num_push_devices_for_user(user_profile, kind = None):
    if kind is None:
        return PushDeviceToken.objects.filter(user=user_profile).count()
    else:
        return PushDeviceToken.objects.filter(user=user_profile, kind=kind).count()

# We store the token as b64, but apns-client wants hex strings
def b64_to_hex(data):
    return binascii.hexlify(base64.b64decode(data))

def hex_to_b64(data):
    return base64.b64encode(binascii.unhexlify(data))

# Send a push notification to the desired clients
# extra_data is a dict that will be passed to the
# mobile app
@statsd_increment("apple_push_notification")
def send_apple_push_notification(user, alert, **extra_data):
    if not connection:
        logging.error("Attempting to send push notification, but no connection was found. This may be because we could not find the APNS Certificate file.")
        return

    tokens = [b64_to_hex(device.token) for device in
        PushDeviceToken.objects.filter(user=user, kind=PushDeviceToken.APNS)]

    logging.info("APNS: Sending apple push notification to devices: %s" % (tokens,))
    message = Message(tokens, alert=alert, **extra_data)

    apns_client = APNs(connection)
    ret = apns_client.send(message)
    if not ret:
       logging.warning("APNS: Failed to send push notification for clients %s" % (tokens,))
       return

    for token, reason in ret.failed.items():
        code, errmsg = reason
        logging.warning("APNS: Failed to deliver APNS notification to %s, reason: %s" % (token, errmsg))
        if code == 8:
            # Invalid Token, remove from our database
            logging.warning("APNS: Removing token from database due to above failure")
            PushDeviceToken.objects.get(user=user, token=hex_to_b64(token)).delete()

    # Check failures not related to devices.
    for code, errmsg in ret.errors:
        logging.warning("APNS: Unknown error when delivering APNS: %s" %  (errmsg,))

    if ret.needs_retry():
        # TODO handle retrying by potentially scheduling a background job
        # or re-queueing
        logging.warning("APNS: delivery needs a retry but ignoring")

# NOTE: This is used by the check_apns_tokens manage.py command. Do not call it otherwise, as the
# feedback() call can take up to 15s
def check_apns_feedback():
    apns_client = APNs(connection, tail_timeout=20)

    for token, since in apns_client.feedback():
        since_date = timestamp_to_datetime(since)
        logging.info("Found unavailable token %s, unavailable since %s" % (token, since_date))

        PushDeviceToken.objects.filter(token=hex_to_b64(token), last_updates__lt=since_date, type=PushDeviceToken.APNS).delete()
    logging.info("Finished checking feedback for stale tokens")


if settings.ANDROID_GCM_API_KEY:
    gcm = gcmclient.GCM(settings.ANDROID_GCM_API_KEY)
else:
    gcm = None

@statsd_increment("android_push_notification")
def send_android_push_notification(user, data):
    if not gcm:
        logging.error("Attempting to send a GCM push notification, but no API key was configured")
        return

    reg_ids = [device.token for device in
        PushDeviceToken.objects.filter(user=user, kind=PushDeviceToken.GCM)]

    msg = gcmclient.JSONMessage(reg_ids, data)
    res = gcm.send(msg)

    for reg_id, msg_id in res.success.items():
        logging.info("GCM: Sent %s as %s" % (reg_id, msg_id))

    for reg_id, new_reg_id in res.canonical.items():
        logging.info("GCM: Updating registration %s with %s" % (reg_id, new_reg_id))

        device = PushDeviceToken.objects.get(token=reg_id, kind=PushDeviceToken.GCM)
        device.token = new_reg_id
        device.save(update_fields=['token'])

    for reg_id in res.not_registered:
        logging.info("GCM: Removing %s" % (reg_id,))

        device = PushDeviceToken.objects.get(token=reg_id, kind=PushDeviceToken.GCM)
        device.delete()

    for reg_id, err_code in res.failed.items():
        logging.warning("GCM: Delivery to %s failed: %s" % (reg_id, err_code))

    if res.needs_retry():
        # TODO
        logging.warning("GCM: delivery needs a retry but ignoring")
