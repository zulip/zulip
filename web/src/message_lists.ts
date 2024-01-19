import $ from "jquery";
import assert from "minimalistic-assert";

import * as blueslip from "./blueslip";
import * as inbox_util from "./inbox_util";
import type {MessageListData} from "./message_list_data";
import type {Message} from "./message_store";
import * as recent_view_util from "./recent_view_util";
import * as ui_util from "./ui_util";

// TODO(typescript): Move this to message_list_view when it's
// converted to typescript.
type MessageListView = {
    update_recipient_bar_background_color: () => void;
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
    view: MessageListView;
    selected_id: () => number;
    selected_row: () => JQuery;
    selected_idx: () => number;
    all_messages: () => Message[];
    get: (id: number) => Message | undefined;
    pre_narrow_offset?: number;
    can_mark_messages_read_without_setting: () => boolean;
    resume_reading: () => void;
    data: MessageListData;
    select_id: (message_id: number, opts?: SelectIdOpts) => void;
    get_row: (message_id: number) => JQuery;
    add_messages: (
        messages: Message[],
        append_opts: {messages_are_new: boolean},
    ) => RenderInfo | undefined;
};

export let home: MessageList | undefined;
export let current: MessageList | undefined;

export function set_current(msg_list: MessageList): void {
    current = msg_list;
}

export function set_home(msg_list: MessageList): void {
    home = msg_list;
}

export function all_rendered_message_lists(): MessageList[] {
    assert(home !== undefined);
    assert(current !== undefined);
    const rendered_message_lists = [home];
    if (current !== home && !recent_view_util.is_visible()) {
        rendered_message_lists.push(current);
    }
    return rendered_message_lists;
}

export function all_rendered_row_for_message_id(message_id: number): JQuery {
    let $rows = $();
    for (const msg_list of all_rendered_message_lists()) {
        $rows = $rows.add(msg_list.get_row(message_id));
    }
    return $rows;
}

export function all_current_message_rows(): JQuery {
    assert(current !== undefined);
    return current.view.$list.find(".message_row");
}

export function update_recipient_bar_background_color(): void {
    for (const msg_list of all_rendered_message_lists()) {
        msg_list.view.update_recipient_bar_background_color();
    }
    inbox_util.update_stream_colors();
}

export function save_pre_narrow_offset_for_reload(): void {
    assert(current !== undefined);
    if (current.selected_id() !== -1) {
        if (current.selected_row().length === 0) {
            const current_message = current.get(current.selected_id());
            blueslip.debug("narrow.activate missing selected row", {
                selected_id: current.selected_id(),
                selected_idx: current.selected_idx(),
                selected_idx_exact:
                    current_message && current.all_messages().indexOf(current_message),
                render_start: current.view._render_win_start,
                render_end: current.view._render_win_end,
            });
        }
        current.pre_narrow_offset = current.selected_row().get_offset_to_window().top;
    }
}

export function initialize(): void {
    // For users with automatic color scheme, we need to detect change
    // in `prefers-color-scheme` as it changes based on time.
    ui_util.listener_for_preferred_color_scheme_change(update_recipient_bar_background_color);
}
