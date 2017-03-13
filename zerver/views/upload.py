# -*- coding: utf-8 -*-
from __future__ import absolute_import

from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, FileResponse, \
    HttpResponseNotFound
from django.shortcuts import redirect
from django.utils.translation import ugettext as _

from zerver.decorator import authenticated_json_post_view
from zerver.lib.request import has_request_variables, REQ
from zerver.lib.response import json_success, json_error
from zerver.lib.upload import upload_message_image_from_request, get_local_file_path, \
    get_signed_upload_url, get_realm_for_filename, within_upload_quota
from zerver.lib.validator import check_bool
from zerver.models import UserProfile
from django.conf import settings

def serve_s3(request, user_profile, realm_id_str, filename):
    # type: (HttpRequest, UserProfile, str, str) -> HttpResponse
    url_path = "%s/%s" % (realm_id_str, filename)

    if realm_id_str == "unk":
        realm_id = get_realm_for_filename(url_path)
        if realm_id is None:
            # File does not exist
            return HttpResponseNotFound('<p>File not found</p>')
    else:
        realm_id = int(realm_id_str)

    # Internal users can access all uploads so we can receive attachments in cross-realm messages
    if user_profile.realm_id == realm_id or user_profile.realm.string_id == 'zulip':
        uri = get_signed_upload_url(url_path)
        return redirect(uri)
    else:
        return HttpResponseForbidden()

# TODO: Rewrite this once we have django-sendfile
def serve_local(request, path_id):
    # type: (HttpRequest, str) -> HttpResponse
    import os
    import mimetypes
    local_path = get_local_file_path(path_id)
    if local_path is None:
        return HttpResponseNotFound('<p>File not found</p>')
    filename = os.path.basename(local_path)
    response = FileResponse(open(local_path, 'rb'),
                            content_type = mimetypes.guess_type(filename))
    return response

@has_request_variables
def serve_file_backend(request, user_profile, realm_id_str, filename):
    # type: (HttpRequest, UserProfile, str, str) -> HttpResponse
    path_id = "%s/%s" % (realm_id_str, filename)
    if settings.LOCAL_UPLOADS_DIR is not None:
        return serve_local(request, path_id)

    return serve_s3(request, user_profile, realm_id_str, filename)

@authenticated_json_post_view
def json_upload_file(request, user_profile):
    # type: (HttpRequest, UserProfile) -> HttpResponse
    return upload_file_backend(request, user_profile)

def upload_file_backend(request, user_profile):
    # type: (HttpRequest, UserProfile) -> HttpResponse
    if len(request.FILES) == 0:
        return json_error(_("You must specify a file to upload"))
    if len(request.FILES) != 1:
        return json_error(_("You may only upload one file at a time"))

    user_file = list(request.FILES.values())[0]
    file_size = user_file._get_size()
    if settings.MAX_FILE_UPLOAD_SIZE * 1024 * 1024 < file_size:
        return json_error(_("Uploaded file is larger than the allowed limit of %s MB") % (
            settings.MAX_FILE_UPLOAD_SIZE))
    if not within_upload_quota(user_profile, file_size):
        return json_error(_("Upload would exceed your maximum quota."))

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
        # >>> from six.moves import urllib
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
