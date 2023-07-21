from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.utils.translation import gettext as _

from zerver.actions.realm_icon import do_change_icon_source
from zerver.decorator import require_realm_admin
from zerver.lib.exceptions import JsonableError
from zerver.lib.realm_icon import realm_icon_url
from zerver.lib.response import json_success
from zerver.lib.upload import upload_icon_image
from zerver.lib.url_encoding import append_url_query_string
from zerver.models import UserProfile


@require_realm_admin
def upload_icon(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    if len(request.FILES) != 1:
        raise JsonableError(_("You must upload exactly one icon."))

    [icon_file] = request.FILES.values()
    assert isinstance(icon_file, UploadedFile)
    assert icon_file.size is not None
    if (settings.MAX_ICON_FILE_SIZE_MIB * 1024 * 1024) < icon_file.size:
        raise JsonableError(
            _("Uploaded file is larger than the allowed limit of {max_size} MiB").format(
                max_size=settings.MAX_ICON_FILE_SIZE_MIB,
            )
        )
    upload_icon_image(icon_file, user_profile)
    do_change_icon_source(
        user_profile.realm, user_profile.realm.ICON_UPLOADED, acting_user=user_profile
    )
    icon_url = realm_icon_url(user_profile.realm)

    json_result = dict(
        icon_url=icon_url,
    )
    return json_success(request, data=json_result)


@require_realm_admin
def delete_icon_backend(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    # We don't actually delete the icon because it might still
    # be needed if the URL was cached and it is rewritten
    # in any case after next update.
    do_change_icon_source(
        user_profile.realm, user_profile.realm.ICON_FROM_GRAVATAR, acting_user=user_profile
    )
    gravatar_url = realm_icon_url(user_profile.realm)
    json_result = dict(
        icon_url=gravatar_url,
    )
    return json_success(request, data=json_result)


def get_icon_backend(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    url = realm_icon_url(user_profile.realm)

    # We can rely on the URL already having query parameters. Because
    # our templates depend on being able to use the ampersand to
    # add query parameters to our url, get_icon_url does '?version=version_number'
    # hacks to prevent us from having to jump through decode/encode hoops.
    url = append_url_query_string(url, request.META["QUERY_STRING"])
    return redirect(url)
