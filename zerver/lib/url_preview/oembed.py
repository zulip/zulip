import json
import re
from typing import Any
from urllib.parse import urlencode

import requests
from django.conf import settings

from version import ZULIP_VERSION
from zerver.lib.outgoing_http import OutgoingSession
from zerver.lib.url_preview.types import UrlEmbedData, UrlOEmbedData

# User-Agent for oEmbed requests
OEMBED_USER_AGENT = (
    f"Mozilla/5.0 (compatible; ZulipURLPreview/{ZULIP_VERSION}; +{settings.ROOT_DOMAIN_URI})"
)
OEMBED_TIMEOUT = 15


class OEmbedSession(OutgoingSession):
    """Session for oEmbed requests using Zulip's outgoing HTTP infrastructure."""

    def __init__(self) -> None:
        super().__init__(
            role="preview",
            timeout=OEMBED_TIMEOUT,
            headers={"User-Agent": OEMBED_USER_AGENT},
        )


# Provider registry with hardcoded oEmbed endpoints
# This avoids autodiscovery which gets blocked by bot detection
OEMBED_PROVIDERS: dict[str, str] = {
    # YouTube
    r"https?://(?:www\.)?youtube\.com/watch": "https://www.youtube.com/oembed",
    r"https?://(?:www\.)?youtube\.com/shorts/": "https://www.youtube.com/oembed",
    r"https?://youtu\.be/": "https://www.youtube.com/oembed",
    # Vimeo
    r"https?://(?:www\.)?vimeo\.com/": "https://vimeo.com/api/oembed.json",
    # Twitter/X
    r"https?://(?:www\.)?twitter\.com/.*/status/": "https://publish.twitter.com/oembed",
    r"https?://(?:www\.)?x\.com/.*/status/": "https://publish.twitter.com/oembed",
    # Spotify
    r"https?://open\.spotify\.com/": "https://open.spotify.com/oembed",
    # SoundCloud
    r"https?://soundcloud\.com/": "https://soundcloud.com/oembed",
    # Flickr
    r"https?://(?:www\.)?flickr\.com/photos/": "https://www.flickr.com/services/oembed/",
    # Instagram
    r"https?://(?:www\.)?instagram\.com/p/": "https://graph.facebook.com/v10.0/instagram_oembed",
    # TikTok
    r"https?://(?:www\.)?tiktok\.com/": "https://www.tiktok.com/oembed",
    # Giphy
    r"https?://(?:www\.)?giphy\.com/gifs/": "https://giphy.com/services/oembed",
    r"https?://gph\.is/": "https://giphy.com/services/oembed",
    # Reddit
    r"https?://(?:www\.)?reddit\.com/r/.*/comments/": "https://www.reddit.com/oembed",
    # Imgur
    r"https?://(?:www\.)?imgur\.com/": "https://api.imgur.com/oembed",
}


def get_oembed_endpoint(url: str) -> str | None:
    """Find the oEmbed endpoint for a given URL."""
    for pattern, endpoint in OEMBED_PROVIDERS.items():
        if re.match(pattern, url, re.IGNORECASE):
            return endpoint
    return None


def fetch_oembed_data(
    url: str, endpoint: str, maxwidth: int = 640, maxheight: int = 480
) -> dict[str, Any] | None:
    """Fetch oEmbed data using Zulip's PreviewSession."""
    params = {
        "url": url,
        "format": "json",
        "maxwidth": maxwidth,
        "maxheight": maxheight,
    }
    oembed_url = f"{endpoint}?{urlencode(params)}"

    try:
        response = OEmbedSession().get(oembed_url)
        if response.ok:
            data = response.json()
            # Ensure response is a dict (valid oEmbed response)
            if isinstance(data, dict):
                return data
    except (requests.exceptions.RequestException, json.decoder.JSONDecodeError):
        pass
    return None


def get_oembed_data(url: str, maxwidth: int = 640, maxheight: int = 480) -> UrlEmbedData | None:
    """Get oEmbed data for a URL using hardcoded provider endpoints."""
    endpoint = get_oembed_endpoint(url)
    if endpoint is None:
        return None

    data = fetch_oembed_data(url, endpoint, maxwidth, maxheight)
    if data is None:
        return None

    oembed_resource_type = data.get("type", "")
    image = data.get("url", data.get("image"))
    thumbnail = data.get("thumbnail_url")
    html = data.get("html", "")

    if oembed_resource_type == "photo" and image:
        return UrlOEmbedData(
            image=image,
            type="photo",
            title=data.get("title"),
            description=data.get("description"),
        )

    if oembed_resource_type == "video" and html and thumbnail:
        return UrlOEmbedData(
            image=thumbnail,
            type="video",
            html=strip_cdata(html),
            title=data.get("title"),
            description=data.get("description"),
        )

    # Otherwise, use the title/description as the basis for our other parsers
    return UrlEmbedData(
        title=data.get("title"),
        description=data.get("description"),
    )


def strip_cdata(html: str) -> str:
    # Work around a bug in SoundCloud's XML generation:
    # <html>&lt;![CDATA[&lt;iframe ...&gt;&lt;/iframe&gt;]]&gt;</html>
    if html.startswith("<![CDATA[") and html.endswith("]]>"):
        html = html[9:-3]
    return html
