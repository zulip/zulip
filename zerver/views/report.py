# System documented in https://zulip.readthedocs.io/en/latest/subsystems/logging.html
import logging
import subprocess
from typing import Any, Mapping, Optional, Union
from urllib.parse import SplitResult

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from zerver.context_processors import get_valid_realm_from_request
from zerver.decorator import human_users_only
from zerver.lib.markdown import privacy_clean_markdown
from zerver.lib.queue import queue_json_publish
from zerver.lib.request import REQ, RequestNotes, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.storage import static_path
from zerver.lib.unminify import SourceMap
from zerver.lib.utils import statsd, statsd_key
from zerver.lib.validator import (
    WildValue,
    check_bool,
    check_dict,
    check_string,
    to_non_negative_int,
    to_wild_value,
)
from zerver.models import UserProfile

js_source_map: Optional[SourceMap] = None


# Read the source map information for decoding JavaScript backtraces.
def get_js_source_map() -> Optional[SourceMap]:
    global js_source_map
    if not js_source_map and not (settings.DEVELOPMENT or settings.TEST_SUITE):
        js_source_map = SourceMap(
            [
                static_path("webpack-bundles"),
            ]
        )
    return js_source_map


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

    base_key = statsd_key(user_profile.realm.string_id, clean_periods=True)
    statsd.timing(f"endtoend.send_time.{base_key}", time)
    if received > 0:
        statsd.timing(f"endtoend.receive_time.{base_key}", received)
    if displayed > 0:
        statsd.timing(f"endtoend.displayed_time.{base_key}", displayed)
    if locally_echoed:
        statsd.incr("locally_echoed")
    if rendered_content_disparity:
        statsd.incr("render_disparity")
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
    realm = get_valid_realm_from_request(request)
    base_key = statsd_key(realm.string_id, clean_periods=True)
    statsd.timing(f"narrow.initial_core.{base_key}", initial_core)
    statsd.timing(f"narrow.initial_free.{base_key}", initial_free)
    statsd.timing(f"narrow.network.{base_key}", network)
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
    realm = get_valid_realm_from_request(request)
    base_key = statsd_key(realm.string_id, clean_periods=True)
    statsd.timing(f"unnarrow.initial_core.{base_key}", initial_core)
    statsd.timing(f"unnarrow.initial_free.{base_key}", initial_free)
    return json_success(request)


@has_request_variables
def report_error(
    request: HttpRequest,
    maybe_user_profile: Union[AnonymousUser, UserProfile],
    message: str = REQ(),
    stacktrace: str = REQ(),
    ui_message: bool = REQ(json_validator=check_bool),
    user_agent: str = REQ(),
    href: str = REQ(),
    log: str = REQ(),
    more_info: Mapping[str, Any] = REQ(json_validator=check_dict([]), default={}),
) -> HttpResponse:
    """Accepts an error report and stores in a queue for processing.  The
    actual error reports are later handled by do_report_error"""
    if not settings.BROWSER_ERROR_REPORTING:
        return json_success(request)
    more_info = dict(more_info)

    js_source_map = get_js_source_map()
    if js_source_map:
        stacktrace = js_source_map.annotate_stacktrace(stacktrace)

    try:
        version: Optional[str] = subprocess.check_output(
            ["git", "show", "-s", "--oneline"],
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        version = None

    # Get the IP address of the request
    remote_ip = request.META["REMOTE_ADDR"]

    # For the privacy of our users, we remove any actual text content
    # in draft_content (from drafts rendering exceptions).  See the
    # comment on privacy_clean_markdown for more details.
    if more_info.get("draft_content"):
        more_info["draft_content"] = privacy_clean_markdown(more_info["draft_content"])

    if maybe_user_profile.is_authenticated:
        email = maybe_user_profile.delivery_email
        full_name = maybe_user_profile.full_name
    else:
        email = "unauthenticated@example.com"
        full_name = "Anonymous User"

    queue_json_publish(
        "error_reports",
        dict(
            type="browser",
            report=dict(
                host=SplitResult("", request.get_host(), "", "", "").hostname,
                ip_address=remote_ip,
                user_email=email,
                user_full_name=full_name,
                user_visible=ui_message,
                server_path=settings.DEPLOY_ROOT,
                version=version,
                user_agent=user_agent,
                href=href,
                message=message,
                stacktrace=stacktrace,
                log=log,
                more_info=more_info,
            ),
        ),
    )

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
