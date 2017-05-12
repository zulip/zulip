from __future__ import absolute_import

from django.utils.timezone import now as timezone_now
from django.utils.timezone import utc as timezone_utc

import hashlib
import logging
import traceback
from datetime import datetime, timedelta
from django.conf import settings
from zerver.lib.str_utils import force_bytes

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
                    tb = force_bytes(str(record))
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

def skip_site_packages_logs(record):
    # type: (logging.LogRecord) -> bool
    # This skips the log records that are generated from libraries
    # installed in site packages.
    # Workaround for https://code.djangoproject.com/ticket/26886
    if 'site-packages' in record.pathname:
        return False
    return True
