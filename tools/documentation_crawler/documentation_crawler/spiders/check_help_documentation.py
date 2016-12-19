#!/usr/bin/env python
from __future__ import print_function

from .common.spiders import BaseDocumentationSpider


class HelpDocumentationSpider(BaseDocumentationSpider):
    name = "help_documentation_crawler"
    start_urls = ['http://localhost:9981/help']
    deny_domains = [] # type: List[str]
    deny = ['/privacy']

    def _is_external_url(self, url):
        # type: (str) -> bool
        is_external = url.startswith('http') and 'localhost:9981/help' not in url
        return is_external or self._has_extension(url)
