import posixpath
import warnings
from urllib.parse import urlsplit

import markdownify
from bs4 import MarkupResemblesLocatorWarning, Tag

from zerver.lib.markdown import get_markdown_link_for_url, sanitize_url


class ZulipMarkdownConverter(markdownify.MarkdownConverter):
    """HTML-to-Markdown converter that linkifies images.

    Zulip doesn't inline-render external images, so images become
    `[label](src)` links instead of broken `![alt](src)`.
    """

    def convert_img(self, el: Tag, text: str, parent_tags: set[str]) -> str:
        src = el.get("src", "")
        alt = el.get("alt", "")
        # BeautifulSoup returns a list only for multi-valued attributes
        # (e.g. class), never for src or alt.
        assert isinstance(src, str)
        assert isinstance(alt, str)
        if not src:
            return alt
        url = sanitize_url(src)
        if not url:
            # Unlinkable src (e.g. data: URIs, unsafe schemes): emit just the
            # alt text rather than a bogus link.
            return alt
        label = alt or posixpath.basename(urlsplit(url).path)
        # No brackets inside an <a> or without a label return a bare URL
        if "a" in parent_tags or not label:
            return label or url
        return get_markdown_link_for_url(label, url)


def convert_html_to_markdown(html: str) -> str:
    # BeautifulSoup warns when content is a bare URL ("looks like a URL, not
    # markup"); harmless here, but fatal under CI's PYTHONWARNINGS=error.
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)
        # ATX headings ("# Title"): Zulip doesn't render Setext underlines.
        # Asterisk/underscore escaping is disabled: Zulip's Markdown has no
        # backslash escaping, so "\*" renders as a literal backslash.
        converter = ZulipMarkdownConverter(
            heading_style="ATX",
            escape_asterisks=False,
            escape_underscores=False,
        )
        markdown: str = converter.convert(html).strip()
    return markdown
