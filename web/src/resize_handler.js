import $ from "jquery";

import * as compose_ui from "./compose_ui";
import * as condense from "./condense";
import * as message_lists from "./message_lists";
import * as message_viewport from "./message_viewport";
import * as resize from "./resize";
import * as scroll_bar from "./scroll_bar";
import * as sidebar_ui from "./sidebar_ui";
import * as util from "./util";

export let _old_width = $(window).width();

export function handler() {
    const new_width = $(window).width();

    const mobile = util.is_mobile();
    if (!mobile || new_width !== _old_width) {
        sidebar_ui.hide_all();
    }

    if (new_width !== _old_width) {
        _old_width = new_width;
    }
    resize.resize_page_components();
    compose_ui.autosize_textarea($("textarea#compose-textarea"));
    resize.update_recent_view_filters_height();
    scroll_bar.handle_overlay_scrollbars();

    // Re-compute and display/remove 'Show more' buttons to messages
    condense.condense_and_collapse(message_lists.all_current_message_rows());

    // This function might run onReady (if we're in a narrow window),
    // but before we've loaded in the messages; in that case, don't
    // try to scroll to one.
    if (message_lists.current !== undefined && message_lists.current.selected_id() !== -1) {
        message_viewport.scroll_to_selected();
    }
}
