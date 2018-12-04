
from django.http import HttpResponse, HttpRequest
import re
from typing import Any, List, Dict, Optional, Tuple, Union

from zerver.lib.response import json_error, json_success
from zerver.lib.user_agent import parse_user_agent

def pop_int(ver: str) -> Tuple[Optional[int], str]:
    match = re.search(r'^(\d+)(.*)', ver)
    if match is None:
        return None, ver
    return int(match.group(1)), match.group(2)

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
    while True:
        # Pull off the leading numeral from each version.
        maj1, rest1 = pop_int(ver1)
        maj2, rest2 = pop_int(ver2)
        if maj1 is None or maj2 is None:
            # One or both has no leading numeral; some unknown format.
            return None
        if maj1 < maj2:
            return True
        if maj1 > maj2:
            return False
        # Leading numerals are equal.

        if rest1 == rest2:
            return False
        if not(rest1.startswith('.') and rest2.startswith('.')):
            return None
        ver1 = rest1[1:]
        ver2 = rest2[1:]


def check_global_compatibility(request: HttpRequest) -> HttpResponse:
    user_agent = parse_user_agent(request.META["HTTP_USER_AGENT"])
    if user_agent['name'] == "ZulipInvalid":
        return json_error("Client is too old")
    return json_success()
