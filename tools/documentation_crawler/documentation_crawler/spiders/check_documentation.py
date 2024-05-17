import os
import pathlib
from typing import List

from .common.spiders import BaseDocumentationSpider


def get_start_url() -> List[str]:
    # Get index.html file as start URL and convert it to file URI
    dir_path = os.path.dirname(os.path.realpath(__file__))
    start_file = os.path.join(
        dir_path, os.path.join(*[os.pardir] * 4), "docs/_build/html/index.html"
    )
    return [
        pathlib.Path(os.path.abspath(start_file)).as_uri(),
    ]


class DocumentationSpider(BaseDocumentationSpider):
    name = "documentation_crawler"
    deny_domains = ["localhost:9991"]
    deny = [r"\_sources\/.*\.txt"]
    start_urls = get_start_url()
