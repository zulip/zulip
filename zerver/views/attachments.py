from django.http import HttpRequest, HttpResponse

from zerver.lib.attachments import access_attachment_by_id, remove_attachment, user_attachments
from zerver.lib.event_types import AttachmentRemoveEvent, IdHolder
from zerver.lib.response import json_success
from zerver.models import UserProfile
from zerver.tornado.django_api import send_event_on_commit


def list_by_user(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    return json_success(
        request,
        data={
            "attachments": user_attachments(user_profile),
            "upload_space_used": user_profile.realm.currently_used_upload_space_bytes(),
        },
    )


def remove(request: HttpRequest, user_profile: UserProfile, attachment_id: int) -> HttpResponse:
    attachment = access_attachment_by_id(user_profile, attachment_id, needs_owner=True)
    remove_attachment(user_profile, attachment)
    event = AttachmentRemoveEvent(
        attachment=IdHolder(id=attachment_id),
        upload_space_used=user_profile.realm.currently_used_upload_space_bytes(),
    )
    send_event_on_commit(user_profile.realm, event, [user_profile.id])
    return json_success(request)
