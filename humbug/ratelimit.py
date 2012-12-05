import traceback
from hashlib import sha256
from datetime import datetime, timedelta

# Adapted http://djangosnippets.org/snippets/2242/ by user s29 (October 25, 2010)

class RateLimitFilter(object):

    last_error = 0

    def filter(self, record):
        from django.conf import settings
        from django.core.cache import cache

        # Track duplicate errors
        duplicate = False
        rate = getattr(settings, 'ERROR_RATE_LIMIT', 600)  # seconds
        if rate > 0:
            # Test if the cache works
            try:
                cache.set('RLF_TEST_KEY', 1, 1)
                use_cache = cache.get('RLF_TEST_KEY') == 1
            except:
                use_cache = False

            if use_cache:
                duplicate = cache.get('ERROR_RATE') == 1
                cache.set('ERROR_RATE', 1, rate)
            else:
                min_date = datetime.now() - timedelta(seconds=rate)
                duplicate = (self.last_error >= min_date)
                if not duplicate:
                    self.last_error = datetime.now()

        return not duplicate
