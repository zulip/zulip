from mimetypes import guess_type

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, HttpResponseNotFound
from django.shortcuts import redirect
from django.utils.cache import patch_cache_control
from django.utils.translation import ugettext as _
from django_sendfile import sendfile

from zerver.lib.response import json_error, json_success
from zerver.lib.upload import (
    INLINE_MIME_TYPES,
    check_upload_within_quota,
    generate_unauthed_file_access_url,
    get_local_file_path,
    get_local_file_path_id_from_token,
    get_signed_upload_url,
    upload_message_image_from_request,
)
from zerver.models import UserProfile, validate_attachment_request


def serve_s3(request: HttpRequest, url_path: str, url_only: bool) -> HttpResponse:
    url = get_signed_upload_url(url_path)
    if url_only:
        return json_success(dict(url=url))

    return redirect(url)

def serve_local(request: HttpRequest, path_id: str, url_only: bool) -> HttpResponse:
    local_path = get_local_file_path(path_id)
    if local_path is None:
        return HttpResponseNotFound('<p>File not found</p>')

    if url_only:
        url = generate_unauthed_file_access_url(path_id)
        return json_success(dict(url=url))

    # Here we determine whether a browser should treat the file like
    # an attachment (and thus clicking a link to it should download)
    # or like a link (and thus clicking a link to it should display it
    # in a browser tab).  This is controlled by the
    # Content-Disposition header; `django-sendfile2` sends the
    # attachment-style version of that header if and only if the
    # attachment argument is passed to it.  For attachments,
    # django-sendfile2 sets the response['Content-disposition'] like
    # this: `attachment; filename="zulip.txt"; filename*=UTF-8''zulip.txt`.
    # The filename* parameter is omitted for ASCII filenames like this one.
    #
    # The "filename" field (used to name the file when downloaded) is
    # unreliable because it doesn't have a well-defined encoding; the
    # newer filename* field takes precedence, since it uses a
    # consistent format (urlquoted).  For more details on filename*
    # and filename, see the below docs:
    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Disposition
    mimetype, encoding = guess_type(local_path)
    attachment = mimetype not in INLINE_MIME_TYPES

    response = sendfile(request, local_path, attachment=attachment,
                        mimetype=mimetype, encoding=encoding)
    patch_cache_control(response, private=True, immutable=True)
    return response

def serve_file_backend(request: HttpRequest, user_profile: UserProfile,
                       realm_id_str: str, filename: str) -> HttpResponse:
    return serve_file(request, user_profile, realm_id_str, filename, url_only=False)

def serve_file_url_backend(request: HttpRequest, user_profile: UserProfile,
                           realm_id_str: str, filename: str) -> HttpResponse:
    """
    We should return a signed, short-lived URL
    that the client can use for native mobile download, rather than serving a redirect.
    """

    return serve_file(request, user_profile, realm_id_str, filename, url_only=True)

def serve_file(request: HttpRequest, user_profile: UserProfile,
               realm_id_str: str, filename: str,
               url_only: bool=False) -> HttpResponse:
    path_id = f"{realm_id_str}/{filename}"
    is_authorized = validate_attachment_request(user_profile, path_id)

    if is_authorized is None:
        return HttpResponseNotFound(_("<p>File not found.</p>"))
    if not is_authorized:
        return HttpResponseForbidden(_("<p>You are not authorized to view this file.</p>"))
    if settings.LOCAL_UPLOADS_DIR is not None:
        return serve_local(request, path_id, url_only)

    return serve_s3(request, path_id, url_only)

def serve_local_file_unauthed(request: HttpRequest, token: str, filename: str) -> HttpResponse:
    path_id = get_local_file_path_id_from_token(token)
    if path_id is None:
        return json_error(_("Invalid token"))
    if path_id.split('/')[-1] != filename:
        return json_error(_("Invalid filename"))

    return serve_local(request, path_id, url_only=False)

def upload_file_backend(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    if len(request.FILES) == 0:
        return json_error(_("You must specify a file to upload"))
    if len(request.FILES) != 1:
        return json_error(_("You may only upload one file at a time"))

    user_file = list(request.FILES.values())[0]
    file_size = user_file.size
    if settings.MAX_FILE_UPLOAD_SIZE * 1024 * 1024 < file_size:
        return json_error(_("Uploaded file is larger than the allowed limit of {} MiB").format(
            settings.MAX_FILE_UPLOAD_SIZE,
        ))
    check_upload_within_quota(user_profile.realm, file_size)

    uri = upload_message_image_from_request(request, user_file, user_profile)
    return json_success({'uri': uri})
