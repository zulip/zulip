import json

import requests
from pyoembed import PyOembedException, oEmbed

from zerver.lib.url_preview.types import UrlEmbedData, UrlOEmbedData


def get_oembed_data(url: str, maxwidth: int = 640, maxheight: int = 480) -> UrlEmbedData | None:
    try:
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
