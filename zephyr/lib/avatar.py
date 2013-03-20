import hashlib
from utils import make_safe_digest

def gravatar_hash(email):
    """Compute the Gravatar hash for an email address."""
    # Non-ASCII characters aren't permitted by the currently active e-mail
    # RFCs. However, the IETF has published https://tools.ietf.org/html/rfc4952,
    # outlining internationalization of email addresses, and regardless if we
    # typo an address or someone manages to give us a non-ASCII address, let's
    # not error out on it.
    return make_safe_digest(email.lower(), hashlib.md5)
