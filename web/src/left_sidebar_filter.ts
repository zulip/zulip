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
    if (pills.length === 0) {
        return "";
    }

    // For now, there is only one pill in the left sidebar filter input.
    // This is because we only allow one topic filter pill at a time.
    // If we allow multiple pills in the future, we may need to
    // change this logic to return the syntax of all pills.
    if (pills.length > 1) {
        blueslip.warn("Multiple pills found in left sidebar filter input.");
    }

    return pills[0]!.syntax;
}

export function clear_without_updating(): void {
    left_sidebar_filter_pill_widget?.clear(true);
    $("#left-sidebar-filter-query").empty();
    update_left_sidebar_filter_placeholder();
}

export function clear_left_sidebar_filter(e: JQuery.Event): void {
    e.stopPropagation();
    left_sidebar_filter_typeahead?.hide();
    left_sidebar_filter_pill_widget?.clear(true);

    const $input = $("#left-sidebar-filter-query");
    $input.empty();
    update_left_sidebar_filter_placeholder();
    $("#left-sidebar-filter-input").trigger("input");
    $input.trigger("blur");
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
    left_sidebar_filter_pill_widget.onPillCreate(update_left_sidebar_filter_placeholder);
    left_sidebar_filter_pill_widget.onTextInputHook(update_left_sidebar_filter_placeholder);

    const typeahead_input: TypeaheadInputElement = {
        $element: $input,
        type: "contenteditable",
    };

    const options = {
        ...topic_filter_pill.get_typeahead_base_options(),
        source() {
            const stream_id = narrow_state.stream_id(narrow_state.filter(), true);
            if (stream_id === undefined || !stream_data.is_subscribed(stream_id)) {
                return [];
            }
            if (!stream_topic_history.stream_has_locally_available_resolved_topics(stream_id)) {
                return [];
            }
            const $pills = $("#left-sidebar-filter-input .pill");
            if ($pills.length > 0) {
                return [];
            }
            return [...topic_filter_pill.filter_options];
        },
        updater(item: TopicFilterPill) {
            assert(left_sidebar_filter_pill_widget !== null);
            left_sidebar_filter_pill_widget.clear(true);
            left_sidebar_filter_pill_widget.appendValue(item.syntax);
            $input.text("");
            $input.trigger("focus");
            $("#left-sidebar-filter-input").trigger("input");
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
