import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";

export function set_message_reminder(send_at_time: number, message_id: number): void {
    channel.post({
        url: "/json/reminders",
        data: {
            message_id,
            scheduled_delivery_timestamp: send_at_time,
        },
        // TODO: Add success / failure UI feedback.
        error(xhr: JQuery.jqXHR): void {
            blueslip.error(channel.xhr_error_message("Error setting reminder", xhr));
        },
    });
}
