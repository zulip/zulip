import re
import requests

from django.conf import settings
from django.utils.encoding import smart_text
import magic
from typing import Any, Optional, Dict, Callable
from typing.re import Match

from version import ZULIP_VERSION
from zerver.lib.cache import cache_with_key, get_cache_with_key, preview_url_cache_key
from zerver.lib.url_preview.oembed import get_oembed_data
from zerver.lib.url_preview.parsers import OpenGraphParser, GenericParser

# FIXME: Should we use a database cache or a memcached in production? What if
# opengraph data is changed for a site?
# Use an in-memory cache for development, to make it easy to develop this code
CACHE_NAME = "database" if not settings.DEVELOPMENT else "in-memory"
# Based on django.core.validators.URLValidator, with ftp support removed.
link_regex = re.compile(
    r'^(?:http)s?://'  # http:// or https://
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
    r'(?::\d+)?'  # optional port
    r'(?:/?|[/?]\S+)$', re.IGNORECASE)
# FIXME: This header and timeout are not used by pyoembed, when trying to autodiscover!
# Set a custom user agent, since some sites block us with the default requests header
HEADERS = {'User-Agent': 'Zulip URL preview/%s' % (ZULIP_VERSION,)}
TIMEOUT = 15


def is_link(url: str) -> Match[str]:
    return link_regex.match(smart_text(url))

def guess_mimetype_from_content(response: requests.Response) -> str:
    mime_magic = magic.Magic(mime=True)
    try:
        content = next(response.iter_content(1000))
    except StopIteration:
        content = ''
    return mime_magic.from_buffer(content)

def valid_content_type(url: str) -> bool:
    try:
        response = requests.get(url, stream=True, headers=HEADERS, timeout=TIMEOUT)
    except requests.RequestException:
        return False

    if not response.ok:
        return False

    content_type = response.headers.get('content-type')
    # Be accommodating of bad servers: assume content may be html if no content-type header
    if not content_type or content_type.startswith('text/html'):
        # Verify that the content is actually HTML if the server claims it is
        content_type = guess_mimetype_from_content(response)
    return content_type.startswith('text/html')

def catch_network_errors(func: Callable[..., Any]) -> Callable[..., Any]:
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except requests.exceptions.RequestException:
            pass
    return wrapper

@catch_network_errors
@cache_with_key(preview_url_cache_key, cache_name=CACHE_NAME, with_statsd_key="urlpreview_data")
def get_link_embed_data(url: str,
                        maxwidth: Optional[int]=640,
                        maxheight: Optional[int]=480) -> Optional[Dict[str, Any]]:
    if not is_link(url):
        return None

    if not valid_content_type(url):
        return None

    # We are using two different mechanisms to get the embed data
    # 1. Use OEmbed data, if found, for photo and video "type" sites
    # 2. Otherwise, use a combination of Open Graph tags and Meta tags
    data = get_oembed_data(url, maxwidth=maxwidth, maxheight=maxheight) or {}
    if data.get('oembed'):
        return data
    response = requests.get(url, stream=True, headers=HEADERS, timeout=TIMEOUT)
    if response.ok:
        og_data = OpenGraphParser(response.text).extract_data()
        if og_data:
            data.update(og_data)
        generic_data = GenericParser(response.text).extract_data() or {}
        for key in ['title', 'description', 'image']:
            if not data.get(key) and generic_data.get(key):
                data[key] = generic_data[key]
    return data

@get_cache_with_key(preview_url_cache_key, cache_name=CACHE_NAME)
def link_embed_data_from_cache(url: str, maxwidth: Optional[int]=640, maxheight: Optional[int]=480) -> Any:
    return
