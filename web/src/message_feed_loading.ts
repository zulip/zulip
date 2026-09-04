import {$} from "jquery";

import * as loading from "./loading.ts";
import * as util from "./util.ts";

// Keep the top-of-feed loading indicator visible for at least this
// long, so that a fast fetch doesn't make it flash briefly on screen.
export const MIN_LOADING_OLDER_INDICATOR_DISPLAY_MS = 750;

let loading_older_messages_indicator_showing = false;
let loading_newer_messages_indicator_showing = false;
let loading_older_shown_at = 0;
let pending_hide_loading_older_timer: ReturnType<typeof setTimeout> | undefined;

function cancel_pending_hide_loading_older(): void {
    if (pending_hide_loading_older_timer !== undefined) {
        clearTimeout(pending_hide_loading_older_timer);
        pending_hide_loading_older_timer = undefined;
    }
}

export function show_loading_older(): void {
    // Each fetch restarts the minimum display time, including one that
    // starts while we're waiting to hide the indicator; the pending
    // hide belongs to the previous fetch, so drop it.
    loading_older_shown_at = Date.now();
    cancel_pending_hide_loading_older();
    if (!loading_older_messages_indicator_showing) {
        $(".top-messages-logo").toggleClass("loading", true);
        loading.make_indicator($("#loading_older_messages_indicator"), {abs_positioned: true});
        loading_older_messages_indicator_showing = true;
    }
}

function hide_loading_older_now(): void {
    cancel_pending_hide_loading_older();
    if (loading_older_messages_indicator_showing) {
        $(".top-messages-logo").toggleClass("loading", false);
        loading.destroy_indicator($("#loading_older_messages_indicator"));
        loading_older_messages_indicator_showing = false;
    }
}

export function hide_loading_older(): void {
    if (!loading_older_messages_indicator_showing) {
        return;
    }
    const remaining_ms = util.get_remaining_time(
        loading_older_shown_at,
        MIN_LOADING_OLDER_INDICATOR_DISPLAY_MS,
    );
    if (remaining_ms > 0) {
        cancel_pending_hide_loading_older();
        pending_hide_loading_older_timer = setTimeout(hide_loading_older_now, remaining_ms);
        return;
    }
    hide_loading_older_now();
}

export function show_loading_newer(): void {
    if (!loading_newer_messages_indicator_showing) {
        $(".bottom-messages-logo").show();
        $(".bottom-messages-logo").toggleClass("loading", true);
        loading.make_indicator($("#loading_more_indicator"), {abs_positioned: true});
        loading_newer_messages_indicator_showing = true;
    }
}

export function hide_loading_newer(): void {
    if (loading_newer_messages_indicator_showing) {
        $(".bottom-messages-logo").hide();
        $(".bottom-messages-logo").toggleClass("loading", false);
        loading.destroy_indicator($("#loading_more_indicator"));
        loading_newer_messages_indicator_showing = false;
    }
}

export function hide_indicators(): void {
    // Called when resetting the UI for a new narrow, so hide right away.
    hide_loading_older_now();
    hide_loading_newer();
}
