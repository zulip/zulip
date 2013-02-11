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

        # The reverse proxy might have sent us the real external IP
        remote_ip = request.META.get('HTTP_X_REAL_IP')
        if remote_ip is None:
            remote_ip = request.META['REMOTE_ADDR']

        time_delta = -1
        # A time duration of -1 means the StartLogRequests middleware
        # didn't run for some reason
        if hasattr(request, '_time_started'):
            time_delta = time.time() - request._time_started

        # Get the amount of time spent doing database queries
        query_time = sum(float(query.get('time', 0)) for query in connection.queries)
        if settings.DEBUG:
            db_stats = "(db: %.3fs/%sq) " % (query_time, len(connection.queries),)
        else:
            db_stats = ""

        # Get the requestor's email address, if available.
        try:
            email = request._email
        except Exception:
            email = "unauth"

        logger.info('%-15s %-7s %3d %.3fs %s%s (%s)'
            % (remote_ip, request.method, response.status_code,
               time_delta, db_stats, request.get_full_path(), email))
        # Log some additional data whenever we return a 40x error
        if 400 <= response.status_code < 500:
            logger.info('status=%3d, data=%s, uid=%s' % (response.status_code, response.content, email))
        return response

class JsonErrorHandler(object):
    def process_exception(self, request, exception):
        if hasattr(exception, 'to_json_error_msg') and callable(exception.to_json_error_msg):
            return json_error(exception.to_json_error_msg())
        return None
