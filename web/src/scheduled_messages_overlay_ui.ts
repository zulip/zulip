import {$} from "jquery";
import assert from "minimalistic-assert";

import render_scheduled_message from "../templates/scheduled_message.hbs";
import render_scheduled_messages_overlay from "../templates/scheduled_messages_overlay.hbs";

import * as browser_history from "./browser_history.ts";
import * as messages_overlay_ui from "./messages_overlay_ui.ts";
import * as mouse_drag from "./mouse_drag.ts";
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

type ScheduledMessageRenderContext = ScheduledMessage & {
    split_message_count: number;
    is_split_message: boolean;
    split_message_ids: string;
} & (
        | {
              is_stream: true;
              formatted_send_at_time: string;
              recipient_bar_color: string;
              stream_id: number;
              stream_name: string | undefined;
              stream_privacy_icon_color: string;
              topic_display_name: string;
              is_empty_string_topic: boolean;
          }
        | {
              is_stream: false;
              is_dm_with_self: boolean;
              formatted_send_at_time: string;
              recipients: string;
          }
    );

function get_row_part_ids(row_scheduled_message_id: number): number[] {
    const sorted_scheduled_messages = sort_scheduled_messages(
        scheduled_messages.get_all_scheduled_messages(),
    );
    for (const group of group_split_scheduled_messages(sorted_scheduled_messages)) {
        if (group.part_ids[0] === row_scheduled_message_id) {
            return group.part_ids;
        }
    }
    return [row_scheduled_message_id];
}

function edit_scheduled_message_row(row_scheduled_message_id: number): void {
    const part_ids = get_row_part_ids(row_scheduled_message_id);
    if (part_ids.length > 1) {
        scheduled_messages_ui.undo_split_scheduled_messages(part_ids);
    } else {
        scheduled_messages_ui.edit_scheduled_message(row_scheduled_message_id);
    }
    overlays.close_overlay("scheduled");
}

export const keyboard_handling_context = {
    get_items_ids() {
        const sorted_scheduled_messages = sort_scheduled_messages(
            scheduled_messages.get_all_scheduled_messages(),
        );
        return group_split_scheduled_messages(sorted_scheduled_messages).map((group) =>
            group.part_ids[0]!.toString(),
        );
    },
    on_enter() {
        const focused_element_id = messages_overlay_ui.get_focused_element_id(this);
        if (focused_element_id === undefined) {
            return;
        }
        edit_scheduled_message_row(Number.parseInt(focused_element_id, 10));
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
        const part_ids = get_row_part_ids(Number.parseInt(focused_element_id, 10));
        for (const part_id of part_ids) {
            scheduled_messages.delete_scheduled_message(part_id);
        }
    },
    items_container_selector: "scheduled-messages-container",
    items_list_selector: "scheduled-messages-list",
    row_item_selector: "scheduled-message-row",
    box_item_selector: "scheduled-message-info-box",
    id_attribute_name: "data-scheduled-message-id",
};

function sort_scheduled_messages(scheduled_messages: ScheduledMessage[]): ScheduledMessage[] {
    return scheduled_messages.toSorted(
        (msg1, msg2) => msg1.scheduled_delivery_timestamp - msg2.scheduled_delivery_timestamp,
    );
}

export function handle_keyboard_events(event_key: string): void {
    messages_overlay_ui.modals_handle_events(event_key, keyboard_handling_context);
}

function group_split_scheduled_messages(
    sorted_scheduled_messages: ScheduledMessage[],
): {scheduled_msg: ScheduledMessage; part_ids: number[]; combined_rendered_content: string}[] {
    const groups: {
        scheduled_msg: ScheduledMessage;
        part_ids: number[];
        combined_rendered_content: string;
    }[] = [];
    const group_index_by_id = new Map<string, number>();

    for (const scheduled_msg of sorted_scheduled_messages) {
        const existing_index =
            scheduled_msg.split_group_id === null
                ? undefined
                : group_index_by_id.get(scheduled_msg.split_group_id);
        if (existing_index === undefined) {
            if (scheduled_msg.split_group_id !== null) {
                group_index_by_id.set(scheduled_msg.split_group_id, groups.length);
            }
            groups.push({
                scheduled_msg,
                part_ids: [scheduled_msg.scheduled_message_id],
                combined_rendered_content: scheduled_msg.rendered_content,
            });
        } else {
            const group = groups[existing_index]!;
            group.part_ids.push(scheduled_msg.scheduled_message_id);
            group.combined_rendered_content += scheduled_msg.rendered_content;
        }
    }
    return groups;
}

function format(scheduled_messages: ScheduledMessage[]): ScheduledMessageRenderContext[] {
    const formatted_scheduled_msgs = [];
    const sorted_scheduled_messages = sort_scheduled_messages(scheduled_messages);

    for (const group of group_split_scheduled_messages(sorted_scheduled_messages)) {
        const scheduled_msg = group.scheduled_msg;
        const split_message_count = group.part_ids.length;
        const is_split_message = split_message_count > 1;
        const split_message_ids = group.part_ids.join(",");
        const rendered_content = group.combined_rendered_content;
        let scheduled_msg_render_context;
        const time = new Date(scheduled_msg.scheduled_delivery_timestamp * 1000);
        const formatted_send_at_time = timerender.get_full_datetime(time, "time");
        if (scheduled_msg.type === "stream") {
            const stream_id = scheduled_msg.to;
            let stream_name;
            const stream = sub_store.get(stream_id);
            if (stream) {
                stream_name = sub_store.maybe_get_stream_name(stream_id);
            }
            const color = stream_data.get_color(stream_id);
            const recipient_bar_color = stream_color.get_recipient_bar_color(color);
            const stream_privacy_icon_color = stream_color.get_stream_privacy_icon_color(color);

            scheduled_msg_render_context = {
                ...scheduled_msg,
                rendered_content,
                split_message_count,
                is_split_message,
                split_message_ids,
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
                rendered_content,
                split_message_count,
                is_split_message,
                split_message_ids,
                is_stream: false as const,
                is_dm_with_self: people.is_direct_message_conversation_with_self(scheduled_msg.to),
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

    const restore_id = messages_overlay_ui.get_and_clear_pending_restore_element_id();
    if (
        restore_id === undefined ||
        !messages_overlay_ui.try_set_initial_element(restore_id, keyboard_handling_context)
    ) {
        const first_element_id = keyboard_handling_context.get_items_ids()[0];
        messages_overlay_ui.set_initial_element(first_element_id, keyboard_handling_context);
    }
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
    if (!overlays.scheduled_messages_open()) {
        return;
    }
    for (const row of $("#scheduled_messages_overlay .scheduled-message-row")) {
        const $row = $(row);
        const part_ids = ($row.attr("data-split-message-ids") ?? "")
            .split(",")
            .filter((id) => id !== "")
            .map((id) => Number.parseInt(id, 10));
        const row_id = Number.parseInt($row.attr("data-scheduled-message-id")!, 10);
        if (row_id === scheduled_msg_id || part_ids.includes(scheduled_msg_id)) {
            $row.remove();
        }
    }
}

export function initialize(): void {
    $("body").on("click", ".scheduled-message-row .restore-overlay-message", (e) => {
        if (mouse_drag.is_drag(e)) {
            return;
        }
        if (
            messages_overlay_ui.handle_overlay_media_click(
                e,
                "scheduled",
                keyboard_handling_context,
                () => {
                    browser_history.go_to_location("#scheduled");
                },
            )
        ) {
            return;
        }

        const scheduled_msg_id = Number.parseInt(
            $(e.currentTarget).closest(".scheduled-message-row").attr("data-scheduled-message-id")!,
            10,
        );
        edit_scheduled_message_row(scheduled_msg_id);
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".scheduled-message-row .delete-overlay-message", (e) => {
        const scheduled_msg_id = $(e.currentTarget)
            .closest(".scheduled-message-row")
            .attr("data-scheduled-message-id");
        assert(scheduled_msg_id !== undefined);

        const part_ids = get_row_part_ids(Number.parseInt(scheduled_msg_id, 10));
        for (const part_id of part_ids) {
            scheduled_messages.delete_scheduled_message(part_id);
        }

        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("focus", ".scheduled-message-info-box", function (this: HTMLElement) {
        messages_overlay_ui.activate_element(this, keyboard_handling_context);
    });
}
