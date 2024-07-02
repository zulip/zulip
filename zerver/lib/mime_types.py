import sys
from mimetypes import add_type
from mimetypes import guess_type as guess_type

add_type("audio/flac", ".flac")
add_type("audio/mp4", ".m4a")
add_type("audio/wav", ".wav")
add_type("audio/webm", ".weba")
add_type("image/apng", ".apng")

if sys.version_info < (3, 11):  # nocoverage
    # https://github.com/python/cpython/issues/89802
    add_type("image/avif", ".avif")
    add_type("image/webp", ".webp")
