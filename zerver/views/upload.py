# -*- coding: utf-8 -*-

from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, FileResponse, \
    HttpResponseNotFound
from django.shortcuts import redirect
from django.utils.translation import ugettext as _

from zerver.lib.request import has_request_variables, REQ
from zerver.lib.response import json_success, json_error
from zerver.lib.upload import upload_message_image_from_request, get_local_file_path, \
    get_signed_upload_url, get_realm_for_filename, check_upload_within_quota
from zerver.lib.validator import check_bool
from zerver.models import UserProfile, validate_attachment_request
from django.conf import settings
from sendfile import sendfile
from mimetypes import guess_type

def serve_s3(request: HttpRequest, url_path: str) -> HttpResponse:
    uri = get_signed_upload_url(url_path)
    return redirect(uri)

def serve_local(request: HttpRequest, path_id: str) -> HttpResponse:
    local_path = get_local_file_path(path_id)
    if local_path is None:
        return HttpResponseNotFound('<p>File not found</p>')

    # Here we determine whether a browser should treat the file like
    # an attachment (and thus clicking a link to it should download)
    # or like a link (and thus clicking a link to it should display it
    # in a browser tab).  This is controlled by the
    # Content-Disposition header; `django-sendfile` sends the
    # attachment-style version of that header if and only if the
    # attachment argument is passed to it.  For attachments,
    # django-sendfile sets the response['Content-disposition'] like
    # this: `attachment; filename="b'zulip.txt'"; filename*=UTF-8''zulip.txt`.
    #
    # The "filename" field (used to name the file when downloaded) is
    # unreliable because it doesn't have a well-defined encoding; the
    # newer filename* field takes precedence, since it uses a
    # consistent format (urlquoted).  For more details on filename*
    # and filename, see the below docs:
    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Disposition
    attachment = True
    file_type = guess_type(local_path)[0]
    if file_type is not None and (file_type.startswith("image/") or
                                  file_type == "application/pdf"):
        attachment = False

    return sendfile(request, local_path, attachment=attachment)

@has_request_variables
def serve_file_backend(request: HttpRequest, user_profile: UserProfile,
                       realm_id_str: str, filename: str) -> HttpResponse:
    path_id = "%s/%s" % (realm_id_str, filename)
    is_authorized = validate_attachment_request(user_profile, path_id)

    if is_authorized is None:
        return HttpResponseNotFound(_("<p>File not found.</p>"))
    if not is_authorized:
        return HttpResponseForbidden(_("<p>You are not authorized to view this file.</p>"))
    if settings.LOCAL_UPLOADS_DIR is not None:
        return serve_local(request, path_id)

    return serve_s3(request, path_id)

def upload_file_backend(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    if len(request.FILES) == 0:
        return json_error(_("You must specify a file to upload"))
    if len(request.FILES) != 1:
        return json_error(_("You may only upload one file at a time"))

    user_file = list(request.FILES.values())[0]
    file_size = user_file._get_size()
    if settings.MAX_FILE_UPLOAD_SIZE * 1024 * 1024 < file_size:
        return json_error(_("Uploaded file is larger than the allowed limit of %s MB") % (
            settings.MAX_FILE_UPLOAD_SIZE))
    check_upload_within_quota(user_profile.realm, file_size)

    if not isinstance(user_file.name, str):
        # It seems that in Python 2 unicode strings containing bytes are
        # rendered differently than ascii strings containing same bytes.
        #
        # Example:
        # >>> print('\xd3\x92')
        # Ӓ
        # >>> print(u'\xd3\x92')
        # Ó
        #
        # This is the cause of the problem as user_file.name variable
        # is received as a unicode which is converted into unicode
        # strings containing bytes and is rendered incorrectly.
        #
        # Example:
        # >>> import urllib.parse
        # >>> name = u'%D0%97%D0%B4%D1%80%D0%B0%D0%B2%D0%B5%D0%B8%CC%86%D1%82%D0%B5.txt'
        # >>> print(urllib.parse.unquote(name))
        # ÐÐ´ÑÐ°Ð²ÐµÐ¸ÌÑÐµ  # This is wrong
        #
        # >>> name = '%D0%97%D0%B4%D1%80%D0%B0%D0%B2%D0%B5%D0%B8%CC%86%D1%82%D0%B5.txt'
        # >>> print(urllib.parse.unquote(name))
        # Здравейте.txt  # This is correct
        user_file.name = user_file.name.encode('ascii')

    uri = upload_message_image_from_request(request, user_file, user_profile)
    return json_success({'uri': uri})
