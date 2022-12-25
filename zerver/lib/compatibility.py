import datetime
import os
import re
from typing import List, Optional, Tuple

from django.conf import settings
from django.utils.timezone import now as timezone_now

from version import DESKTOP_MINIMUM_VERSION, DESKTOP_WARNING_VERSION
from zerver.lib.user_agent import parse_user_agent
from zerver.models import UserProfile
from zerver.signals import get_device_browser

# LAST_SERVER_UPGRADE_TIME is the last time the server had a version deployed.
if settings.PRODUCTION:  # nocoverage
    timestamp = os.path.basename(os.path.abspath(settings.DEPLOY_ROOT))
    LAST_SERVER_UPGRADE_TIME = datetime.datetime.strptime(timestamp, "%Y-%m-%d-%H-%M-%S").replace(
        tzinfo=datetime.timezone.utc
    )
else:
    LAST_SERVER_UPGRADE_TIME = timezone_now()


def is_outdated_server(user_profile: Optional[UserProfile]) -> bool:
    # Release tarballs are unpacked via `tar -xf`, which means the
    # `mtime` on files in them is preserved from when the release
    # tarball was built.  Checking this allows us to catch cases where
    # someone has upgraded in the last year but to a release more than
    # a year old.
    git_version_path = os.path.join(settings.DEPLOY_ROOT, "version.py")
    release_build_time = datetime.datetime.fromtimestamp(
        os.path.getmtime(git_version_path), datetime.timezone.utc
    )

    version_no_newer_than = min(LAST_SERVER_UPGRADE_TIME, release_build_time)
    deadline = version_no_newer_than + datetime.timedelta(
        days=settings.SERVER_UPGRADE_NAG_DEADLINE_DAYS
    )

    if user_profile is None or not user_profile.is_realm_admin:
        # Administrators get warned at the deadline; all users 30 days later.
        deadline = deadline + datetime.timedelta(days=30)

    if timezone_now() > deadline:
        return True
    return False


def pop_numerals(ver: str) -> Tuple[List[int], str]:
    match = re.search(r"^( \d+ (?: \. \d+ )* ) (.*)", ver, re.X)
    if match is None:
        return [], ver
    numerals, rest = match.groups()
    numbers = [int(n) for n in numerals.split(".")]
    return numbers, rest


def version_lt(ver1: str, ver2: str) -> Optional[bool]:
    """
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
    """
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
    if re.search(r"\b Android \b", user_agent, re.I | re.X):
        return "android"
    if re.search(r"\b(?: iOS | iPhone\ OS )\b", user_agent, re.I | re.X):
        return "ios"
    return None


def is_outdated_desktop_app(user_agent_str: str) -> Tuple[bool, bool, bool]:
    # Returns (insecure, banned, auto_update_broken)
    user_agent = parse_user_agent(user_agent_str)
    if user_agent["name"] == "ZulipDesktop":
        # The deprecated QT/webkit based desktop app, last updated in ~2016.
        return (True, True, True)

    if user_agent["name"] != "ZulipElectron":
        return (False, False, False)

    if version_lt(user_agent["version"], "4.0.0"):
        # Version 2.3.82 and older (aka <4.0.0) of the modern
        # Electron-based Zulip desktop app with known security issues.
        # won't auto-update; we may want a special notice to
        # distinguish those from modern releases.
        return (True, True, True)

    if version_lt(user_agent["version"], DESKTOP_MINIMUM_VERSION):
        # Below DESKTOP_MINIMUM_VERSION, we reject access as well.
        return (True, True, False)

    if version_lt(user_agent["version"], DESKTOP_WARNING_VERSION):
        # Other insecure versions should just warn.
        return (True, False, False)

    return (False, False, False)


def is_unsupported_browser(user_agent: str) -> Tuple[bool, Optional[str]]:
    browser_name = get_device_browser(user_agent)
    if browser_name == "Internet Explorer":
        return (True, browser_name)
    return (False, browser_name)


def is_pronouns_field_type_supported(user_agent_str: Optional[str]) -> bool:
    # In order to avoid users having a bad experience with these
    # custom profile fields disappearing after applying migration
    # 0421_migrate_pronouns_custom_profile_fields, we provide this
    # compatibility shim to show such custom profile fields as
    # SHORT_TEXT to older mobile app clients.
    #
    # TODO/compatibility(7.0): Because this is a relatively minor
    # detail, we can remove this compatibility hack once most users
    # have upgraded to a sufficiently new mobile client.
    if user_agent_str is None:
        return True

    user_agent = parse_user_agent(user_agent_str)
    if user_agent["name"] != "ZulipMobile":
        return True

    FIRST_VERSION_TO_SUPPORT_PRONOUNS_FIELD = "27.192"
    if version_lt(user_agent["version"], FIRST_VERSION_TO_SUPPORT_PRONOUNS_FIELD):
        return False

    return True
