import $ from "jquery";
import type * as z from "zod/mini";

import * as channel from "./channel.ts";
import * as feedback_widget from "./feedback_widget.ts";
import {$t} from "./i18n.ts";
import type {StateData, reminder_schema} from "./state_data.ts";
import * as timerender from "./timerender.ts";
import * as ui_report from "./ui_report.ts";

export type Reminder = z.infer<typeof reminder_schema>;

export const reminders_by_id = new Map<number, Reminder>();

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
                hide_delay: 6000,
            });
        },
        error(xhr: JQuery.jqXHR): void {
            ui_report.error($t({defaultMessage: "Failed"}), xhr, $("#home-error"), 2000);
        },
    });
}

export function add_reminders(reminders: Reminder[]): void {
    for (const reminder of reminders) {
        reminders_by_id.set(reminder.reminder_id, reminder);
    }
}

export function initialize(reminders_params: StateData["reminders"]): void {
    add_reminders(reminders_params.reminders);
}

export function remove_reminder(reminder_id: number): void {
    if (reminders_by_id.has(reminder_id)) {
        reminders_by_id.delete(reminder_id);
    }
}

export function delete_reminder(reminder_id: number, success?: () => void): void {
    void channel.del({
        url: "/json/reminders/" + reminder_id,
        success,
    });
}

export function get_count(): number {
    return reminders_by_id.size;
}
