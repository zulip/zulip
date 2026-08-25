import posixpath
import re
import sys
import warnings
from urllib.parse import urlsplit

import markdownify
from bs4 import MarkupResemblesLocatorWarning, Tag

from zerver.lib.markdown import get_markdown_link_for_url, sanitize_url


class ZulipMarkdownConverter(markdownify.MarkdownConverter):
    """HTML-to-Markdown converter adapted to Zulip's Markdown.

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
        if not label:
            # No alt text, and no filename in the path to fall back on, as in
            # `<img src="https://example.com/?token=abc">`.
            return url
        if "a" in parent_tags:
            # Markdown has no nested links, so hand the label up for the
            # enclosing <a> to use as its text, with brackets stripped.
            return re.sub(r"\[|\]", "", label)
        return get_markdown_link_for_url(label, url)

    def convert_title(self, el: Tag, text: str, parent_tags: set[str]) -> str:
        return ""


def convert_html_to_markdown(
    html: str, *, converter_class: type[ZulipMarkdownConverter] = ZulipMarkdownConverter
) -> str:
    # A bare URL is expected input here (the text/html part of an incoming
    # email), but BeautifulSoup warns about it ("looks like a URL, not markup").
    # Suppress the warning so that expected input doesn't spam our logs.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", MarkupResemblesLocatorWarning)
        converter = converter_class(
            # Zulip's Markdown supports only ATX headings, not Setext headings.
            heading_style="ATX",
            # Zulip's Markdown has no backslash escaping; it renders "\" as a
            # literal character.
            escape_asterisks=False,
            escape_underscores=False,
            # HTML treats a newline as insignificant whitespace, but Zulip
            # renders it as a line break. Collapse source newlines to spaces.
            # <br>, <pre>, and block-level elements still produce line breaks.
            wrap=True,
            # An effectively infinite width disables column wrapping. Don't
            # use None, which also disables wrapping but skips the pass that
            # strips indentation from lines following a <br>.
            wrap_width=sys.maxsize,
        )
        markdown: str = converter.convert(html).strip()
    return markdown
