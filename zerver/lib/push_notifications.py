from __future__ import absolute_import

from zerver.models import UserProfile, AppleDeviceToken
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.decorator import statsd_increment

from apnsclient import Session, Connection, Message, APNs

from django.conf import settings

import base64, binascii, logging

# Maintain a long-lived Session object to avoid having to re-SSL-handshake
# for each request
session = Session()
connection = session.get_connection(settings.APNS_SANDBOX, cert_file=settings.APNS_CERT_FILE)


def num_push_devices_for_user(user_profile):
    return AppleDeviceToken.objects.filter(user=user_profile).count()

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
    # Sends a push notifications to all the PushClients
    # Only Apple Push Notifications clients are supported at the moment
    tokens = [b64_to_hex(device.token) for device in AppleDeviceToken.objects.filter(user=user)]

    logging.info("Sending apple push notification to devices: %s" % (tokens,))
    message = Message(tokens, alert=alert, **extra_data)

    apns_client = APNs(connection)
    ret = apns_client.send(message)
    if not ret:
       logging.warning("Failed to send push notification for clients %s" % (tokens,))
       return

    for token, reason in ret.failed.items():
        code, errmsg = reason
        logging.warning("Failed to deliver APNS notification to %s, reason: %s" % (token, errmsg))

    # Check failures not related to devices.
    for code, errmsg in ret.errors:
        logging.warning("Unknown error when delivering APNS: %s" %  (errmsg,))

    if ret.needs_retry():
        # TODO handle retrying by potentially scheduling a background job
        # or re-queueing
        logging.warning("APNS delivery needs a retry but ignoring")

# NOTE: This is used by the check_apns_tokens manage.py command. Do not call it otherwise, as the
# feedback() call can take up to 15s
def check_apns_feedback():
    apns_client = APNs(connection, tail_timeout=20)

    for token, since in apns_client.feedback():
        since_date = timestamp_to_datetime(since)
        logging.info("Found unavailable token %s, unavailable since %s" % (token, since_date))

        AppleDeviceToken.objects.filter(token=hex_to_b64(token), last_updates__lt=since_date).delete()
    logging.info("Finished checking feedback for stale tokens")
