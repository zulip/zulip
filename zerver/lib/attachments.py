from __future__ import absolute_import

from django.utils.translation import ugettext as _
from typing import Any, Dict, List

from zerver.lib.request import JsonableError
from zerver.lib.upload import delete_message_image
from zerver.models import Attachment, UserProfile

def user_attachments(user_profile):
    # type: (UserProfile) -> List[Dict[str, Any]]
    attachments = Attachment.objects.filter(owner=user_profile).prefetch_related('messages')
    return [a.to_dict() for a in attachments]

def access_attachment_by_id(user_profile, attachment_id, needs_owner=False):
    # type: (UserProfile, int, bool) -> Attachment
    query = Attachment.objects.filter(id=attachment_id)
    if needs_owner:
        query = query.filter(owner=user_profile)

    attachment = query.first()
    if attachment is None:
        raise JsonableError(_("Invalid attachment"))
    return attachment

def remove_attachment(user_profile, attachment):
    # type: (UserProfile, Attachment) -> None
    delete_message_image(attachment.path_id)
    attachment.delete()
