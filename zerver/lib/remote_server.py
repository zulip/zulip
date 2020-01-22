import logging
import requests
import ujson
import urllib
from typing import Any, Dict, List, Optional, Tuple, Union

from django.conf import settings
from django.forms.models import model_to_dict
from django.utils.translation import ugettext as _

from analytics.models import InstallationCount, RealmCount
from version import ZULIP_VERSION
from zerver.lib.exceptions import JsonableError
from zerver.lib.export import floatify_datetime_fields
from zerver.models import RealmAuditLog

class PushNotificationBouncerException(Exception):
    pass

class PushNotificationBouncerRetryLaterError(JsonableError):
    http_status_code = 502

def send_to_push_bouncer(method: str,
                         endpoint: str,
                         post_data: Union[str, Dict[str, Any]],
                         extra_headers: Optional[Dict[str, Any]]=None) -> Dict[str, Any]:
    """While it does actually send the notice, this function has a lot of
    code and comments around error handling for the push notifications
    bouncer.  There are several classes of failures, each with its own
    potential solution:

    * Network errors with requests.request.  We raise an exception to signal
      it to the callers.

    * 500 errors from the push bouncer or other unexpected responses;
      we don't try to parse the response, but do make clear the cause.

    * 400 errors from the push bouncer.  Here there are 2 categories:
      Our server failed to connect to the push bouncer (should throw)
      vs. client-side errors like and invalid token.

    """
    url = urllib.parse.urljoin(settings.PUSH_NOTIFICATION_BOUNCER_URL,
                               '/api/v1/remotes/' + endpoint)
    api_auth = requests.auth.HTTPBasicAuth(settings.ZULIP_ORG_ID,
                                           settings.ZULIP_ORG_KEY)

    headers = {"User-agent": "ZulipServer/%s" % (ZULIP_VERSION,)}
    if extra_headers is not None:
        headers.update(extra_headers)

    try:
        res = requests.request(method,
                               url,
                               data=post_data,
                               auth=api_auth,
                               timeout=30,
                               verify=True,
                               headers=headers)
    except (requests.exceptions.Timeout, requests.exceptions.SSLError,
            requests.exceptions.ConnectionError) as e:
        raise PushNotificationBouncerRetryLaterError(
            "{} while trying to connect to push notification bouncer".format(e.__class__.__name__))

    if res.status_code >= 500:
        # 500s should be resolved by the people who run the push
        # notification bouncer service, and they'll get an appropriate
        # error notification from the server. We raise an exception to signal
        # to the callers that the attempt failed and they can retry.
        error_msg = "Received 500 from push notification bouncer"
        logging.warning(error_msg)
        raise PushNotificationBouncerRetryLaterError(error_msg)
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
    return ujson.loads(res.content)

def send_json_to_push_bouncer(method: str, endpoint: str, post_data: Dict[str, Any]) -> None:
    send_to_push_bouncer(
        method,
        endpoint,
        ujson.dumps(post_data),
        extra_headers={"Content-type": "application/json"},
    )

REALMAUDITLOG_PUSHED_FIELDS = ['id', 'realm', 'event_time', 'backfilled', 'extra_data', 'event_type']

def build_analytics_data(realm_count_query: Any,
                         installation_count_query: Any,
                         realmauditlog_query: Any) -> Tuple[List[Dict[str, Any]],
                                                            List[Dict[str, Any]],
                                                            List[Dict[str, Any]]]:
    # We limit the batch size on the client side to avoid OOM kills timeouts, etc.
    MAX_CLIENT_BATCH_SIZE = 10000
    data = {}
    data['analytics_realmcount'] = [
        model_to_dict(row) for row in
        realm_count_query.order_by("id")[0:MAX_CLIENT_BATCH_SIZE]
    ]
    data['analytics_installationcount'] = [
        model_to_dict(row) for row in
        installation_count_query.order_by("id")[0:MAX_CLIENT_BATCH_SIZE]
    ]
    data['zerver_realmauditlog'] = [
        model_to_dict(row, fields=REALMAUDITLOG_PUSHED_FIELDS) for row in
        realmauditlog_query.order_by("id")[0:MAX_CLIENT_BATCH_SIZE]
    ]

    floatify_datetime_fields(data, 'analytics_realmcount')
    floatify_datetime_fields(data, 'analytics_installationcount')
    floatify_datetime_fields(data, 'zerver_realmauditlog')
    return (data['analytics_realmcount'], data['analytics_installationcount'],
            data['zerver_realmauditlog'])

def send_analytics_to_remote_server() -> None:
    # first, check what's latest
    try:
        result = send_to_push_bouncer("GET", "server/analytics/status", {})
    except PushNotificationBouncerRetryLaterError as e:
        logging.warning(e.msg)
        return

    last_acked_realm_count_id = result['last_realm_count_id']
    last_acked_installation_count_id = result['last_installation_count_id']
    last_acked_realmauditlog_id = result['last_realmauditlog_id']

    (realm_count_data, installation_count_data, realmauditlog_data) = build_analytics_data(
        realm_count_query=RealmCount.objects.filter(
            id__gt=last_acked_realm_count_id),
        installation_count_query=InstallationCount.objects.filter(
            id__gt=last_acked_installation_count_id),
        realmauditlog_query=RealmAuditLog.objects.filter(
            event_type__in=RealmAuditLog.SYNCED_BILLING_EVENTS,
            id__gt=last_acked_realmauditlog_id))

    if len(realm_count_data) + len(installation_count_data) + len(realmauditlog_data) == 0:
        return

    request = {
        'realm_counts': ujson.dumps(realm_count_data),
        'installation_counts': ujson.dumps(installation_count_data),
        'realmauditlog_rows': ujson.dumps(realmauditlog_data),
        'version': ujson.dumps(ZULIP_VERSION),
    }

    # Gather only entries with an ID greater than last_realm_count_id
    try:
        send_to_push_bouncer("POST", "server/analytics", request)
    except JsonableError as e:
        logging.warning(e.msg)
