import os
import re
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


def check_external_host_setting(
    app_configs: Sequence[AppConfig] | None,
    databases: Sequence[str] | None,
    **kwargs: Any,
) -> Iterable[checks.CheckMessage]:
    if not hasattr(settings, "EXTERNAL_HOST"):  # nocoverage
        return []

    errors = []
    hostname = settings.EXTERNAL_HOST
    if "." not in hostname and os.environ.get("ZULIP_TEST_SUITE") != "true" and settings.PRODUCTION:
        suggest = ".localdomain" if hostname == "localhost" else ".local"
        errors.append(
            checks.Error(
                f"EXTERNAL_HOST ({hostname}) does not contain a domain part",
                obj="settings.EXTERNAL_HOST",
                hint=f"Add {suggest} to the end",
                id="zulip.E002",
            )
        )

    if ":" in hostname:
        hostname = hostname.split(":")[0]

    if len(hostname) > 255:
        errors.append(
            checks.Error(
                f"EXTERNAL_HOST ({hostname}) is too long to be a valid hostname",
                obj="settings.EXTERNAL_HOST",
                id="zulip.E002",
            )
        )
    domain_part = re.compile(r"(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
    if not hostname.isascii():
        suggestion = ".".join(
            "xn--" + part.encode("punycode").decode() if not part.isascii() else part
            for part in hostname.split(".")
        )
        errors.append(
            checks.Error(
                f"EXTERNAL_HOST ({hostname}) contains non-ASCII characters",
                hint=f"Switch to punycode: {suggestion}",
                obj="settings.EXTERNAL_HOST",
                id="zulip.E002",
            )
        )
    elif not all(domain_part.match(x) for x in hostname.split(".")):
        errors.append(
            checks.Error(
                f"EXTERNAL_HOST ({hostname}) does not validate as a hostname",
                obj="settings.EXTERNAL_HOST",
                id="zulip.E002",
            )
        )
    return errors


def check_auth_settings(
    app_configs: Sequence[AppConfig] | None,
    databases: Sequence[str] | None,
    **kwargs: Any,
) -> Iterable[checks.CheckMessage]:
    errors = []
    for idp_name, idp_dict in settings.SOCIAL_AUTH_SAML_ENABLED_IDPS.items():
        if "zulip_groups" in idp_dict.get("extra_attrs", []):
            errors.append(
                checks.Error(
                    "zulip_groups can't be listed in extra_attrs",
                    obj=f'settings.SOCIAL_AUTH_SAML_ENABLED_IDPS["{idp_name}"]["extra_attrs"]',
                    id="zulip.E003",
                )
            )

    for subdomain, config_dict in settings.SOCIAL_AUTH_SYNC_ATTRS_DICT.items():
        for auth_name, attrs_map in config_dict.items():
            for attr_key, attr_value in attrs_map.items():
                if attr_value == "zulip_groups":
                    errors.append(
                        checks.Error(
                            "zulip_groups can't be listed as a SAML attribute",
                            obj=f'settings.SOCIAL_AUTH_SYNC_ATTRS_DICT["{subdomain}"]["{auth_name}"]["{attr_key}"]',
                            id="zulip.E004",
                        )
                    )
    return errors
