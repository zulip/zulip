import json
from typing import Any, Dict, Iterator, Optional

# Taken from
# https://github.com/simplejson/simplejson/blob/8edc82afcf6f7512b05fba32baa536fe756bd273/simplejson/encoder.py#L378-L402
# License: MIT
class JSONEncoderForHTML(json.JSONEncoder):
    """An encoder that produces JSON safe to embed in HTML.
    To embed JSON content in, say, a script tag on a web page, the
    characters &, < and > should be escaped. They cannot be escaped
    with the usual entities (e.g. &amp;) because they are not expanded
    within <script> tags.
    """

    def encode(self, o: Any) -> str:
        # Override JSONEncoder.encode because it has hacks for
        # performance that make things more complicated.
        chunks = self.iterencode(o, True)
        return ''.join(chunks)

    def iterencode(self, o: Any, _one_shot: bool=False) -> Iterator[str]:
        chunks = super().iterencode(o, _one_shot)
        for chunk in chunks:
            chunk = chunk.replace('&', '\\u0026')
            chunk = chunk.replace('<', '\\u003c')
            chunk = chunk.replace('>', '\\u003e')
            yield chunk
