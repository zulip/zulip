import $ from "jquery";
import assert from "minimalistic-assert";

import render_reminder_list from "../templates/reminder_list.hbs";
import render_reminders_overlay from "../templates/reminders_overlay.hbs";

import * as browser_history from "./browser_history.ts";
import * as message_reminder from "./message_reminder.ts";
import type {Reminder} from "./message_reminder.ts";
import * as messages_overlay_ui from "./messages_overlay_ui.ts";
import * as overlays from "./overlays.ts";
import * as timerender from "./timerender.ts";

type ReminderRenderContext = Reminder & {
    formatted_send_at_time: string;
};

export const keyboard_handling_context = {
    get_items_ids() {
        const reminders_ids = [];
        const sorted_reminders = sort_reminders(message_reminder.reminders_by_id);
        for (const reminder of sorted_reminders) {
            reminders_ids.push(reminder.reminder_id.toString());
        }
        return reminders_ids;
    },
    on_enter() {
        // TODO: Allow editing reminder.
        return;
    },
    on_delete() {
        const focused_element_id = messages_overlay_ui.get_focused_element_id(this);
        if (focused_element_id === undefined) {
            return;
        }
        const $focused_row = messages_overlay_ui.row_with_focus(this);
        messages_overlay_ui.focus_on_sibling_element(this);
        // We need to have a super responsive UI feedback here, so we remove the row from the DOM manually
        $focused_row.remove();
        message_reminder.delete_reminder(Number.parseInt(focused_element_id, 10));
    },
    items_container_selector: "reminders-container",
    items_list_selector: "reminders-list",
    row_item_selector: "reminder-row",
    box_item_selector: "reminder-info-box",
    id_attribute_name: "data-reminder-id",
};

function sort_reminders(reminders: Map<number, Reminder>): Reminder[] {
    const sorted_reminders = [...reminders.values()].sort(
        (reminder1, reminder2) =>
            reminder1.scheduled_delivery_timestamp - reminder2.scheduled_delivery_timestamp,
    );
    return sorted_reminders;
}

export function handle_keyboard_events(event_key: string): void {
    messages_overlay_ui.modals_handle_events(event_key, keyboard_handling_context);
}

function format(reminders: Map<number, Reminder>): ReminderRenderContext[] {
    const formatted_reminders = [];
    const sorted_reminders = sort_reminders(reminders);

    for (const reminder of sorted_reminders) {
        const time = new Date(reminder.scheduled_delivery_timestamp * 1000);
        const formatted_send_at_time = timerender.get_full_datetime(time, "time");
        const reminder_render_context = {
            ...reminder,
            formatted_send_at_time,
        };
        formatted_reminders.push(reminder_render_context);
    }
    return formatted_reminders;
}

export function launch(): void {
    $("#reminders-overlay-container").html(render_reminders_overlay());
    overlays.open_overlay({
        name: "reminders",
        $overlay: $("#reminders-overlay"),
        on_close() {
            browser_history.exit_overlay();
        },
    });

    const rendered_list = render_reminder_list({
        reminders_data: format(message_reminder.reminders_by_id),
    });
    const $messages_list = $("#reminders-overlay .overlay-messages-list");
    $messages_list.append($(rendered_list));

    const first_element_id = keyboard_handling_context.get_items_ids()[0];
    messages_overlay_ui.set_initial_element(first_element_id, keyboard_handling_context);
}

export function rerender(): void {
    if (!overlays.reminders_open()) {
        return;
    }
    const rendered_list = render_reminder_list({
        reminders_data: format(message_reminder.reminders_by_id),
    });
    const $messages_list = $("#reminders-overlay .overlay-messages-list");
    $messages_list.find(".reminder-row").remove();
    $messages_list.append($(rendered_list));
}

export function remove_reminder_id(reminder_id: number): void {
    if (overlays.reminders_open()) {
        $(`#reminders-overlay .reminder-row[data-reminder-id=${reminder_id}]`).remove();
    }
}

export function initialize(): void {
    $("body").on("click", ".reminder-row .delete-overlay-message", (e) => {
        const scheduled_msg_id = $(e.currentTarget)
            .closest(".reminder-row")
            .attr("data-reminder-id");
        assert(scheduled_msg_id !== undefined);

        message_reminder.delete_reminder(Number.parseInt(scheduled_msg_id, 10));

        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("focus", ".reminder-info-box", function (this: HTMLElement) {
        messages_overlay_ui.activate_element(this, keyboard_handling_context);
    });
}
