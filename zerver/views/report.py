# System documented in https://zulip.readthedocs.io/en/latest/subsystems/logging.html

from typing import Any, Dict, Optional, Text, Union

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from zerver.decorator import human_users_only, \
    to_non_negative_int
from zerver.lib.bugdown import privacy_clean_markdown
from zerver.lib.request import has_request_variables, REQ
from zerver.lib.response import json_success, json_error
from zerver.lib.queue import queue_json_publish
from zerver.lib.unminify import SourceMap
from zerver.lib.utils import statsd, statsd_key
from zerver.lib.validator import check_bool, check_dict
from zerver.models import UserProfile

import subprocess
import os
import logging
import ujson

js_source_map = None

# Read the source map information for decoding JavaScript backtraces.
def get_js_source_map() -> Optional[SourceMap]:
    global js_source_map
    if not js_source_map and not (settings.DEVELOPMENT or settings.TEST_SUITE):
        js_source_map = SourceMap([
            os.path.join(settings.DEPLOY_ROOT, 'prod-static/source-map'),
            os.path.join(settings.STATIC_ROOT, 'webpack-bundles')
        ])
    return js_source_map

@human_users_only
@has_request_variables
def report_send_times(request: HttpRequest, user_profile: UserProfile,
                      time: int=REQ(converter=to_non_negative_int),
                      received: int=REQ(converter=to_non_negative_int, default=-1),
                      displayed: int=REQ(converter=to_non_negative_int, default=-1),
                      locally_echoed: bool=REQ(validator=check_bool, default=False),
                      rendered_content_disparity: bool=REQ(validator=check_bool,
                                                           default=False)) -> HttpResponse:
    received_str = "(unknown)"
    if received > 0:
        received_str = str(received)
    displayed_str = "(unknown)"
    if displayed > 0:
        displayed_str = str(displayed)

    request._log_data["extra"] = "[%sms/%sms/%sms/echo:%s/diff:%s]" \
        % (time, received_str, displayed_str, locally_echoed, rendered_content_disparity)

    base_key = statsd_key(user_profile.realm.string_id, clean_periods=True)
    statsd.timing("endtoend.send_time.%s" % (base_key,), time)
    if received > 0:
        statsd.timing("endtoend.receive_time.%s" % (base_key,), received)
    if displayed > 0:
        statsd.timing("endtoend.displayed_time.%s" % (base_key,), displayed)
    if locally_echoed:
        statsd.incr('locally_echoed')
    if rendered_content_disparity:
        statsd.incr('render_disparity')
    return json_success()

@human_users_only
@has_request_variables
def report_narrow_times(request: HttpRequest, user_profile: UserProfile,
                        initial_core: int=REQ(converter=to_non_negative_int),
                        initial_free: int=REQ(converter=to_non_negative_int),
                        network: int=REQ(converter=to_non_negative_int)) -> HttpResponse:
    request._log_data["extra"] = "[%sms/%sms/%sms]" % (initial_core, initial_free, network)
    base_key = statsd_key(user_profile.realm.string_id, clean_periods=True)
    statsd.timing("narrow.initial_core.%s" % (base_key,), initial_core)
    statsd.timing("narrow.initial_free.%s" % (base_key,), initial_free)
    statsd.timing("narrow.network.%s" % (base_key,), network)
    return json_success()

@human_users_only
@has_request_variables
def report_unnarrow_times(request: HttpRequest, user_profile: UserProfile,
                          initial_core: int=REQ(converter=to_non_negative_int),
                          initial_free: int=REQ(converter=to_non_negative_int)) -> HttpResponse:
    request._log_data["extra"] = "[%sms/%sms]" % (initial_core, initial_free)
    base_key = statsd_key(user_profile.realm.string_id, clean_periods=True)
    statsd.timing("unnarrow.initial_core.%s" % (base_key,), initial_core)
    statsd.timing("unnarrow.initial_free.%s" % (base_key,), initial_free)
    return json_success()

@human_users_only
@has_request_variables
def report_error(request: HttpRequest, user_profile: UserProfile, message: Text=REQ(),
                 stacktrace: Text=REQ(), ui_message: bool=REQ(validator=check_bool),
                 user_agent: Text=REQ(), href: Text=REQ(), log: Text=REQ(),
                 more_info: Optional[Dict[str, Any]]=REQ(validator=check_dict([]), default=None)
                 ) -> HttpResponse:
    """Accepts an error report and stores in a queue for processing.  The
    actual error reports are later handled by do_report_error (below)"""
    if not settings.BROWSER_ERROR_REPORTING:
        return json_success()
    if more_info is None:
        more_info = {}

    js_source_map = get_js_source_map()
    if js_source_map:
        stacktrace = js_source_map.annotate_stacktrace(stacktrace)

    try:
        version = subprocess.check_output(["git", "log", "HEAD^..HEAD", "--oneline"],
                                          universal_newlines=True)  # type: Optional[Text]
    except Exception:
        version = None

    # Get the IP address of the request
    remote_ip = request.META.get('HTTP_X_REAL_IP')
    if remote_ip is None:
        remote_ip = request.META['REMOTE_ADDR']

    # For the privacy of our users, we remove any actual text content
    # in draft_content (from drafts rendering exceptions).  See the
    # comment on privacy_clean_markdown for more details.
    if more_info.get('draft_content'):
        more_info['draft_content'] = privacy_clean_markdown(more_info['draft_content'])

    queue_json_publish('error_reports', dict(
        type = "browser",
        report = dict(
            host = request.get_host().split(":")[0],
            ip_address = remote_ip,
            user_email = user_profile.email,
            user_full_name = user_profile.full_name,
            user_visible = ui_message,
            server_path = settings.DEPLOY_ROOT,
            version = version,
            user_agent = user_agent,
            href = href,
            message = message,
            stacktrace = stacktrace,
            log = log,
            more_info = more_info,
        )
    ))

    return json_success()

@csrf_exempt
@require_POST
@has_request_variables
def report_csp_violations(request: HttpRequest,
                          csp_report: Dict[str, Any]=REQ(argument_type='body')) -> HttpResponse:
    def get_attr(csp_report_attr: str) -> str:
        return csp_report.get(csp_report_attr, '')

    logging.warning("CSP Violation in Document('%s'). "
                    "Blocked URI('%s'), Original Policy('%s'), "
                    "Violated Directive('%s'), Effective Directive('%s'), "
                    "Disposition('%s'), Referrer('%s'), "
                    "Status Code('%s'), Script Sample('%s')" % (get_attr('document-uri'),
                                                                get_attr('blocked-uri'),
                                                                get_attr('original-policy'),
                                                                get_attr('violated-directive'),
                                                                get_attr('effective-directive'),
                                                                get_attr('disposition'),
                                                                get_attr('referrer'),
                                                                get_attr('status-code'),
                                                                get_attr('script-sample')))

    return json_success()
