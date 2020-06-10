from django.http import HttpRequest, HttpResponse

from zerver.lib.actions import notify_attachment_update
from zerver.lib.attachments import access_attachment_by_id, remove_attachment, user_attachments
from zerver.lib.response import json_success
from zerver.models import UserProfile


def list_by_user(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    return json_success({
        "attachments": user_attachments(user_profile),
        "upload_space_used": user_profile.realm.currently_used_upload_space_bytes(),
    })

def remove(request: HttpRequest, user_profile: UserProfile, attachment_id: str) -> HttpResponse:
    attachment = access_attachment_by_id(user_profile, int(attachment_id),
                                         needs_owner=True)
    remove_attachment(user_profile, attachment)
    notify_attachment_update(user_profile, "remove", {"id": int(attachment_id)})
    return json_success()
