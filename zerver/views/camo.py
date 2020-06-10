import binascii

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, HttpResponseNotFound
from django.shortcuts import redirect
from django.utils.translation import ugettext as _

from zerver.lib.camo import is_camo_url_valid
from zerver.lib.thumbnail import generate_thumbnail_url


def handle_camo_url(request: HttpRequest, digest: str,
                    received_url: str) -> HttpResponse:
    if not settings.THUMBOR_SERVES_CAMO:
        return HttpResponseNotFound()

    hex_encoded_url = received_url.encode('utf-8')
    hex_decoded_url = binascii.a2b_hex(hex_encoded_url)
    original_url = hex_decoded_url.decode('utf-8')
    if is_camo_url_valid(digest, original_url):
        return redirect(generate_thumbnail_url(original_url, is_camo_url=True))
    else:
        return HttpResponseForbidden(_("<p>Not a valid URL.</p>"))
