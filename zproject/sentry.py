import os
from typing import TYPE_CHECKING, Optional

import sentry_sdk
from django.utils.translation import override as override_language
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import ignore_logger
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.utils import capture_internal_exceptions

from version import ZULIP_VERSION
from zproject.config import DEPLOY_ROOT

if TYPE_CHECKING:
    from sentry_sdk._types import Event, Hint


def add_context(event: "Event", hint: "Hint") -> Optional["Event"]:
    if "exc_info" in hint:
        _, exc_value, _ = hint["exc_info"]
        # Ignore GeneratorExit, KeyboardInterrupt, and SystemExit exceptions
        if not isinstance(exc_value, Exception):
            return None
    from django.conf import settings

    from zerver.models import get_user_profile_by_id

    with capture_internal_exceptions():
        # event.user is the user context, from Sentry, which is
        # pre-populated with some keys via its Django integration:
        # https://docs.sentry.io/platforms/python/guides/django/enriching-error-data/additional-data/identify-user/
        event.setdefault("tags", {})
        user_info = event.get("user", {})
        if user_info.get("id"):
            user_profile = get_user_profile_by_id(user_info["id"])
            event["tags"]["realm"] = user_info["realm"] = user_profile.realm.string_id or "root"
            with override_language(settings.LANGUAGE_CODE):
                # str() to force the lazy-translation to apply now,
                # since it won't serialize into json for Sentry otherwise
                user_info["role"] = str(user_profile.get_role_name())

        # These are PII, and should be scrubbed
        if "username" in user_info:
            del user_info["username"]
        if "email" in user_info:
            del user_info["email"]

    return event


def setup_sentry(dsn: Optional[str], environment: str) -> None:
    if not dsn:
        return

    sentry_release = ZULIP_VERSION
    if os.path.exists(os.path.join(DEPLOY_ROOT, "sentry-release")):
        with open(os.path.join(DEPLOY_ROOT, "sentry-release")) as sentry_release_file:
            sentry_release = sentry_release_file.readline().strip()
    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=sentry_release,
        integrations=[
            DjangoIntegration(),
            RedisIntegration(),
            SqlalchemyIntegration(),
        ],
        before_send=add_context,
        # Increase possible max wait to send exceptions during
        # shutdown, from 2 to 10; potentially-large exceptions are of
        # value to catch during shutdown.
        shutdown_timeout=10,
        # Because we strip the email/username from the Sentry data
        # above, the effect of this flag is that the requests/users
        # involved in exceptions will be identified in Sentry only by
        # their IP address, user ID, realm, and role.  We consider
        # this an appropriate balance between avoiding Sentry getting
        # PII while having the identifiers needed to determine that an
        # exception only affects a small subset of users or realms.
        send_default_pii=True,
    )

    # Ignore all of the loggers from django.security that are for user
    # errors; see https://docs.djangoproject.com/en/3.2/ref/exceptions/#suspiciousoperation
    ignore_logger("django.security.SuspiciousOperation")
    ignore_logger("django.security.DisallowedHost")
    ignore_logger("django.security.DisallowedModelAdminLookup")
    ignore_logger("django.security.DisallowedModelAdminToField")
    ignore_logger("django.security.DisallowedRedirect")
    ignore_logger("django.security.InvalidSessionKey")
    ignore_logger("django.security.RequestDataTooBig")
    ignore_logger("django.security.SuspiciousFileOperation")
    ignore_logger("django.security.SuspiciousMultipartForm")
    ignore_logger("django.security.SuspiciousSession")
    ignore_logger("django.security.TooManyFieldsSent")
