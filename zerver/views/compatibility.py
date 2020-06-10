import re
from typing import List, Optional, Tuple

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from version import DESKTOP_MINIMUM_VERSION, DESKTOP_WARNING_VERSION
from zerver.lib.response import json_error, json_success
from zerver.lib.user_agent import parse_user_agent
from zerver.signals import get_device_browser


def pop_numerals(ver: str) -> Tuple[List[int], str]:
    match = re.search(r'^( \d+ (?: \. \d+ )* ) (.*)', ver, re.X)
    if match is None:
        return [], ver
    numerals, rest = match.groups()
    numbers = [int(n) for n in numerals.split('.')]
    return numbers, rest

def version_lt(ver1: str, ver2: str) -> Optional[bool]:
    '''
    Compare two Zulip-style version strings.

    Versions are dot-separated sequences of decimal integers,
    followed by arbitrary trailing decoration.  Comparison is
    lexicographic on the integer sequences, and refuses to
    guess how any trailing decoration compares to any other,
    to further numerals, or to nothing.

    Returns:
      True if ver1 < ver2
      False if ver1 >= ver2
      None if can't tell.
    '''
    num1, rest1 = pop_numerals(ver1)
    num2, rest2 = pop_numerals(ver2)
    if not num1 or not num2:
        return None
    common_len = min(len(num1), len(num2))
    common_num1, rest_num1 = num1[:common_len], num1[common_len:]
    common_num2, rest_num2 = num2[:common_len], num2[common_len:]

    # Leading numbers win.
    if common_num1 != common_num2:
        return common_num1 < common_num2

    # More numbers beats end-of-string, but ??? vs trailing text.
    # (NB at most one of rest_num1, rest_num2 is nonempty.)
    if not rest1 and rest_num2:
        return True
    if rest_num1 and not rest2:
        return False
    if rest_num1 or rest_num2:
        return None

    # Trailing text we can only compare for equality.
    if rest1 == rest2:
        return False
    return None


def find_mobile_os(user_agent: str) -> Optional[str]:
    if re.search(r'\b Android \b', user_agent, re.I | re.X):
        return 'android'
    if re.search(r'\b(?: iOS | iPhone\ OS )\b', user_agent, re.I | re.X):
        return 'ios'
    return None


# Zulip Mobile release 16.2.96 was made 2018-08-22.  It fixed a
# bug in our Android code that causes spammy, obviously-broken
# notifications once the "remove_push_notification" feature is
# enabled on the user's Zulip server.
android_min_app_version = '16.2.96'

def check_global_compatibility(request: HttpRequest) -> HttpResponse:
    if request.META.get('HTTP_USER_AGENT') is None:
        return json_error(_('User-Agent header missing from request'))

    # This string should not be tagged for translation, since old
    # clients are checking for an extra string.
    legacy_compatibility_error_message = "Client is too old"
    user_agent = parse_user_agent(request.META["HTTP_USER_AGENT"])
    if user_agent['name'] == "ZulipInvalid":
        return json_error(legacy_compatibility_error_message)
    if user_agent['name'] == "ZulipMobile":
        user_os = find_mobile_os(request.META["HTTP_USER_AGENT"])
        if (user_os == 'android'
                and version_lt(user_agent['version'], android_min_app_version)):
            return json_error(legacy_compatibility_error_message)
    return json_success()

def is_outdated_desktop_app(user_agent_str: str) -> Tuple[bool, bool, bool]:
    # Returns (insecure, banned, auto_update_broken)
    user_agent = parse_user_agent(user_agent_str)
    if user_agent['name'] == 'ZulipDesktop':
        # The deprecated QT/webkit based desktop app, last updated in ~2016.
        return (True, True, True)

    if user_agent['name'] != 'ZulipElectron':
        return (False, False, False)

    if version_lt(user_agent['version'], '4.0.0'):
        # Version 2.3.82 and older (aka <4.0.0) of the modern
        # Electron-based Zulip desktop app with known security issues.
        # won't auto-update; we may want a special notice to
        # distinguish those from modern releases.
        return (True, True, True)

    if version_lt(user_agent['version'], DESKTOP_MINIMUM_VERSION):
        # Below DESKTOP_MINIMUM_VERSION, we reject access as well.
        return (True, True, False)

    if version_lt(user_agent['version'], DESKTOP_WARNING_VERSION):
        # Other insecure versions should just warn.
        return (True, False, False)

    return (False, False, False)

def is_unsupported_browser(user_agent: str) -> Tuple[bool, Optional[str]]:
    browser_name = get_device_browser(user_agent)
    if browser_name == "Internet Explorer":
        return (True, browser_name)
    return (False, browser_name)
