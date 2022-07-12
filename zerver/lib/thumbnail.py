import os
import sys
from urllib.parse import urljoin

from django.utils.http import url_has_allowed_host_and_scheme

ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ZULIP_PATH)

from zerver.lib.camo import get_camo_url


def user_uploads_or_external(url: str) -> bool:
    return not url_has_allowed_host_and_scheme(url, allowed_hosts=None) or url.startswith(
        "/user_uploads/"
    )


def generate_thumbnail_url(path: str, size: str = "0x0") -> str:
    path = urljoin("/", path)

    if url_has_allowed_host_and_scheme(path, allowed_hosts=None):
        return path
    return get_camo_url(path)
