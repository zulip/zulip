import logging
import os
import subprocess
from typing import Any

import lxml.html
import requests
from django.conf import settings

from zerver.lib.outgoing_http import OutgoingSession
from zerver.lib.storage import static_path


class KatexSession(OutgoingSession):
    def __init__(self, **kwargs: Any) -> None:
        # We set a very short timeout because these requests are
        # expected to be quite fast (milliseconds) and blocking on
        # this affects message rendering performance.
        super().__init__(role="katex", timeout=0.5, **kwargs)


def render_tex(tex: str, is_inline: bool = True) -> str | None:
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

    if settings.KATEX_SERVER:
        try:
            resp = KatexSession().post(
                # We explicitly disable the Smokescreen proxy for this
                # call, since it intentionally connects to localhost.
                # This is safe because the host is explicitly fixed, and
                # the port is pulled from our own configuration.
                f"http://localhost:{settings.KATEX_SERVER_PORT}/",
                data={
                    "content": tex,
                    "is_display": "false" if is_inline else "true",
                    "shared_secret": settings.SHARED_SECRET,
                },
                proxies={"http": ""},
            )
        except requests.exceptions.Timeout:
            logging.warning("KaTeX rendering service timed out with %d byte long input", len(tex))
            return None
        except requests.exceptions.RequestException as e:
            logging.warning("KaTeX rendering service failed: %s", type(e).__name__)
            return None

        if resp.status_code == 200:
            return resp.content.decode().strip()
        elif resp.status_code == 400:
            return None
        else:
            logging.warning(
                "KaTeX rendering service failed: (%s) %s", resp.status_code, resp.content.decode()
            )
            return None

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
