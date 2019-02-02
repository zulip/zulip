import logging
import re
import scrapy

from scrapy import Request
from scrapy.linkextractors import IGNORED_EXTENSIONS
from scrapy.linkextractors.lxmlhtml import LxmlLinkExtractor
from scrapy.utils.url import url_has_any_extension

from typing import Any, Generator, List, Optional

EXCLUDED_URLS = [
    # Google calendar returns 404s on HEAD requests unconditionally
    'https://calendar.google.com/calendar/embed?src=ktiduof4eoh47lmgcl2qunnc0o@group.calendar.google.com',
    # Returns 409 errors to HEAD requests frequently
    'https://medium.freecodecamp.org/',
    # Returns 404 to HEAD requests unconditionally
    'https://www.git-tower.com/blog/command-line-cheat-sheet/',
    # Requires authentication
    'https://circleci.com/gh/zulip/zulip',
    'https://circleci.com/gh/zulip/zulip/16617',
    # 500s because the site is semi-down
    'http://citizencodeofconduct.org/',
]


class BaseDocumentationSpider(scrapy.Spider):
    name = None  # type: Optional[str]
    # Exclude domain address.
    deny_domains = []  # type: List[str]
    start_urls = []  # type: List[str]
    deny = []  # type: List[str]
    file_extensions = ['.' + ext for ext in IGNORED_EXTENSIONS]  # type: List[str]
    tags = ('a', 'area', 'img')
    attrs = ('href', 'src')

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.has_error = False
        self.skip_external = kwargs.get('skip_external', None)

    def _set_error_state(self) -> None:
        self.has_error = True

    def _has_extension(self, url: str) -> bool:
        return url_has_any_extension(url, self.file_extensions)

    def _is_external_url(self, url: str) -> bool:
        return url.startswith('http') or self._has_extension(url)

    def check_existing(self, response: Any) -> None:
        self.log(response)

    def _is_external_link(self, url: str) -> bool:
        if "zulip.readthedocs" in url or "zulipchat.com" in url or "zulip.org" in url:
            # We want CI to check any links to Zulip sites.
            return False
        if (len(url) > 4 and url[:4] == "file") or ("localhost" in url):
            # We also want CI to check any links to built documentation.
            return False
        if 'github.com/zulip' in url:
            # Finally, links to our own GitHub organization should always work.
            return False
        return True

    def check_permalink(self, response: Any) -> None:
        self.log(response)
        xpath_template = "//*[@id='{permalink}' or @name='{permalink}']"
        m = re.match(r".+\#(?P<permalink>.*)$", response.request.url)  # Get anchor value.
        if not m:
            return
        permalink = m.group('permalink')
        # Check permalink existing on response page.
        if not response.selector.xpath(xpath_template.format(permalink=permalink)):
            self._set_error_state()
            raise Exception(
                "Permalink #{} is not found on page {}".format(permalink, response.request.url))

    def parse(self, response: Any) -> Generator[Request, None, None]:
        self.log(response)
        for link in LxmlLinkExtractor(deny_domains=self.deny_domains, deny_extensions=['doc'],
                                      tags=self.tags, attrs=self.attrs, deny=self.deny,
                                      canonicalize=False).extract_links(response):
            callback = self.parse  # type: Any
            dont_filter = False
            method = 'GET'
            if self._is_external_url(link.url):
                callback = self.check_existing
                method = 'HEAD'
            elif '#' in link.url:
                dont_filter = True
                callback = self.check_permalink
            if self.skip_external:
                if (self._is_external_link(link.url)):
                    continue
            yield Request(link.url, method=method, callback=callback, dont_filter=dont_filter,
                          errback=self.error_callback)

    def retry_request_with_get(self, request: Request) -> Generator[Request, None, None]:
        request.method = 'GET'
        request.dont_filter = True
        yield request

    def exclude_error(self, url: str) -> bool:
        if url in EXCLUDED_URLS:
            return True
        return False

    def error_callback(self, failure: Any) -> Optional[Generator[Any, None, None]]:
        if hasattr(failure.value, 'response') and failure.value.response:
            response = failure.value.response
            if self.exclude_error(response.url):
                return None
            if response.status == 404:
                self._set_error_state()
                raise Exception('Page not found: {}'.format(response))
            if response.status == 405 and response.request.method == 'HEAD':
                # Method 'HEAD' not allowed, repeat request with 'GET'
                return self.retry_request_with_get(response.request)
            self.log("Error! Please check link: {}".format(response), logging.ERROR)
        elif isinstance(failure.type, IOError):
            self._set_error_state()
        else:
            raise Exception(failure.value)
        return None
