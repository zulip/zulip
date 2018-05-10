import re
from typing import Dict
from .base import BaseParser


class OpenGraphParser(BaseParser):
    def extract_data(self) -> Dict[str, str]:
        meta = self._soup.findAll('meta')
        content = {}
        for tag in meta:
            if tag.has_attr('property') and 'og:' in tag['property']:
                content[re.sub('og:', '', tag['property'])] = tag['content']
        return content
