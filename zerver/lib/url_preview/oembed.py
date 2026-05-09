import json
import re
from typing import Any, cast
from urllib.parse import urlsplit, urlunsplit

import orjson
import requests

from zerver.lib.storage import static_path
from zerver.lib.url_preview.types import UrlEmbedData, UrlOEmbedData


def load_oembed_providers() -> list[dict[str, Any]]:
    # Load the list of the official providers from https://oembed.com/providers.json,
    # as maintained in the `oembed-providers` npm package.
    with open(static_path("generated/oembed-providers.json"), "rb") as f:
        return cast(list[dict[str, Any]], orjson.loads(f.read()))


def scheme_to_regex(scheme: str) -> str:
    # The provider list uses `*` as a wildcard, and a leading `://*.` to mean
    # "with or without a leading subdomain".  Schemes are written with a
    # single protocol, but oEmbed traffic may use either http or https, so
    # accept both.
    host_variants = [scheme]
    if "://*." in scheme:
        host_variants.append(scheme.replace("://*.", "://", 1))

    variants: list[str] = []
    for variant in host_variants:
        variants.append(variant)
        if variant.startswith("https://"):
            variants.append("http://" + variant[len("https://") :])
        elif variant.startswith("http://"):
            variants.append("https://" + variant[len("http://") :])

    patterns = []
    for variant in variants:
        pattern = re.escape(variant).replace(r"\*", ".*")
        if not variant.endswith("*"):
            pattern += "$"
        patterns.append(pattern)

    return "(?:" + "|".join(patterns) + ")"


def compile_oembed_providers(providers: list[dict[str, Any]]) -> dict[re.Pattern[str], str]:
    endpoint_map: dict[re.Pattern[str], str] = {}

    for provider in providers:
        for endpoint in provider.get("endpoints", []):
            schemes = endpoint.get("schemes", [])
            endpoint_url = endpoint.get("url")

            if not schemes or not endpoint_url:
                continue

            formatted_endpoint = endpoint_url.replace("{format}", "json")
            joined_patterns = "|".join(scheme_to_regex(s) for s in schemes)
            regex_str = f"(?:{joined_patterns})"

            compiled_regex = re.compile(regex_str)
            endpoint_map[compiled_regex] = formatted_endpoint

    return endpoint_map


OEMBED_PROVIDERS = load_oembed_providers()
OEMBED_ENDPOINT_MAP = compile_oembed_providers(OEMBED_PROVIDERS)


def get_oembed_endpoint(url: str) -> str | None:
    # Lowercase the scheme and host so that e.g. HTTPS://YOUTUBE.COM/... still
    # matches, but leave the path and query alone so that case-sensitive
    # tokens like literal `?v=` query keys in provider schemes are respected.
    parsed = urlsplit(url)
    normalized_url = urlunsplit(
        parsed._replace(scheme=parsed.scheme.lower(), netloc=parsed.netloc.lower())
    )
    for compiled_regex, endpoint_url in OEMBED_ENDPOINT_MAP.items():
        if compiled_regex.match(normalized_url):
            return endpoint_url
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

    params: dict[str, str | int] = {
        "url": url,
        "maxwidth": maxwidth,
        "maxheight": maxheight,
    }

    try:
        response = session.get(endpoint, params=params)
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
    # For unsupported oEmbed types (e.g. "link"),
    # return basic metadata to seed the merge.
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
