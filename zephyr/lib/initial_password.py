from django.conf import settings

import hashlib
import base64

def initial_password(email):

    """Given an email address, returns the initial password for that account, as
       created by populate_db."""

    digest = hashlib.sha256(settings.INITIAL_PASSWORD_SALT + email).digest()
    return base64.b64encode(digest)[:16]

def initial_api_key(email):

    """Given an email address, returns the initial API key for that account"""

    digest = hashlib.sha256(settings.INITIAL_API_KEY_SALT + email).digest()
    return base64.b16encode(digest)[:32].lower()
