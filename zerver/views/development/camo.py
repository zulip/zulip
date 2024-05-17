from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect

from zerver.lib.camo import is_camo_url_valid
from zerver.lib.thumbnail import generate_thumbnail_url


def handle_camo_url(
    request: HttpRequest, digest: str, received_url: str
) -> HttpResponse:  # nocoverage
    original_url = bytes.fromhex(received_url).decode()
    if is_camo_url_valid(digest, original_url):
        return redirect(generate_thumbnail_url(original_url))
    else:
        return HttpResponseForbidden("<p>Not a valid URL.</p>")
