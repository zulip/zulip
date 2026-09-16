import {$} from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import * as message_lists from "./message_lists.ts";
import * as message_viewport from "./message_viewport.ts";
import {the} from "./util.ts";

let hide_scroll_to_bottom_timer: ReturnType<typeof setInterval> | undefined;
export function hide_scroll_to_bottom(): void {
    const $show_scroll_to_bottom_button = $("#scroll-to-bottom-button-container");
    if (message_lists.current === undefined) {
        // Scroll to bottom button is not for non-message views.
        $show_scroll_to_bottom_button.removeClass("show");
        return;
    }

    if (
        message_viewport.bottom_rendered_message_visible() ||
        message_lists.current.visibly_empty()
    ) {
        // If last message is visible, just hide the
        // scroll to bottom button.
        $show_scroll_to_bottom_button.removeClass("show");
        return;
    }

    clearInterval(hide_scroll_to_bottom_timer);
    hide_scroll_to_bottom_timer = setInterval(() => {
        // Check if the user is hovered over the scroll-to-bottom
        // button every 3 seconds to allow time for interaction.
        // If the user is not hovered on the button, hide the button
        // and clear the timer until the next scroll event triggers
        // showing the button again.
        if (!the($show_scroll_to_bottom_button).matches(":hover")) {
            $show_scroll_to_bottom_button.removeClass("show");
            clearInterval(hide_scroll_to_bottom_timer);
        }
    }, 3000);
}

export function show_scroll_to_bottom_button(): void {
    if (message_viewport.bottom_rendered_message_visible()) {
        // Only show scroll to bottom button when
        // last message is not visible in the
        // current scroll position.
        return;
    }

    clearInterval(hide_scroll_to_bottom_timer);
    $("#scroll-to-bottom-button-container").addClass("show");
}

export function initialize(): void {
    $(document).on("keydown", (e) => {
        if (e.shiftKey || e.ctrlKey || e.metaKey) {
            return;
        }

        // Hide scroll to bottom button on any keypress.
        // Keyboard users are very less likely to use this button.
        $("#scroll-to-bottom-button-container").removeClass("show");
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
            if (tooltip && !$show_scroll_to_bottom_button.hasClass("show")) {
                tooltip.destroy();
            }
        }
    });
}
