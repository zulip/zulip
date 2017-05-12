#!/usr/bin/env python
from __future__ import print_function

import os
import pathlib2

from typing import List

from .common.spiders import BaseDocumentationSpider


def get_start_url():
    # type: () -> List[str]
    # Get index html file as start url and convert it to file uri
    dir_path = os.path.dirname(os.path.realpath(__file__))
    start_file = os.path.join(dir_path, os.path.join(*[os.pardir] * 4),
                              "docs/_build/html/index.html")
    return [
        pathlib2.Path(os.path.abspath(start_file)).as_uri()
    ]


class DocumentationSpider(BaseDocumentationSpider):
    name = "documentation_crawler"
    deny_domains = ['localhost:9991']
    deny = ['\_sources\/.*\.txt']
    start_urls = get_start_url()
