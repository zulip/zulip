from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect
from django.utils.translation import gettext as _

from zerver.context_processors import get_valid_realm_from_request
from zerver.lib.attachments import validate_attachment_request
from zerver.lib.thumbnail import generate_thumbnail_url
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models import Realm, UserProfile


def validate_thumbnail_request(
    realm: Realm,
    maybe_user_profile: UserProfile | AnonymousUser,
    path: str,
) -> bool | None:
    # path here does not have a leading / as it is parsed from request hitting the
    # thumbnail endpoint (defined in urls.py) that way.
    if path.startswith("user_uploads/"):
        path_id = path[len("user_uploads/") :]
        return validate_attachment_request(maybe_user_profile, path_id, realm)

    # This is an external link and we don't enforce restricted view policy here.
    return True


@typed_endpoint
def backend_serve_thumbnail(
    request: HttpRequest,
    maybe_user_profile: UserProfile | AnonymousUser,
    *,
    url: str,
    size: str,
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
