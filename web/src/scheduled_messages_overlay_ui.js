import $ from "jquery";

import render_scheduled_message from "../templates/scheduled_message.hbs";
import render_scheduled_messages_overlay from "../templates/scheduled_messages_overlay.hbs";

import * as browser_history from "./browser_history";
import * as messages_overlay_ui from "./messages_overlay_ui";
import * as overlays from "./overlays";
import * as people from "./people";
import * as scheduled_messages from "./scheduled_messages";
import * as scheduled_messages_ui from "./scheduled_messages_ui";
import * as stream_color from "./stream_color";
import * as stream_data from "./stream_data";
import * as sub_store from "./sub_store";
import * as timerender from "./timerender";

export const keyboard_handling_context = {
    get_items_ids() {
        const scheduled_messages_ids = [];
        const sorted_messages = sort_scheduled_messages(scheduled_messages.scheduled_messages_data);
        for (const message of sorted_messages) {
            scheduled_messages_ids.push(message.scheduled_message_id);
        }
        return scheduled_messages_ids;
    },
    on_enter() {
        const focused_element_id = Number.parseInt(
            messages_overlay_ui.get_focused_element_id(this),
            10,
        );
        scheduled_messages_ui.edit_scheduled_message(focused_element_id);
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
        scheduled_messages.delete_scheduled_message(focused_element_id);
    },
    items_container_selector: "overlay-messages-container",
    items_list_selector: "overlay-messages-list",
    row_item_selector: "scheduled-message-row",
    box_item_selector: "overlay-message-info-box",
    id_attribute_name: "data-scheduled-message-id",
};

function sort_scheduled_messages(scheduled_messages) {
    const sorted_messages = [...scheduled_messages.values()].sort(
        (msg1, msg2) => msg1.scheduled_delivery_timestamp - msg2.scheduled_delivery_timestamp,
    );
    return sorted_messages;
}

export function handle_keyboard_events(event_key) {
    messages_overlay_ui.modals_handle_events(event_key, keyboard_handling_context);
}

function format(scheduled_messages) {
    const formatted_msgs = [];
    const sorted_messages = sort_scheduled_messages(scheduled_messages);
    for (const msg of sorted_messages) {
        const msg_render_context = {...msg};
        if (msg.type === "stream") {
            msg_render_context.is_stream = true;
            msg_render_context.stream_id = msg.to;
            msg_render_context.stream_name = sub_store.maybe_get_stream_name(
                msg_render_context.stream_id,
            );
            const color = stream_data.get_color(msg_render_context.stream_id);
            msg_render_context.recipient_bar_color = stream_color.get_recipient_bar_color(color);
            msg_render_context.stream_privacy_icon_color =
                stream_color.get_stream_privacy_icon_color(color);
        } else {
            msg_render_context.is_stream = false;
            msg_render_context.recipients = people.get_recipients(msg.to.join(","));
        }
        const time = new Date(msg.scheduled_delivery_timestamp * 1000);
        msg_render_context.formatted_send_at_time = timerender.get_full_datetime(time, "time");
        formatted_msgs.push(msg_render_context);
    }
    return formatted_msgs;
}

export function launch() {
    $("#scheduled_messages_overlay_container").html(render_scheduled_messages_overlay());
    overlays.open_overlay({
        name: "scheduled",
        $overlay: $("#scheduled_messages_overlay"),
        on_close() {
            browser_history.exit_overlay();
        },
    });

    const rendered_list = render_scheduled_message({
        scheduled_messages_data: format(scheduled_messages.scheduled_messages_data),
    });
    const $messages_list = $("#scheduled_messages_overlay .overlay-messages-list");
    $messages_list.append($(rendered_list));

    const first_element_id = keyboard_handling_context.get_items_ids()[0];
    messages_overlay_ui.set_initial_element(first_element_id, keyboard_handling_context);
}

export function rerender() {
    if (!overlays.scheduled_messages_open()) {
        return;
    }
    const rendered_list = render_scheduled_message({
        scheduled_messages_data: format(scheduled_messages.scheduled_messages_data),
    });
    const $messages_list = $("#scheduled_messages_overlay .overlay-messages-list");
    $messages_list.find(".scheduled-message-row").remove();
    $messages_list.append($(rendered_list));
}

export function remove_scheduled_message_id(scheduled_msg_id) {
    if (overlays.scheduled_messages_open()) {
        $(
            `#scheduled_messages_overlay .scheduled-message-row[data-scheduled-message-id=${scheduled_msg_id}]`,
        ).remove();
    }
}

export function initialize() {
    $("body").on("click", ".scheduled-message-row .restore-overlay-message", (e) => {
        let scheduled_msg_id = $(e.currentTarget)
            .closest(".scheduled-message-row")
            .attr("data-scheduled-message-id");
        scheduled_msg_id = Number.parseInt(scheduled_msg_id, 10);
        scheduled_messages_ui.edit_scheduled_message(scheduled_msg_id);
        overlays.close_overlay("scheduled");
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".scheduled-message-row .delete-overlay-message", (e) => {
        const scheduled_msg_id = $(e.currentTarget)
            .closest(".scheduled-message-row")
            .attr("data-scheduled-message-id");
        scheduled_messages.delete_scheduled_message(scheduled_msg_id);

        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("focus", ".overlay-message-info-box", (e) => {
        messages_overlay_ui.activate_element(e.target, keyboard_handling_context);
    });
}
