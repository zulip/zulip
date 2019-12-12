from typing import Dict
from .base import BaseParser


class OpenGraphParser(BaseParser):
    allowed_og_properties = {
        'og:title',
        'og:description',
        'og:image',
    }

    def extract_data(self) -> Dict[str, str]:
        meta = self._soup.findAll('meta')
        result = {}
        for tag in meta:
            if not tag.has_attr('property'):
                continue
            if tag['property'] not in self.allowed_og_properties:
                continue

            og_property_name = tag['property'][len('og:'):]
            if not tag.has_attr('content'):
                continue

            result[og_property_name] = tag['content']

        return result
