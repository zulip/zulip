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

class PushNotificationBouncerException(Exception):
    pass

def send_to_push_bouncer(method: str,
                         endpoint: str,
                         post_data: Union[str, Dict[str, Any]],
                         extra_headers: Optional[Dict[str, Any]]=None) -> Tuple[Dict[str, Any], bool]:
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
                               '/api/v1/remotes/' + endpoint)
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
        # notification bouncer service, and they'll get an appropriate
        # error notification from the server.  We just return after
        # doing something.  Ideally, we'll add do some sort of spaced
        # retry eventually.
        logging.warning("Received 500 from push notification bouncer")
        return {}, True
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
    return ujson.loads(res.content), False

def send_json_to_push_bouncer(method: str, endpoint: str, post_data: Dict[str, Any]) -> None:
    send_to_push_bouncer(
        method,
        endpoint,
        ujson.dumps(post_data),
        extra_headers={"Content-type": "application/json"},
    )

def build_analytics_data(realm_count_query: Any,
                         installation_count_query: Any) -> Tuple[List[Dict[str, Any]],
                                                                 List[Dict[str, Any]]]:
    # We limit the batch size on the client side to avoid OOM kills timeouts, etc.
    MAX_CLIENT_BATCH_SIZE = 10000
    data = {}
    data['analytics_realmcount'] = [
        model_to_dict(realm_count) for realm_count in
        realm_count_query.order_by("id")[0:MAX_CLIENT_BATCH_SIZE]
    ]
    data['analytics_installationcount'] = [
        model_to_dict(count) for count in
        installation_count_query.order_by("id")[0:MAX_CLIENT_BATCH_SIZE]
    ]

    floatify_datetime_fields(data, 'analytics_realmcount')
    floatify_datetime_fields(data, 'analytics_installationcount')
    return (data['analytics_realmcount'], data['analytics_installationcount'])

def send_analytics_to_remote_server() -> None:
    # first, check what's latest
    (result, failed) = send_to_push_bouncer("GET", "server/analytics/status", {})
    if failed:  # nocoverage
        return

    last_acked_realm_count_id = result['last_realm_count_id']
    last_acked_installation_count_id = result['last_installation_count_id']

    (realm_count_data, installation_count_data) = build_analytics_data(
        realm_count_query=RealmCount.objects.filter(
            id__gt=last_acked_realm_count_id),
        installation_count_query=InstallationCount.objects.filter(
            id__gt=last_acked_installation_count_id))

    if len(realm_count_data) == 0 and len(installation_count_data) == 0:
        return

    request = {
        'realm_counts': ujson.dumps(realm_count_data),
        'installation_counts': ujson.dumps(installation_count_data),
        'version': ujson.dumps(ZULIP_VERSION),
    }

    # Gather only entries with an ID greater than last_realm_count_id
    send_to_push_bouncer("POST", "server/analytics", request)
