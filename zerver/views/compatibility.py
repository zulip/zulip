
from django.http import HttpResponse, HttpRequest
import re
from typing import Any, List, Dict, Optional, Tuple, Union

from zerver.lib.response import json_error, json_success
from zerver.lib.user_agent import parse_user_agent

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

def check_global_compatibility(request: HttpRequest) -> HttpResponse:
    user_agent = parse_user_agent(request.META["HTTP_USER_AGENT"])
    if user_agent['name'] == "ZulipInvalid":
        return json_error("Client is too old")
    return json_success()
