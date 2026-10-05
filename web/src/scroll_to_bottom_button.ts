import {$} from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import * as message_lists from "./message_lists.ts";
import * as message_scroll_state from "./message_scroll_state.ts";
import * as message_viewport from "./message_viewport.ts";
import * as narrow_state from "./narrow_state.ts";
import {the} from "./util.ts";

let hide_timer: ReturnType<typeof setInterval> | undefined;

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

function stop_hide_timer(): void {
    clearInterval(hide_timer);
    hide_timer = undefined;
}

function hide(): void {
    stop_hide_timer();
    $("#scroll-to-bottom-button-container").removeClass("show");
}

function show(): void {
    stop_hide_timer();
    $("#scroll-to-bottom-button-container").addClass("show");
}

function is_shown(): boolean {
    return $("#scroll-to-bottom-button-container").hasClass("show");
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

    if (!above_bottom_of_view()) {
        hide();
        return;
    }

    if (is_shown()) {
        hide_once_not_hovered();
    }
}

export function show_scroll_to_bottom_button(): void {
    if (!above_bottom_of_view()) {
        return;
    }

    show();
}

export function initialize(on_click: {scroll_to_bottom: () => void}): void {
    $("body").on("click", "#scroll-to-bottom-button-clickable-area", (e) => {
        e.preventDefault();
        e.stopPropagation();

        // Since it take a few milliseconds for this button complete disappear transition,
        // it is possible for user to click it before it hides when switching narrows.
        if (narrow_state.is_message_feed_visible()) {
            on_click.scroll_to_bottom();
        }
    });

    $(document).on("keydown", (e) => {
        if (e.shiftKey || e.ctrlKey || e.metaKey) {
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
            const tooltip = the(
                $<tippy.ReferenceElement>("#scroll-to-bottom-button-clickable-area"),
            )._tippy;
            // make sure the tooltip exists and the class is not currently showing
            if (tooltip && !is_shown()) {
                tooltip.destroy();
            }
        }
    });
}
