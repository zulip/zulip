from django.http import HttpRequest, HttpResponse

from zerver.actions.uploads import do_delete_attachment
from zerver.lib.attachments import access_attachment_by_id, user_attachments
from zerver.lib.response import json_success
from zerver.models import UserProfile


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

    do_delete_attachment(attachment, user_profile)

    return json_success(request)
