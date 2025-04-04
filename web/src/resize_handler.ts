import $ from "jquery";

import * as compose_ui from "./compose_ui.ts";
import * as condense from "./condense.ts";
import * as message_lists from "./message_lists.ts";
import * as message_viewport from "./message_viewport.ts";
import * as resize from "./resize.ts";
import * as scroll_bar from "./scroll_bar.ts";
import * as sidebar_ui from "./sidebar_ui.ts";
import * as util from "./util.ts";

export let _old_width = $(window).width();

export function handler(): void {
    const new_width = $(window).width();
    let width_changed = false;

    const mobile = util.is_mobile();
    if (!mobile || new_width !== _old_width) {
        sidebar_ui.hide_all();
    }

    if (new_width !== _old_width) {
        _old_width = new_width;
        width_changed = true;
    }
    resize.resize_page_components();
    compose_ui.autosize_textarea($("textarea#compose-textarea"));
    compose_ui.maybe_show_scrolling_formatting_buttons("#message-formatting-controls-container");
    compose_ui.maybe_show_scrolling_formatting_buttons(".message-edit-feature-group");
    resize.update_recent_view();
    scroll_bar.handle_overlay_scrollbars();

    // Re-compute and display/remove 'Show more' buttons to messages
    condense.condense_and_collapse(message_lists.all_current_message_rows());

    // Height can change on mobile OS like i0S if scrolling causes URL bar to change height.
    // We don't want to cause scroll jump in that case and just let our logic for keeping the
    // selected message in the view handle it. Width can change due change in device orientation
    // in which case we want to scroll to the selected message.
    const only_height_changed_on_mobile = mobile && !width_changed;
    // This function might run onReady (if we're in a narrow window),
    // but before we've loaded in the messages; in that case, don't
    // try to scroll to one.
    if (
        !only_height_changed_on_mobile &&
        message_lists.current !== undefined &&
        message_lists.current.selected_id() !== -1
    ) {
        message_viewport.scroll_to_selected();
    }
}
