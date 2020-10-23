import base64
import logging
import re
import shlex
import subprocess
from typing import Optional

import orjson
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import authenticated_json_view
from zerver.lib.ccache import make_ccache
from zerver.lib.pysa import mark_sanitized
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.users import get_api_key
from zerver.models import UserProfile

# Hack for mit.edu users whose Kerberos usernames don't match what they zephyr
# as.  The key is for Kerberos and the value is for zephyr.
kerberos_alter_egos = {
    'golem': 'ctl',
}

@authenticated_json_view
@has_request_variables
def webathena_kerberos_login(request: HttpRequest, user_profile: UserProfile,
                             cred: Optional[str]=REQ(default=None)) -> HttpResponse:
    global kerberos_alter_egos
    if cred is None:
        return json_error(_("Could not find Kerberos credential"))
    if not user_profile.realm.webathena_enabled:
        return json_error(_("Webathena login not enabled"))

    try:
        parsed_cred = orjson.loads(cred)
        user = parsed_cred["cname"]["nameString"][0]
        if user in kerberos_alter_egos:
            user = kerberos_alter_egos[user]
        assert(user == user_profile.email.split("@")[0])
        # Limit characters in usernames to valid MIT usernames
        # This is important for security since DNS is not secure.
        assert(re.match(r'^[a-z0-9_.-]+$', user) is not None)
        ccache = make_ccache(parsed_cred)

        # 'user' has been verified to contain only benign characters that won't
        # help with shell injection.
        user = mark_sanitized(user)

        # 'ccache' is only written to disk by the script and used as a kerberos
        # credential cache file.
        ccache = mark_sanitized(ccache)
    except Exception:
        return json_error(_("Invalid Kerberos cache"))

    # TODO: Send these data via (say) RabbitMQ
    try:
        api_key = get_api_key(user_profile)
        command = [
            "/home/zulip/python-zulip-api/zulip/integrations/zephyr/process_ccache",
            user,
            api_key,
            base64.b64encode(ccache).decode("utf-8"),
        ]
        subprocess.check_call(["ssh", settings.PERSONAL_ZMIRROR_SERVER, "--",
                               " ".join(map(shlex.quote, command))])
    except subprocess.CalledProcessError:
        logging.exception("Error updating the user's ccache", stack_info=True)
        return json_error(_("We were unable to setup mirroring for you"))

    return json_success()
