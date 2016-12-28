from zerver.models import Attachment, UserProfile


def user_attachments(user_profile):
    # type: (UserProfile) -> list[dict]
    attachments = Attachment.objects.filter(owner=user_profile).prefetch_related('messages')
    return [a.to_dict() for a in attachments]


def remove_attachment(user_profile, pk):
    # type: (UserProfile, int) -> None
    Attachment.objects.filter(owner=user_profile, pk=pk).delete()
