import re
from typing import Any, Optional, Dict
from typing.re import Match
import requests
from zerver.lib.cache import cache_with_key, get_cache_with_key, preview_url_cache_key
from zerver.lib.url_preview.oembed import get_oembed_data
from zerver.lib.url_preview.parsers import OpenGraphParser, GenericParser
from django.utils.encoding import smart_text


CACHE_NAME = "database"
# Based on django.core.validators.URLValidator, with ftp support removed.
link_regex = re.compile(
    r'^(?:http)s?://'  # http:// or https://
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
    r'(?::\d+)?'  # optional port
    r'(?:/?|[/?]\S+)$', re.IGNORECASE)


def is_link(url: str) -> Match[str]:
    return link_regex.match(smart_text(url))


@cache_with_key(preview_url_cache_key, cache_name=CACHE_NAME, with_statsd_key="urlpreview_data")
def get_link_embed_data(url: str,
                        maxwidth: Optional[int]=640,
                        maxheight: Optional[int]=480) -> Optional[Dict[str, Any]]:
    if not is_link(url):
        return None
    # Fetch information from URL.
    # We are using three sources in next order:
    # 1. OEmbed
    # 2. Open Graph
    # 3. Meta tags
    try:
        data = get_oembed_data(url, maxwidth=maxwidth, maxheight=maxheight)
    except requests.exceptions.RequestException:
        # This is what happens if the target URL cannot be fetched; in
        # that case, there's nothing to do here, and this URL has no
        # open graph data.
        return None
    data = data or {}
    response = requests.get(url)
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
