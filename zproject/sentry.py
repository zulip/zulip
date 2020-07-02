import sentry_sdk
from sentry_sdk.integrations import Integration
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from .config import PRODUCTION


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
    )
