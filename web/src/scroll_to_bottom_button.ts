import {$} from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import * as message_lists from "./message_lists.ts";
import * as message_scroll_state from "./message_scroll_state.ts";
import * as message_viewport from "./message_viewport.ts";
import {page_params} from "./page_params.ts";
import * as tippyjs from "./tippyjs.ts";
import {the} from "./util.ts";

export type ButtonMode = "scroll_to_bottom" | "next_unread_topic" | "next_unread_dm_conversation";

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

export let mode: ButtonMode = "scroll_to_bottom";
let hide_timer: ReturnType<typeof setInterval> | undefined;
let scrolled_away_from_bottom_of_list_id: number | undefined;

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

function hide(): void {
    clearInterval(hide_timer);
    $("#scroll-to-bottom-button-container").removeClass("show");
}

function show(): void {
    clearInterval(hide_timer);
    $("#scroll-to-bottom-button-container").addClass("show");
}

function hide_once_not_hovered(): void {
    clearInterval(hide_timer);
    const $container = $("#scroll-to-bottom-button-container");
    hide_timer = setInterval(() => {
        // Check if the user is hovered over the scroll-to-bottom
        // button every 3 seconds to allow time for interaction.
        // If the user is not hovered on the button, hide the button
        // and clear the timer until the next scroll event triggers
        // showing the button again.
        if (!the($container).matches(":hover")) {
            hide();
        }
    }, 3000);
}

function at_bottom_of_view(): boolean {
    assert(message_lists.current !== undefined);
    // Seeing the last rendered message is not enough: newer messages
    // may be outside the render window, or not fetched yet.
    return (
        message_lists.current.view.is_end_rendered() &&
        message_viewport.bottom_rendered_message_visible()
    );
}

function next_unread_conversation_mode(): ButtonMode | undefined {
    assert(message_lists.current !== undefined);
    if (page_params.is_spectator) {
        // Spectators have no unread messages to navigate to.
        return undefined;
    }

    const filter = message_lists.current.data.filter;
    if (filter.can_show_next_unread_topic_conversation_button()) {
        return "next_unread_topic";
    }
    if (filter.can_show_next_unread_dm_conversation_button()) {
        return "next_unread_dm_conversation";
    }
    return undefined;
}

// Called when a scroll that was not triggered by the keyboard starts.
export function show_scroll_to_bottom_button(): void {
    if (
        message_lists.current === undefined ||
        message_lists.current.visibly_empty() ||
        at_bottom_of_view()
    ) {
        // Only show scroll to bottom button when
        // last message is not visible in the
        // current scroll position.
        return;
    }

    const $container = $("#scroll-to-bottom-button-container");
    if (mode !== "scroll_to_bottom" && $container.hasClass("show")) {
        // The feed may only be passing through this position, e.g.,
        // while autoscrolling to show a newly arrived message, so we
        // let update() decide what to show once the scroll finishes.
        scrolled_away_from_bottom_of_list_id = message_lists.current.id;
        return;
    }

    set_mode("scroll_to_bottom");
    show();
}

// Called whenever the scroll position or the contents of the message
// feed may have changed.
export function update(): void {
    if (message_scroll_state.actively_scrolling) {
        // The feed is not in its final position yet; we are called
        // again once the scroll finishes.
        return;
    }

    // A scroll that finished after a change of narrow says nothing
    // about the view now being shown.
    const scrolled_away =
        scrolled_away_from_bottom_of_list_id !== undefined &&
        scrolled_away_from_bottom_of_list_id === message_lists.current?.id;
    scrolled_away_from_bottom_of_list_id = undefined;

    if (message_lists.current === undefined || message_lists.current.visibly_empty()) {
        // Scroll to bottom button is not for non-message views.
        hide();
        return;
    }

    if (at_bottom_of_view()) {
        const next_mode = next_unread_conversation_mode();
        if (next_mode === undefined) {
            hide();
            return;
        }
        set_mode(next_mode);
        show();
        return;
    }

    if (mode !== "scroll_to_bottom") {
        if (scrolled_away) {
            set_mode("scroll_to_bottom");
            show();
        } else {
            // Only a mouse scroll reveals the scroll to bottom
            // button. The arrow stays while the button fades out;
            // the mode is set again before it is next shown.
            hide();
        }
    }

    if ($("#scroll-to-bottom-button-container").hasClass("show")) {
        hide_once_not_hovered();
    }
}

export function initialize(): void {
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

    const $container = $("#scroll-to-bottom-button-container").expectOne();
    // Delete the tippy tooltip whenever the fadeout animation for
    // this button is finished. This is necessary because the fading animation
    // confuses Tippy's built-in `data-reference-hidden` feature.
    $container.on("transitionend", (e) => {
        assert(e.originalEvent instanceof TransitionEvent);
        // make sure the class is not currently showing
        if (e.originalEvent.propertyName === "visibility" && !$container.hasClass("show")) {
            get_tooltip()?.destroy();
        }
    });
}
