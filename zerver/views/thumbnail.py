# -*- coding: utf-8 -*-
# See https://zulip.readthedocs.io/en/latest/subsystems/thumbnailing.html
from django.shortcuts import redirect
from django.utils.translation import ugettext as _
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from typing import Optional
from zerver.models import UserProfile, validate_attachment_request
from zerver.lib.request import has_request_variables, REQ
from zerver.lib.thumbnail import generate_thumbnail_url

def validate_thumbnail_request(user_profile: UserProfile, path: str) -> Optional[bool]:
    # path here does not have a leading / as it is parsed from request hitting the
    # thumbnail endpoint (defined in urls.py) that way.
    if path.startswith('user_uploads/'):
        path_id = path[len('user_uploads/'):]
        return validate_attachment_request(user_profile, path_id)

    # This is an external link and we don't enforce restricted view policy here.
    return True

@has_request_variables
def backend_serve_thumbnail(request: HttpRequest, user_profile: UserProfile,
                            url: str=REQ(), size_requested: str=REQ("size")) -> HttpResponse:
    if not validate_thumbnail_request(user_profile, url):
        return HttpResponseForbidden(_("<p>You are not authorized to view this file.</p>"))

    size = None
    if size_requested == 'thumbnail':
        size = '0x300'
    elif size_requested == 'full':
        size = '0x0'

    if size is None:
        return HttpResponseForbidden(_("<p>Invalid size.</p>"))

    thumbnail_url = generate_thumbnail_url(url, size)
    return redirect(thumbnail_url)
