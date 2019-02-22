
import logging
from typing import Any

from django.apps import AppConfig
from django.conf import settings
from django.core.cache import cache
from django.db.models.signals import post_migrate

def flush_cache(sender: AppConfig, **kwargs: Any) -> None:
    logging.info("Clearing memcached cache after migrations")
    cache.clear()


class ZerverConfig(AppConfig):
    name = "zerver"  # type: str

    def ready(self) -> None:
        # We import zerver.signals here for the side effect of
        # registering the user_logged_in signal receiver.  This import
        # needs to be here (rather than e.g. at top-of-file) to avoid
        # running that code too early in Django's setup process, but
        # in any case, this is an intentionally unused import.
        import zerver.signals
        zerver.signals

        if settings.POST_MIGRATION_CACHE_FLUSHING:
            post_migrate.connect(flush_cache, sender=self)
