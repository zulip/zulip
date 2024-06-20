from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.utils.translation import gettext as _

from zerver.actions.realm_background import do_change_background_source
from zerver.decorator import require_realm_admin
from zerver.lib.exceptions import JsonableError
from zerver.lib.realm_background import realm_background_url
from zerver.lib.response import json_success
from zerver.lib.upload import upload_background_image
from zerver.lib.url_encoding import append_url_query_string
from zerver.models import UserProfile


@require_realm_admin
def upload_background(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    if len(request.FILES) != 1:
        raise JsonableError(_("You must upload exactly one background image."))

    [background_file] = request.FILES.values()
    assert isinstance(background_file, UploadedFile)
    assert background_file.size is not None
    if background_file.size > settings.MAX_BACKGROUND_FILE_SIZE_MIB * 1024 * 1024:
        raise JsonableError(
            _("Uploaded file is larger than the allowed limit of {max_size} MiB").format(
                max_size=settings.MAX_BACKGROUND_FILE_SIZE_MIB,
            )
        )
    upload_background_image(background_file, user_profile)
    do_change_background_source(
        user_profile.realm, user_profile.realm.BACKGROUND_UPLOADED, acting_user=user_profile
    )
    background_url = realm_background_url(user_profile.realm)

    json_result = dict(
        background_url=background_url,
    )
    return json_success(request, data=json_result)


@require_realm_admin
def delete_background_backend(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    # We don't actually delete the background because it might still
    # be needed if the URL was cached and it is rewritten
    # in any case after next update.
    do_change_background_source(
        user_profile.realm, user_profile.realm.BACKGROUND_DEFAULT, acting_user=user_profile
    )
    default_url = realm_background_url(user_profile.realm)
    json_result = dict(
        background_url=default_url,
    )
    return json_success(request, data=json_result)


def get_background_backend(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    url = realm_background_url(user_profile.realm)

    # We can rely on the URL already having query parameters. Because
    # our templates depend on being able to use the ampersand to
    # add query parameters to our url, get_background_url does '?version=version_number'
    # hacks to prevent us from having to jump through decode/encode hoops.
    url = append_url_query_string(url, request.META["QUERY_STRING"])
    return redirect(url)
