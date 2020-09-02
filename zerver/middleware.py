import cProfile
import logging
import time
import traceback
from typing import Any, AnyStr, Callable, Dict, Iterable, List, MutableMapping, Optional, Union

from django.conf import settings
from django.core.handlers.wsgi import WSGIRequest
from django.db import connection
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, StreamingHttpResponse
from django.middleware.common import CommonMiddleware
from django.shortcuts import render
from django.utils.deprecation import MiddlewareMixin
from django.utils.translation import ugettext as _
from django.views.csrf import csrf_failure as html_csrf_failure
from sentry_sdk import capture_exception
from sentry_sdk.integrations.logging import ignore_logger

from zerver.lib.cache import get_remote_cache_requests, get_remote_cache_time
from zerver.lib.db import reset_queries
from zerver.lib.debug import maybe_tracemalloc_listen
from zerver.lib.exceptions import ErrorCode, JsonableError, MissingAuthenticationError, RateLimited
from zerver.lib.html_to_text import get_content_description
from zerver.lib.markdown import get_markdown_requests, get_markdown_time
from zerver.lib.rate_limiter import RateLimitResult
from zerver.lib.response import json_error, json_response_from_error, json_unauthorized
from zerver.lib.subdomains import get_subdomain
from zerver.lib.types import ViewFuncT
from zerver.lib.utils import statsd
from zerver.models import Realm, flush_per_request_caches, get_realm

logger = logging.getLogger('zulip.requests')
slow_query_logger = logging.getLogger('zulip.slow_queries')

def record_request_stop_data(log_data: MutableMapping[str, Any]) -> None:
    log_data['time_stopped'] = time.time()
    log_data['remote_cache_time_stopped'] = get_remote_cache_time()
    log_data['remote_cache_requests_stopped'] = get_remote_cache_requests()
    log_data['markdown_time_stopped'] = get_markdown_time()
    log_data['markdown_requests_stopped'] = get_markdown_requests()
    if settings.PROFILE_ALL_REQUESTS:
        log_data["prof"].disable()

def async_request_timer_stop(request: HttpRequest) -> None:
    record_request_stop_data(request._log_data)

def record_request_restart_data(log_data: MutableMapping[str, Any]) -> None:
    if settings.PROFILE_ALL_REQUESTS:
        log_data["prof"].enable()
    log_data['time_restarted'] = time.time()
    log_data['remote_cache_time_restarted'] = get_remote_cache_time()
    log_data['remote_cache_requests_restarted'] = get_remote_cache_requests()
    log_data['markdown_time_restarted'] = get_markdown_time()
    log_data['markdown_requests_restarted'] = get_markdown_requests()

def async_request_timer_restart(request: HttpRequest) -> None:
    if "time_restarted" in request._log_data:
        # Don't destroy data when being called from
        # finish_current_handler
        return
    record_request_restart_data(request._log_data)

def record_request_start_data(log_data: MutableMapping[str, Any]) -> None:
    if settings.PROFILE_ALL_REQUESTS:
        log_data["prof"] = cProfile.Profile()
        log_data["prof"].enable()

    reset_queries()
    log_data['time_started'] = time.time()
    log_data['remote_cache_time_start'] = get_remote_cache_time()
    log_data['remote_cache_requests_start'] = get_remote_cache_requests()
    log_data['markdown_time_start'] = get_markdown_time()
    log_data['markdown_requests_start'] = get_markdown_requests()

def timedelta_ms(timedelta: float) -> float:
    return timedelta * 1000

def format_timedelta(timedelta: float) -> str:
    if (timedelta >= 1):
        return f"{timedelta:.1f}s"
    return f"{timedelta_ms(timedelta):.0f}ms"

def is_slow_query(time_delta: float, path: str) -> bool:
    if time_delta < 1.2:
        return False
    is_exempt = \
        path in ["/activity", "/json/report/error",
                 "/api/v1/deployments/report_error"] \
        or path.startswith("/realm_activity/") \
        or path.startswith("/user_activity/")
    if is_exempt:
        return time_delta >= 5
    if 'webathena_kerberos' in path:
        return time_delta >= 10
    return True

statsd_blacklisted_requests = [
    'do_confirm', 'signup_send_confirm', 'new_realm_send_confirm,'
    'eventslast_event_id', 'webreq.content', 'avatar', 'user_uploads',
    'password.reset', 'static', 'json.bots', 'json.users', 'json.streams',
    'accounts.unsubscribe', 'apple-touch-icon', 'emoji', 'json.bots',
    'upload_file', 'realm_activity', 'user_activity',
]

def write_log_line(log_data: MutableMapping[str, Any], path: str, method: str, remote_ip: str,
                   requestor_for_logs: str, client_name: str, status_code: int=200,
                   error_content: Optional[AnyStr]=None,
                   error_content_iter: Optional[Iterable[AnyStr]]=None) -> None:
    assert error_content is None or error_content_iter is None
    if error_content is not None:
        error_content_iter = (error_content,)

    if settings.STATSD_HOST != '':
        # For statsd timer name
        if path == '/':
            statsd_path = 'webreq'
        else:
            statsd_path = "webreq.{}".format(path[1:].replace('/', '.'))
            # Remove non-ascii chars from path (there should be none, if there are it's
            # because someone manually entered a nonexistent path), as UTF-8 chars make
            # statsd sad when it sends the key name over the socket
            statsd_path = statsd_path.encode('ascii', errors='ignore').decode("ascii")
        # TODO: This could probably be optimized to use a regular expression rather than a loop.
        suppress_statsd = any(blacklisted in statsd_path for blacklisted in statsd_blacklisted_requests)
    else:
        suppress_statsd = True
        statsd_path = ''

    time_delta = -1
    # A time duration of -1 means the StartLogRequests middleware
    # didn't run for some reason
    optional_orig_delta = ""
    if 'time_started' in log_data:
        time_delta = time.time() - log_data['time_started']
    if 'time_stopped' in log_data:
        orig_time_delta = time_delta
        time_delta = ((log_data['time_stopped'] - log_data['time_started']) +
                      (time.time() - log_data['time_restarted']))
        optional_orig_delta = f" (lp: {format_timedelta(orig_time_delta)})"
    remote_cache_output = ""
    if 'remote_cache_time_start' in log_data:
        remote_cache_time_delta = get_remote_cache_time() - log_data['remote_cache_time_start']
        remote_cache_count_delta = get_remote_cache_requests() - log_data['remote_cache_requests_start']
        if 'remote_cache_requests_stopped' in log_data:
            # (now - restarted) + (stopped - start) = (now - start) + (stopped - restarted)
            remote_cache_time_delta += (log_data['remote_cache_time_stopped'] -
                                        log_data['remote_cache_time_restarted'])
            remote_cache_count_delta += (log_data['remote_cache_requests_stopped'] -
                                         log_data['remote_cache_requests_restarted'])

        if (remote_cache_time_delta > 0.005):
            remote_cache_output = f" (mem: {format_timedelta(remote_cache_time_delta)}/{remote_cache_count_delta})"

        if not suppress_statsd:
            statsd.timing(f"{statsd_path}.remote_cache.time", timedelta_ms(remote_cache_time_delta))
            statsd.incr(f"{statsd_path}.remote_cache.querycount", remote_cache_count_delta)

    startup_output = ""
    if 'startup_time_delta' in log_data and log_data["startup_time_delta"] > 0.005:
        startup_output = " (+start: {})".format(format_timedelta(log_data["startup_time_delta"]))

    markdown_output = ""
    if 'markdown_time_start' in log_data:
        markdown_time_delta = get_markdown_time() - log_data['markdown_time_start']
        markdown_count_delta = get_markdown_requests() - log_data['markdown_requests_start']
        if 'markdown_requests_stopped' in log_data:
            # (now - restarted) + (stopped - start) = (now - start) + (stopped - restarted)
            markdown_time_delta += (log_data['markdown_time_stopped'] -
                                    log_data['markdown_time_restarted'])
            markdown_count_delta += (log_data['markdown_requests_stopped'] -
                                     log_data['markdown_requests_restarted'])

        if (markdown_time_delta > 0.005):
            markdown_output = f" (md: {format_timedelta(markdown_time_delta)}/{markdown_count_delta})"

            if not suppress_statsd:
                statsd.timing(f"{statsd_path}.markdown.time", timedelta_ms(markdown_time_delta))
                statsd.incr(f"{statsd_path}.markdown.count", markdown_count_delta)

    # Get the amount of time spent doing database queries
    db_time_output = ""
    queries = connection.connection.queries if connection.connection is not None else []
    if len(queries) > 0:
        query_time = sum(float(query.get('time', 0)) for query in queries)
        db_time_output = f" (db: {format_timedelta(query_time)}/{len(queries)}q)"

        if not suppress_statsd:
            # Log ms, db ms, and num queries to statsd
            statsd.timing(f"{statsd_path}.dbtime", timedelta_ms(query_time))
            statsd.incr(f"{statsd_path}.dbq", len(queries))
            statsd.timing(f"{statsd_path}.total", timedelta_ms(time_delta))

    if 'extra' in log_data:
        extra_request_data = " {}".format(log_data['extra'])
    else:
        extra_request_data = ""
    logger_client = f"({requestor_for_logs} via {client_name})"
    logger_timing = f'{format_timedelta(time_delta):>5}{optional_orig_delta}{remote_cache_output}{markdown_output}{db_time_output}{startup_output} {path}'
    logger_line = f'{remote_ip:<15} {method:<7} {status_code:3} {logger_timing}{extra_request_data} {logger_client}'
    if (status_code in [200, 304] and method == "GET" and path.startswith("/static")):
        logger.debug(logger_line)
    else:
        logger.info(logger_line)

    if (is_slow_query(time_delta, path)):
        slow_query_logger.info(logger_line)

    if settings.PROFILE_ALL_REQUESTS:
        log_data["prof"].disable()
        profile_path = "/tmp/profile.data.{}.{}".format(path.split("/")[-1], int(time_delta * 1000))
        log_data["prof"].dump_stats(profile_path)

    # Log some additional data whenever we return certain 40x errors
    if 400 <= status_code < 500 and status_code not in [401, 404, 405]:
        assert error_content_iter is not None
        error_content_list = list(error_content_iter)
        if not error_content_list:
            error_data = ''
        elif isinstance(error_content_list[0], str):
            error_data = ''.join(error_content_list)
        elif isinstance(error_content_list[0], bytes):
            error_data = repr(b''.join(error_content_list))
        if len(error_data) > 200:
            error_data = "[content more than 200 characters]"
        logger.info('status=%3d, data=%s, uid=%s', status_code, error_data, requestor_for_logs)

class LogRequests(MiddlewareMixin):
    # We primarily are doing logging using the process_view hook, but
    # for some views, process_view isn't run, so we call the start
    # method here too
    def process_request(self, request: HttpRequest) -> None:
        maybe_tracemalloc_listen()

        if hasattr(request, "_log_data"):
            # Sanity check to ensure this is being called from the
            # Tornado code path that returns responses asynchronously.
            assert getattr(request, "saved_response", False)

            # Avoid re-initializing request._log_data if it's already there.
            return

        request._log_data = {}
        record_request_start_data(request._log_data)

    def process_view(self, request: HttpRequest, view_func: ViewFuncT,
                     args: List[str], kwargs: Dict[str, Any]) -> None:
        if hasattr(request, "saved_response"):
            # The below logging adjustments are unnecessary (because
            # we've already imported everything) and incorrect
            # (because they'll overwrite data from pre-long-poll
            # request processing) when returning a saved response.
            return

        # process_request was already run; we save the initialization
        # time (i.e. the time between receiving the request and
        # figuring out which view function to call, which is primarily
        # importing modules on the first start)
        request._log_data["startup_time_delta"] = time.time() - request._log_data["time_started"]
        # And then completely reset our tracking to only cover work
        # done as part of this request
        record_request_start_data(request._log_data)

    def process_response(self, request: HttpRequest,
                         response: StreamingHttpResponse) -> StreamingHttpResponse:
        if getattr(response, "asynchronous", False):
            # This special Tornado "asynchronous" response is
            # discarded after going through this code path as Tornado
            # intends to block, so we stop here to avoid unnecessary work.
            return response

        remote_ip = request.META['REMOTE_ADDR']

        # Get the requestor's identifier and client, if available.
        try:
            requestor_for_logs = request._requestor_for_logs
        except Exception:
            if hasattr(request, 'user') and hasattr(request.user, 'format_requestor_for_logs'):
                requestor_for_logs = request.user.format_requestor_for_logs()
            else:
                requestor_for_logs = "unauth@{}".format(get_subdomain(request) or 'root')
        try:
            client = request.client.name
        except Exception:
            client = "?"

        if response.streaming:
            content_iter = response.streaming_content
            content = None
        else:
            content = response.content
            content_iter = None

        write_log_line(request._log_data, request.path, request.method,
                       remote_ip, requestor_for_logs, client, status_code=response.status_code,
                       error_content=content, error_content_iter=content_iter)
        return response

class JsonErrorHandler(MiddlewareMixin):
    def __init__(self, get_response: Callable[[Any, WSGIRequest], Union[HttpResponse, BaseException]]) -> None:
        super().__init__(get_response)
        ignore_logger("zerver.middleware.json_error_handler")

    def process_exception(self, request: HttpRequest, exception: Exception) -> Optional[HttpResponse]:
        if isinstance(exception, MissingAuthenticationError):
            if 'text/html' in request.META.get('HTTP_ACCEPT', ''):
                # If this looks like a request from a top-level page in a
                # browser, send the user to the login page.
                #
                # TODO: The next part is a bit questionable; it will
                # execute the likely intent for intentionally visiting
                # an API endpoint without authentication in a browser,
                # but that's an unlikely to be done intentionally often.
                return HttpResponseRedirect(f'{settings.HOME_NOT_LOGGED_IN}?next={request.path}')
            if request.path.startswith("/api"):
                # For API routes, ask for HTTP basic auth (email:apiKey).
                return json_unauthorized()
            else:
                # For /json routes, ask for session authentication.
                return json_unauthorized(www_authenticate='session')

        if isinstance(exception, JsonableError):
            return json_response_from_error(exception)
        if request.error_format == "JSON":
            capture_exception(exception)
            json_error_logger = logging.getLogger("zerver.middleware.json_error_handler")
            json_error_logger.error(traceback.format_exc(), extra=dict(request=request))
            return json_error(_("Internal server error"), status=500)
        return None

class TagRequests(MiddlewareMixin):
    def process_view(self, request: HttpRequest, view_func: ViewFuncT,
                     args: List[str], kwargs: Dict[str, Any]) -> None:
        self.process_request(request)

    def process_request(self, request: HttpRequest) -> None:
        if request.path.startswith("/api/") or request.path.startswith("/json/"):
            request.error_format = "JSON"
        else:
            request.error_format = "HTML"

class CsrfFailureError(JsonableError):
    http_status_code = 403
    code = ErrorCode.CSRF_FAILED
    data_fields = ['reason']

    def __init__(self, reason: str) -> None:
        self.reason: str = reason

    @staticmethod
    def msg_format() -> str:
        return _("CSRF Error: {reason}")

def csrf_failure(request: HttpRequest, reason: str="") -> HttpResponse:
    if request.error_format == "JSON":
        return json_response_from_error(CsrfFailureError(reason))
    else:
        return html_csrf_failure(request, reason)

class RateLimitMiddleware(MiddlewareMixin):
    def set_response_headers(self, response: HttpResponse,
                             rate_limit_results: List[RateLimitResult]) -> None:
        # The limit on the action that was requested is the minimum of the limits that get applied:
        limit = min(result.entity.max_api_calls() for result in rate_limit_results)
        response['X-RateLimit-Limit'] = str(limit)
        # Same principle applies to remaining api calls:
        remaining_api_calls = min(result.remaining for result in rate_limit_results)
        response['X-RateLimit-Remaining'] = str(remaining_api_calls)

        # The full reset time is the maximum of the reset times for the limits that get applied:
        reset_time = time.time() + max(result.secs_to_freedom for result in rate_limit_results)
        response['X-RateLimit-Reset'] = str(int(reset_time))

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        if not settings.RATE_LIMITING:
            return response

        # Add X-RateLimit-*** headers
        if hasattr(request, '_ratelimits_applied'):
            self.set_response_headers(response, request._ratelimits_applied)

        return response

    def process_exception(self, request: HttpRequest,
                          exception: Exception) -> Optional[HttpResponse]:
        if isinstance(exception, RateLimited):
            # secs_to_freedom is passed to RateLimited when raising
            secs_to_freedom = float(str(exception))
            resp = json_error(
                _("API usage exceeded rate limit"),
                data={'retry-after': secs_to_freedom},
                status=429,
            )
            resp['Retry-After'] = secs_to_freedom
            return resp
        return None

class FlushDisplayRecipientCache(MiddlewareMixin):
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        # We flush the per-request caches after every request, so they
        # are not shared at all between requests.
        flush_per_request_caches()
        return response

class HostDomainMiddleware(MiddlewareMixin):
    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        # Match against ALLOWED_HOSTS, which is rather permissive;
        # failure will raise DisallowedHost, which is a 400.
        request.get_host()

        # This check is important to avoid doing the extra work of
        # `get_realm` (which does a database query that could be
        # problematic for Tornado).  Also the error page below is only
        # appropriate for a page visited in a browser, not the API.
        #
        # API authentication will end up checking for an invalid
        # realm, and throw a JSON-format error if appropriate.
        if request.path.startswith(("/static/", "/api/", "/json/")):
            return None

        subdomain = get_subdomain(request)
        if subdomain != Realm.SUBDOMAIN_FOR_ROOT_DOMAIN:
            try:
                request.realm = get_realm(subdomain)
            except Realm.DoesNotExist:
                return render(request, "zerver/invalid_realm.html", status=404)
        return None

class SetRemoteAddrFromForwardedFor(MiddlewareMixin):
    """
    Middleware that sets REMOTE_ADDR based on the HTTP_X_FORWARDED_FOR.

    This middleware replicates Django's former SetRemoteAddrFromForwardedFor middleware.
    Because Zulip sits behind a NGINX reverse proxy, if the HTTP_X_FORWARDED_FOR
    is set in the request, then it has properly been set by NGINX.
    Therefore HTTP_X_FORWARDED_FOR's value is trusted.
    """

    def process_request(self, request: HttpRequest) -> None:
        try:
            real_ip = request.META['HTTP_X_FORWARDED_FOR']
        except KeyError:
            return None
        else:
            # HTTP_X_FORWARDED_FOR can be a comma-separated list of IPs.
            # For NGINX reverse proxy servers, the client's IP will be the first one.
            real_ip = real_ip.split(",")[0].strip()
            request.META['REMOTE_ADDR'] = real_ip

def alter_content(request: HttpRequest, content: bytes) -> bytes:
    first_paragraph_text = get_content_description(content, request)
    return content.replace(request.placeholder_open_graph_description.encode("utf-8"),
                           first_paragraph_text.encode("utf-8"))

class FinalizeOpenGraphDescription(MiddlewareMixin):
    def process_response(self, request: HttpRequest,
                         response: StreamingHttpResponse) -> StreamingHttpResponse:

        if getattr(request, "placeholder_open_graph_description", None) is not None:
            assert not response.streaming
            response.content = alter_content(request, response.content)
        return response

class ZulipCommonMiddleware(CommonMiddleware):
    """
    Patched version of CommonMiddleware to disable the APPEND_SLASH
    redirect behavior inside Tornado.

    While this has some correctness benefit in encouraging clients
    to implement the API correctly, this also saves about 600us in
    the runtime of every GET /events query, as the APPEND_SLASH
    route resolution logic is surprisingly expensive.

    TODO: We should probably extend this behavior to apply to all of
    our API routes.  The APPEND_SLASH behavior is really only useful
    for non-API endpoints things like /login.  But doing that
    transition will require more careful testing.
    """

    def should_redirect_with_slash(self, request: HttpRequest) -> bool:
        if settings.RUNNING_INSIDE_TORNADO:
            return False
        return super().should_redirect_with_slash(request)
