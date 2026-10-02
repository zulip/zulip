import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import requests
from django.conf import settings
from pyoembed import PyOembedException, oEmbed

from version import ZULIP_VERSION
from zerver.lib.url_preview.types import UrlEmbedData, UrlOEmbedData

# Use Chrome User-Agent, since some sites refuse to work on old browsers.
ZULIP_URL_PREVIEW_USER_AGENT = (
    f"Mozilla/5.0 (compatible; ZulipURLPreview/{ZULIP_VERSION}; +{settings.ROOT_DOMAIN_URI})"
)
HEADERS = {"User-Agent": ZULIP_URL_PREVIEW_USER_AGENT}
TIMEOUT = 15


@contextmanager
def _patched_oembed_requests() -> Iterator[None]:
    original_get = requests.get

    def wrapped_get(*args: Any, **kwargs: Any) -> Any:
        kwargs.setdefault("headers", HEADERS)
        kwargs.setdefault("timeout", TIMEOUT)
        return original_get(*args, **kwargs)

    requests.get = wrapped_get
    try:
        yield
    finally:
        requests.get = original_get


def get_oembed_data(url: str, maxwidth: int = 640, maxheight: int = 480) -> UrlEmbedData | None:
    # pyoembed makes its requests directly, not through OutgoingSession,
    # but they still go through Smokescreen: requests lib honors the
    # HTTP_proxy/HTTPS_proxy variables we set in every process's environment.
    try:
        with _patched_oembed_requests():
            data = oEmbed(url, maxwidth=maxwidth, maxheight=maxheight)
    except (PyOembedException, json.decoder.JSONDecodeError, requests.exceptions.ConnectionError):
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

    # Otherwise, use the title/description from pyembed as the basis
    # for our other parsers
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
