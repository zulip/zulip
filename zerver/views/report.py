# System documented in https://zulip.readthedocs.io/en/latest/subsystems/logging.html
import logging
from typing import Union

from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from zerver.decorator import human_users_only
from zerver.lib.request import REQ, RequestNotes, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import (
    WildValue,
    check_bool,
    check_string,
    to_non_negative_int,
    to_wild_value,
)
from zerver.models import UserProfile


@human_users_only
@has_request_variables
def report_send_times(
    request: HttpRequest,
    user_profile: UserProfile,
    time: int = REQ(converter=to_non_negative_int),
    received: int = REQ(converter=to_non_negative_int, default=-1),
    displayed: int = REQ(converter=to_non_negative_int, default=-1),
    locally_echoed: bool = REQ(json_validator=check_bool, default=False),
    rendered_content_disparity: bool = REQ(json_validator=check_bool, default=False),
) -> HttpResponse:
    received_str = "(unknown)"
    if received > 0:
        received_str = str(received)
    displayed_str = "(unknown)"
    if displayed > 0:
        displayed_str = str(displayed)

    log_data = RequestNotes.get_notes(request).log_data
    assert log_data is not None
    log_data[
        "extra"
    ] = f"[{time}ms/{received_str}ms/{displayed_str}ms/echo:{locally_echoed}/diff:{rendered_content_disparity}]"

    return json_success(request)


@has_request_variables
def report_narrow_times(
    request: HttpRequest,
    user_profile: Union[UserProfile, AnonymousUser],
    initial_core: int = REQ(converter=to_non_negative_int),
    initial_free: int = REQ(converter=to_non_negative_int),
    network: int = REQ(converter=to_non_negative_int),
) -> HttpResponse:
    log_data = RequestNotes.get_notes(request).log_data
    assert log_data is not None
    log_data["extra"] = f"[{initial_core}ms/{initial_free}ms/{network}ms]"
    return json_success(request)


@has_request_variables
def report_unnarrow_times(
    request: HttpRequest,
    user_profile: Union[UserProfile, AnonymousUser],
    initial_core: int = REQ(converter=to_non_negative_int),
    initial_free: int = REQ(converter=to_non_negative_int),
) -> HttpResponse:
    log_data = RequestNotes.get_notes(request).log_data
    assert log_data is not None
    log_data["extra"] = f"[{initial_core}ms/{initial_free}ms]"
    return json_success(request)


@csrf_exempt
@require_POST
@has_request_variables
def report_csp_violations(
    request: HttpRequest,
    csp_report: WildValue = REQ(argument_type="body", converter=to_wild_value),
) -> HttpResponse:
    def get_attr(csp_report_attr: str) -> str:
        return csp_report.get(csp_report_attr, "").tame(check_string)

    logging.warning(
        "CSP violation in document('%s'). "
        "blocked URI('%s'), original policy('%s'), "
        "violated directive('%s'), effective directive('%s'), "
        "disposition('%s'), referrer('%s'), "
        "status code('%s'), script sample('%s')",
        get_attr("document-uri"),
        get_attr("blocked-uri"),
        get_attr("original-policy"),
        get_attr("violated-directive"),
        get_attr("effective-directive"),
        get_attr("disposition"),
        get_attr("referrer"),
        get_attr("status-code"),
        get_attr("script-sample"),
    )

    return json_success(request)
