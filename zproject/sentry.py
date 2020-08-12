from typing import TYPE_CHECKING, Optional

import sentry_sdk
from sentry_sdk.integrations import Integration
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import ignore_logger
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.utils import capture_internal_exceptions

from .config import PRODUCTION

if TYPE_CHECKING:
    from sentry_sdk._types import Event, Hint

def add_context(event: 'Event', hint: 'Hint') -> Optional['Event']:
    if "exc_info" in hint:
        _, exc_value, _ = hint["exc_info"]
        # Ignore GeneratorExit, KeyboardInterrupt, and SystemExit exceptions
        if not isinstance(exc_value, Exception):
            return None
    from zerver.models import get_user_profile_by_id
    with capture_internal_exceptions():
        user_info = event.get("user", {})
        if user_info.get("id"):
            user_profile = get_user_profile_by_id(user_info["id"])
            user_info["realm"] = user_profile.realm.string_id or 'root'
            user_info["role"] = user_profile.get_role_name()
    return event

def setup_sentry(dsn: Optional[str], *integrations: Integration) -> None:
    if not dsn:
        return
    sentry_sdk.init(
        dsn=dsn,
        environment="production" if PRODUCTION else "development",
        integrations=[
            DjangoIntegration(),
            RedisIntegration(),
            SqlalchemyIntegration(),
            *integrations,
        ],
        before_send=add_context,
    )

    # Ignore all of the loggers from django.security that are for user
    # errors; see https://docs.djangoproject.com/en/3.0/ref/exceptions/#suspiciousoperation
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
