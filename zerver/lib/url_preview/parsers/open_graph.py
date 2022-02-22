from typing import Dict
from urllib.parse import urlparse

from .base import BaseParser


class OpenGraphParser(BaseParser):
    allowed_og_properties = {
        "og:title",
        "og:description",
        "og:image",
    }

    def extract_data(self) -> Dict[str, str]:
        meta = self._soup.findAll("meta")
        result = {}
        for tag in meta:
            if not tag.has_attr("property"):
                continue
            if tag["property"] not in self.allowed_og_properties:
                continue

            og_property_name = tag["property"][len("og:") :]
            if not tag.has_attr("content"):
                continue

            if og_property_name == "image":
                try:
                    # We use urlparse and not URLValidator because we
                    # need to support relative URLs.
                    urlparse(tag["content"])
                except ValueError:
                    continue

            result[og_property_name] = tag["content"]

        return result
