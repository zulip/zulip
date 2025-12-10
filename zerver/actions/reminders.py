import datetime

from django.db import transaction

from zerver.actions.message_send import check_message
from zerver.actions.scheduled_messages import do_schedule_messages
from zerver.lib.addressee import Addressee
from zerver.lib.message import access_message
from zerver.lib.reminders import get_reminder_formatted_content, notify_remove_reminder
from zerver.models import Client, ScheduledMessage, UserProfile


def schedule_reminder_for_message(
    current_user: UserProfile,
    client: Client,
    message_id: int,
    deliver_at: datetime.datetime,
    note: str,
) -> int:
    message = access_message(current_user, message_id, is_modifying_message=False)
    # Even though reminder will be sent from NOTIFICATION_BOT, we still
    # set current_user as the sender here to help us make the permission checks easier.
    addressee = Addressee.for_user_profile(current_user)
    # This can raise an exception in the unlikely event that the current user cannot DM themself.
    send_request = check_message(
        current_user,
        client,
        addressee,
        get_reminder_formatted_content(message, current_user, note),
        current_user.realm,
    )
    send_request.deliver_at = deliver_at
    send_request.reminder_target_message_id = message_id
    send_request.reminder_note = note

    return do_schedule_messages(
        [send_request],
        current_user,
        read_by_sender=False,
        delivery_type=ScheduledMessage.REMIND,
    )[0]


@transaction.atomic(durable=True)
def do_delete_reminder(user_profile: UserProfile, reminder: ScheduledMessage) -> None:
    assert reminder.delivery_type == ScheduledMessage.REMIND
    reminder_id = reminder.id
    reminder.delete()
    notify_remove_reminder(user_profile, reminder_id)
