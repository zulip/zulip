#!/usr/bin/env python
from __future__ import print_function

import os

from posixpath import basename
from six.moves.urllib.parse import urlparse

from .common.spiders import BaseDocumentationSpider

from typing import Any, List, Set


def get_help_images_dir(help_images_path):
    # type: (str) -> str
    # Get index html file as start url and convert it to file uri
    dir_path = os.path.dirname(os.path.realpath(__file__))
    target_path = os.path.join(dir_path, os.path.join(*[os.pardir] * 4), help_images_path)
    return os.path.realpath(target_path)


class HelpDocumentationSpider(BaseDocumentationSpider):
    name = "help_documentation_crawler"
    start_urls = ['http://localhost:9981/help']
    deny_domains = []  # type: List[str]
    deny = ['/privacy']
    help_images_path = "static/images/help"
    help_images_static_dir = get_help_images_dir(help_images_path)

    def __init__(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        super(HelpDocumentationSpider, self).__init__(*args, **kwargs)
        self.static_images = set()  # type: Set

    def _is_external_url(self, url):
        # type: (str) -> bool
        is_external = url.startswith('http') and 'localhost:9981/help' not in url
        if self._has_extension(url) and 'localhost:9981/static/images/help' in url:
            self.static_images.add(basename(urlparse(url).path))
        return is_external or self._has_extension(url)

    def closed(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        unused_images = set(os.listdir(self.help_images_static_dir)) - self.static_images
        if unused_images:
            exception_message = "The following images are not used in help documentation " \
                                "and can be removed: {}"
            self._set_error_state()
            unused_images_relatedpath = [
                os.path.join(self.help_images_path, img) for img in unused_images]
            raise Exception(exception_message.format(', '.join(unused_images_relatedpath)))
