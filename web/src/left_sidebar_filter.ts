import * as blueslip from "./blueslip.ts";
import * as narrow_state from "./narrow_state.ts";
import * as stream_data from "./stream_data.ts";
import type {TopicFilterPillWidget} from "./topic_filter_pill.ts";

export let left_sidebar_filter_pill_widget: TopicFilterPillWidget | null = null;

export function rewire_left_sidebar_filter_pill_widget(
    value: typeof left_sidebar_filter_pill_widget,
): void {
    left_sidebar_filter_pill_widget = value;
}

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
