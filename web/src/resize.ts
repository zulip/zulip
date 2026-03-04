import autosize from "autosize";
import $ from "jquery";
import assert from "minimalistic-assert";

import * as blueslip from "./blueslip.ts";
import * as compose_state from "./compose_state.ts";
import * as compose_ui from "./compose_ui.ts";
import {media_breakpoints_num} from "./css_variables.ts";
import * as message_viewport from "./message_viewport.ts";
import {user_settings} from "./user_settings.ts";

let recent_view_participants_rerender: (() => void) | null = null;

export function set_recent_view_participants_rerender(rerender_func: (() => void) | null): void {
    recent_view_participants_rerender = rerender_func;
}

function get_bottom_whitespace_height(): number {
    return message_viewport.height() * 0.4;
}

export function get_stream_filters_max_height(): number {
    const viewport_height = message_viewport.height();
    // Add some gap for bottom element to be properly visible.
    const GAP = 15;

    const $left_sidebar_search = $("#left-sidebar-search");
    const is_search_visible = $left_sidebar_search.css("display") !== "none";

    let stream_filters_max_height =
        viewport_height -
        Number.parseInt($("#left-sidebar").css("paddingTop"), 10) -
        (is_search_visible ? ($left_sidebar_search.outerHeight(true) ?? 0) : 0) -
        ($("#left-sidebar-navigation-area").not(".hidden-by-filters").outerHeight(true) ?? 0) -
        GAP;

    // Don't let us crush the stream sidebar completely out of view
    stream_filters_max_height = Math.max(80, stream_filters_max_height);
    return stream_filters_max_height;
}

function get_new_heights(): {
    stream_filters_max_height: number;
    buddy_list_wrapper_max_height: number;
} {
    const viewport_height = message_viewport.height();
    const usable_height =
        viewport_height -
        Number.parseInt($("#right-sidebar").css("paddingTop"), 10) -
        ($("#userlist-header").outerHeight(true) ?? 0);

    const buddy_list_wrapper_max_height = Math.max(80, usable_height);

    return {
        stream_filters_max_height: get_stream_filters_max_height(),
        buddy_list_wrapper_max_height,
    };
}

export function watch_manual_resize(element: string): (() => void)[] | undefined {
    const box = document.querySelector(element);

    if (!box) {
        blueslip.error("Bad selector in watch_manual_resize", {element});
        return undefined;
    }

    return watch_manual_resize_for_element(box);
}

export function watch_manual_resize_for_element(
    box: Element,
    resize_callback?: (height: number) => void,
): (() => void)[] {
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
                autosize.destroy($(box)).height(height + "px");
                if (resize_callback) {
                    resize_callback(height);
                }
            }
        }
    };
    document.body.addEventListener("mouseup", body_handler);

    return [box_handler, body_handler];
}

function height_of($element: JQuery): number {
    return $element.get(0)!.getBoundingClientRect().height;
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

    const compose_height = height_of($("#compose"));
    const compose_textarea_height = Math.max(
        height_of($("textarea#compose-textarea")),
        height_of($("#preview_message_area")),
    );
    const compose_non_textarea_height = compose_height - compose_textarea_height;

    // We ensure that the last message is not overlapped by compose box.
    $("textarea#compose-textarea").css(
        "max-height",
        bottom_whitespace_height - compose_non_textarea_height,
    );
    $("#preview_message_area").css(
        "max-height",
        bottom_whitespace_height - compose_non_textarea_height,
    );
    $("#scroll-to-bottom-button-container").css("bottom", compose_height);
    compose_ui.autosize_textarea($("#compose-textarea"));
}

export function resize_bottom_whitespace(): void {
    const bottom_whitespace_height = get_bottom_whitespace_height();
    $(":root").css("--max-unmaximized-compose-height", `${bottom_whitespace_height}px`);
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

    const $subscriptions_info = $("#subscription_overlay .two-pane-settings-container .right");
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
    $(":root").css("--stream-subscriber-list-max-height", `${subscribers_list_height}px`);
}

export function resize_stream_filters_container(): void {
    resize_bottom_whitespace();
    $("#left_sidebar_scroll_container").css("max-height", get_stream_filters_max_height());
}

export function resize_sidebars(): void {
    const h = get_new_heights();
    $("#buddy_list_wrapper").css("max-height", h.buddy_list_wrapper_max_height);
    $("#left_sidebar_scroll_container").css("max-height", h.stream_filters_max_height);
}

export function update_recent_view(rerender_view_if_needed = false): void {
    const $middle_column = $(".app .column-middle");

    // Update max avatars to prevent participant avatars from overflowing.
    // These numbers are just based on speculation.
    const middle_column_width = $middle_column.outerWidth() ?? 0;
    if (!middle_column_width) {
        return;
    }
    const prev_num_avatars_max = Number($(":root").css("--recent-view-max-avatars"));
    let num_avatars_max = 4;
    if (middle_column_width < (media_breakpoints_num.md * user_settings.web_font_size_px) / 16) {
        num_avatars_max = 2;
    }

    if (prev_num_avatars_max !== num_avatars_max) {
        $(":root").css("--recent-view-max-avatars", `${num_avatars_max}`);

        if (rerender_view_if_needed) {
            recent_view_participants_rerender?.();
        }
    }
}

function resize_navbar_alerts(): void {
    const navbar_alerts_height = $("#navbar_alerts_wrapper").height();
    document.documentElement.style.setProperty(
        "--navbar-alerts-wrapper-height",
        navbar_alerts_height + "px",
    );

    // If the compose-box is in full sized state,
    // reset its height as well.
    if (compose_ui.is_full_size()) {
        compose_ui.set_compose_box_top(true);
    }
}

// We need to make the height of subheaders on both sides same. This is not
// easy to achieve using only CSS because we cannot set a fixed height — the
// right subheader contains the stream name, which can sometimes be long
// enough to wrap the text into multiple lines. Text wrapping may also be
// required for smaller window sizes.
//
// Here we first let subheaders on both sides attain their natural height as
// per the content and then make both of them equal by setting the
// height of subheader which is smaller to the height of subheader that
// has larger height.
// This feels a bit hacky and a cleaner solution would be nice to find.
export function resize_settings_overlay_subheader($container: JQuery): void {
    const $left_subheader = $container.find(".left .two-pane-settings-subheader");
    const $right_subheader = $container.find(".right .two-pane-settings-subheader");

    $left_subheader.css("height", "");
    $right_subheader.css("height", "");

    const left_subheader_height = height_of($left_subheader);
    const right_subheader_height = height_of($right_subheader);

    // Since height_of returns height including border width, we will
    // subtract 1px, which is the bottom border width.
    if (left_subheader_height < right_subheader_height) {
        $left_subheader.css("height", right_subheader_height - 1);
    } else {
        $right_subheader.css("height", left_subheader_height - 1);
    }
}

export function resize_settings_overlay($container: JQuery): void {
    if ($container.find(".two-pane-settings-overlay.show").length === 0) {
        return;
    }

    resize_settings_overlay_subheader($container);

    $container
        .find(".two-pane-settings-left-simplebar-container")
        .css(
            "height",
            height_of($container.find(".two-pane-settings-container")) -
                height_of($container.find(".two-pane-settings-header")) -
                height_of($container.find(".two-pane-settings-subheader")) -
                height_of($container.find(".two-pane-settings-search")),
        );

    $container
        .find(".two-pane-settings-right-simplebar-container")
        .css(
            "height",
            height_of($container.find(".two-pane-settings-container")) -
                height_of($container.find(".two-pane-settings-header")) -
                height_of($container.find(".two-pane-settings-subheader")),
        );
}

export function resize_settings_creation_overlay($container: JQuery): void {
    if ($container.find(".two-pane-settings-creation-simplebar-container").length === 0) {
        return;
    }

    $container
        .find(".two-pane-settings-creation-simplebar-container")
        .css(
            "height",
            height_of($container.find(".two-pane-settings-container")) -
                height_of($container.find(".two-pane-settings-header")) -
                height_of($container.find(".two-pane-settings-subheader")) -
                height_of($container.find(".settings-sticky-footer")),
        );
}

export function resize_page_components(): void {
    resize_navbar_alerts();
    resize_sidebars();
    resize_bottom_whitespace();
    resize_stream_subscribers_list();
    resize_settings_overlay($("#groups_overlay_container"));
    resize_settings_overlay($("#channels_overlay_container"));
    resize_settings_creation_overlay($("#groups_overlay_container"));
    resize_settings_creation_overlay($("#channels_overlay_container"));
}
