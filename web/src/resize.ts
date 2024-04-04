import autosize from "autosize";
import $ from "jquery";
import assert from "minimalistic-assert";

import * as blueslip from "./blueslip";
import * as compose_state from "./compose_state";
import * as compose_ui from "./compose_ui";
import * as message_viewport from "./message_viewport";

function get_bottom_whitespace_height(): number {
    return message_viewport.height() * 0.4;
}

function get_new_heights(): {
    stream_filters_max_height: number;
    buddy_list_wrapper_max_height: number;
} {
    const viewport_height = message_viewport.height();
    const right_sidebar_shortcuts_height = $(".right-sidebar-shortcuts").outerHeight(true) ?? 0;

    let stream_filters_max_height =
        viewport_height -
        Number.parseInt($("#left-sidebar").css("paddingTop"), 10) -
        Number.parseInt($("#left-sidebar-navigation-area").css("marginTop"), 10) -
        Number.parseInt($("#left-sidebar-navigation-area").css("marginBottom"), 10) -
        ($("#left-sidebar-navigation-list").outerHeight(true) ?? 0) -
        ($("#private_messages_sticky_header").outerHeight(true) ?? 0);

    // Don't let us crush the stream sidebar completely out of view
    stream_filters_max_height = Math.max(80, stream_filters_max_height);

    // RIGHT SIDEBAR

    const usable_height =
        viewport_height -
        Number.parseInt($("#right-sidebar").css("paddingTop"), 10) -
        ($("#userlist-header").outerHeight(true) ?? 0) -
        ($("#user_search_section").outerHeight(true) ?? 0) -
        right_sidebar_shortcuts_height;

    const buddy_list_wrapper_max_height = Math.max(80, usable_height);

    return {
        stream_filters_max_height,
        buddy_list_wrapper_max_height,
    };
}

export function watch_manual_resize(element: string): (() => void)[] | undefined {
    const box = document.querySelector(element);

    if (!box) {
        blueslip.error("Bad selector in watch_manual_resize", {element});
        return undefined;
    }

    let height: number;
    let mousedown = false;

    const box_handler = function (): void {
        mousedown = true;
        height = box.clientHeight;
    };
    box.addEventListener("mousedown", box_handler);

    // If the user resizes the textarea manually, we use the
    // callback to stop autosize from adjusting the height.
    // It will be re-enabled when this component is next opened.
    const body_handler = function (): void {
        if (mousedown) {
            mousedown = false;
            if (height !== box.clientHeight) {
                height = box.clientHeight;
                autosize.destroy($(element)).height(height + "px");
            }
        }
    };
    document.body.addEventListener("mouseup", body_handler);

    return [box_handler, body_handler];
}

export function reset_compose_message_max_height(bottom_whitespace_height?: number): void {
    // If the compose-box is open, we set the `max-height` property of
    // `compose-textarea` and `preview-textarea`, so that the
    // compose-box's maximum extent does not overlap the last message
    // in the current stream.  We also leave a tiny bit of space after
    // the last message of the current stream.

    // Compute bottom_whitespace_height if not provided by caller.
    if (typeof bottom_whitespace_height !== "number") {
        bottom_whitespace_height = get_bottom_whitespace_height();
    }

    const compose_height = $("#compose").get(0)!.getBoundingClientRect().height;
    const compose_textarea_height = Math.max(
        $("textarea#compose-textarea").get(0)!.getBoundingClientRect().height,
        $("#preview_message_area").get(0)!.getBoundingClientRect().height,
    );
    const compose_non_textarea_height = compose_height - compose_textarea_height;

    // We ensure that the last message is not overlapped by compose box.
    $("textarea#compose-textarea").css(
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

export function resize_bottom_whitespace(): void {
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

export function resize_stream_subscribers_list(): void {
    // Calculates the height of the subscribers list in stream settings.
    // This avoids the stream settings from overflowing the container and
    // having a scroll bar.

    if ($("#stream_settings").length === 0) {
        // Don't run if stream settings (like $subscriptions_info below) is not open.
        return;
    }

    const $subscriptions_info = $("#subscription_overlay .subscriptions-container .right");
    const classes_above_subscribers_list = [
        ".display-type", // = stream_settings_title
        ".subscriber_list_settings_container .stream_settings_header",
        ".subscription_settings .stream_setting_subsection_title",
        ".subscription_settings .subscriber_list_settings",
        ".subscription_settings .stream_setting_subsection_title",
    ];
    const $classes_above_subscribers_list = $subscriptions_info.find(
        classes_above_subscribers_list.join(", "),
    );
    let total_height_of_classes_above_subscribers_list = 0;
    $classes_above_subscribers_list.each(function () {
        const outer_height = $(this).outerHeight(true);
        assert(outer_height !== undefined);
        total_height_of_classes_above_subscribers_list += outer_height;
    });
    const subscribers_list_header_height = 30;
    const margin_between_tab_switcher_and_add_subscribers_title = 20;
    const subscriptions_info_height = $subscriptions_info.height();
    assert(subscriptions_info_height !== undefined);
    const subscribers_list_height =
        subscriptions_info_height -
        total_height_of_classes_above_subscribers_list -
        subscribers_list_header_height -
        margin_between_tab_switcher_and_add_subscribers_title;
    $("html").css("--stream-subscriber-list-max-height", `${subscribers_list_height}px`);
}

export function resize_stream_filters_container(): void {
    const h = get_new_heights();
    resize_bottom_whitespace();
    $("#left_sidebar_scroll_container").css("max-height", h.stream_filters_max_height);
}

export function resize_sidebars(): void {
    const h = get_new_heights();
    $("#buddy_list_wrapper").css("max-height", h.buddy_list_wrapper_max_height);
    $("#left_sidebar_scroll_container").css("max-height", h.stream_filters_max_height);
}

export function update_recent_view_filters_height(): void {
    const recent_view_filters_height = $("#recent_view_filter_buttons").outerHeight(true) ?? 0;
    $("html").css("--recent-topics-filters-height", `${recent_view_filters_height}px`);
}

function resize_navbar_alerts(): void {
    const navbar_alerts_height = $("#navbar_alerts_wrapper").height();
    document.documentElement.style.setProperty(
        "--navbar-alerts-wrapper-height",
        navbar_alerts_height + "px",
    );

    // If the compose-box is in expanded state,
    // reset its height as well.
    if (compose_ui.is_full_size()) {
        compose_ui.set_compose_box_top(true);
    }
}

export function resize_page_components(): void {
    resize_navbar_alerts();
    resize_sidebars();
    resize_bottom_whitespace();
    resize_stream_subscribers_list();
}
