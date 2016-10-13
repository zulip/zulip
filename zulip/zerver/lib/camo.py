from django.conf import settings
import codecs
import hashlib
import hmac

from six import text_type

# Encodes the provided URL using the same algorithm used by the camo
# caching https image proxy
def get_camo_url(url):
    # type: (text_type) -> text_type
    # Only encode the url if Camo is enabled
    if settings.CAMO_URI == '':
        return url
    encoded_url = url.encode("utf-8")
    encoded_camo_key = settings.CAMO_KEY.encode("utf-8")
    digest = hmac.new(encoded_camo_key, encoded_url, hashlib.sha1).hexdigest()
    hex_encoded_url = codecs.encode(encoded_url, "hex") # type: ignore # https://github.com/python/typeshed/issues/300
    return "%s%s/%s" % (settings.CAMO_URI, digest, hex_encoded_url.decode("utf-8"))
