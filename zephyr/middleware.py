from __future__ import absolute_import

from django.conf import settings
from zephyr.decorator import RequestVariableMissingError, RequestVariableConversionError
from zephyr.lib.response import json_error
from django.db import connection
from zephyr.lib.utils import statsd
from zephyr.lib.cache import get_memcached_time, get_memcached_requests
from zephyr.lib.bugdown import get_bugdown_time, get_bugdown_requests

import logging
import time

logger = logging.getLogger('humbug.requests')

def async_request_stop(request):
    request._time_stopped = time.time()
    request._memcached_time_stopped = get_memcached_time()
    request._memcached_requests_stopped = get_memcached_requests()
    request._bugdown_time_stopped = get_bugdown_time()
    request._bugdown_requests_stopped = get_bugdown_requests()

def async_request_restart(request):
    request._time_restarted = time.time()
    request._memcached_time_restarted = get_memcached_time()
    request._memcached_requests_restarted = get_memcached_requests()
    request._bugdown_time_restarted = get_bugdown_time()
    request._bugdown_requests_restarted = get_bugdown_requests()

class LogRequests(object):
    def process_request(self, request):
        request._time_started = time.time()
        request._memcached_time_start = get_memcached_time()
        request._memcached_requests_start = get_memcached_requests()
        request._bugdown_time_start = get_bugdown_time()
        request._bugdown_requests_start = get_bugdown_requests()

    def process_response(self, request, response):
        def timedelta_ms(timedelta):
            return timedelta * 1000

        def format_timedelta(timedelta):
            if (timedelta >= 1):
                return "%.1fs" % (timedelta)
            return "%.0fms" % (timedelta_ms(timedelta),)

        # For statsd timer name
        if request.path == '/':
            statsd_path = 'webreq'
        else:
            statsd_path = "webreq.%s" % (request.path[1:].replace('/', '.'),)


        # The reverse proxy might have sent us the real external IP
        remote_ip = request.META.get('HTTP_X_REAL_IP')
        if remote_ip is None:
            remote_ip = request.META['REMOTE_ADDR']

        time_delta = -1
        # A time duration of -1 means the StartLogRequests middleware
        # didn't run for some reason
        optional_orig_delta = ""
        if hasattr(request, '_time_started'):
            time_delta = time.time() - request._time_started
        if hasattr(request, "_time_stopped"):
            orig_time_delta = time_delta
            time_delta = ((request._time_stopped - request._time_started) +
                          (time.time() - request._time_restarted))
            optional_orig_delta = " (lp: %s)" % (format_timedelta(orig_time_delta),)
        memcached_output = ""
        if hasattr(request, '_memcached_time_start'):
            memcached_time_delta = get_memcached_time() - request._memcached_time_start
            memcached_count_delta = get_memcached_requests() - request._memcached_requests_start
            if hasattr(request, "_memcached_requests_stopped"):
                # (now - restarted) + (stopped - start) = (now - start) + (stopped - restarted)
                memcached_time_delta += (request._memcached_time_stopped -
                                         request._memcached_time_restarted)
                memcached_count_delta += (request._memcached_requests_stopped -
                                          request._memcached_requests_restarted)

            if (memcached_time_delta > 0.005):
                memcached_output = " (mem: %s/%s)" % (format_timedelta(memcached_time_delta),
                                                      memcached_count_delta)

            statsd.timing("%s.memcached.time" % (statsd_path,), timedelta_ms(memcached_time_delta))
            statsd.incr("%s.memcached.querycount" % (statsd_path,), memcached_count_delta)

        bugdown_output = ""
        if hasattr(request, '_bugdown_time_start'):
            bugdown_time_delta = get_bugdown_time() - request._bugdown_time_start
            bugdown_count_delta = get_bugdown_requests() - request._bugdown_requests_start
            if hasattr(request, "_bugdown_requests_stopped"):
                # (now - restarted) + (stopped - start) = (now - start) + (stopped - restarted)
                bugdown_time_delta += (request._bugdown_time_stopped -
                                       request._bugdown_time_restarted)
                bugdown_count_delta += (request._bugdown_requests_stopped -
                                        request._bugdown_requests_restarted)

            if (bugdown_time_delta > 0.005):
                bugdown_output = " (md: %s/%s)" % (format_timedelta(bugdown_time_delta),
                                                   bugdown_count_delta)

        # Get the amount of time spent doing database queries
        db_time_output = ""
        if len(connection.queries) > 0:
            query_time = sum(float(query.get('time', 0)) for query in connection.queries)
            db_time_output = " (db: %s/%sq)" % (format_timedelta(query_time),
                                                len(connection.queries))

            # Log ms, db ms, and num queries to statsd
            statsd.timing("%s.dbtime" % (statsd_path,), timedelta_ms(query_time))
            statsd.incr("%s.dbq" % (statsd_path, ), len(connection.queries))
            statsd.timing("%s.total" % (statsd_path,), timedelta_ms(time_delta))

        # Get the requestor's email address and client, if available.
        try:
            email = request._email
        except Exception:
            email = "unauth"
        try:
            client = request.client.name
        except Exception:
            client = "?"

        logger.info('%-15s %-7s %3d %5s%s%s%s%s %s (%s via %s)' %
                    (remote_ip, request.method, response.status_code,
                     format_timedelta(time_delta), optional_orig_delta,
                     memcached_output, bugdown_output,
                     db_time_output, request.get_full_path(), email, client))

        # Log some additional data whenever we return certain 40x errors
        if 400 <= response.status_code < 500 and response.status_code not in [401, 404, 405]:
            content = response.content
            if len(content) > 100:
                content = "[content more than 100 characters]"
            logger.info('status=%3d, data=%s, uid=%s' % (response.status_code, content, email))

        return response

class JsonErrorHandler(object):
    def process_exception(self, request, exception):
        if hasattr(exception, 'to_json_error_msg') and callable(exception.to_json_error_msg):
            return json_error(exception.to_json_error_msg())
        return None

# Monkeypatch in time tracking to the Django non-debug cursor
# Code comes from CursorDebugWrapper
def wrapper_execute(self, action, sql, params=()):
    self.set_dirty()
    start = time.time()
    try:
        return action(sql, params)
    finally:
        stop = time.time()
        duration = stop - start
        self.db.queries.append({
                'time': "%.3f" % duration,
                })

from django.db.backends.util import CursorWrapper
def cursor_execute(self, sql, params=()):
    return wrapper_execute(self, self.cursor.execute, sql, params)
CursorWrapper.execute = cursor_execute

def cursor_executemany(self, sql, params=()):
    return wrapper_execute(self, self.cursor.executemany, sql, params)
CursorWrapper.executemany = cursor_executemany
