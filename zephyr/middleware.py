from django.conf import settings
from decorator import RequestVariableMissingError, RequestVariableConversionError
from zephyr.lib.response import json_error
from django.db import connection

import logging
import time

logger = logging.getLogger('humbug.requests')

class LogRequests(object):
    def process_request(self, request):
        request._time_started = time.time()

    def process_response(self, request, response):
        def format_timedelta(timedelta):
            if (timedelta >= 1):
                return "%.1fs" % (timedelta)
            return "%.0fms" % (timedelta * 1000,)

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

        # Get the amount of time spent doing database queries
        query_time = sum(float(query.get('time', 0)) for query in connection.queries)

        # Get the requestor's email address and client, if available.
        try:
            email = request._email
        except Exception:
            email = "unauth"
        try:
            client = request._client.name
        except Exception:
            client = "?"

        logger.info('%-15s %-7s %3d %5s%s (db: %s/%sq) %s (%s via %s)' %
                    (remote_ip, request.method, response.status_code,
                     format_timedelta(time_delta), optional_orig_delta,
                     format_timedelta(query_time), len(connection.queries),
                     request.get_full_path(), email, client))

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
