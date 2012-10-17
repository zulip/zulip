import hashlib

def gravatar_hash(email):
    """Compute the Gravatar hash for an email address."""
    return hashlib.md5(email.lower()).hexdigest()
