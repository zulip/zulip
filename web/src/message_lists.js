import $ from "jquery";

import * as blueslip from "./blueslip";
import * as inbox_util from "./inbox_util";
import * as recent_view_util from "./recent_view_util";
import * as ui_util from "./ui_util";

export let home;
export let current;

export function set_current(msg_list) {
    current = msg_list;
}

export function set_home(msg_list) {
    home = msg_list;
}

export function all_rendered_message_lists() {
    const rendered_message_lists = [home];
    if (current !== home && !recent_view_util.is_visible()) {
        rendered_message_lists.push(current);
    }
    return rendered_message_lists;
}

export function all_current_message_rows() {
    return $(`#${CSS.escape(current.table_name)}.message-list .message_row`);
}

export function update_recipient_bar_background_color() {
    for (const msg_list of all_rendered_message_lists()) {
        msg_list.view.update_recipient_bar_background_color();
    }
    inbox_util.update_stream_colors();
}

export function save_pre_narrow_offset_for_reload() {
    if (current.selected_id() !== -1) {
        if (current.selected_row().length === 0) {
            blueslip.debug("narrow.activate missing selected row", {
                selected_id: current.selected_id(),
                selected_idx: current.selected_idx(),
                selected_idx_exact: current
                    .all_messages()
                    .indexOf(current.get(current.selected_id())),
                render_start: current.view._render_win_start,
                render_end: current.view._render_win_end,
            });
        }
        current.pre_narrow_offset = current.selected_row().get_offset_to_window().top;
    }
}

export function initialize() {
    // For users with automatic color scheme, we need to detect change
    // in `prefers-color-scheme` as it changes based on time.
    ui_util.listener_for_preferred_color_scheme_change(update_recipient_bar_background_color);
}
