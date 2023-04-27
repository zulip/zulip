from django.utils.translation import gettext as _

from zerver.lib.exceptions import ResourceNotFoundError
from zerver.models import ScheduledMessage, UserProfile


def access_scheduled_message(
    user_profile: UserProfile, scheduled_message_id: int
) -> ScheduledMessage:
    try:
        return ScheduledMessage.objects.get(id=scheduled_message_id, sender=user_profile)
    except ScheduledMessage.DoesNotExist:
        raise ResourceNotFoundError(_("Scheduled message does not exist"))
