# See https://zulip.readthedocs.io/en/latest/subsystems/thumbnailing.html
from typing import Optional, Union

from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect
from django.utils.translation import gettext as _

from zerver.context_processors import get_valid_realm_from_request
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.thumbnail import generate_thumbnail_url
from zerver.models import Realm, UserProfile, validate_attachment_request


def validate_thumbnail_request(
    realm: Realm,
    maybe_user_profile: Union[UserProfile, AnonymousUser],
    path: str,
) -> Optional[bool]:
    # path here does not have a leading / as it is parsed from request hitting the
    # thumbnail endpoint (defined in urls.py) that way.
    if path.startswith("user_uploads/"):
        path_id = path[len("user_uploads/") :]
        return validate_attachment_request(maybe_user_profile, path_id, realm)

    # This is an external link and we don't enforce restricted view policy here.
    return True


@has_request_variables
def backend_serve_thumbnail(
    request: HttpRequest,
    maybe_user_profile: Union[UserProfile, AnonymousUser],
    url: str = REQ(),
    size_requested: str = REQ("size"),
) -> HttpResponse:
    if not maybe_user_profile.is_authenticated:
        realm = get_valid_realm_from_request(request)
    else:
        assert isinstance(maybe_user_profile, UserProfile)
        realm = maybe_user_profile.realm

    if not validate_thumbnail_request(realm, maybe_user_profile, url):
        return HttpResponseForbidden(_("<p>You are not authorized to view this file.</p>"))

    thumbnail_url = generate_thumbnail_url(url)
    return redirect(thumbnail_url)
