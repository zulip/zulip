import posixpath
import re
import warnings
from typing import Any
from urllib.parse import urlsplit

import markdownify
from bs4 import MarkupResemblesLocatorWarning, Tag


class ZulipMarkdownConverter(markdownify.MarkdownConverter):
    """HTML-to-Markdown converter that linkifies external images.

    Zulip inline-renders only /user_uploads/ images, so other images become
    `[label](src)` links instead of broken `![alt](src)`.  Importers that
    re-host images themselves (e.g. Microsoft Teams) pass
    link_external_images=False to keep the inline form.
    """

    def __init__(self, *, link_external_images: bool, **options: Any) -> None:
        self.link_external_images = link_external_images
        super().__init__(**options)

    def convert_img(self, el: Tag, text: str, parent_tags: set[str]) -> str:
        src = el.get("src", "")
        if (
            not self.link_external_images
            or not isinstance(src, str)
            or not src
            or src.startswith("/user_uploads/")
        ):
            # markdownify's incomplete type stub omits convert_img, so mypy
            # can't see it on the base; reach it through Any.
            base: Any = super()
            default: str = base.convert_img(el, text, parent_tags)
            return default

        alt = el.get("alt", "")
        if not isinstance(alt, str):
            alt = ""
        label = alt or posixpath.basename(urlsplit(src).path) or src
        # Zulip's Markdown has no escaping, so brackets in the link text would
        # break the link; strip them, as get_markdown_link_for_url does.
        label = re.sub(r"[][]", "", label)
        # Inside an <a>, return only the label so the link isn't nested.
        if "a" in parent_tags:
            return label
        return f"[{label}]({src})"


def convert_html_to_markdown(html: str, *, link_external_images: bool = True) -> str:
    # BeautifulSoup warns when content is a bare URL ("looks like a URL, not
    # markup"); harmless here, but fatal under CI's PYTHONWARNINGS=error.
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)
        # ATX headings ("# Title"): Zulip doesn't render Setext underlines.
        converter = ZulipMarkdownConverter(
            link_external_images=link_external_images, heading_style="ATX"
        )
        markdown: str = converter.convert(html).strip()
    return markdown
