import logging
import os
import subprocess
from typing import Optional

import lxml.html
from django.conf import settings

from zerver.lib.storage import static_path


def render_tex(tex: str, is_inline: bool = True) -> Optional[str]:
    r"""Render a TeX string into HTML using KaTeX

    Returns the HTML string, or None if there was some error in the TeX syntax

    Keyword arguments:
    tex -- Text string with the TeX to render
           Don't include delimiters ('$$', '\[ \]', etc.)
    is_inline -- Boolean setting that indicates whether the render should be
                 inline (i.e. for embedding it in text) or not. The latter
                 will show the content centered, and in the "expanded" form
                 (default True)
    """

    katex_path = (
        static_path("webpack-bundles/katex-cli.js")
        if settings.PRODUCTION
        else os.path.join(settings.DEPLOY_ROOT, "node_modules/katex/cli.js")
    )
    if not os.path.isfile(katex_path):
        logging.error("Cannot find KaTeX for latex rendering!")
        return None
    command = ["node", katex_path]
    if not is_inline:
        command.extend(["--display-mode"])
    try:
        stdout = subprocess.check_output(command, input=tex, stderr=subprocess.DEVNULL, text=True)
        # stdout contains a newline at the end
        return stdout.strip()
    except subprocess.CalledProcessError:
        return None


def change_katex_to_raw_latex(fragment: lxml.html.HtmlElement) -> None:
    # Selecting the <span> elements with class 'katex'
    katex_spans = fragment.xpath("//span[@class='katex']")

    # Iterate through 'katex_spans' and replace with a new <span> having LaTeX text.
    for katex_span in katex_spans:
        latex_text = katex_span.xpath(".//annotation[@encoding='application/x-tex']")[0].text
        # We store 'tail' to insert them back as the replace operation removes it.
        tail = katex_span.tail
        latex_span = lxml.html.Element("span")
        latex_span.text = f"$${latex_text}$$"
        katex_span.getparent().replace(katex_span, latex_span)
        latex_span.tail = tail
