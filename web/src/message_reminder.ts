import $ from "jquery";

import * as channel from "./channel.ts";
import * as feedback_widget from "./feedback_widget.ts";
import {$t} from "./i18n.ts";
import * as timerender from "./timerender.ts";
import * as ui_report from "./ui_report.ts";

export function set_message_reminder(send_at_time: number, message_id: number): void {
    channel.post({
        url: "/json/reminders",
        data: {
            message_id,
            scheduled_delivery_timestamp: send_at_time,
        },
        success(): void {
            const populate: (element: JQuery) => void = ($container) => {
                $container.html(
                    $t(
                        {defaultMessage: "Your reminder has been scheduled for {translated_time}."},
                        {
                            translated_time: timerender.get_full_datetime(
                                new Date(send_at_time * 1000),
                                "time",
                            ),
                        },
                    ),
                );
            };
            const title_text = $t({defaultMessage: "Reminder scheduled"});
            feedback_widget.show({
                populate,
                title_text,
            });
        },
        error(xhr: JQuery.jqXHR): void {
            ui_report.error($t({defaultMessage: "Failed"}), xhr, $("#home-error"), 2000);
        },
    });
}
