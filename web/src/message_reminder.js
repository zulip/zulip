import * as blueslip from "./blueslip";
import * as channel from "./channel";
import * as modals from "./modals";

export function set_message_reminder(send_at_time, message_id) {
    modals.close_if_open("send_later_modal");

    if (!Number.isInteger(send_at_time)) {
        // Convert to timestamp if this is not a timestamp.
        send_at_time = Math.floor(Date.parse(send_at_time) / 1000);
    }

    channel.post({
        url: "/json/reminders",
        data: {
            message_id,
            scheduled_delivery_timestamp: send_at_time,
        },
        // TODO: Add success UI feedback.
        error(xhr) {
            blueslip.log(
                `Failed to set reminder for message with id ${message_id} at ${send_at_time}: ${xhr}`,
            );
        },
    });
}
