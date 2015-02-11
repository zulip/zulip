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

# We maintain an additional APNS connection for pushing to Zulip apps that have been signed
# by the Dropbox certs (and have an app id of com.dropbox.zulip)
dbx_session = Session()
dbx_connection = None
if settings.DBX_APNS_CERT_FILE is not None and os.path.exists(settings.DBX_APNS_CERT_FILE):
    dbx_connection = session.get_connection(settings.APNS_SANDBOX, cert_file=settings.DBX_APNS_CERT_FILE)

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

def _do_push_to_apns_service(user, message, apns_connection):
    if not apns_connection:
        logging.info("Not delivering APNS message %s to user %s due to missing connection" % (message, user))
        return

    apns_client = APNs(apns_connection)
    ret = apns_client.send(message)
    if not ret:
       logging.warning("APNS: Failed to send push notification for clients %s" % (message.tokens,))
       return

    for token, reason in ret.failed.items():
        code, errmsg = reason
        b64_token = hex_to_b64(token)
        logging.warning("APNS: Failed to deliver APNS notification to %s, reason: %s" % (b64_token, errmsg))
        if code == 8:
            # Invalid Token, remove from our database
            logging.warning("APNS: Removing token from database due to above failure")
            PushDeviceToken.objects.get(user=user, token=b64_token).delete()

    # Check failures not related to devices.
    for code, errmsg in ret.errors:
        logging.warning("APNS: Unknown error when delivering APNS: %s" %  (errmsg,))

    if ret.needs_retry():
        logging.warning("APNS: delivery needs a retry, trying again")
        retry_msg = ret.retry()
        ret = apns_client.send(retry_msg)
        for code, errmsg in ret.errors:
            logging.warning("APNS: Unknown error when delivering APNS: %s" %  (errmsg,))


# Send a push notification to the desired clients
# extra_data is a dict that will be passed to the
# mobile app
@statsd_increment("apple_push_notification")
def send_apple_push_notification(user, alert, **extra_data):
    if not connection and not dbx_connection:
        logging.error("Attempting to send push notification, but no connection was found. This may be because we could not find the APNS Certificate file.")
        return

    devices = PushDeviceToken.objects.filter(user=user, kind=PushDeviceToken.APNS)
    # Plain b64 token kept for debugging purposes
    tokens = [(b64_to_hex(device.token), device.ios_app_id, device.token) for device in devices]

    logging.info("APNS: Sending apple push notification to devices: %s" % (tokens,))
    zulip_message = Message([token[0] for token in tokens if token[1] in (settings.ZULIP_IOS_APP_ID, None)],
                            alert=alert, **extra_data)
    dbx_message = Message([token[0] for token in tokens if token[1] in (settings.DBX_IOS_APP_ID,)],
                            alert=alert, **extra_data)

    _do_push_to_apns_service(user, zulip_message, connection)
    _do_push_to_apns_service(user, dbx_message, dbx_connection)

# NOTE: This is used by the check_apns_tokens manage.py command. Do not call it otherwise, as the
# feedback() call can take up to 15s
def check_apns_feedback():
    feedback_connection = session.get_connection(settings.APNS_FEEDBACK, cert_file=settings.APNS_CERT_FILE)
    apns_client = APNs(feedback_connection, tail_timeout=20)

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
