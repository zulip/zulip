from collections.abc import Iterable, Sequence
from typing import Any

from django.apps.config import AppConfig
from django.conf import settings
from django.core import checks


def check_required_settings(
    app_configs: Sequence[AppConfig] | None,
    databases: Sequence[str] | None,
    **kwargs: Any,
) -> Iterable[checks.CheckMessage]:
    # These are the settings that we will check that the user has filled in for
    # production deployments before starting the app.  It consists of a series
    # of pairs of (setting name, default value that it must be changed from)
    required_settings = [
        ("EXTERNAL_HOST", "zulip.example.com"),
        ("ZULIP_ADMINISTRATOR", "zulip-admin@example.com"),
        # SECRET_KEY doesn't really need to be here, in
        # that we set it automatically, but just in
        # case, it seems worth having in this list
        ("SECRET_KEY", ""),
        ("AUTHENTICATION_BACKENDS", ()),
    ]
    errors = []
    for setting_name, default in required_settings:
        if (
            hasattr(settings, setting_name)
            and getattr(settings, setting_name) != default
            and getattr(settings, setting_name)
        ):
            continue

        errors.append(
            checks.Error(
                f"You must set {setting_name} in /etc/zulip/settings.py",
                obj=f"settings.{setting_name}",
                id="zulip.E001",
            )
        )
    return errors
