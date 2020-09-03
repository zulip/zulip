import logging
import os
import subprocess
from typing import Optional

from django.conf import settings

from zerver.lib.storage import static_path


def render_tex(tex: str, is_inline: bool=True) -> Optional[str]:
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
    command = ['node', katex_path]
    if not is_inline:
        command.extend(['--display-mode'])
    try:
        stdout = subprocess.check_output(
            command, input=tex, stderr=subprocess.DEVNULL, universal_newlines=True
        )
        # stdout contains a newline at the end
        return stdout.strip()
    except subprocess.CalledProcessError:
        return None
