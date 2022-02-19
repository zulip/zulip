from typing import Dict, Optional
from urllib.parse import urlparse

from bs4.element import Tag

from zerver.lib.url_preview.parsers.base import BaseParser


class GenericParser(BaseParser):
    def extract_data(self) -> Dict[str, Optional[str]]:
        return {
            "title": self._get_title(),
            "description": self._get_description(),
            "image": self._get_image(),
        }

    def _get_title(self) -> Optional[str]:
        soup = self._soup
        if soup.title and soup.title.text != "":
            return soup.title.text
        if soup.h1 and soup.h1.text != "":
            return soup.h1.text
        return None

    def _get_description(self) -> Optional[str]:
        soup = self._soup
        meta_description = soup.find("meta", attrs={"name": "description"})
        if isinstance(meta_description, Tag) and meta_description.get("content", "") != "":
            assert isinstance(meta_description["content"], str)
            return meta_description["content"]
        first_h1 = soup.find("h1")
        if first_h1:
            first_p = first_h1.find_next("p")
            if first_p and first_p.text != "":
                return first_p.text
        first_p = soup.find("p")
        if first_p and first_p.text != "":
            return first_p.text
        return None

    def _get_image(self) -> Optional[str]:
        """
        Finding a first image after the h1 header.
        Presumably it will be the main image.
        """
        soup = self._soup
        first_h1 = soup.find("h1")
        if first_h1:
            first_image = first_h1.find_next_sibling("img", src=True)
            if isinstance(first_image, Tag) and first_image["src"] != "":
                assert isinstance(first_image["src"], str)
                try:
                    # We use urlparse and not URLValidator because we
                    # need to support relative URLs.
                    urlparse(first_image["src"])
                except ValueError:
                    return None
                return first_image["src"]
        return None
