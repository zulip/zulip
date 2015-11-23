from __future__ import absolute_import

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

from zerver.decorator import authenticated_json_post_view, has_request_variables, REQ, \
    to_non_negative_int
from zerver.lib.response import json_success
from zerver.lib.queue import queue_json_publish
from zerver.lib.unminify import SourceMap
from zerver.lib.utils import statsd, statsd_key
from zerver.lib.validator import check_bool, check_dict

import subprocess
import os

from zerver.lib.rest import rest_dispatch as _rest_dispatch
rest_dispatch = csrf_exempt((lambda request, *args, **kwargs: _rest_dispatch(request, globals(), *args, **kwargs)))

# Read the source map information for decoding JavaScript backtraces
js_source_map = None
if not (settings.DEBUG or settings.TEST_SUITE):
    js_source_map = SourceMap(os.path.join(
        settings.DEPLOY_ROOT, 'prod-static/source-map'))

@authenticated_json_post_view
@has_request_variables
def json_report_send_time(request, user_profile,
                          time=REQ(converter=to_non_negative_int),
                          received=REQ(converter=to_non_negative_int, default="(unknown)"),
                          displayed=REQ(converter=to_non_negative_int, default="(unknown)"),
                          locally_echoed=REQ(validator=check_bool, default=False),
                          rendered_content_disparity=REQ(validator=check_bool, default=False)):
    request._log_data["extra"] = "[%sms/%sms/%sms/echo:%s/diff:%s]" \
        % (time, received, displayed, locally_echoed, rendered_content_disparity)
    statsd.timing("endtoend.send_time.%s" % (statsd_key(user_profile.realm.domain, clean_periods=True),), time)
    if received != "(unknown)":
        statsd.timing("endtoend.receive_time.%s" % (statsd_key(user_profile.realm.domain, clean_periods=True),), received)
    if displayed != "(unknown)":
        statsd.timing("endtoend.displayed_time.%s" % (statsd_key(user_profile.realm.domain, clean_periods=True),), displayed)
    if locally_echoed:
        statsd.incr('locally_echoed')
    if rendered_content_disparity:
        statsd.incr('render_disparity')
    return json_success()

@authenticated_json_post_view
@has_request_variables
def json_report_narrow_time(request, user_profile,
                            initial_core=REQ(converter=to_non_negative_int),
                            initial_free=REQ(converter=to_non_negative_int),
                            network=REQ(converter=to_non_negative_int)):
    request._log_data["extra"] = "[%sms/%sms/%sms]" % (initial_core, initial_free, network)
    statsd.timing("narrow.initial_core.%s" % (statsd_key(user_profile.realm.domain, clean_periods=True),), initial_core)
    statsd.timing("narrow.initial_free.%s" % (statsd_key(user_profile.realm.domain, clean_periods=True),), initial_free)
    statsd.timing("narrow.network.%s" % (statsd_key(user_profile.realm.domain, clean_periods=True),), network)
    return json_success()

@authenticated_json_post_view
@has_request_variables
def json_report_unnarrow_time(request, user_profile,
                            initial_core=REQ(converter=to_non_negative_int),
                            initial_free=REQ(converter=to_non_negative_int)):
    request._log_data["extra"] = "[%sms/%sms]" % (initial_core, initial_free)
    statsd.timing("unnarrow.initial_core.%s" % (statsd_key(user_profile.realm.domain, clean_periods=True),), initial_core)
    statsd.timing("unnarrow.initial_free.%s" % (statsd_key(user_profile.realm.domain, clean_periods=True),), initial_free)
    return json_success()

@authenticated_json_post_view
@has_request_variables
def json_report_error(request, user_profile, message=REQ, stacktrace=REQ,
                      ui_message=REQ(validator=check_bool), user_agent=REQ,
                      href=REQ, log=REQ,
                      more_info=REQ(validator=check_dict([]), default=None)):

    if not settings.ERROR_REPORTING:
        return json_success()

    if js_source_map:
        stacktrace = js_source_map.annotate_stacktrace(stacktrace)

    try:
        version = subprocess.check_output(["git", "log", "HEAD^..HEAD", "--oneline"])
    except Exception:
        version = None

    queue_json_publish('error_reports', dict(
        type = "browser",
        report = dict(
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
    ), lambda x: None)

    return json_success()
