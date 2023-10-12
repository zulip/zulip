import $ from "jquery";

import * as compose_ui from "./compose_ui";
import * as condense from "./condense";
import * as message_lists from "./message_lists";
import * as message_viewport from "./message_viewport";
import * as popover_menus from "./popover_menus";
import * as popovers from "./popovers";
import * as resize from "./resize";
import * as sidebar_ui from "./sidebar_ui";
import * as util from "./util";

export let _old_width = $(window).width();

export function handler() {
    const new_width = $(window).width();

    // On mobile web, we want to avoid hiding a popover here on height change,
    // especially if this resize was triggered by a virtual keyboard
    // popping up when the user opened that very popover.
    const mobile = util.is_mobile();
    if (!mobile || new_width !== _old_width) {
        sidebar_ui.hide_all();
        popovers.hide_all();
    }

    if (new_width !== _old_width) {
        _old_width = new_width;
    }
    resize.resize_page_components();
    compose_ui.autosize_textarea($("#compose-textarea"));
    resize.update_recent_view_filters_height();

    // Re-compute and display/remove 'Show more' buttons to messages
    condense.condense_and_collapse(message_lists.all_current_message_rows());

    // This function might run onReady (if we're in a narrow window),
    // but before we've loaded in the messages; in that case, don't
    // try to scroll to one.
    if (message_lists.current.selected_id() !== -1) {
        if (mobile) {
            popover_menus.set_suppress_scroll_hide();
        }

        message_viewport.scroll_to_selected();
    }
}
