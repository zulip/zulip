import autosize from "autosize";
import $ from "jquery";

import * as blueslip from "./blueslip";
import * as compose_state from "./compose_state";
import * as condense from "./condense";
import * as message_lists from "./message_lists";
import * as message_viewport from "./message_viewport";
import * as navbar_alerts from "./navbar_alerts";
import * as navigate from "./navigate";
import * as popovers from "./popovers";
import * as recent_topics_util from "./recent_topics_util";
import * as util from "./util";

function get_new_heights() {
    const res = {};
    const viewport_height = message_viewport.height();
    const top_navbar_height = $("#top_navbar").safeOuterHeight(true);
    const right_sidebar_shortcuts_height = $(".right-sidebar-shortcuts").safeOuterHeight(true) || 0;

    res.bottom_whitespace_height = viewport_height * 0.4;

    res.main_div_min_height = viewport_height - top_navbar_height;

    res.stream_filters_max_height =
        viewport_height -
        Number.parseInt($("#left-sidebar").css("marginTop"), 10) -
        Number.parseInt($(".narrows_panel").css("marginTop"), 10) -
        Number.parseInt($(".narrows_panel").css("marginBottom"), 10) -
        $("#global_filters").safeOuterHeight(true) -
        $("#private_messages_sticky_header").safeOuterHeight(true);

    // Don't let us crush the stream sidebar completely out of view
    res.stream_filters_max_height = Math.max(80, res.stream_filters_max_height);

    // RIGHT SIDEBAR

    const usable_height =
        viewport_height -
        Number.parseInt($("#right-sidebar").css("marginTop"), 10) -
        $("#userlist-header").safeOuterHeight(true) -
        $("#user_search_section").safeOuterHeight(true) -
        right_sidebar_shortcuts_height;

    res.buddy_list_wrapper_max_height = Math.max(80, usable_height);

    return res;
}

export function watch_manual_resize(element) {
    const box = document.querySelector(element);

    if (!box) {
        blueslip.error("Bad selector in watch_manual_resize: " + element);
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
    if (bottom_whitespace_height === undefined) {
        const h = get_new_heights();
        bottom_whitespace_height = h.bottom_whitespace_height;
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
}

export function resize_bottom_whitespace(h) {
    $("#bottom_whitespace").height(h.bottom_whitespace_height);

    // The height of the compose box is tied to that of
    // bottom_whitespace, so update it if necessary.
    //
    // reset_compose_message_max_height cannot compute the right
    // height correctly while compose is hidden. This is OK, because
    // we also resize compose every time it is opened.
    if (compose_state.composing()) {
        reset_compose_message_max_height(h.bottom_whitespace_height);
    }
}

export function resize_stream_filters_container() {
    const h = get_new_heights();
    resize_bottom_whitespace(h);
    $("#left_sidebar_scroll_container").css("max-height", h.stream_filters_max_height);
}

export function resize_sidebars() {
    const h = get_new_heights();
    $("#buddy_list_wrapper").css("max-height", h.buddy_list_wrapper_max_height);
    $("#left_sidebar_scroll_container").css("max-height", h.stream_filters_max_height);
    return h;
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
        condense.clear_message_content_height_cache();
    }
    resize_page_components();

    // Re-compute and display/remove [More] links to messages
    condense.condense_and_collapse($(".message_table .message_row"));

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

export function initialize() {
    // Hack: If the app is loaded directly to recent topics, then we
    // need to arrange to call navbar_alerts.resize_app when we first
    // visit a message list. This is a workaround for bugs where the
    // floating recipient bar will be invisible (as well as other
    // alignment issues) when they are initially rendered in the
    // background because recent topics is displayed.

    if (recent_topics_util.is_visible()) {
        // We bind the handler for the message_feed_container shown event, such
        // that it will only get executed once.
        //
        // The selector here is based on #gear-menu, to take advantage
        // of the Bootstrap the 'show' event handler on that legacy
        // data-toggle element.
        $('#gear-menu a[data-toggle="tab"][href="#message_feed_container"]').one("show", () => {
            // We use a requestAnimationFrame here to prevent this call from
            // causing a forced reflow.
            window.requestAnimationFrame(() => {
                navbar_alerts.resize_app();
            });
        });
    }
}
