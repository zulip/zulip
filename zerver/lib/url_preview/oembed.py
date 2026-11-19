import json
import re
from functools import cache
from typing import Any, TypeAlias, cast
from urllib.parse import parse_qs, urlsplit

import orjson
import requests

from zerver.lib.storage import static_path
from zerver.lib.url_preview.types import UrlEmbedData, UrlOEmbedData

# Matches a single valid domain label (1–63 alphanumeric/hyphen characters,
# starting and ending with an alphanumeric character).
DOMAIN_LABEL_PATTERN = r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"

# Keep path wildcards permissive (`.*` rather than `[^/]*`) because some
# provider schemes use a trailing `*` to match across path segments (e.g.
# `https://*.youtube.com/shorts*` matching `/shorts/<video_id>`).
PATH_WILDCARD_PATTERN = r".*"

OembedEndpointMap: TypeAlias = dict[re.Pattern[str], list[tuple[re.Pattern[str], str]]]


def load_oembed_providers() -> list[dict[str, Any]]:
    # Load the list of the official providers from https://oembed.com/providers.json,
    # as maintained in the `oembed-providers` npm package.
    with open(static_path("generated/oembed-providers.json"), "rb") as f:
        return cast(list[dict[str, Any]], orjson.loads(f.read()))


def host_to_regex(host: str) -> str:
    # A leading `*.` in an oEmbed scheme matches an optional subdomain label
    # (e.g. `*.youtube.com` matches both `www.youtube.com` and `youtube.com`).
    if host.startswith("*."):
        return rf"(?:{DOMAIN_LABEL_PATTERN}\.)?" + re.escape(host[2:]).replace(
            r"\*", DOMAIN_LABEL_PATTERN
        )
    return re.escape(host).replace(r"\*", DOMAIN_LABEL_PATTERN)


def path_to_regex(path: str) -> str:
    return re.escape(path).replace(r"\*", PATH_WILDCARD_PATTERN)


def compile_oembed_providers(providers: list[dict[str, Any]]) -> OembedEndpointMap:
    # Group patterns in two stages: host pattern -> {endpoint_url -> path patterns}.
    # Scheme protocols (http/https) are validated at match time instead of
    # duplicating regex variants here.
    grouped: dict[str, dict[str, list[str]]] = {}

    for provider in providers:
        for endpoint in provider.get("endpoints", []):
            schemes = endpoint.get("schemes", [])
            endpoint_url = endpoint.get("url")

            if not schemes or not endpoint_url:
                continue

            formatted_endpoint = endpoint_url.replace("{format}", "json")

            for scheme in schemes:
                if not scheme.lower().startswith(("http://", "https://")):
                    continue

                without_scheme = scheme.split("://", 1)[1]
                host, sep, rest = without_scheme.partition("/")
                if not host:
                    continue

                host_pattern = host_to_regex(host.lower())
                path_pattern = path_to_regex(sep + rest)

                endpoint_paths = grouped.setdefault(host_pattern, {}).setdefault(
                    formatted_endpoint, []
                )
                if path_pattern not in endpoint_paths:
                    endpoint_paths.append(path_pattern)

    return {
        re.compile(host_pattern, re.IGNORECASE): [
            (re.compile("|".join(path_patterns)), endpoint_url)
            for endpoint_url, path_patterns in endpoints.items()
        ]
        for host_pattern, endpoints in grouped.items()
    }


@cache
def get_oembed_endpoint_map() -> OembedEndpointMap:
    return compile_oembed_providers(load_oembed_providers())


def get_oembed_endpoint(url: str) -> str | None:
    try:
        parsed = urlsplit(url)
    except ValueError:
        return None

    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None

    path_and_query = parsed.path
    if parsed.query:
        path_and_query += f"?{parsed.query}"
    if parsed.fragment:
        path_and_query += f"#{parsed.fragment}"

    for host_regex, path_matchers in get_oembed_endpoint_map().items():
        if host_regex.fullmatch(parsed.netloc):
            for path_regex, endpoint_url in path_matchers:
                if path_regex.fullmatch(path_and_query):
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
    if "format" not in parse_qs(urlsplit(endpoint).query):
        params["format"] = "json"

    try:
        response = session.get(endpoint, params=params)
        if not response.ok:
            return None
        data = response.json()
    except (requests.RequestException, json.JSONDecodeError):
        return None

    if not isinstance(data, dict):
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
