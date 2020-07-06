import re
from typing import Tuple

THUMBOR_EXTERNAL_TYPE = 'external'
THUMBOR_S3_TYPE = 's3'
THUMBOR_LOCAL_FILE_TYPE = 'local_file'

def separate_url_and_source_type(url: str) -> Tuple[str, str]:
    THUMBNAIL_URL_PATT = re.compile('^(?P<actual_url>.+)/source_type/(?P<source_type>.+)')
    matches = THUMBNAIL_URL_PATT.match(url)
    assert matches is not None
    return (matches.group('source_type'), matches.group('actual_url'))
