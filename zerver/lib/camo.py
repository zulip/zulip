import hashlib
import hmac

from django.conf import settings


def generate_camo_url(url: str) -> str:
    encoded_url = url.encode()
    assert settings.CAMO_KEY is not None
    encoded_camo_key = settings.CAMO_KEY.encode()
    digest = hmac.new(encoded_camo_key, encoded_url, hashlib.sha1).hexdigest()
    return f"{digest}/{encoded_url.hex()}"


# Encodes the provided URL using the same algorithm used by the camo
# caching https image proxy
def get_camo_url(url: str) -> str:
    # Only encode the URL if Camo is enabled
    if settings.CAMO_URI == "":
        return url
    return f"{settings.CAMO_URI}{generate_camo_url(url)}"


def is_camo_url_valid(digest: str, url: str) -> bool:
    camo_url = generate_camo_url(url)
    camo_url_digest = camo_url.split("/")[0]
    return camo_url_digest == digest
