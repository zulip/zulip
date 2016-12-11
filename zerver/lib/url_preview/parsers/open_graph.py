from __future__ import absolute_import
import re
from six import text_type
from typing import Dict
from .base import BaseParser


class OpenGraphParser(BaseParser):
    def extract_data(self):
        # type: () -> Dict[str, text_type]
        meta = self._soup.findAll('meta')
        content = {}
        for tag in meta:
            if tag.has_attr('property') and 'og:' in tag['property']:
                content[re.sub('og:', '', tag['property'])] = tag['content']
        return content
