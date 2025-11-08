import $ from "jquery";
import type * as z from "zod/mini";

import render_message_reminders from "../templates/message_reminders.hbs";

import * as channel from "./channel.ts";
import * as feedback_widget from "./feedback_widget.ts";
import {$t} from "./i18n.ts";
import * as message_lists from "./message_lists.ts";
import type {StateData, reminder_schema} from "./state_data.ts";
import * as timerender from "./timerender.ts";
import * as ui_report from "./ui_report.ts";

export type Reminder = z.infer<typeof reminder_schema>;

// Used to render reminders in message list.
export type TimeFormattedReminder = {
    reminder_id: number;
    formatted_delivery_time: string;
    scheduled_delivery_timestamp: number;
};

export const reminders_by_id = new Map<number, Reminder>();

export const reminders_by_message_id = new Map<number, TimeFormattedReminder[]>();

export function get_reminders(message_id: number): TimeFormattedReminder[] | undefined {
    return reminders_by_message_id.get(message_id);
}

export function set_message_reminder(send_at_time: number, message_id: number, note: string): void {
    channel.post({
        url: "/json/reminders",
        data: {
            message_id,
            scheduled_delivery_timestamp: send_at_time,
            note,
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
    const message_ids_to_rerender = new Set<number>();
    for (const reminder of reminders) {
        message_ids_to_rerender.add(reminder.reminder_target_message_id);
        reminders_by_id.set(reminder.reminder_id, reminder);

        // Do all the formatting and sorting needed to display
        // reminders for a message to avoid doing at the time of render.
        const formatted_delivery_time = timerender.get_full_datetime(
            new Date(reminder.scheduled_delivery_timestamp * 1000),
            "time",
        );
        const time_formatted_reminder: TimeFormattedReminder = {
            reminder_id: reminder.reminder_id,
            formatted_delivery_time,
            scheduled_delivery_timestamp: reminder.scheduled_delivery_timestamp,
        };
        if (!reminders_by_message_id.has(reminder.reminder_target_message_id)) {
            reminders_by_message_id.set(reminder.reminder_target_message_id, [
                time_formatted_reminder,
            ]);
            continue;
        }
        const message_reminders = get_reminders(reminder.reminder_target_message_id)!;
        message_reminders.push(time_formatted_reminder);
        // Sort reminders to show the earliest one first.
        message_reminders.sort(
            (a, b) => a.scheduled_delivery_timestamp - b.scheduled_delivery_timestamp,
        );
    }

    for (const message_id of message_ids_to_rerender) {
        rerender_reminders_for_message(message_id);
    }
}

export function initialize(reminders_params: StateData["reminders"]): void {
    add_reminders(reminders_params.reminders);
}

export function remove_reminder(reminder_id: number): void {
    if (reminders_by_id.has(reminder_id)) {
        reminders_by_id.delete(reminder_id);

        for (const [message_id, message_reminders] of reminders_by_message_id) {
            const index = message_reminders.findIndex((r) => r.reminder_id === reminder_id);
            if (index !== -1) {
                message_reminders.splice(index, 1);
                if (message_reminders.length === 0) {
                    reminders_by_message_id.delete(message_id);
                }
                rerender_reminders_for_message(message_id);
                break;
            }
        }
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

export function rerender_reminders_for_message(message_id: number): void {
    const $rows = message_lists.all_rendered_row_for_message_id(message_id);
    if ($rows.length === 0) {
        return;
    }

    const message_reminders = get_reminders(message_id) ?? [];
    if (message_reminders.length === 0) {
        $rows.find(".message-reminders").remove();
        return;
    }

    const rendered_message_reminders_html = render_message_reminders({
        msg: {
            reminders: message_reminders,
        },
    });

    $rows.each(function () {
        const $row = $(this);
        const $existing = $row.find(".message-reminders");
        if ($existing.length > 0) {
            $existing.replaceWith($(rendered_message_reminders_html));
        } else {
            // Insert after reactions if they exist, otherwise after "more" section.
            const $content = $row.find(".messagebox-content");
            $content.append($(rendered_message_reminders_html));
        }
    });
}
