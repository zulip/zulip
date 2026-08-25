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

from zerver.checks import (
    check_auth_settings,
    check_external_host_setting,
    check_required_settings,
    check_uploads_settings,
)


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


def skip_smokescreen_proxy_for_boto3() -> None:
    # https://github.com/boto/botocore/issues/2644: the request boto3
    # makes to fetch EC2 instance credentials from the IMDS endpoint
    # always reads the proxy configuration from the environment,
    # ignoring any per-client setting. Our application processes route
    # outgoing HTTP through Smokescreen, so that metadata request would
    # be proxied; and Smokescreen would refuse the internal
    # IMDS address (169.254.169.254). Disable proxying for boto3 so the
    # metadata request (and other boto3 traffic) goes direct.
    #
    # This must run at process startup so that it takes effect in every
    # process, including queue workers.
    import botocore.utils

    botocore.utils.should_bypass_proxies = lambda url: True


class ZerverConfig(AppConfig):
    name: str = "zerver"

    @override
    def ready(self) -> None:
        register(check_required_settings)
        register(check_external_host_setting)
        register(check_auth_settings)
        register(check_uploads_settings)

        if settings.SENTRY_DSN:  # nocoverage
            from zproject.config import get_config
            from zproject.sentry import setup_sentry

            setup_sentry(settings.SENTRY_DSN, get_config("machine", "deploy_type", "development"))

        from django.contrib.auth.forms import SetPasswordMixin

        django_stubs_ext.monkeypatch(extra_classes=[SetPasswordMixin])

        if settings.S3_SKIP_PROXY is True and settings.LOCAL_UPLOADS_DIR is None:  # nocoverage
            skip_smokescreen_proxy_for_boto3()

        # We import zerver.signals here for the side effect of
        # registering the user_logged_in signal receiver.  This import
        # needs to be here (rather than e.g. at top-of-file) to avoid
        # running that code too early in Django's setup process, but
        # in any case, this is an intentionally unused import.
        import zerver.signals  # noqa: F401

        if settings.POST_MIGRATION_CACHE_FLUSHING:
            post_migrate.connect(flush_cache, sender=self)

        pre_migrate.connect(create_zulip_schema)
