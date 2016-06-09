from __future__ import absolute_import

from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect
from django.utils.translation import ugettext as _

from zerver.decorator import authenticated_json_post_view, zulip_login_required
from zerver.lib.request import has_request_variables, REQ
from zerver.lib.response import json_success, json_error
from zerver.lib.upload import upload_message_image_from_request, \
    get_signed_upload_url, get_realm_for_filename
from zerver.lib.validator import check_bool
from zerver.models import UserProfile
from django.conf import settings

def upload_file_backend(request, user_profile):
    # type: (HttpRequest, UserProfile) -> HttpResponse
    if len(request.FILES) == 0:
        return json_error(_("You must specify a file to upload"))
    if len(request.FILES) != 1:
        return json_error(_("You may only upload one file at a time"))

    user_file = list(request.FILES.values())[0]
    if ((settings.MAX_FILE_UPLOAD_SIZE * 1024 * 1024) < user_file._get_size()):
        return json_error(_("File Upload is larger than allowed limit"))

    uri = upload_message_image_from_request(request, user_file, user_profile)
    return json_success({'uri': uri})

def serve_s3(request, user_profile, realm_id_str, filename, redir):
    # type: (HttpRequest, UserProfile, str, str, bool) -> HttpResponse
    url_path = "%s/%s" % (realm_id_str, filename)

    if realm_id_str == "unk":
        realm_id = get_realm_for_filename(url_path)
        if realm_id is None:
            # File does not exist
            return json_error(_("That file does not exist."), status=404)
    else:
        realm_id = int(realm_id_str)

    # Internal users can access all uploads so we can receive attachments in cross-realm messages
    if user_profile.realm.id == realm_id or user_profile.realm.domain == 'zulip.com':
        uri = get_signed_upload_url(url_path)
        if redir:
            return redirect(uri)
        else:
            return json_success({'uri': uri})
    else:
        return HttpResponseForbidden()

def serve_file_backend(request, user_profile, realm_id_str, filename, redir):
    # type: (HttpRequest, UserProfile, str, str, bool) -> HttpResponse
    if settings.LOCAL_UPLOADS_DIR is not None:
         return HttpResponseForbidden() # Should have been served by nginx

    return serve_s3(request, user_profile, realm_id_str, filename, redir)

@authenticated_json_post_view
@has_request_variables
def json_upload_file(request, user_profile):
    # type: (HttpRequest, UserProfile) -> HttpResponse
    return upload_file_backend(request, user_profile)

@zulip_login_required
@has_request_variables
def get_uploaded_file(request, realm_id_str, filename,
                      redir=REQ(validator=check_bool, default=True)):
    # type: (HttpRequest, str, str, bool) -> HttpResponse
    user_profile = request.user
    return serve_file_backend(request, user_profile, realm_id_str, filename, redir)

