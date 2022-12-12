from urllib.parse import urlparse

from zerver.lib.url_preview.types import UrlEmbedData

from .base import BaseParser


class TwitterCardParser(BaseParser):
    def extract_data(self) -> UrlEmbedData:
        meta = self._soup.findAll("meta")

        data = UrlEmbedData()

        for tag in meta:
            if not tag.has_attr("name"):
                continue
            if not tag.has_attr("content"):
                continue

            if tag["name"] == "twitter:title":
                data.title = tag["content"]
            elif tag["name"] == "twitter:description":
                data.description = tag["content"]
            elif tag["name"] == "twitter:image":
                try:
                    # We use urlparse and not URLValidator because we
                    # need to support relative URLs.
                    urlparse(tag["content"])
                except ValueError:
                    continue
                data.image = tag["content"]

        return data
