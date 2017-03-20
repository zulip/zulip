import os
import subprocess
from django.conf import settings
from typing import Text
from zerver.lib.str_utils import force_bytes

def render_tex(tex, is_inline=True):
    # type: (Text, bool) -> Text
    """Render a TeX string into HTML using KaTeX

    Returns the HTML string, or None if there was some error in the TeX syntax

    Keyword arguments:
    tex -- Text string with the TeX to render
           Don't include delimiters ('$$', '\[ \]', etc.)
    is_inline -- Boolean setting that indicates whether the render should be
                 inline (i.e. for embedding it in text) or not. The latter
                 will show the content centered, and in the "expanded" form
                 (default True)
    """

    command = ['node']
    if settings.PRODUCTION:
        # Running in production
        command.append(os.path.join(settings.STATIC_ROOT,
                                    'prod-static/serve/third/katex/cli.js'))
    else:
        # Running in a development environment
        command.append(os.path.join(settings.STATIC_ROOT,
                                    'third/katex/cli.js'))

    if not is_inline:
        command.extend(['--', '--display-mode'])
    katex = subprocess.Popen(command,
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    stdout = katex.communicate(input=force_bytes(tex))[0]
    if katex.returncode == 0:
        # stdout contains a newline at the end
        return stdout.decode('utf-8').strip()
    else:
        return None
