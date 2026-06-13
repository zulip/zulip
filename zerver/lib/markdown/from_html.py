import re
import warnings

import markdownify
from bs4 import MarkupResemblesLocatorWarning


def convert_html_to_markdown(html: str) -> str:
    # Message content is often a bare URL, which BeautifulSoup warns about
    # ("looks like a URL, not markup"). The warning is harmless here but
    # fatal under PYTHONWARNINGS=error, so silence it; the URL converts fine.
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)
        # Use ATX-style headings (e.g. "# Title") since Zulip's Markdown
        # renderer does not support Setext-style underline headings.
        markdown = markdownify.markdownify(html, heading_style="ATX").strip()

    # We want images to get linked and inline previewed, but markdownify
    # turns them into links of the form `![](http://foo.com/image.png)`,
    # which is ugly and won't render in Zulip for external URLs.  Convert
    # links of the form `![](http://foo.com/image.png?12345)` into
    # `[image.png](http://foo.com/image.png)`.
    return re.sub(r"!\[\]\((\S*)/(\S*)\?(\S*)\)", "[\\2](\\1/\\2)", markdown)
