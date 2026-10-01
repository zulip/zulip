from django.db import transaction
from django.http import HttpRequest, HttpResponse

from zerver.lib.attachments import access_attachment_by_id, remove_attachment, user_attachments
from zerver.lib.event_types import (
    AttachmentFieldForAttachmentRemoveEvent,
    AttachmentRemoveEvent,
    RealmUpdateDictEvent,
    UploadQuotaUsedData,
)
from zerver.lib.response import json_success
from zerver.models import UserProfile
from zerver.models.users import active_user_ids
from zerver.tornado.django_api import send_event_on_commit


def list_by_user(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    return json_success(
        request,
        data={
            "attachments": user_attachments(user_profile),
            "upload_space_used": user_profile.realm.currently_used_upload_space_bytes(),
        },
    )


@transaction.atomic(durable=True)
def remove(request: HttpRequest, user_profile: UserProfile, attachment_id: int) -> HttpResponse:
    attachment = access_attachment_by_id(user_profile, attachment_id, needs_owner=True)
    remove_attachment(user_profile, attachment)

    realm = user_profile.realm
    upload_space_used = realm.currently_used_upload_space_bytes()
    event = AttachmentRemoveEvent(
        attachment=AttachmentFieldForAttachmentRemoveEvent(id=attachment_id),
        upload_space_used=upload_space_used,
    )
    send_event_on_commit(realm, event, [user_profile.id])

    # The event above describes one user's file, so it goes only to that
    # user. The organization's total usage isn't private to them though,
    # and clients use it to warn as the organization approaches its upload
    # quota, so it needs to reach everyone.
    if realm.upload_quota_bytes() is not None:
        realm_update_event = RealmUpdateDictEvent(
            property="default",
            data=UploadQuotaUsedData(upload_quota_used_bytes=upload_space_used),
        )
        send_event_on_commit(realm, realm_update_event, active_user_ids(realm.id))
    return json_success(request)
