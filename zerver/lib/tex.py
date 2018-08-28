
import logging
import os
import subprocess
from django.conf import settings
from typing import Optional

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

    katex_path = os.path.join(settings.STATIC_ROOT, 'third/katex/cli.js')
    if not os.path.isfile(katex_path):
        logging.error("Cannot find KaTeX for latex rendering!")
        return None
    command = ['node', katex_path]
    if not is_inline:
        command.extend(['--', '--display-mode'])
    katex = subprocess.Popen(command,
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    stdout = katex.communicate(input=tex.encode())[0]
    if katex.returncode == 0:
        # stdout contains a newline at the end
        assert stdout is not None
        return stdout.decode('utf-8').strip()
    else:
        return None
