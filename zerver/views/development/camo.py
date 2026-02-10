from urllib.parse import urljoin

from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme

from zerver.lib.camo import is_camo_url_valid


def handle_camo_url(
    request: HttpRequest, digest: str, received_url: str
) -> HttpResponse:  # nocoverage
    original_url = bytes.fromhex(received_url).decode()
    if is_camo_url_valid(digest, original_url):
        original_url = urljoin("/", original_url)
        if url_has_allowed_host_and_scheme(original_url, allowed_hosts=None):
            return redirect(original_url)
        return HttpResponseForbidden("<p>Not a valid URL.</p>")
    else:
        return HttpResponseForbidden("<p>Not a valid URL.</p>")
