import $ from "jquery";
import assert from "minimalistic-assert";

import * as blueslip from "./blueslip.ts";
import {Typeahead} from "./bootstrap_typeahead.ts";
import type {TypeaheadInputElement} from "./bootstrap_typeahead.ts";
import {$t} from "./i18n.ts";
import * as narrow_state from "./narrow_state.ts";
import * as stream_data from "./stream_data.ts";
import * as stream_topic_history from "./stream_topic_history.ts";
import * as topic_filter_pill from "./topic_filter_pill.ts";
import type {TopicFilterPill, TopicFilterPillWidget} from "./topic_filter_pill.ts";

let left_sidebar_filter_pill_widget: TopicFilterPillWidget | null = null;
let left_sidebar_filter_typeahead: Typeahead<TopicFilterPill> | undefined;

function get_narrowed_subscribed_stream_id(): number | undefined {
    const stream_id = narrow_state.stream_id(narrow_state.filter(), true);
    if (stream_id === undefined || !stream_data.is_subscribed(stream_id)) {
        return undefined;
    }

    return stream_id;
}

function topic_state_filter_applies(): boolean {
    return get_narrowed_subscribed_stream_id() !== undefined;
}

export function get_raw_topics_state(): string {
    const pills = left_sidebar_filter_pill_widget?.items() ?? [];
    if (pills.length === 0) {
        return "";
    }

    if (pills.length > 1) {
        blueslip.warn("Multiple pills found in left sidebar filter input.");
    }

    return pills[0]!.syntax;
}

export function get_effective_topics_state_for_search(): string {
    const topics_state = get_raw_topics_state();
    if (topics_state === "" || !topic_state_filter_applies()) {
        return "";
    }

    // Once a topic-state pill exists, it stays active for any subscribed-stream
    // narrow. More specific constraints, like whether local resolved-topic
    // metadata is available, only affect which suggestions we offer in the
    // typeahead, not whether an existing pill continues to filter results.
    return topics_state;
}

const filter_placeholder_text = $t({defaultMessage: "Filter"});
const default_filter_placeholder_text = $t({defaultMessage: "Filter left sidebar"});

function update_left_sidebar_filter_placeholder(): void {
    const $input = $("#left-sidebar-filter-query");
    const has_filter_pill = (left_sidebar_filter_pill_widget?.items().length ?? 0) > 0;
    const has_search_term = $input.text().trim() !== "";
    if (has_search_term) {
        $input.attr("data-placeholder", "");
        return;
    }
    $input.attr(
        "data-placeholder",
        has_filter_pill ? filter_placeholder_text : default_filter_placeholder_text,
    );
}

export function clear_query_without_updating(): void {
    $("#left-sidebar-filter-query").empty();
    update_left_sidebar_filter_placeholder();
}

export function has_left_sidebar_filter_value(): boolean {
    return $("#left-sidebar-filter-query").text().trim() !== "" || get_raw_topics_state() !== "";
}

export function clear_query(): void {
    clear_query_without_updating();
    notify_left_sidebar_filter_changed();
}
function clear_without_updating(): void {
    left_sidebar_filter_pill_widget?.clear(true);
    clear_query_without_updating();
}

function notify_left_sidebar_filter_changed(): void {
    $("#left-sidebar-filter-input").trigger("input");
}

function update_left_sidebar_filter_after_content_change(): void {
    update_left_sidebar_filter_placeholder();
    // Left-sidebar filtering listens to the pill container's `input` event.
    // Trigger it after pill add/remove so the sidebar recomputes visible
    // rows immediately.
    notify_left_sidebar_filter_changed();
}

export function clear_left_sidebar_filter(e: JQuery.Event): void {
    e.stopPropagation();
    left_sidebar_filter_typeahead?.hide();
    clear_without_updating();
    // Clearing the pill widget/query above does not go through the normal
    // contenteditable input flow, so explicitly update sidebar matches.
    notify_left_sidebar_filter_changed();
    // Clearing the filter should also leave the search field, so follow-up
    // keyboard input is no longer treated as left-sidebar search input.
    $("#left-sidebar-filter-query").trigger("blur");
}

export function is_typeahead_shown(): boolean {
    return left_sidebar_filter_typeahead?.shown ?? false;
}

function handle_typeahead_keydown(e: JQuery.KeyDownEvent): void {
    if (e.key === "Enter") {
        // Reserve Enter for the typeahead and left-sidebar keyboard navigation.
        // Do not let other handlers process it here.
        e.preventDefault();
        e.stopPropagation();
    } else if (e.key === ",") {
        // input_pill.ts converts comma-separated text into pills by default.
        // Topic-state filters only allow a single pill, so we block that
        // generic comma handling and keep pill creation on the typeahead path.
        e.stopPropagation();
    }
}

export function setup_left_sidebar_filter_typeahead(): void {
    left_sidebar_filter_typeahead?.unlisten();
    left_sidebar_filter_typeahead = undefined;
    left_sidebar_filter_pill_widget = null;

    const $input = $("#left-sidebar-filter-query");
    const $pill_container = $("#left-sidebar-filter-input");

    if ($input.length === 0 || $pill_container.length === 0) {
        return;
    }

    left_sidebar_filter_pill_widget = topic_filter_pill.create_pills($pill_container);
    left_sidebar_filter_pill_widget.onPillCreate(update_left_sidebar_filter_after_content_change);
    left_sidebar_filter_pill_widget.onTextInputHook(update_left_sidebar_filter_placeholder);

    const typeahead_input: TypeaheadInputElement = {
        $element: $input,
        type: "contenteditable",
    };

    const options = {
        ...topic_filter_pill.get_typeahead_base_options(),
        source() {
            const stream_id = get_narrowed_subscribed_stream_id();
            if (stream_id === undefined) {
                return [];
            }

            const pills = left_sidebar_filter_pill_widget?.items() ?? [];
            const query = $input.text().trim();

            const has_locally_available_resolved_topics =
                stream_topic_history.stream_has_locally_available_resolved_topics(stream_id);
            return topic_filter_pill.get_matching_filter_options({
                current_items: pills,
                query,
                allow_resolved_topic_filters: has_locally_available_resolved_topics,
            });
        },
        updater(item: TopicFilterPill) {
            assert(left_sidebar_filter_pill_widget !== null);
            left_sidebar_filter_pill_widget.clear(true);
            left_sidebar_filter_pill_widget.appendValue(item.syntax);
            $input.text("");
            $input.trigger("focus");
            return $input.text().trim();
        },
    };

    left_sidebar_filter_typeahead = new Typeahead(typeahead_input, options);

    $input.on("keydown", handle_typeahead_keydown);

    left_sidebar_filter_pill_widget.onPillRemove(update_left_sidebar_filter_after_content_change);

    update_left_sidebar_filter_placeholder();
}
