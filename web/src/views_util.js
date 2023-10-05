import $ from "jquery";

import * as message_view_header from "./message_view_header";
import * as narrow from "./narrow";
import * as narrow_state from "./narrow_state";
import * as narrow_title from "./narrow_title";
import * as navigate from "./navigate";
import * as pm_list from "./pm_list";
import * as resize from "./resize";
import * as search from "./search";
import * as stream_list from "./stream_list";
import * as unread_ui from "./unread_ui";

export function show(opts) {
    if (narrow.has_shown_message_list_view) {
        narrow.save_pre_narrow_offset_for_reload();
    }

    if (opts.is_visible()) {
        // If we're already visible, E.g. because the user hit Esc
        // while already in the view, do nothing.
        return;
    }

    // Hide selected elements in the left sidebar.
    opts.highlight_view_in_left_sidebar();
    stream_list.handle_message_view_deactivated();
    pm_list.handle_message_view_deactivated();

    // Hide "middle-column" which has html for rendering
    // a messages narrow. We hide it and show the view.
    $("#message_feed_container").hide();
    opts.$view.show();
    opts.set_visible(true);

    unread_ui.hide_unread_banner();
    opts.update_compose();
    narrow_state.reset_current_filter();
    narrow_title.update_narrow_title(narrow_state.filter());
    message_view_header.render_title_area();
    narrow.handle_middle_pane_transition();
    search.clear_search_form();
    opts.complete_rerender();
    resize.update_recent_view_filters_height();

    // Misc.
    if (opts.is_recent_view) {
        resize.update_recent_view_filters_height();
    }
}

export function hide(opts) {
    const $focused_element = $(document.activeElement);
    if (opts.$view.has($focused_element)) {
        $focused_element.trigger("blur");
    }

    $("#message_feed_container").show();
    opts.$view.hide();
    opts.set_visible(false);

    // This solves a bug with message_view_header
    // being broken sometimes when we narrow
    // to a filter and back to view
    // before it completely re-rerenders.
    message_view_header.render_title_area();

    // Fire our custom event
    $("#message_feed_container").trigger("message_feed_shown");

    // This makes sure user lands on the selected message
    // and not always at the top of the narrow.
    navigate.plan_scroll_to_selected();
}
