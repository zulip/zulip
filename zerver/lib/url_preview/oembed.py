import json
import re
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlencode

import requests

from zerver.lib.url_preview.types import UrlEmbedData, UrlOEmbedData


def strip_cdata(html: str) -> str:
    # Work around a bug in SoundCloud's XML generation:
    # <html>&lt;![CDATA[&lt;iframe ...&gt;&lt;/iframe&gt;]]&gt;</html>
    if html.startswith("<![CDATA[") and html.endswith("]]>"):
        html = html[9:-3]
    return html


def load_oembed_providers() -> list[dict[str, Any]]:
    providers_path = Path(__file__).parent / "oembed_providers.json"
    with open(providers_path) as f:
        return cast(list[dict[str, Any]], json.load(f))


OEMBED_PROVIDERS = load_oembed_providers()


def scheme_to_regex(scheme: str) -> str:
    pattern = re.escape(scheme)
    pattern = pattern.replace(r"\*", ".*")
    return f"^{pattern}$"


def get_oembed_endpoint(url: str) -> str | None:
    for provider in OEMBED_PROVIDERS:
        for endpoint in provider.get("endpoints", []):
            for scheme in endpoint.get("schemes", []):
                regex = scheme_to_regex(scheme)
                if re.match(regex, url, re.IGNORECASE):
                    return endpoint.get("url")
    return None


def get_oembed_data(
    url: str,
    maxwidth: int = 640,
    maxheight: int = 480,
    session: requests.Session | None = None,
) -> UrlEmbedData | None:
    endpoint = get_oembed_endpoint(url)
    if endpoint is None:
        return None

    if session is None:
        from zerver.lib.url_preview.preview import PreviewSession

        session = PreviewSession()

    params = {
        "url": url,
        "format": "json",
        "maxwidth": maxwidth,
        "maxheight": maxheight,
    }

    try:
        request_url = f"{endpoint}?{urlencode(params)}"
        response = session.get(request_url)
        if not response.ok:
            return None
        data = response.json()
    except (requests.RequestException, json.JSONDecodeError):
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
