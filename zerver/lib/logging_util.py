from __future__ import absolute_import

from django.utils.timezone import now as timezone_now
from django.utils.timezone import utc as timezone_utc

import hashlib
import logging
import re
import traceback
from datetime import datetime, timedelta
from django.conf import settings
from zerver.lib.str_utils import force_bytes
from logging import Logger

# Adapted http://djangosnippets.org/snippets/2242/ by user s29 (October 25, 2010)

class _RateLimitFilter(object):
    last_error = datetime.min.replace(tzinfo=timezone_utc)

    def filter(self, record):
        # type: (logging.LogRecord) -> bool
        from django.conf import settings
        from django.core.cache import cache

        # Track duplicate errors
        duplicate = False
        rate = getattr(settings, '%s_LIMIT' % self.__class__.__name__.upper(),
                       600)  # seconds
        if rate > 0:
            # Test if the cache works
            try:
                cache.set('RLF_TEST_KEY', 1, 1)
                use_cache = cache.get('RLF_TEST_KEY') == 1
            except Exception:
                use_cache = False

            if use_cache:
                if record.exc_info is not None:
                    tb = force_bytes('\n'.join(traceback.format_exception(*record.exc_info)))
                else:
                    tb = force_bytes(u'%s' % (record,))
                key = self.__class__.__name__.upper() + hashlib.sha1(tb).hexdigest()
                duplicate = cache.get(key) == 1
                if not duplicate:
                    cache.set(key, 1, rate)
            else:
                min_date = timezone_now() - timedelta(seconds=rate)
                duplicate = (self.last_error >= min_date)
                if not duplicate:
                    self.last_error = timezone_now()

        return not duplicate

class ZulipLimiter(_RateLimitFilter):
    pass

class EmailLimiter(_RateLimitFilter):
    pass

class ReturnTrue(logging.Filter):
    def filter(self, record):
        # type: (logging.LogRecord) -> bool
        return True

class ReturnEnabled(logging.Filter):
    def filter(self, record):
        # type: (logging.LogRecord) -> bool
        return settings.LOGGING_NOT_DISABLED

class RequireReallyDeployed(logging.Filter):
    def filter(self, record):
        # type: (logging.LogRecord) -> bool
        from django.conf import settings
        return settings.PRODUCTION

def skip_200_and_304(record):
    # type: (logging.LogRecord) -> bool
    # Apparently, `status_code` is added by Django and is not an actual
    # attribute of LogRecord; as a result, mypy throws an error if we
    # access the `status_code` attribute directly.
    if getattr(record, 'status_code') in [200, 304]:
        return False

    return True

IGNORABLE_404_URLS = [
    re.compile(r'^/apple-touch-icon.*\.png$'),
    re.compile(r'^/favicon\.ico$'),
    re.compile(r'^/robots\.txt$'),
    re.compile(r'^/django_static_404.html$'),
    re.compile(r'^/wp-login.php$'),
]

def skip_boring_404s(record):
    # type: (logging.LogRecord) -> bool
    """Prevents Django's 'Not Found' warnings from being logged for common
    404 errors that don't reflect a problem in Zulip.  The overall
    result is to keep the Zulip error logs cleaner than they would
    otherwise be.

    Assumes that its input is a django.request log record.
    """
    # Apparently, `status_code` is added by Django and is not an actual
    # attribute of LogRecord; as a result, mypy throws an error if we
    # access the `status_code` attribute directly.
    if getattr(record, 'status_code') != 404:
        return True

    # We're only interested in filtering the "Not Found" errors.
    if getattr(record, 'msg') != 'Not Found: %s':
        return True

    path = getattr(record, 'args', [''])[0]
    for pattern in IGNORABLE_404_URLS:
        if re.match(pattern, path):
            return False
    return True

def skip_site_packages_logs(record):
    # type: (logging.LogRecord) -> bool
    # This skips the log records that are generated from libraries
    # installed in site packages.
    # Workaround for https://code.djangoproject.com/ticket/26886
    if 'site-packages' in record.pathname:
        return False
    return True

def create_logger(name, log_file, log_level, log_format="%(asctime)s %(levelname)-8s %(message)s"):
    # type: (str, str, str, str) -> Logger
    """Creates a named logger for use in logging content to a certain
    file.  A few notes:

    * "name" is used in determining what gets logged to which files;
    see "loggers" in zproject/settings.py for details.  Don't use `""`
    -- that's the root logger.
    * "log_file" should be declared in zproject/settings.py in ZULIP_PATHS.

    """
    logging.basicConfig(format=log_format)
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))

    if log_file:
        formatter = logging.Formatter(log_format)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
