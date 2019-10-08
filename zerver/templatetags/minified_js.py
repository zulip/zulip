from typing import Any, Dict

from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.template import Library, Node


register = Library()

class MinifiedJSNode(Node):
    def __init__(self, sourcefile: str, csp_nonce: str) -> None:
        self.sourcefile = sourcefile
        self.csp_nonce = csp_nonce

    def render(self, context: Dict[str, Any]) -> str:
        if settings.DEBUG:
            source_files = settings.JS_SPECS[self.sourcefile]
            normal_source = source_files['source_filenames']
            minified_source = source_files.get('minifed_source_filenames', [])

            # Minified source files (most likely libraries) should be loaded
            # first to prevent any dependency errors.
            scripts = minified_source + normal_source
        else:
            scripts = [settings.JS_SPECS[self.sourcefile]['output_filename']]
        script_urls = [staticfiles_storage.url(script) for script in scripts]
        script_tags = ['<script nonce="%s" src="%s"></script>' % (self.csp_nonce, url)
                       for url in script_urls]
        return '\n'.join(script_tags)
