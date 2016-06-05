from __future__ import absolute_import

import logging
from datetime import datetime, timedelta

# Adapted http://djangosnippets.org/snippets/2242/ by user s29 (October 25, 2010)

class _RateLimitFilter(object):
    last_error = datetime.min

    def filter(self, record):
        # type: (logging.LogRecord) -> bool
        from django.conf import settings
        from django.core.cache import cache

        # Track duplicate errors
        duplicate = False
        rate = getattr(settings, '%s_LIMIT' %  self.__class__.__name__.upper(),
               600)  # seconds
        if rate > 0:
            # Test if the cache works
            try:
                cache.set('RLF_TEST_KEY', 1, 1)
                use_cache = cache.get('RLF_TEST_KEY') == 1
            except:
                use_cache = False

            if use_cache:
                key = self.__class__.__name__.upper()
                duplicate = cache.get(key) == 1
                cache.set(key, 1, rate)
            else:
                min_date = datetime.now() - timedelta(seconds=rate)
                duplicate = (self.last_error >= min_date)
                if not duplicate:
                    self.last_error = datetime.now()

        return not duplicate

class ZulipLimiter(_RateLimitFilter):
    pass

class EmailLimiter(_RateLimitFilter):
    pass

class ReturnTrue(logging.Filter):
    def filter(self, record):
        # type: (logging.LogRecord) -> bool
        return True

class RequireReallyDeployed(logging.Filter):
    def filter(self, record):
        # type: (logging.LogRecord) -> bool
        from django.conf import settings
        return settings.PRODUCTION
