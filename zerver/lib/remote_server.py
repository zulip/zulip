import requests
import ujson
import urllib
from typing import Any, Dict, List, Optional, Union

from django.conf import settings
from django.utils.translation import ugettext as _

from version import ZULIP_VERSION
from zerver.lib.exceptions import JsonableError

class PushNotificationBouncerException(Exception):
    pass

def send_to_push_bouncer(method: str,
                         endpoint: str,
                         post_data: Union[str, Dict[str, Any]],
                         extra_headers: Optional[Dict[str, Any]]=None) -> Dict[str, Any]:
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
    return ujson.loads(res.content)

def send_json_to_push_bouncer(method: str, endpoint: str, post_data: Dict[str, Any]) -> None:
    send_to_push_bouncer(
        method,
        endpoint,
        ujson.dumps(post_data),
        extra_headers={"Content-type": "application/json"},
    )
