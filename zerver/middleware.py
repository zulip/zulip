
import cProfile
import logging
import time
import traceback
from typing import Any, AnyStr, Dict, \
    Iterable, List, MutableMapping, Optional

from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib.sessions.backends.base import UpdateError
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import DisallowedHost, SuspiciousOperation
from django.db import connection
from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from django.shortcuts import render
from django.utils.cache import patch_vary_headers
from django.utils.deprecation import MiddlewareMixin
from django.utils.http import cookie_date
from django.utils.translation import ugettext as _
from django.views.csrf import csrf_failure as html_csrf_failure

from zerver.lib.bugdown import get_bugdown_requests, get_bugdown_time
from zerver.lib.cache import get_remote_cache_requests, get_remote_cache_time, \
    cache_with_key, open_graph_description_cache_key
from zerver.lib.debug import maybe_tracemalloc_listen
from zerver.lib.db import reset_queries
from zerver.lib.exceptions import ErrorCode, JsonableError, RateLimited
from zerver.lib.queue import queue_json_publish
from zerver.lib.response import json_error, json_response_from_error
from zerver.lib.subdomains import get_subdomain
from zerver.lib.utils import statsd
from zerver.lib.types import ViewFuncT
from zerver.models import Realm, flush_per_request_caches, get_realm

logger = logging.getLogger('zulip.requests')

def record_request_stop_data(log_data: MutableMapping[str, Any]) -> None:
    log_data['time_stopped'] = time.time()
    log_data['remote_cache_time_stopped'] = get_remote_cache_time()
    log_data['remote_cache_requests_stopped'] = get_remote_cache_requests()
    log_data['bugdown_time_stopped'] = get_bugdown_time()
    log_data['bugdown_requests_stopped'] = get_bugdown_requests()
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
    log_data['bugdown_time_restarted'] = get_bugdown_time()
    log_data['bugdown_requests_restarted'] = get_bugdown_requests()

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
    log_data['bugdown_time_start'] = get_bugdown_time()
    log_data['bugdown_requests_start'] = get_bugdown_requests()

def timedelta_ms(timedelta: float) -> float:
    return timedelta * 1000

def format_timedelta(timedelta: float) -> str:
    if (timedelta >= 1):
        return "%.1fs" % (timedelta)
    return "%.0fms" % (timedelta_ms(timedelta),)

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
    'upload_file', 'realm_activity', 'user_activity'
]

def write_log_line(log_data: MutableMapping[str, Any], path: str, method: str, remote_ip: str, email: str,
                   client_name: str, status_code: int=200, error_content: Optional[AnyStr]=None,
                   error_content_iter: Optional[Iterable[AnyStr]]=None) -> None:
    assert error_content is None or error_content_iter is None
    if error_content is not None:
        error_content_iter = (error_content,)

    if settings.STATSD_HOST != '':
        # For statsd timer name
        if path == '/':
            statsd_path = u'webreq'
        else:
            statsd_path = u"webreq.%s" % (path[1:].replace('/', '.'),)
            # Remove non-ascii chars from path (there should be none, if there are it's
            # because someone manually entered a nonexistent path), as UTF-8 chars make
            # statsd sad when it sends the key name over the socket
            statsd_path = statsd_path.encode('ascii', errors='ignore').decode("ascii")
        # TODO: This could probably be optimized to use a regular expression rather than a loop.
        suppress_statsd = any((blacklisted in statsd_path for blacklisted in statsd_blacklisted_requests))
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
        optional_orig_delta = " (lp: %s)" % (format_timedelta(orig_time_delta),)
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
            remote_cache_output = " (mem: %s/%s)" % (format_timedelta(remote_cache_time_delta),
                                                     remote_cache_count_delta)

        if not suppress_statsd:
            statsd.timing("%s.remote_cache.time" % (statsd_path,), timedelta_ms(remote_cache_time_delta))
            statsd.incr("%s.remote_cache.querycount" % (statsd_path,), remote_cache_count_delta)

    startup_output = ""
    if 'startup_time_delta' in log_data and log_data["startup_time_delta"] > 0.005:
        startup_output = " (+start: %s)" % (format_timedelta(log_data["startup_time_delta"]))

    bugdown_output = ""
    if 'bugdown_time_start' in log_data:
        bugdown_time_delta = get_bugdown_time() - log_data['bugdown_time_start']
        bugdown_count_delta = get_bugdown_requests() - log_data['bugdown_requests_start']
        if 'bugdown_requests_stopped' in log_data:
            # (now - restarted) + (stopped - start) = (now - start) + (stopped - restarted)
            bugdown_time_delta += (log_data['bugdown_time_stopped'] -
                                   log_data['bugdown_time_restarted'])
            bugdown_count_delta += (log_data['bugdown_requests_stopped'] -
                                    log_data['bugdown_requests_restarted'])

        if (bugdown_time_delta > 0.005):
            bugdown_output = " (md: %s/%s)" % (format_timedelta(bugdown_time_delta),
                                               bugdown_count_delta)

            if not suppress_statsd:
                statsd.timing("%s.markdown.time" % (statsd_path,), timedelta_ms(bugdown_time_delta))
                statsd.incr("%s.markdown.count" % (statsd_path,), bugdown_count_delta)

    # Get the amount of time spent doing database queries
    db_time_output = ""
    queries = connection.connection.queries if connection.connection is not None else []
    if len(queries) > 0:
        query_time = sum(float(query.get('time', 0)) for query in queries)
        db_time_output = " (db: %s/%sq)" % (format_timedelta(query_time),
                                            len(queries))

        if not suppress_statsd:
            # Log ms, db ms, and num queries to statsd
            statsd.timing("%s.dbtime" % (statsd_path,), timedelta_ms(query_time))
            statsd.incr("%s.dbq" % (statsd_path,), len(queries))
            statsd.timing("%s.total" % (statsd_path,), timedelta_ms(time_delta))

    if 'extra' in log_data:
        extra_request_data = " %s" % (log_data['extra'],)
    else:
        extra_request_data = ""
    logger_client = "(%s via %s)" % (email, client_name)
    logger_timing = ('%5s%s%s%s%s%s %s' %
                     (format_timedelta(time_delta), optional_orig_delta,
                      remote_cache_output, bugdown_output,
                      db_time_output, startup_output, path))
    logger_line = ('%-15s %-7s %3d %s%s %s' %
                   (remote_ip, method, status_code,
                    logger_timing, extra_request_data, logger_client))
    if (status_code in [200, 304] and method == "GET" and path.startswith("/static")):
        logger.debug(logger_line)
    else:
        logger.info(logger_line)

    if (is_slow_query(time_delta, path)):
        queue_json_publish("slow_queries", "%s (%s)" % (logger_line, email))

    if settings.PROFILE_ALL_REQUESTS:
        log_data["prof"].disable()
        profile_path = "/tmp/profile.data.%s.%s" % (path.split("/")[-1], int(time_delta * 1000),)
        log_data["prof"].dump_stats(profile_path)

    # Log some additional data whenever we return certain 40x errors
    if 400 <= status_code < 500 and status_code not in [401, 404, 405]:
        assert error_content_iter is not None
        error_content_list = list(error_content_iter)
        if error_content_list:
            error_data = u''
        elif isinstance(error_content_list[0], str):
            error_data = u''.join(error_content_list)
        elif isinstance(error_content_list[0], bytes):
            error_data = repr(b''.join(error_content_list))
        if len(error_data) > 100:
            error_data = u"[content more than 100 characters]"
        logger.info('status=%3d, data=%s, uid=%s' % (status_code, error_data, email))

class LogRequests(MiddlewareMixin):
    # We primarily are doing logging using the process_view hook, but
    # for some views, process_view isn't run, so we call the start
    # method here too
    def process_request(self, request: HttpRequest) -> None:
        maybe_tracemalloc_listen()
        request._log_data = dict()
        record_request_start_data(request._log_data)

    def process_view(self, request: HttpRequest, view_func: ViewFuncT,
                     args: List[str], kwargs: Dict[str, Any]) -> None:
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
        # The reverse proxy might have sent us the real external IP
        remote_ip = request.META.get('HTTP_X_REAL_IP')
        if remote_ip is None:
            remote_ip = request.META['REMOTE_ADDR']

        # Get the requestor's email address and client, if available.
        try:
            email = request._email
        except Exception:
            email = "unauth"
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
                       remote_ip, email, client, status_code=response.status_code,
                       error_content=content, error_content_iter=content_iter)
        return response

class JsonErrorHandler(MiddlewareMixin):
    def process_exception(self, request: HttpRequest, exception: Exception) -> Optional[HttpResponse]:
        if isinstance(exception, JsonableError):
            return json_response_from_error(exception)
        if request.error_format == "JSON":
            logging.error(traceback.format_exc(), extra=dict(request=request))
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
        self.reason = reason  # type: str

    @staticmethod
    def msg_format() -> str:
        return _("CSRF Error: {reason}")

def csrf_failure(request: HttpRequest, reason: str="") -> HttpResponse:
    if request.error_format == "JSON":
        return json_response_from_error(CsrfFailureError(reason))
    else:
        return html_csrf_failure(request, reason)

class RateLimitMiddleware(MiddlewareMixin):
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        if not settings.RATE_LIMITING:
            return response

        from zerver.lib.rate_limiter import max_api_calls, RateLimitedUser
        # Add X-RateLimit-*** headers
        if hasattr(request, '_ratelimit_applied_limits'):
            entity = RateLimitedUser(request.user)
            response['X-RateLimit-Limit'] = str(max_api_calls(entity))
            if hasattr(request, '_ratelimit_secs_to_freedom'):
                response['X-RateLimit-Reset'] = str(int(time.time() + request._ratelimit_secs_to_freedom))
            if hasattr(request, '_ratelimit_remaining'):
                response['X-RateLimit-Remaining'] = str(request._ratelimit_remaining)
        return response

    def process_exception(self, request: HttpRequest, exception: Exception) -> Optional[HttpResponse]:
        if isinstance(exception, RateLimited):
            resp = json_error(
                _("API usage exceeded rate limit"),
                data={'retry-after': request._ratelimit_secs_to_freedom},
                status=429
            )
            resp['Retry-After'] = request._ratelimit_secs_to_freedom
            return resp
        return None

class FlushDisplayRecipientCache(MiddlewareMixin):
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        # We flush the per-request caches after every request, so they
        # are not shared at all between requests.
        flush_per_request_caches()
        return response

class SessionHostDomainMiddleware(SessionMiddleware):
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        try:
            request.get_host()
        except DisallowedHost:
            # If we get a DisallowedHost exception trying to access
            # the host, (1) the request is failed anyway and so the
            # below code will do nothing, and (2) the below will
            # trigger a recursive exception, breaking things, so we
            # just return here.
            return response

        if (not request.path.startswith("/static/") and not request.path.startswith("/api/") and
                not request.path.startswith("/json/")):
            subdomain = get_subdomain(request)
            if subdomain != Realm.SUBDOMAIN_FOR_ROOT_DOMAIN:
                realm = get_realm(subdomain)
                if (realm is None):
                    return render(request, "zerver/invalid_realm.html")
        """
        If request.session was modified, or if the configuration is to save the
        session every time, save the changes and set a session cookie or delete
        the session cookie if the session has been emptied.
        """
        try:
            accessed = request.session.accessed
            modified = request.session.modified
            empty = request.session.is_empty()
        except AttributeError:
            pass
        else:
            # First check if we need to delete this cookie.
            # The session should be deleted only if the session is entirely empty
            if settings.SESSION_COOKIE_NAME in request.COOKIES and empty:
                response.delete_cookie(
                    settings.SESSION_COOKIE_NAME,
                    path=settings.SESSION_COOKIE_PATH,
                    domain=settings.SESSION_COOKIE_DOMAIN,
                )
            else:
                if accessed:
                    patch_vary_headers(response, ('Cookie',))
                if (modified or settings.SESSION_SAVE_EVERY_REQUEST) and not empty:
                    if request.session.get_expire_at_browser_close():
                        max_age = None
                        expires = None
                    else:
                        max_age = request.session.get_expiry_age()
                        expires_time = time.time() + max_age
                        expires = cookie_date(expires_time)
                    # Save the session data and refresh the client cookie.
                    # Skip session save for 500 responses, refs #3881.
                    if response.status_code != 500:
                        try:
                            request.session.save()
                        except UpdateError:
                            raise SuspiciousOperation(
                                "The request's session was deleted before the "
                                "request completed. The user may have logged "
                                "out in a concurrent request, for example."
                            )
                        host = request.get_host().split(':')[0]

                        # The subdomains feature overrides the
                        # SESSION_COOKIE_DOMAIN setting, since the setting
                        # is a fixed value and with subdomains enabled,
                        # the session cookie domain has to vary with the
                        # subdomain.
                        session_cookie_domain = host
                        response.set_cookie(
                            settings.SESSION_COOKIE_NAME,
                            request.session.session_key, max_age=max_age,
                            expires=expires, domain=session_cookie_domain,
                            path=settings.SESSION_COOKIE_PATH,
                            secure=settings.SESSION_COOKIE_SECURE or None,
                            httponly=settings.SESSION_COOKIE_HTTPONLY or None,
                        )
        return response

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

@cache_with_key(open_graph_description_cache_key, timeout=3600*24)
def get_content_description(content: bytes, request: HttpRequest) -> str:
    str_content = content.decode("utf-8")
    bs = BeautifulSoup(str_content, features='lxml')
    # Skip any admonition (warning) blocks, since they're
    # usually something about users needing to be an
    # organization administrator, and not useful for
    # describing the page.
    for tag in bs.find_all('div', class_="admonition"):
        tag.clear()

    # Skip code-sections, which just contains navigation instructions.
    for tag in bs.find_all('div', class_="code-section"):
        tag.clear()

    text = ''
    for paragraph in bs.find_all('p'):
        # .text converts it from HTML to text
        text = text + paragraph.text + ' '
        if len(text) > 500:
            return ' '.join(text.split())
    return ' '.join(text.split())

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
