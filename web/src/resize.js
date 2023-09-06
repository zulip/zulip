import autosize from "autosize";
import $ from "jquery";

import * as blueslip from "./blueslip";
import * as compose_state from "./compose_state";
import * as compose_ui from "./compose_ui";
import * as condense from "./condense";
import * as message_lists from "./message_lists";
import * as message_viewport from "./message_viewport";
import * as navbar_alerts from "./navbar_alerts";
import * as navigate from "./navigate";
import * as popovers from "./popovers";
import * as util from "./util";

function get_bottom_whitespace_height() {
    return message_viewport.height() * 0.4;
}

function get_new_heights() {
    const res = {};
    const viewport_height = message_viewport.height();
    const right_sidebar_shortcuts_height = $(".right-sidebar-shortcuts").outerHeight(true) ?? 0;

    res.stream_filters_max_height =
        viewport_height -
        Number.parseInt($("#left-sidebar").css("paddingTop"), 10) -
        Number.parseInt($(".narrows_panel").css("marginTop"), 10) -
        Number.parseInt($(".narrows_panel").css("marginBottom"), 10) -
        ($("#global_filters").outerHeight(true) ?? 0) -
        ($("#private_messages_sticky_header").outerHeight(true) ?? 0);

    // Don't let us crush the stream sidebar completely out of view
    res.stream_filters_max_height = Math.max(80, res.stream_filters_max_height);

    // RIGHT SIDEBAR

    const usable_height =
        viewport_height -
        Number.parseInt($("#right-sidebar").css("paddingTop"), 10) -
        ($("#userlist-header").outerHeight(true) ?? 0) -
        ($("#user_search_section").outerHeight(true) ?? 0) -
        right_sidebar_shortcuts_height;

    res.buddy_list_wrapper_max_height = Math.max(80, usable_height);

    return res;
}

export function watch_manual_resize(element) {
    const box = document.querySelector(element);

    if (!box) {
        blueslip.error("Bad selector in watch_manual_resize", {element});
        return undefined;
    }

    const meta = {
        box,
        height: null,
        mousedown: false,
    };

    const box_handler = function () {
        meta.mousedown = true;
        meta.height = meta.box.clientHeight;
    };
    meta.box.addEventListener("mousedown", box_handler);

    // If the user resizes the textarea manually, we use the
    // callback to stop autosize from adjusting the height.
    // It will be re-enabled when this component is next opened.
    const body_handler = function () {
        if (meta.mousedown === true) {
            meta.mousedown = false;
            if (meta.height !== meta.box.clientHeight) {
                meta.height = meta.box.clientHeight;
                autosize.destroy($(element)).height(meta.height + "px");
            }
        }
    };
    document.body.addEventListener("mouseup", body_handler);

    return [box_handler, body_handler];
}

export function reset_compose_message_max_height(bottom_whitespace_height) {
    // If the compose-box is open, we set the `max-height` property of
    // `compose-textarea` and `preview-textarea`, so that the
    // compose-box's maximum extent does not overlap the last message
    // in the current stream.  We also leave a tiny bit of space after
    // the last message of the current stream.

    // Compute bottom_whitespace_height if not provided by caller.
    if (typeof bottom_whitespace_height !== "number") {
        bottom_whitespace_height = get_bottom_whitespace_height();
    }

    const compose_height = $("#compose").get(0).getBoundingClientRect().height;
    const compose_textarea_height = Math.max(
        $("#compose-textarea").get(0).getBoundingClientRect().height,
        $("#preview_message_area").get(0).getBoundingClientRect().height,
    );
    const compose_non_textarea_height = compose_height - compose_textarea_height;

    // We ensure that the last message is not overlapped by compose box.
    $("#compose-textarea").css(
        "max-height",
        // Because <textarea> max-height includes padding, we subtract
        // 10 for the padding and 10 for the selected message border.
        bottom_whitespace_height - compose_non_textarea_height - 20,
    );
    $("#preview_message_area").css(
        "max-height",
        // Because <div> max-height doesn't include padding, we only
        // subtract 10 for the selected message border.
        bottom_whitespace_height - compose_non_textarea_height - 10,
    );
    $("#scroll-to-bottom-button-container").css("bottom", compose_height);
}

export function resize_bottom_whitespace() {
    const bottom_whitespace_height = get_bottom_whitespace_height();
    $("html").css("--max-unexpanded-compose-height", `${bottom_whitespace_height}px`);
    // The height of the compose box is tied to that of
    // bottom_whitespace, so update it if necessary.
    //
    // reset_compose_message_max_height cannot compute the right
    // height correctly while compose is hidden. This is OK, because
    // we also resize compose every time it is opened.
    if (compose_state.composing()) {
        reset_compose_message_max_height(bottom_whitespace_height);
    }
}

export function resize_stream_filters_container() {
    const h = get_new_heights();
    resize_bottom_whitespace();
    $("#left_sidebar_scroll_container").css("max-height", h.stream_filters_max_height);
}

export function resize_sidebars() {
    const h = get_new_heights();
    $("#buddy_list_wrapper").css("max-height", h.buddy_list_wrapper_max_height);
    $("#left_sidebar_scroll_container").css("max-height", h.stream_filters_max_height);
    return h;
}

export function update_recent_view_filters_height() {
    const recent_view_filters_height = $("#recent_topics_filter_buttons").outerHeight(true) ?? 0;
    $("html").css("--recent-topics-filters-height", `${recent_view_filters_height}px`);
}

export function resize_page_components() {
    navbar_alerts.resize_app();
    const h = resize_sidebars();
    resize_bottom_whitespace(h);
}

let _old_width = $(window).width();

export function handler() {
    const new_width = $(window).width();

    // On mobile web, we want to avoid hiding a popover here on height change,
    // especially if this resize was triggered by a virtual keyboard
    // popping up when the user opened that very popover.
    const mobile = util.is_mobile();
    if (!mobile || new_width !== _old_width) {
        popovers.hide_all();
    }

    if (new_width !== _old_width) {
        _old_width = new_width;
    }
    resize_page_components();
    compose_ui.autosize_textarea($("#compose-textarea"));
    update_recent_view_filters_height();

    // Re-compute and display/remove 'Show more' buttons to messages
    condense.condense_and_collapse(message_lists.all_current_message_rows());

    // This function might run onReady (if we're in a narrow window),
    // but before we've loaded in the messages; in that case, don't
    // try to scroll to one.
    if (message_lists.current.selected_id() !== -1) {
        if (mobile) {
            popovers.set_suppress_scroll_hide();
        }

        navigate.scroll_to_selected();
    }
}
