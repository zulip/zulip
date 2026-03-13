import $ from "jquery";
import assert from "minimalistic-assert";

import {Typeahead} from "./bootstrap_typeahead.ts";
import type {TypeaheadInputElement} from "./bootstrap_typeahead.ts";
import {$t} from "./i18n.ts";
import * as narrow_state from "./narrow_state.ts";
import * as stream_data from "./stream_data.ts";
import * as stream_topic_history from "./stream_topic_history.ts";
import * as topic_filter_pill from "./topic_filter_pill.ts";
import type {TopicFilterPill, TopicFilterPillWidget} from "./topic_filter_pill.ts";

export let left_sidebar_filter_pill_widget: TopicFilterPillWidget | null = null;
export let left_sidebar_filter_typeahead: Typeahead<TopicFilterPill> | undefined;

export function rewire_left_sidebar_filter_pill_widget(
    value: typeof left_sidebar_filter_pill_widget,
): void {
    left_sidebar_filter_pill_widget = value;
}

export function rewire_left_sidebar_filter_typeahead(
    value: typeof left_sidebar_filter_typeahead,
): void {
    left_sidebar_filter_typeahead = value;
}

const filter_placeholder_text = $t({defaultMessage: "Filter"});
const default_filter_placeholder_text = $t({defaultMessage: "Filter left sidebar"});

function get_narrowed_subscribed_stream_id(): number | undefined {
    const stream_id = narrow_state.stream_id(narrow_state.filter(), true);
    if (stream_id === undefined || !stream_data.is_subscribed(stream_id)) {
        return undefined;
    }

    return stream_id;
}

export function topic_state_filter_applies(): boolean {
    return get_narrowed_subscribed_stream_id() !== undefined;
}

export function get_effective_topics_state_for_search(): string {
    const topics_state = get_topics_state();
    if (topics_state === "" || !topic_state_filter_applies()) {
        return "";
    }

    return topics_state;
}

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

export function get_topics_state(): string {
    const pills = left_sidebar_filter_pill_widget?.items() ?? [];
    return topic_filter_pill.get_single_pill_syntax(
        pills,
        "Multiple pills found in left sidebar filter input.",
    );
}

export function clear_without_updating(): void {
    left_sidebar_filter_pill_widget?.clear(true);
    clear_query_without_updating();
}

export function clear_query_without_updating(): void {
    $("#left-sidebar-filter-query").empty();
    update_left_sidebar_filter_placeholder();
}

export function clear_left_sidebar_filter(e: JQuery.Event): void {
    e.stopPropagation();
    left_sidebar_filter_typeahead?.hide();
    clear_without_updating();
    $("#left-sidebar-filter-input").trigger("input");
    $("#left-sidebar-filter-query").trigger("blur");
}

export function is_typeahead_shown(): boolean {
    return left_sidebar_filter_typeahead?.shown ?? false;
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
    left_sidebar_filter_pill_widget.onPillCreate(() => {
        update_left_sidebar_filter_placeholder();
        $("#left-sidebar-filter-input").trigger("input");
    });
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

    $input.on("keydown", (e: JQuery.KeyDownEvent) => {
        if (e.key === "Enter") {
            e.preventDefault();
            e.stopPropagation();
        } else if (e.key === ",") {
            e.stopPropagation();
        }
    });

    left_sidebar_filter_pill_widget.onPillRemove(() => {
        update_left_sidebar_filter_placeholder();
        $("#left-sidebar-filter-input").trigger("input");
    });

    update_left_sidebar_filter_placeholder();
}
