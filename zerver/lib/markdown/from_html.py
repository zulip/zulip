import os
import re
import subprocess
import sys


def convert_html_to_markdown(html: str) -> str:
    # html2text is GPL licensed, so run it as a subprocess.
    markdown = subprocess.check_output(
        [os.path.join(sys.prefix, "bin", "html2text"), "--unicode-snob"], input=html, text=True
    ).strip()

    # We want images to get linked and inline previewed, but html2text will turn
    # them into links of the form `![](http://foo.com/image.png)`, which is
    # ugly. Run a regex over the resulting description, turning links of the
    # form `![](http://foo.com/image.png?12345)` into
    # `[image.png](http://foo.com/image.png)`.
    return re.sub(r"!\[\]\((\S*)/(\S*)\?(\S*)\)", "[\\2](\\1/\\2)", markdown)
