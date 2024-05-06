import $ from "jquery";

import * as inbox_util from "./inbox_util";
import type {MessageListData} from "./message_list_data";
import type {Message} from "./message_store";
import {stringify_time} from "./timerender";
import * as ui_util from "./ui_util";

// TODO(typescript): Move this to message_list_view when it's
// converted to typescript.
type MessageListView = {
    update_recipient_bar_background_color: () => void;
    rerender_messages: (messages: Message[], message_content_edited?: boolean) => void;
    _render_win_start: number;
    _render_win_end: number;
    sticky_recipient_message_id: number | undefined;
    $list: JQuery;
};

export type RenderInfo = {need_user_to_scroll: boolean};

export type SelectIdOpts = {
    then_scroll?: boolean;
    target_scroll_offset?: number;
    use_closest?: boolean;
    empty_ok?: boolean;
    mark_read?: boolean;
    force_rerender?: boolean;
    from_scroll?: boolean;
};

export type MessageList = {
    id: number;
    preserve_rendered_state: boolean;
    view: MessageListView;
    selected_id: () => number;
    selected_row: () => JQuery;
    selected_idx: () => number;
    all_messages: () => Message[];
    get: (id: number) => Message | undefined;
    can_mark_messages_read_without_setting: () => boolean;
    rerender_view: () => void;
    resume_reading: () => void;
    data: MessageListData;
    select_id: (message_id: number, opts?: SelectIdOpts) => void;
    get_row: (message_id: number) => JQuery;
    add_messages: (
        messages: Message[],
        append_opts: {messages_are_new: boolean},
    ) => RenderInfo | undefined;
    last: () => Message | undefined;
};

export let current: MessageList | undefined;
export const rendered_message_lists = new Map<number, MessageList>();

export function set_current(msg_list: MessageList | undefined): void {
    // NOTE: Strictly used for mocking in node tests.
    // Use `update_current_message_list` instead in production.
    current = msg_list;
}

export function update_current_message_list(msg_list: MessageList | undefined): void {
    if (current && !current.preserve_rendered_state) {
        // Remove the current message list from the DOM.
        current.view.$list.remove();
        rendered_message_lists.delete(current.id);
    } else {
        current?.view.$list.removeClass("focused-message-list");
    }

    current = msg_list;
    if (current !== undefined) {
        rendered_message_lists.set(current.id, current);
        current.view.$list.addClass("focused-message-list");
    }
}

export function all_rendered_message_lists(): MessageList[] {
    return [...rendered_message_lists.values()];
}

export function add_rendered_message_list(msg_list: MessageList): void {
    rendered_message_lists.set(msg_list.id, msg_list);
}

export function all_rendered_row_for_message_id(message_id: number): JQuery {
    let $rows = $();
    for (const msg_list of all_rendered_message_lists()) {
        const $row = msg_list.get_row(message_id);
        $rows = $rows.add($row);
    }
    return $rows;
}

export function all_current_message_rows(): JQuery {
    if (current === undefined) {
        return $();
    }

    return current.view.$list.find(".message_row");
}

export function update_recipient_bar_background_color(): void {
    for (const msg_list of all_rendered_message_lists()) {
        msg_list.view.update_recipient_bar_background_color();
    }
    inbox_util.update_stream_colors();
}

export function calculate_timestamp_widths(): void {
    const $temp_time_div = $("<div>");
    $temp_time_div.attr("id", "calculated-timestamp-widths");
    // Size the div to the width of the largest timestamp,
    // but the div out of the document flow with absolute positioning.
    $temp_time_div.css({
        width: "max-content",
        visibility: "hidden",
        position: "absolute",
        top: "-100vh",
    });
    // We should get a reasonable max-width by looking only at
    // the first and last minutes of AM and PM
    const candidate_times = ["00:00", "11:59", "12:00", "23:59"];

    for (const time of candidate_times) {
        const $temp_time_element = $("<a>");
        $temp_time_element.attr("class", "message-time");
        // stringify_time only returns the time, so the date here is
        // arbitrary and only required for creating a Date object
        const candidate_timestamp = stringify_time(Date.parse(`1999-07-01T${time}`));
        $temp_time_element.text(candidate_timestamp);
        $temp_time_div.append($temp_time_element);
    }

    // Append the <div> element to calculate the maximum rendered width
    $("body").append($temp_time_div);
    const max_timestamp_width = $temp_time_div.width();
    // Set the width as a CSS variable
    $(":root").css("--message-box-timestamp-column-width", `${max_timestamp_width}px`);
    // Clean up by removing the temporary <div> element
    $temp_time_div.remove();
}

export function initialize(): void {
    // We calculate the widths of a candidate set of timestamps,
    // and use the largest to set `--message-box-timestamp-column-width`
    calculate_timestamp_widths();
    // For users with automatic color scheme, we need to detect change
    // in `prefers-color-scheme` as it changes based on time.
    ui_util.listener_for_preferred_color_scheme_change(update_recipient_bar_background_color);
}
