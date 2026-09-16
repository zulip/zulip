import {$} from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import * as message_lists from "./message_lists.ts";
import * as message_scroll_state from "./message_scroll_state.ts";
import * as message_viewport from "./message_viewport.ts";
import * as narrow_state from "./narrow_state.ts";
import * as stream_list from "./stream_list.ts";
import * as tippyjs from "./tippyjs.ts";
import * as topic_generator from "./topic_generator.ts";
import * as ui_util from "./ui_util.ts";
import {the} from "./util.ts";

type ButtonMode = "scroll_to_bottom" | "next_unread_topic" | "next_unread_dm_conversation";

const button_mode_config: Record<ButtonMode, {icon: string; tooltip_template_id: string}> = {
    scroll_to_bottom: {
        icon: "chevron-down",
        tooltip_template_id: "scroll-to-bottom-button-tooltip-template",
    },
    next_unread_topic: {
        icon: "arrow-right",
        tooltip_template_id: "next-unread-topic-button-tooltip-template",
    },
    next_unread_dm_conversation: {
        icon: "arrow-right",
        tooltip_template_id: "next-unread-dm-conversation-button-tooltip-template",
    },
};

let mode: ButtonMode = "scroll_to_bottom";
let hide_timer: ReturnType<typeof setInterval> | undefined;
let scrolled_away_from_bottom_of_list_id: number | undefined;
let waiting_for_animated_scroll = false;

function above_bottom_of_view(): boolean {
    assert(message_lists.current !== undefined);
    return (
        !message_lists.current.visibly_empty() &&
        (!message_viewport.bottom_rendered_message_visible() ||
            !message_lists.current.view.is_fetched_end_rendered() ||
            // False while newer messages are being fetched, when
            // there may turn out to be none.
            message_lists.current.data.fetch_status.can_load_newer_messages())
    );
}

function get_tooltip(): tippy.Instance | undefined {
    return the($<tippy.ReferenceElement>("#scroll-to-bottom-button-clickable-area"))._tippy;
}

function set_mode(new_mode: ButtonMode): void {
    if (mode === new_mode) {
        return;
    }

    const $icon = $("#scroll-to-bottom-button .zulip-icon");
    $icon.removeClass(`zulip-icon-${button_mode_config[mode].icon}`);
    $icon.addClass(`zulip-icon-${button_mode_config[new_mode].icon}`);
    const $clickable_area = $("#scroll-to-bottom-button-clickable-area");
    $clickable_area.attr(
        "data-tooltip-template-id",
        button_mode_config[new_mode].tooltip_template_id,
    );
    // A tooltip that is already open would otherwise keep describing
    // the old mode.
    get_tooltip()?.setContent(tippyjs.get_tooltip_content(the($clickable_area)));
    mode = new_mode;
}

function stop_hide_timer(): void {
    clearInterval(hide_timer);
    hide_timer = undefined;
}

function hide(): void {
    stop_hide_timer();
    $("#scroll-to-bottom-button-container").removeClass("show");
}

function show(new_mode: ButtonMode): void {
    set_mode(new_mode);
    stop_hide_timer();
    $("#scroll-to-bottom-button-container").addClass("show");
}

function is_shown(): boolean {
    return $("#scroll-to-bottom-button-container").hasClass("show");
}

function showing_next_unread_conversation(): boolean {
    return is_shown() && mode !== "scroll_to_bottom";
}

function mouse_is_over_button(): boolean {
    return the($("#scroll-to-bottom-button-container")).matches(":hover");
}

function hide_once_not_hovered(): void {
    hide_timer ??= setInterval(() => {
        // Check if the user is hovered over the scroll-to-bottom
        // button every 3 seconds to allow time for interaction.
        // If the user is not hovered on the button, hide the button
        // and clear the timer until the next scroll event triggers
        // showing the button again.
        if (!mouse_is_over_button()) {
            hide();
        }
    }, 3000);
}

function next_unread_conversation_mode(): ButtonMode | undefined {
    assert(message_lists.current !== undefined);
    const filter = message_lists.current.data.filter;
    if (filter.can_show_next_unread_topic_conversation_button()) {
        const has_next_unread_topic = topic_generator.has_next_unread_topic(
            narrow_state.stream_id(),
            narrow_state.topic(),
            stream_list.get_sorted_channel_ids_for_next_unread_navigation(),
        );
        return has_next_unread_topic ? "next_unread_topic" : undefined;
    }
    if (filter.can_show_next_unread_dm_conversation_button()) {
        const has_next_unread_dm_conversation =
            topic_generator.get_next_unread_pm_string(narrow_state.pm_ids_string()) !== undefined;
        return has_next_unread_dm_conversation ? "next_unread_dm_conversation" : undefined;
    }
    return undefined;
}

function show_next_unread_conversation_or_hide(): void {
    const next_mode = next_unread_conversation_mode();
    if (next_mode === undefined) {
        hide();
    } else {
        show(next_mode);
    }
}

// Safe to call whenever the scroll position or the message feed may
// have changed.
export function update(): void {
    if (message_lists.current === undefined) {
        // Scroll to bottom button is not for non-message views.
        hide();
        return;
    }

    if (message_scroll_state.actively_scrolling) {
        // The feed is not in its final position yet; we are called
        // again once the scroll finishes.
        return;
    }

    if (message_viewport.is_animating_scroll()) {
        // An animated scroll may not have moved the feed yet, and
        // fires no scroll event if there is nowhere to scroll to.
        if (!waiting_for_animated_scroll) {
            waiting_for_animated_scroll = true;
            message_viewport.after_animated_scroll(() => {
                waiting_for_animated_scroll = false;
                update();
            });
        }
        return;
    }

    const scrolled_away = scrolled_away_from_bottom_of_list_id === message_lists.current.id;
    scrolled_away_from_bottom_of_list_id = undefined;

    if (above_bottom_of_view()) {
        if (showing_next_unread_conversation()) {
            const mouse_in_use = scrolled_away || mouse_is_over_button();
            if (mouse_in_use) {
                show("scroll_to_bottom");
            } else {
                // The icon stays an arrow while the button fades out.
                hide();
            }
        }
        if (is_shown()) {
            hide_once_not_hovered();
        }
    } else if (!message_lists.current.data.fetch_status.has_found_newest()) {
        // We are called again once the newest messages are fetched.
        // Until then, an arrow that is already showing stays if this
        // view offers one, so that it does not flicker between views.
        if (showing_next_unread_conversation()) {
            show_next_unread_conversation_or_hide();
        } else {
            hide();
        }
    } else if (message_lists.current.visibly_empty()) {
        hide();
    } else {
        show_next_unread_conversation_or_hide();
    }
}

export function handle_non_keyboard_scroll(): void {
    assert(message_lists.current !== undefined);
    if (!above_bottom_of_view()) {
        return;
    }

    if (showing_next_unread_conversation()) {
        // The feed may only be passing through this position, e.g.,
        // while autoscrolling to show a newly arrived message, so we
        // let update() decide what to show once the scroll finishes.
        scrolled_away_from_bottom_of_list_id = message_lists.current.id;
        return;
    }

    show("scroll_to_bottom");
}

// update() keeps an arrow while the newest messages are awaited, and
// after a failed fetch they never arrive.
export function hide_after_failed_fetch(): void {
    hide();
}

export function initialize(on_click: Record<ButtonMode, () => void>): void {
    $("body").on("click", "#scroll-to-bottom-button-clickable-area", (e) => {
        e.preventDefault();
        e.stopPropagation();

        // Since it take a few milliseconds for this button complete disappear transition,
        // it is possible for user to click it before it hides when switching narrows.
        if (narrow_state.is_message_feed_visible()) {
            // Enter would otherwise click the button again, rather
            // than open the compose box.
            ui_util.blur_active_element();
            on_click[mode]();
        }
    });

    $(document).on("keydown", (e) => {
        if (e.shiftKey || e.ctrlKey || e.metaKey) {
            return;
        }

        if (mode !== "scroll_to_bottom") {
            // Typing a reply should not take away the button for
            // moving on to the next conversation.
            return;
        }

        // Hide scroll to bottom button on any keypress.
        // Keyboard users are very less likely to use this button.
        hide();
    });

    const $show_scroll_to_bottom_button = $("#scroll-to-bottom-button-container").expectOne();
    // Delete the tippy tooltip whenever the fadeout animation for
    // this button is finished. This is necessary because the fading animation
    // confuses Tippy's built-in `data-reference-hidden` feature.
    $show_scroll_to_bottom_button.on("transitionend", (e) => {
        assert(e.originalEvent instanceof TransitionEvent);
        if (e.originalEvent.propertyName === "visibility") {
            const tooltip = get_tooltip();
            // make sure the tooltip exists and the class is not currently showing
            if (tooltip && !is_shown()) {
                tooltip.destroy();
            }
        }
    });
}
