from typing import List, Optional

from bs4 import BeautifulSoup
from django.http import HttpRequest
from django.utils.html import escape

from zerver.lib.cache import cache_with_key, open_graph_description_cache_key

def html_to_text(content: str, tags: Optional[List[str]]=None) -> str:
    bs = BeautifulSoup(content, features='lxml')
    # Skip any admonition (warning) blocks, since they're
    # usually something about users needing to be an
    # organization administrator, and not useful for
    # describing the page.
    for tag in bs.find_all('div', class_="admonition"):
        tag.clear()

    # Skip code-sections, which just contains navigation instructions.
    for tag in bs.find_all('div', class_="code-section"):
        tag.clear()

    text = ''
    if tags is None:
        tags = ['p']
    for paragraph in bs.find_all(tags):
        # .text converts it from HTML to text
        text = text + paragraph.text + ' '
        if len(text) > 500:
            break
    return escape(' '.join(text.split()))

@cache_with_key(open_graph_description_cache_key, timeout=3600*24)
def get_content_description(content: bytes, request: HttpRequest) -> str:
    str_content = content.decode("utf-8")
    return html_to_text(str_content)
