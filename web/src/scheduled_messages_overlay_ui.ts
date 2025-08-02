import $ from "jquery";
import assert from "minimalistic-assert";

import render_scheduled_message from "../templates/scheduled_message.hbs";
import render_scheduled_messages_overlay from "../templates/scheduled_messages_overlay.hbs";

import * as browser_history from "./browser_history.ts";
import * as messages_overlay_ui from "./messages_overlay_ui.ts";
import * as overlays from "./overlays.ts";
import * as people from "./people.ts";
import * as scheduled_messages from "./scheduled_messages.ts";
import type {ScheduledMessage} from "./scheduled_messages.ts";
import * as scheduled_messages_ui from "./scheduled_messages_ui.ts";
import * as stream_color from "./stream_color.ts";
import * as stream_data from "./stream_data.ts";
import * as sub_store from "./sub_store.ts";
import * as timerender from "./timerender.ts";
import * as util from "./util.ts";

type ScheduledMessageRenderContext = ScheduledMessage &
    (
        | {
              is_stream: true;
              formatted_send_at_time: string;
              recipient_bar_color: string;
              stream_id: number;
              stream_name: string;
              stream_privacy_icon_color: string;
              topic_display_name: string;
              is_empty_string_topic: boolean;
          }
        | {
              is_stream: false;
              formatted_send_at_time: string;
              recipients: string;
          }
    );

export const keyboard_handling_context = {
    get_items_ids() {
        const scheduled_messages_ids = [];
        const sorted_scheduled_messages = sort_scheduled_messages(
            scheduled_messages.get_all_scheduled_messages(),
        );
        for (const scheduled_message of sorted_scheduled_messages) {
            scheduled_messages_ids.push(scheduled_message.scheduled_message_id.toString());
        }
        return scheduled_messages_ids;
    },
    on_enter() {
        const focused_element_id = messages_overlay_ui.get_focused_element_id(this);
        if (focused_element_id === undefined) {
            return;
        }
        scheduled_messages_ui.edit_scheduled_message(Number.parseInt(focused_element_id, 10));
        overlays.close_overlay("scheduled");
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
        scheduled_messages.delete_scheduled_message(Number.parseInt(focused_element_id, 10));
    },
    items_container_selector: "scheduled-messages-container",
    items_list_selector: "scheduled-messages-list",
    row_item_selector: "scheduled-message-row",
    box_item_selector: "scheduled-message-info-box",
    id_attribute_name: "data-scheduled-message-id",
};

function sort_scheduled_messages(scheduled_messages: ScheduledMessage[]): ScheduledMessage[] {
    const sorted_scheduled_messages = scheduled_messages.sort(
        (msg1, msg2) => msg1.scheduled_delivery_timestamp - msg2.scheduled_delivery_timestamp,
    );
    return sorted_scheduled_messages;
}

export function handle_keyboard_events(event_key: string): void {
    messages_overlay_ui.modals_handle_events(event_key, keyboard_handling_context);
}

function format(scheduled_messages: ScheduledMessage[]): ScheduledMessageRenderContext[] {
    const formatted_scheduled_msgs = [];
    const sorted_scheduled_messages = sort_scheduled_messages(scheduled_messages);

    for (const scheduled_msg of sorted_scheduled_messages) {
        let scheduled_msg_render_context;
        const time = new Date(scheduled_msg.scheduled_delivery_timestamp * 1000);
        const formatted_send_at_time = timerender.get_full_datetime(time, "time");
        if (scheduled_msg.type === "stream") {
            const stream_id = scheduled_msg.to;
            const stream_name = sub_store.maybe_get_stream_name(stream_id);
            const color = stream_data.get_color(stream_id);
            const recipient_bar_color = stream_color.get_recipient_bar_color(color);
            const stream_privacy_icon_color = stream_color.get_stream_privacy_icon_color(color);

            assert(stream_name !== undefined);
            scheduled_msg_render_context = {
                ...scheduled_msg,
                is_stream: true as const,
                stream_id,
                stream_name,
                recipient_bar_color,
                stream_privacy_icon_color,
                formatted_send_at_time,
                topic_display_name: util.get_final_topic_display_name(scheduled_msg.topic),
                is_empty_string_topic: scheduled_msg.topic === "",
            };
        } else {
            const user_ids_string = scheduled_msg.to.join(",");
            const recipients = people.format_recipients(user_ids_string, "long");
            scheduled_msg_render_context = {
                ...scheduled_msg,
                is_stream: false as const,
                recipients,
                formatted_send_at_time,
            };
        }
        formatted_scheduled_msgs.push(scheduled_msg_render_context);
    }
    return formatted_scheduled_msgs;
}

export function launch(): void {
    $("#scheduled_messages_overlay_container").html(render_scheduled_messages_overlay());
    overlays.open_overlay({
        name: "scheduled",
        $overlay: $("#scheduled_messages_overlay"),
        on_close() {
            browser_history.exit_overlay();
        },
    });

    const rendered_list = render_scheduled_message({
        scheduled_messages_data: format(scheduled_messages.get_all_scheduled_messages()),
    });
    const $messages_list = $("#scheduled_messages_overlay .overlay-messages-list");
    $messages_list.append($(rendered_list));

    const first_element_id = keyboard_handling_context.get_items_ids()[0];
    messages_overlay_ui.set_initial_element(first_element_id, keyboard_handling_context);
}

export function rerender(): void {
    if (!overlays.scheduled_messages_open()) {
        return;
    }
    const rendered_list = render_scheduled_message({
        scheduled_messages_data: format(scheduled_messages.get_all_scheduled_messages()),
    });
    const $messages_list = $("#scheduled_messages_overlay .overlay-messages-list");
    $messages_list.find(".scheduled-message-row").remove();
    $messages_list.append($(rendered_list));
}

export function remove_scheduled_message_id(scheduled_msg_id: number): void {
    if (overlays.scheduled_messages_open()) {
        $(
            `#scheduled_messages_overlay .scheduled-message-row[data-scheduled-message-id=${scheduled_msg_id}]`,
        ).remove();
    }
}

export function initialize(): void {
    $("body").on("click", ".scheduled-message-row .restore-overlay-message", (e) => {
        if (document.getSelection()?.type === "Range") {
            return;
        }

        const scheduled_msg_id = Number.parseInt(
            $(e.currentTarget).closest(".scheduled-message-row").attr("data-scheduled-message-id")!,
            10,
        );
        scheduled_messages_ui.edit_scheduled_message(scheduled_msg_id);
        overlays.close_overlay("scheduled");
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".scheduled-message-row .delete-overlay-message", (e) => {
        const scheduled_msg_id = $(e.currentTarget)
            .closest(".scheduled-message-row")
            .attr("data-scheduled-message-id");
        assert(scheduled_msg_id !== undefined);

        scheduled_messages.delete_scheduled_message(Number.parseInt(scheduled_msg_id, 10));

        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("focus", ".scheduled-message-info-box", function (this: HTMLElement) {
        messages_overlay_ui.activate_element(this, keyboard_handling_context);
    });
}
