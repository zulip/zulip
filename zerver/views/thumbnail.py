import re

from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest, HttpResponseBase, HttpResponseForbidden
from django.utils.translation import gettext as _

from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.thumbnail import missing_thumbnails
from zerver.lib.typed_endpoint import PathOnly, typed_endpoint
from zerver.models import Attachment, ImageAttachment, UserProfile
from zerver.views.upload import serve_file


@typed_endpoint
def backend_serve_thumbnail(
    request: HttpRequest,
    maybe_user_profile: UserProfile | AnonymousUser,
    *,
    size: str,
    url: str,
) -> HttpResponseBase:
    # This URL used to be passed arbitrary URLs, and pass them through
    # Camo; we no longer support doing so, and instead return a 403.
    #
    # Modern thumbnailing uses URLs of the style
    # `/user_uploads/thumbnail/.../300x200.webp`; this endpoint is
    # kept for backward compatibility, and for future extension for
    # thumbnailing external URLs.
    upload_path_parts = re.match(r"user_uploads/(\d+)/(.*)", url)
    if not upload_path_parts:
        return HttpResponseForbidden()

    realm_id_str = upload_path_parts[1]
    path_id = upload_path_parts[2]

    # We do not have ImageAttachment rows for historical uploads, so
    # we cannot serve a "new" thumbnail for these requests; serve the
    # full-size file.
    return serve_file(request, maybe_user_profile, realm_id_str, path_id)


@typed_endpoint
def check_thumbnail_status(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    realm_id_str: PathOnly[str],
    filename: PathOnly[str],
) -> HttpResponseBase:
    path_id = f"{realm_id_str}/{filename}"

    if not Attachment.objects.filter(path_id=path_id, owner=user_profile).exists():
        raise JsonableError(_("Invalid attachment"))

    try:
        image_attachment = ImageAttachment.objects.get(path_id=path_id)
    except ImageAttachment.DoesNotExist:
        raise JsonableError(_("Invalid attachment"))

    needed_thumbnails = missing_thumbnails(image_attachment)

    return json_success(request, data={"has_thumbnail": len(needed_thumbnails) == 0})
