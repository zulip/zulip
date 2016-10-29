#!/usr/bin/env python
from __future__ import print_function

import logging
import os
import pathlib2
import re
import scrapy

from scrapy import Request
from scrapy.linkextractors import IGNORED_EXTENSIONS
from scrapy.linkextractors.lxmlhtml import LxmlLinkExtractor
from scrapy.utils.url import url_has_any_extension

from typing import Any, Callable, Generator, List, Optional


def get_start_url():
    # type: () -> List[str]
    # Get index html file as start url and convert it to file uri
    dir_path = os.path.dirname(os.path.realpath(__file__))
    start_file = os.path.join(dir_path, os.path.join(*[os.pardir] * 4),
                              "docs/_build/html/index.html")
    return [
        pathlib2.Path(os.path.abspath(start_file)).as_uri()
    ]


class DocumentationSpider(scrapy.Spider):
    name = "documentation_crawler"
    deny_domains = ['localhost:9991']  # Exclude domain address.
    start_urls = get_start_url()
    file_extensions = ['.' + ext for ext in IGNORED_EXTENSIONS]

    def _has_extension(self, url):
        # type: (str) -> bool
        return url_has_any_extension(url, self.file_extensions)

    def check_existing(self, response):
        # type: (Any) -> None
        self.log(response)

    def check_permalink(self, response):
        # type: (Any) -> None
        self.log(response)
        xpath_template = "//*[@id='{permalink}' or @name='{permalink}']"
        m = re.match(r".+\#(?P<permalink>.*)$", response.request.url)  # Get anchor value.
        if not m:
            return
        permalink = m.group('permalink')
        # Check permalink existing on response page.
        if not response.selector.xpath(xpath_template.format(permalink=permalink)):
            raise Exception(
                "Permalink #{} is not found on page {}".format(permalink, response.request.url))

    def parse(self, response):
        # type: (Any) -> Generator[Request, None, None]
        self.log(response)
        for link in LxmlLinkExtractor(deny_domains=self.deny_domains, deny_extensions=[],
                                      deny='\_sources\/.*\.txt',
                                      canonicalize=False).extract_links(response):
            callback = self.parse  # type: Any
            dont_filter = False
            method = 'GET'
            if link.url.startswith('http') or self._has_extension(link.url):
                callback = self.check_existing
                method = 'HEAD'
            elif '#' in link.url:
                dont_filter = True
                callback = self.check_permalink
            yield Request(link.url, method=method, callback=callback, dont_filter=dont_filter,
                          errback=self.error_callback)

    def retry_request_with_get(self, request):
        # type: (Request) -> Generator[Request, None, None]
        request.method = 'GET'
        request.dont_filter = True
        yield request

    def error_callback(self, failure):
        # type: (Any) -> Optional[Generator[Any, None, None]]
        if hasattr(failure.value, 'response') and failure.value.response:
            response = failure.value.response
            if response.status == 404:
                raise Exception('Page not found: {}'.format(response))
            if response.status == 405 and response.request.method == 'HEAD':
                # Method 'HEAD' not allowed, repeat request with 'GET'
                return self.retry_request_with_get(response.request)
            self.log("Error! Please check link: {}".format(response), logging.ERROR)
        else:
            raise Exception(failure.value)
