import {$} from "jquery";

import * as loading from "./loading.ts";
import * as util from "./util.ts";

export const MIN_TOP_OF_FEED_INDICATOR_DISPLAY_MS = 750;
export const TOP_OF_FEED_INDICATOR_FADE_OUT_MS = 200;

let top_of_feed_indicator_showing = false;
let loading_newer_messages_indicator_showing = false;

// The indicator at the top of the feed is shown for two reasons: the
// initial page load, until the initial message fetch completes, and a
// fetch for older messages. It stays up while either applies.
let initial_page_load_pending = false;
let fetching_older_messages = false;
let top_of_feed_indicator_shown_at = 0;
let pending_hide_top_of_feed_indicator_timer: ReturnType<typeof setTimeout> | undefined;
let top_of_feed_indicator_fade_out_timer: ReturnType<typeof setTimeout> | undefined;
let run_when_top_of_feed_indicator_hidden_callbacks: (() => void)[] = [];

function cancel_pending_hide_top_of_feed_indicator(): void {
    if (pending_hide_top_of_feed_indicator_timer !== undefined) {
        clearTimeout(pending_hide_top_of_feed_indicator_timer);
        pending_hide_top_of_feed_indicator_timer = undefined;
    }
}

function top_of_feed_in_view(): boolean {
    // Same check as message_viewport.at_rendered_top, duplicated here
    // to avoid an import cycle.
    return window.scrollY <= 0;
}

function show_top_of_feed_indicator_now(): void {
    cancel_pending_hide_top_of_feed_indicator();
    if (!top_of_feed_indicator_showing) {
        top_of_feed_indicator_shown_at = Date.now();
        if (top_of_feed_indicator_fade_out_timer !== undefined) {
            clearTimeout(top_of_feed_indicator_fade_out_timer);
            top_of_feed_indicator_fade_out_timer = undefined;
        }
        $("#top_of_feed_loading_indicator").removeClass("fade-out").addClass("loading");
        top_of_feed_indicator_showing = true;
    }
}

function hide_top_of_feed_indicator_now(): void {
    cancel_pending_hide_top_of_feed_indicator();
    if (top_of_feed_indicator_showing) {
        $("#top_of_feed_loading_indicator").removeClass("loading").addClass("fade-out");
        top_of_feed_indicator_fade_out_timer = setTimeout(() => {
            $("#top_of_feed_loading_indicator").removeClass("fade-out");
            top_of_feed_indicator_fade_out_timer = undefined;
        }, TOP_OF_FEED_INDICATOR_FADE_OUT_MS);
        top_of_feed_indicator_showing = false;
    }
    const callbacks = run_when_top_of_feed_indicator_hidden_callbacks;
    run_when_top_of_feed_indicator_hidden_callbacks = [];
    for (const callback of callbacks) {
        callback();
    }
}

function update_top_of_feed_indicator(): void {
    // The initial page load always shows the indicator. Loading older
    // messages only shows it when the user is at the top of the feed.
    const should_show =
        initial_page_load_pending || (fetching_older_messages && top_of_feed_in_view());
    if (should_show) {
        show_top_of_feed_indicator_now();
        return;
    }
    if (!top_of_feed_indicator_showing) {
        return;
    }
    if (!top_of_feed_in_view()) {
        hide_top_of_feed_indicator_now();
        return;
    }
    const remaining_ms = util.get_remaining_time(
        top_of_feed_indicator_shown_at,
        MIN_TOP_OF_FEED_INDICATOR_DISPLAY_MS,
    );
    if (remaining_ms > 0) {
        cancel_pending_hide_top_of_feed_indicator();
        pending_hide_top_of_feed_indicator_timer = setTimeout(
            hide_top_of_feed_indicator_now,
            remaining_ms,
        );
        return;
    }
    hide_top_of_feed_indicator_now();
}

export function update_for_scroll_position(): void {
    // Scrolling can bring the top of the feed into or out of view while
    // older messages are being fetched, or while the line is still up
    // for its minimum display time after one.
    if (fetching_older_messages || top_of_feed_indicator_showing) {
        update_top_of_feed_indicator();
    }
}

export function run_when_top_of_feed_indicator_hidden(callback: () => void): void {
    // Notices that say there is nothing more to load should not appear
    // while the indicator is still being kept on screen; they wait
    // until it goes away.
    if (!top_of_feed_indicator_showing) {
        callback();
        return;
    }
    run_when_top_of_feed_indicator_hidden_callbacks.push(callback);
}

export function cancel_run_when_top_of_feed_indicator_hidden(): void {
    run_when_top_of_feed_indicator_hidden_callbacks = [];
}

export function show_loading_initial_page(): void {
    initial_page_load_pending = true;
    update_top_of_feed_indicator();
}

export function hide_loading_initial_page(): void {
    initial_page_load_pending = false;
    update_top_of_feed_indicator();
}

export function show_loading_older(): void {
    fetching_older_messages = true;
    update_top_of_feed_indicator();
}

export function hide_loading_older(): void {
    fetching_older_messages = false;
    update_top_of_feed_indicator();
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
    // Called when resetting the UI for a new narrow, so hide right away,
    // unless the initial page load is still pending. Anything waiting
    // on the old narrow's indicator is stale.
    cancel_run_when_top_of_feed_indicator_hidden();
    fetching_older_messages = false;
    if (!initial_page_load_pending) {
        hide_top_of_feed_indicator_now();
    }
    hide_loading_newer();
}
