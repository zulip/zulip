import ipaddress
import os
import re
from collections.abc import Iterable, Sequence
from email.headerregistry import Address
from typing import Any

from django.apps.config import AppConfig
from django.conf import settings
from django.core import checks
from django.core.exceptions import ValidationError
from django.core.validators import validate_email


def setting_name_and_location(setting_name: str) -> tuple[str, str]:
    # Describe a setting the way the administrator knows it, along
    # with where they should adjust it.  Even in Docker,
    # MANUAL_CONFIGURATION means the admin manages
    # /etc/zulip/settings.py themselves, so the SETTING_* environment
    # variables are not where to make changes.
    if settings.RUNNING_IN_HELM:
        return ("zulip.environment.SETTING_" + setting_name, "your Helm values")
    elif settings.RUNNING_IN_DOCKER and os.environ.get("MANUAL_CONFIGURATION") != "True":
        return ("SETTING_" + setting_name, "your Docker environment configuration")
    else:
        return (setting_name, "/etc/zulip/settings.py")


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
        value = getattr(settings, setting_name, None)
        if value and value != default:
            continue

        setting_display_name, settings_location = setting_name_and_location(setting_name)
        if value:
            # The setting is still the example value from the
            # documentation, which the admin must replace -- saying
            # "you must set" it would be confusing, as it is set.
            message = (
                f"{setting_display_name} is still set to the example value {default!r}; "
                f"change it in {settings_location}"
            )
        else:
            message = f"You must set {setting_display_name} in {settings_location}"
        errors.append(
            checks.Error(
                message,
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
    scheme = settings.EXTERNAL_URI_SCHEME
    if scheme != "https://" and not settings.DEVELOPMENT:
        errors.append(
            checks.Error(
                "Zulip does not support a non-HTTPS external scheme in production",
                obj="settings.EXTERNAL_URI_SCHEME",
                hint="Do not override EXTERNAL_URI_SCHEME in production",
                id="zulip.E004",
            )
        )

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


def check_fake_email_domain_setting(
    app_configs: Sequence[AppConfig] | None,
    databases: Sequence[str] | None,
    **kwargs: Any,
) -> Iterable[checks.CheckMessage]:
    if not hasattr(settings, "FAKE_EMAIL_DOMAIN"):  # nocoverage
        return []

    fake_email_domain = settings.FAKE_EMAIL_DOMAIN
    try:
        # The same invariant get_fake_email_domain relies on: the
        # fallback domain for generated email addresses must itself
        # form valid addresses.  Address() rejects some malformed
        # domains with ValueError before validate_email sees them.
        validate_email(Address(username="bot", domain=fake_email_domain).addr_spec)
        return []
    except (ValidationError, ValueError):
        pass

    fake_display_name, settings_location = setting_name_and_location("FAKE_EMAIL_DOMAIN")
    # Users have tried IP addresses and URLs here, so the advice
    # spells out what shape of value is valid.
    advice = (
        f"{fake_display_name} in {settings_location} to a domain name (not an "
        'IP address or URL), like "fake-domain.example.com".  The email '
        "addresses which Zulip generates for bots and users include this "
        "domain and are stored permanently, so it should not change later."
    )

    if fake_email_domain != settings.EXTERNAL_HOST_WITHOUT_PORT:
        return [
            checks.Error(
                f"{fake_display_name} ({fake_email_domain}) cannot be used to form email addresses",
                hint="Set " + advice,
                obj="settings.FAKE_EMAIL_DOMAIN",
                id="zulip.E007",
            )
        ]

    # FAKE_EMAIL_DOMAIN was defaulted from EXTERNAL_HOST, so the
    # advice depends on what is wrong with that setting.
    external_host_display_name, _ = setting_name_and_location("EXTERNAL_HOST")
    try:
        ipaddress.ip_address(fake_email_domain)
    except ValueError:
        # EXTERNAL_HOST is malformed in some way other than being an
        # IP address; check_external_host_setting likely also has a
        # complaint about it.
        return [
            checks.Error(
                f"{fake_display_name}, which defaults to {external_host_display_name} "
                f"({fake_email_domain}), cannot be used to form email addresses",
                hint="Set " + advice,
                obj="settings.FAKE_EMAIL_DOMAIN",
                id="zulip.E007",
            )
        ]

    return [
        checks.Error(
            f"{external_host_display_name} ({fake_email_domain}) is an IP address, "
            "which cannot be used in the email addresses Zulip generates for bots "
            "and users",
            hint=(
                f"Using a hostname for {external_host_display_name} is strongly "
                "recommended: if the server has no name in DNS, invent one (like "
                "zulip.internal), and map it to the server's IP address in "
                "/etc/hosts on every machine that will access Zulip.  To keep the "
                "IP address instead, set " + advice
            ),
            obj="settings.EXTERNAL_HOST",
            id="zulip.E007",
        )
    ]


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


def check_uploads_settings(
    app_configs: Sequence[AppConfig] | None,
    databases: Sequence[str] | None,
    **kwargs: Any,
) -> Iterable[checks.CheckMessage]:
    uploads_dir = settings.LOCAL_UPLOADS_DIR
    if uploads_dir is None:
        errors = []
        if settings.S3_AUTH_UPLOADS_BUCKET == "":
            errors.append(
                checks.Error(
                    "Neither settings.LOCAL_UPLOADS_DIR nor settings.S3_AUTH_UPLOADS_BUCKET is set",
                    obj="settings.S3_AUTH_UPLOADS_BUCKET",
                    id="zulip.E005",
                )
            )
        if settings.S3_AVATAR_BUCKET == "":
            errors.append(
                checks.Error(
                    "Neither settings.LOCAL_UPLOADS_DIR nor settings.S3_AVATAR_BUCKET is set",
                    obj="settings.S3_AVATAR_BUCKET",
                    id="zulip.E005",
                )
            )
        return errors

    if not os.path.isdir(uploads_dir):
        return [
            checks.Error(
                f"settings.LOCAL_UPLOADS_DIR ({uploads_dir}) does not exist",
                obj="settings.LOCAL_UPLOADS_DIR",
                id="zulip.E006",
            )
        ]
    elif not os.access(uploads_dir, os.W_OK):
        return [
            checks.Error(
                f"settings.LOCAL_UPLOADS_DIR ({uploads_dir}) is not writable",
                obj="settings.LOCAL_UPLOADS_DIR",
                id="zulip.E006",
            )
        ]
    return []
