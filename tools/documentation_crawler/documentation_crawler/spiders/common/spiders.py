import json
import re
import scrapy

from scrapy.http import Request, Response
from scrapy.linkextractors import IGNORED_EXTENSIONS
from scrapy.linkextractors.lxmlhtml import LxmlLinkExtractor
from scrapy.spidermiddlewares.httperror import HttpError
from scrapy.utils.url import url_has_any_extension
from twisted.python.failure import Failure

from typing import Callable, Iterable, List, Optional, Union

EXCLUDED_URLS = [
    # Google calendar returns 404s on HEAD requests unconditionally
    'https://calendar.google.com/calendar/embed?src=ktiduof4eoh47lmgcl2qunnc0o@group.calendar.google.com',
    # Returns 409 errors to HEAD requests frequently
    'https://medium.freecodecamp.org/',
    # Returns 404 to HEAD requests unconditionally
    'https://www.git-tower.com/blog/command-line-cheat-sheet/',
    'https://marketplace.visualstudio.com/items?itemName=rafaelmaiolla.remote-vscode',
    # Requires authentication
    'https://circleci.com/gh/zulip/zulip/tree/master',
    'https://circleci.com/gh/zulip/zulip/16617',
    'https://www.linkedin.com/company/zulip-project',
    # Returns 403 errors to HEAD requests
    'https://giphy.com',
    'https://giphy.com/apps/giphycapture',
    'https://www.udemy.com/course/the-complete-react-native-and-redux-course/',
]

VNU_IGNORE = re.compile(r'|'.join([
    # Real errors that should be fixed.
    r'Duplicate ID “[^”]*”\.',
    r'The first occurrence of ID “[^”]*” was here\.',
    r'Attribute “markdown” not allowed on element “div” at this point\.',
    r'No “p” element in scope but a “p” end tag seen\.',
    r'Element “div” not allowed as child of element “ul” in this context\. '
    + r'\(Suppressing further errors from this subtree\.\)',

    # Warnings that are probably less important.
    r'The “type” attribute is unnecessary for JavaScript resources\.',
]))


class BaseDocumentationSpider(scrapy.Spider):
    name = None  # type: Optional[str]
    # Exclude domain address.
    deny_domains = []  # type: List[str]
    start_urls = []  # type: List[str]
    deny = []  # type: List[str]
    file_extensions = ['.' + ext for ext in IGNORED_EXTENSIONS]  # type: List[str]
    tags = ('a', 'area', 'img')
    attrs = ('href', 'src')

    def _has_extension(self, url: str) -> bool:
        return url_has_any_extension(url, self.file_extensions)

    def _is_external_url(self, url: str) -> bool:
        return url.startswith('http') or self._has_extension(url)

    def check_existing(self, response: Response) -> None:
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

    def check_fragment(self, response: Response) -> None:
        self.log(response)
        xpath_template = "//*[@id='{fragment}' or @name='{fragment}']"
        m = re.match(r".+\#(?P<fragment>.*)$", response.request.url)  # Get fragment value.
        if not m:
            return
        fragment = m.group('fragment')
        # Check fragment existing on response page.
        if not response.selector.xpath(xpath_template.format(fragment=fragment)):
            self.logger.error(
                "Fragment #%s is not found on page %s", fragment, response.request.url)

    def _vnu_callback(self, url: str) -> Callable[[Response], None]:
        def callback(response: Response) -> None:
            vnu_out = json.loads(response.text)
            for message in vnu_out['messages']:
                if not VNU_IGNORE.fullmatch(message['message']):
                    self.logger.error(
                        '"%s":%d.%d-%d.%d: %s: %s',
                        url,
                        message.get('firstLine', message['lastLine']),
                        message.get('firstColumn', message['lastColumn']),
                        message['lastLine'],
                        message['lastColumn'],
                        message['type'],
                        message['message'],
                    )

        return callback

    def _make_requests(self, url: str) -> Iterable[Request]:
        callback = self.parse  # type: Callable[[Response], Optional[Iterable[Request]]]
        dont_filter = False
        method = 'GET'
        if self._is_external_url(url):
            callback = self.check_existing
            method = 'HEAD'
        elif '#' in url:
            dont_filter = True
            callback = self.check_fragment
        if getattr(self, 'skip_external', False) and self._is_external_link(url):
            return
        yield Request(url, method=method, callback=callback, dont_filter=dont_filter,
                      errback=self.error_callback)

    def start_requests(self) -> Iterable[Request]:
        for url in self.start_urls:
            yield from self._make_requests(url)

    def parse(self, response: Response) -> Iterable[Request]:
        self.log(response)

        if getattr(self, 'validate_html', False):
            yield Request(
                'http://127.0.0.1:9988/?out=json',
                method='POST',
                headers={'Content-Type': response.headers['Content-Type']},
                body=response.body,
                callback=self._vnu_callback(response.url),
                errback=self.error_callback,
            )

        for link in LxmlLinkExtractor(deny_domains=self.deny_domains, deny_extensions=['doc'],
                                      tags=self.tags, attrs=self.attrs, deny=self.deny,
                                      canonicalize=False).extract_links(response):
            yield from self._make_requests(link.url)

    def retry_request_with_get(self, request: Request) -> Iterable[Request]:
        request.method = 'GET'
        request.dont_filter = True
        yield request

    def exclude_error(self, url: str) -> bool:
        return url in EXCLUDED_URLS

    def error_callback(self, failure: Failure) -> Optional[Union[Failure, Iterable[Request]]]:
        if failure.check(HttpError):
            response = failure.value.response
            if self.exclude_error(response.url):
                return None
            if response.status == 405 and response.request.method == 'HEAD':
                # Method 'HEAD' not allowed, repeat request with 'GET'
                return self.retry_request_with_get(response.request)
            self.logger.error("Please check link: %s", response)

        return failure
