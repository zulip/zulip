from bs4 import BeautifulSoup
from django.http import HttpRequest

from zerver.lib.cache import cache_with_key, open_graph_description_cache_key

def html_to_text(content: str) -> str:
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
    for paragraph in bs.find_all('p'):
        # .text converts it from HTML to text
        text = text + paragraph.text + ' '
        if len(text) > 500:
            return ' '.join(text.split())
    return ' '.join(text.split())

@cache_with_key(open_graph_description_cache_key, timeout=3600*24)
def get_content_description(content: bytes, request: HttpRequest) -> str:
    str_content = content.decode("utf-8")
    return html_to_text(str_content)
