import {$} from "jquery";

import * as loading from "./loading.ts";

let loading_older_messages_indicator_showing = false;
let loading_newer_messages_indicator_showing = false;

// The indicator at the top of the feed is shown for two reasons: the
// initial page load, until the initial message fetch completes, and a
// fetch for older messages. It stays up while either applies.
let initial_page_load_pending = false;
let fetching_older_messages = false;

function update_top_of_feed_indicator(): void {
    const should_show = initial_page_load_pending || fetching_older_messages;
    if (should_show && !loading_older_messages_indicator_showing) {
        $(".top-messages-logo").toggleClass("loading", true);
        loading.make_indicator($("#top_of_feed_loading_indicator"), {abs_positioned: true});
        loading_older_messages_indicator_showing = true;
    } else if (!should_show && loading_older_messages_indicator_showing) {
        $(".top-messages-logo").toggleClass("loading", false);
        loading.destroy_indicator($("#top_of_feed_loading_indicator"));
        loading_older_messages_indicator_showing = false;
    }
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
    hide_loading_older();
    hide_loading_newer();
}
