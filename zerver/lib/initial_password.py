import base64
import hashlib

from django.conf import settings


def initial_password(email: str) -> str | None:
    """Given an email address, returns the initial password for that account, as
    created by populate_db."""

    if settings.INITIAL_PASSWORD_SALT is not None:
        # We check settings.DEVELOPMENT, not settings.PRODUCTION,
        # because some tests mock settings.PRODUCTION and then use
        # self.login, which will call this function.
        assert settings.DEVELOPMENT, "initial_password_salt should not be set in production."
        encoded_key = (settings.INITIAL_PASSWORD_SALT + email).encode()
        digest = hashlib.sha256(encoded_key).digest()
        return base64.b64encode(digest)[:16].decode()
    else:
        # None as a password for a user tells Django to set an unusable password
        return None
