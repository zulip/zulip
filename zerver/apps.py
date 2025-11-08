import logging
from typing import Any

import django_stubs_ext
from django.apps import AppConfig
from django.conf import settings
from django.core.cache import cache
from django.db.models.signals import post_migrate
from typing_extensions import override


def flush_cache(sender: AppConfig | None, **kwargs: Any) -> None:
    logging.info("Clearing memcached cache after migrations")
    cache.clear()


class ZerverConfig(AppConfig):
    name: str = "zerver"

    @override
    def ready(self) -> None:
        if settings.SENTRY_DSN:  # nocoverage
            from zproject.config import get_config
            from zproject.sentry import setup_sentry

            setup_sentry(settings.SENTRY_DSN, get_config("machine", "deploy_type", "development"))

        from django.contrib.auth.forms import SetPasswordMixin

        django_stubs_ext.monkeypatch(extra_classes=[SetPasswordMixin])

        # We import zerver.signals here for the side effect of
        # registering the user_logged_in signal receiver.  This import
        # needs to be here (rather than e.g. at top-of-file) to avoid
        # running that code too early in Django's setup process, but
        # in any case, this is an intentionally unused import.
        import zerver.signals  # noqa: F401

        if settings.POST_MIGRATION_CACHE_FLUSHING:
            post_migrate.connect(flush_cache, sender=self)
