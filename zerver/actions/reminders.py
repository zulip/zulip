import datetime

from zerver.actions.message_send import check_message
from zerver.actions.scheduled_messages import do_schedule_messages
from zerver.lib.addressee import Addressee
from zerver.lib.reminders import access_message_for_reminder
from zerver.models import Client, ScheduledMessage, UserProfile


def check_reminders_message(
    current_user: UserProfile,
    client: Client,
    message_id: int,
    deliver_at: datetime.datetime,
) -> int:
    message = access_message_for_reminder(current_user, message_id)
    # Even though reminder will be sent from NOTIFICATION_BOT, we still
    # set current_user as the sender here to help us make the permission checks easier.
    addressee = Addressee.legacy_build(
        current_user,
        "private",
        [current_user.id],
        None,
        current_user.realm,
    )
    send_request = check_message(
        current_user,
        client,
        addressee,
        # Store the content for displaying scheduled reminders in the UI,
        # it will be modified before sending to the user.
        message.content,
        realm=current_user.realm,
        forwarder_user_profile=current_user,
    )
    send_request.deliver_at = deliver_at
    send_request.reminder_target_message_id = message_id

    return do_schedule_messages([send_request], current_user, ScheduledMessage.REMIND)[0]
