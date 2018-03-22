
from django.http import HttpResponse, HttpRequest
from typing import Any, List, Dict, Optional, Text

from zerver.lib.response import json_error, json_success
from zerver.lib.user_agent import parse_user_agent

def check_compatibility(request: HttpRequest) -> HttpResponse:
    user_agent = parse_user_agent(request.META["HTTP_USER_AGENT"])
    if user_agent['name'] == "ZulipInvalid":
        return json_error("Client is too old")
    return json_success()
