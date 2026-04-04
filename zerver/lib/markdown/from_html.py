import re

import markdownify


def convert_html_to_markdown(html: str) -> str:
    # Use ATX-style headings (e.g. "# Title") since Zulip's Markdown
    # renderer does not support Setext-style underline headings.
    markdown = markdownify.markdownify(html, heading_style="ATX").strip()

    # We want images to get linked and inline previewed, but markdownify
    # turns them into links of the form `![](http://foo.com/image.png)`,
    # which is ugly and won't render in Zulip for external URLs.  Convert
    # links of the form `![](http://foo.com/image.png?12345)` into
    # `[image.png](http://foo.com/image.png)`.
    return re.sub(r"!\[\]\((\S*)/(\S*)\?(\S*)\)", "[\\2](\\1/\\2)", markdown)
