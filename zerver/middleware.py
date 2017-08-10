from __future__ import absolute_import

from six import binary_type
from typing import Any, AnyStr, Callable, Dict, Iterable, List, MutableMapping, Optional, Text

from django.conf import settings
from django.core.exceptions import DisallowedHost
from django.utils.translation import ugettext as _
from django.utils.deprecation import MiddlewareMixin

from zerver.lib.response import json_error, json_response_from_error
from zerver.lib.exceptions import JsonableError, ErrorCode
from django.db import connection
from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from zerver.lib.utils import statsd, get_subdomain
from zerver.lib.queue import queue_json_publish
from zerver.lib.cache import get_remote_cache_time, get_remote_cache_requests
from zerver.lib.bugdown import get_bugdown_time, get_bugdown_requests
from zerver.models import flush_per_request_caches, get_realm
from zerver.lib.exceptions import RateLimited
from django.contrib.sessions.middleware import SessionMiddleware
from django.views.csrf import csrf_failure as html_csrf_failure
from django.utils.cache import patch_vary_headers
from django.utils.http import cookie_date
from django.shortcuts import redirect, render

import logging
import time
import cProfile
import traceback

logger = logging.getLogger('zulip.requests')

def record_request_stop_data(log_data):
    # type: (MutableMapping[str, Any]) -> None
    log_data['time_stopped'] = time.time()
    log_data['remote_cache_time_stopped'] = get_remote_cache_time()
    log_data['remote_cache_requests_stopped'] = get_remote_cache_requests()
    log_data['bugdown_time_stopped'] = get_bugdown_time()
    log_data['bugdown_requests_stopped'] = get_bugdown_requests()
    if settings.PROFILE_ALL_REQUESTS:
        log_data["prof"].disable()

def async_request_stop(request):
    # type: (HttpRequest) -> None
    record_request_stop_data(request._log_data)

def record_request_restart_data(log_data):
    # type: (MutableMapping[str, Any]) -> None
    if settings.PROFILE_ALL_REQUESTS:
        log_data["prof"].enable()
    log_data['time_restarted'] = time.time()
    log_data['remote_cache_time_restarted'] = get_remote_cache_time()
    log_data['remote_cache_requests_restarted'] = get_remote_cache_requests()
    log_data['bugdown_time_restarted'] = get_bugdown_time()
    log_data['bugdown_requests_restarted'] = get_bugdown_requests()

def async_request_restart(request):
    # type: (HttpRequest) -> None
    if "time_restarted" in request._log_data:
        # Don't destroy data when being called from
        # finish_current_handler
        return
    record_request_restart_data(request._log_data)

def record_request_start_data(log_data):
    # type: (MutableMapping[str, Any]) -> None
    if settings.PROFILE_ALL_REQUESTS:
        log_data["prof"] = cProfile.Profile()
        log_data["prof"].enable()

    log_data['time_started'] = time.time()
    log_data['remote_cache_time_start'] = get_remote_cache_time()
    log_data['remote_cache_requests_start'] = get_remote_cache_requests()
    log_data['bugdown_time_start'] = get_bugdown_time()
    log_data['bugdown_requests_start'] = get_bugdown_requests()

def timedelta_ms(timedelta):
    # type: (float) -> float
    return timedelta * 1000

def format_timedelta(timedelta):
    # type: (float) -> str
    if (timedelta >= 1):
        return "%.1fs" % (timedelta)
    return "%.0fms" % (timedelta_ms(timedelta),)

def is_slow_query(time_delta, path):
    # type: (float, Text) -> bool
    if time_delta < 1.2:
        return False
    is_exempt = \
        path in ["/activity", "/json/report_error",
                 "/api/v1/deployments/report_error"] \
        or path.startswith("/realm_activity/") \
        or path.startswith("/user_activity/")
    if is_exempt:
        return time_delta >= 5
    if 'webathena_kerberos' in path:
        return time_delta >= 10
    return True

def write_log_line(log_data, path, method, remote_ip, email, client_name,
                   status_code=200, error_content=None, error_content_iter=None):
    # type: (MutableMapping[str, Any], Text, str, str, Text, Text, int, Optional[AnyStr], Optional[Iterable[AnyStr]]) -> None
    assert error_content is None or error_content_iter is None
    if error_content is not None:
        error_content_iter = (error_content,)

    # For statsd timer name
    if path == '/':
        statsd_path = u'webreq'
    else:
        statsd_path = u"webreq.%s" % (path[1:].replace('/', '.'),)
        # Remove non-ascii chars from path (there should be none, if there are it's
        # because someone manually entered a nonexistant path), as UTF-8 chars make
        # statsd sad when it sends the key name over the socket
        statsd_path = statsd_path.encode('ascii', errors='ignore').decode("ascii")
    blacklisted_requests = ['do_confirm', 'send_confirm',
                            'eventslast_event_id', 'webreq.content', 'avatar', 'user_uploads',
                            'password.reset', 'static', 'json.bots', 'json.users', 'json.streams',
                            'accounts.unsubscribe', 'apple-touch-icon', 'emoji', 'json.bots',
                            'upload_file', 'realm_activity', 'user_activity']
    suppress_statsd = any((blacklisted in statsd_path for blacklisted in blacklisted_requests))

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
        queue_json_publish("slow_queries", "%s (%s)" % (logger_line, email), lambda e: None)

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
        elif isinstance(error_content_list[0], Text):
            error_data = u''.join(error_content_list)
        elif isinstance(error_content_list[0], binary_type):
            error_data = repr(b''.join(error_content_list))
        if len(error_data) > 100:
            error_data = u"[content more than 100 characters]"
        logger.info('status=%3d, data=%s, uid=%s' % (status_code, error_data, email))

class LogRequests(MiddlewareMixin):
    # We primarily are doing logging using the process_view hook, but
    # for some views, process_view isn't run, so we call the start
    # method here too
    def process_request(self, request):
        # type: (HttpRequest) -> None
        request._log_data = dict()
        record_request_start_data(request._log_data)
        if connection.connection is not None:
            connection.connection.queries = []

    def process_view(self, request, view_func, args, kwargs):
        # type: (HttpRequest, Callable[..., HttpResponse], List[str], Dict[str, Any]) -> None
        # process_request was already run; we save the initialization
        # time (i.e. the time between receiving the request and
        # figuring out which view function to call, which is primarily
        # importing modules on the first start)
        request._log_data["startup_time_delta"] = time.time() - request._log_data["time_started"]
        # And then completely reset our tracking to only cover work
        # done as part of this request
        record_request_start_data(request._log_data)
        if connection.connection is not None:
            connection.connection.queries = []

    def process_response(self, request, response):
        # type: (HttpRequest, StreamingHttpResponse) -> StreamingHttpResponse
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
    def process_exception(self, request, exception):
        # type: (HttpRequest, Exception) -> Optional[HttpResponse]
        if isinstance(exception, JsonableError):
            return json_response_from_error(exception)
        if request.error_format == "JSON":
            logging.error(traceback.format_exc())
            return json_error(_("Internal server error"), status=500)
        return None

class TagRequests(MiddlewareMixin):
    def process_view(self, request, view_func, args, kwargs):
        # type: (HttpRequest, Callable[..., HttpResponse], List[str], Dict[str, Any]) -> None
        self.process_request(request)

    def process_request(self, request):
        # type: (HttpRequest) -> None
        if request.path.startswith("/api/") or request.path.startswith("/json/"):
            request.error_format = "JSON"
        else:
            request.error_format = "HTML"

class CsrfFailureError(JsonableError):
    http_status_code = 403
    code = ErrorCode.CSRF_FAILED
    data_fields = ['reason']

    def __init__(self, reason):
        # type: (Text) -> None
        self.reason = reason  # type: Text

    @staticmethod
    def msg_format():
        # type: () -> Text
        return _("CSRF Error: {reason}")

def csrf_failure(request, reason=""):
    # type: (HttpRequest, Text) -> HttpResponse
    if request.error_format == "JSON":
        return json_response_from_error(CsrfFailureError(reason))
    else:
        return html_csrf_failure(request, reason)

class RateLimitMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        # type: (HttpRequest, HttpResponse) -> HttpResponse
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

    def process_exception(self, request, exception):
        # type: (HttpRequest, Exception) -> Optional[HttpResponse]
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
    def process_response(self, request, response):
        # type: (HttpRequest, HttpResponse) -> HttpResponse
        # We flush the per-request caches after every request, so they
        # are not shared at all between requests.
        flush_per_request_caches()
        return response

class SessionHostDomainMiddleware(SessionMiddleware):
    def process_response(self, request, response):
        # type: (HttpRequest, HttpResponse) -> HttpResponse
        try:
            request.get_host()
        except DisallowedHost:
            # If we get a DisallowedHost exception trying to access
            # the host, (1) the request is failed anyway and so the
            # below code will do nothing, and (2) the below will
            # trigger a recursive exception, breaking things, so we
            # just return here.
            return response

        if settings.REALMS_HAVE_SUBDOMAINS:
            if (not request.path.startswith("/static/") and not request.path.startswith("/api/") and
                    not request.path.startswith("/json/")):
                subdomain = get_subdomain(request)
                if (request.get_host() == "127.0.0.1:9991" or request.get_host() == "localhost:9991"):
                    return redirect("%s%s" % (settings.EXTERNAL_URI_SCHEME,
                                              settings.EXTERNAL_HOST))
                if subdomain != "":
                    realm = get_realm(subdomain)
                    if (realm is None):
                        return render(request, "zerver/invalid_realm.html")
        """
        If request.session was modified, or if the configuration is to save the
        session every time, save the changes and set a session cookie.
        """
        try:
            accessed = request.session.accessed
            modified = request.session.modified
        except AttributeError:
            pass
        else:
            if accessed:
                patch_vary_headers(response, ('Cookie',))
            if modified or settings.SESSION_SAVE_EVERY_REQUEST:
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
                    request.session.save()
                    host = request.get_host().split(':')[0]

                    session_cookie_domain = settings.SESSION_COOKIE_DOMAIN
                    # The subdomains feature overrides the
                    # SESSION_COOKIE_DOMAIN setting, since the setting
                    # is a fixed value and with subdomains enabled,
                    # the session cookie domain has to vary with the
                    # subdomain.
                    if settings.REALMS_HAVE_SUBDOMAINS:
                        session_cookie_domain = host
                    response.set_cookie(settings.SESSION_COOKIE_NAME,
                                        request.session.session_key, max_age=max_age,
                                        expires=expires, domain=session_cookie_domain,
                                        path=settings.SESSION_COOKIE_PATH,
                                        secure=settings.SESSION_COOKIE_SECURE or None,
                                        httponly=settings.SESSION_COOKIE_HTTPONLY or None)
        return response

class SetRemoteAddrFromForwardedFor(MiddlewareMixin):
    """
    Middleware that sets REMOTE_ADDR based on the HTTP_X_FORWARDED_FOR.

    This middleware replicates Django's former SetRemoteAddrFromForwardedFor middleware.
    Because Zulip sits behind a NGINX reverse proxy, if the HTTP_X_FORWARDED_FOR
    is set in the request, then it has properly been set by NGINX.
    Therefore HTTP_X_FORWARDED_FOR's value is trusted.
    """
    def process_request(self, request):
        # type: (HttpRequest) -> None
        try:
            real_ip = request.META['HTTP_X_FORWARDED_FOR']
        except KeyError:
            return None
        else:
            # HTTP_X_FORWARDED_FOR can be a comma-separated list of IPs.
            # For NGINX reverse proxy servers, the client's IP will be the first one.
            real_ip = real_ip.split(",")[0].strip()
            request.META['REMOTE_ADDR'] = real_ip
