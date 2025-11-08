from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.utils.translation import gettext as _
from pydantic import Json

from zerver.actions.realm_logo import do_change_logo_source
from zerver.decorator import require_realm_admin
from zerver.lib.exceptions import JsonableError
from zerver.lib.realm_logo import get_realm_logo_url
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.lib.upload import get_file_info, upload_logo_image
from zerver.lib.url_encoding import append_url_query_string
from zerver.models import UserProfile


@require_realm_admin
@typed_endpoint
def upload_logo(
    request: HttpRequest, user_profile: UserProfile, *, night: Json[bool]
) -> HttpResponse:
    user_profile.realm.ensure_not_on_limited_plan()

    if len(request.FILES) != 1:
        raise JsonableError(_("You must upload exactly one logo."))
    [logo_file] = request.FILES.values()
    assert isinstance(logo_file, UploadedFile)
    assert logo_file.size is not None
    if logo_file.size > settings.MAX_LOGO_FILE_SIZE_MIB * 1024 * 1024:
        raise JsonableError(
            _("Uploaded file is larger than the allowed limit of {max_size} MiB").format(
                max_size=settings.MAX_LOGO_FILE_SIZE_MIB,
            )
        )
    _filename, content_type = get_file_info(logo_file)
    upload_logo_image(logo_file, user_profile, night, content_type=content_type)
    do_change_logo_source(
        user_profile.realm, user_profile.realm.LOGO_UPLOADED, night, acting_user=user_profile
    )
    return json_success(request)


@require_realm_admin
@typed_endpoint
def delete_logo_backend(
    request: HttpRequest, user_profile: UserProfile, *, night: Json[bool]
) -> HttpResponse:
    # We don't actually delete the logo because it might still
    # be needed if the URL was cached and it is rewritten
    # in any case after next update.
    do_change_logo_source(
        user_profile.realm, user_profile.realm.LOGO_DEFAULT, night, acting_user=user_profile
    )
    return json_success(request)


@typed_endpoint
def get_logo_backend(
    request: HttpRequest, user_profile: UserProfile, *, night: Json[bool]
) -> HttpResponse:
    url = get_realm_logo_url(user_profile.realm, night)

    # We can rely on the URL already having query parameters. Because
    # our templates depend on being able to use the ampersand to
    # add query parameters to our url, get_logo_url does '?version=version_number'
    # hacks to prevent us from having to jump through decode/encode hoops.
    url = append_url_query_string(url, request.META["QUERY_STRING"])
    return redirect(url)
