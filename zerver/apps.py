import logging
from typing import Any

import django_stubs_ext
from django.apps import AppConfig
from django.conf import settings
from django.core.cache import cache
from django.core.checks import register
from django.db import connection
from django.db.models.signals import post_migrate, pre_migrate
from typing_extensions import override

from zerver.checks import check_auth_settings, check_external_host_setting, check_required_settings


def flush_cache(sender: AppConfig | None, **kwargs: Any) -> None:
    logging.info("Clearing memcached cache after migrations")
    cache.clear()


def create_zulip_schema(sender: AppConfig, **kwargs: Any) -> None:  # nocoverage
    # We do this here, and not in a zerver migration, because we
    # cannot be sure that zerver migrations run _first_, of all of the
    # Django apps.  Updating `SET search_path` is just for the current
    # connection; the user's default search_path is set in the
    # zerver/0001 migrations.
    with connection.cursor() as cursor:
        cursor.execute("CREATE SCHEMA IF NOT EXISTS zulip")
        cursor.execute("SET search_path = zulip,public")


class ZerverConfig(AppConfig):
    name: str = "zerver"

    @override
    def ready(self) -> None:
        register(check_required_settings)
        register(check_external_host_setting)
        register(check_auth_settings)

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

        pre_migrate.connect(create_zulip_schema)
