import sys
from mimetypes import add_type
from mimetypes import guess_extension as guess_extension
from mimetypes import guess_type as guess_type

EXTRA_MIME_TYPES = [
    ("audio/flac", ".flac"),
    ("audio/mp4", ".m4a"),
    ("audio/wav", ".wav"),
    ("audio/webm", ".weba"),
    ("image/apng", ".apng"),
]

if sys.version_info < (3, 11):  # nocoverage
    # https://github.com/python/cpython/issues/89802
    EXTRA_MIME_TYPES += [
        ("image/avif", ".avif"),
        ("image/webp", ".webp"),
    ]

for mime_type, extension in EXTRA_MIME_TYPES:
    add_type(mime_type, extension)
