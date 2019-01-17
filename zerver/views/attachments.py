from django.http import HttpRequest, HttpResponse

from zerver.models import UserProfile
from zerver.lib.actions import notify_attachment_update
from zerver.lib.response import json_success
from zerver.lib.attachments import user_attachments, remove_attachment, \
    access_attachment_by_id


def list_by_user(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    return json_success({"attachments": user_attachments(user_profile)})


def remove(request: HttpRequest, user_profile: UserProfile, attachment_id: str) -> HttpResponse:
    attachment = access_attachment_by_id(user_profile, int(attachment_id),
                                         needs_owner=True)
    remove_attachment(user_profile, attachment)
    notify_attachment_update(user_profile, "remove", {"id": int(attachment_id)})
    return json_success()

def upload_space_used(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    return json_success({"upload_space_used": user_profile.realm.currently_used_upload_space_bytes()})
