import _ from "lodash";

import * as narrow_state from "./narrow_state.ts";
import * as pm_conversations from "./pm_conversations.ts";
import * as stream_data from "./stream_data.ts";
import * as stream_list_sort from "./stream_list_sort.ts";
import * as stream_topic_history from "./stream_topic_history.ts";
import * as unread from "./unread.ts";
import * as user_topics from "./user_topics.ts";

export function next_topic(
    stream_ids: number[],
    get_topics: (stream_id: number) => string[],
    has_unread_messages: (stream_id: number, topic: string) => boolean,
    curr_stream_id: number | undefined,
    curr_topic: string | undefined,
): {stream_id: number; topic: string} | undefined {
    const curr_stream_index = curr_stream_id ? stream_ids.indexOf(curr_stream_id) : -1; // -1 if not found

    if (curr_stream_index >= 0) {
        const stream_id = stream_ids[curr_stream_index]!;
        const topics = get_topics(stream_id);
        const curr_topic_index = curr_topic ? topics.indexOf(curr_topic) : -1; // -1 if not found

        for (let i = curr_topic_index + 1; i < topics.length; i += 1) {
            const topic = topics[i]!;
            if (has_unread_messages(stream_id, topic)) {
                return {stream_id, topic};
            }
        }

        for (let i = 0; i < curr_topic_index; i += 1) {
            const topic = topics[i]!;
            if (has_unread_messages(stream_id, topic)) {
                return {stream_id, topic};
            }
        }
    }

    for (let i = curr_stream_index + 1; i < stream_ids.length; i += 1) {
        const stream_id = stream_ids[i]!;
        for (const topic of get_topics(stream_id)) {
            if (has_unread_messages(stream_id, topic)) {
                return {stream_id, topic};
            }
        }
    }

    for (let i = 0; i < curr_stream_index; i += 1) {
        const stream_id = stream_ids[i]!;
        for (const topic of get_topics(stream_id)) {
            if (has_unread_messages(stream_id, topic)) {
                return {stream_id, topic};
            }
        }
    }

    return undefined;
}

export function get_next_topic(
    curr_stream_id: number | undefined,
    curr_topic: string | undefined,
    only_followed_topics: boolean,
): {stream_id: number; topic: string} | undefined {
    let my_streams = stream_list_sort.get_stream_ids();

    my_streams = my_streams.filter((stream_id) => {
        if (!stream_data.is_muted(stream_id)) {
            return true;
        }
        if (only_followed_topics) {
            // We can use Shift + N to go to unread followed topic in muted stream.
            const topics = stream_topic_history.get_recent_topic_names(stream_id);
            return topics.some((topic) => user_topics.is_topic_followed(stream_id, topic));
        }
        if (stream_id === curr_stream_id) {
            // We can use n within a muted stream if we are
            // currently narrowed to it.
            return true;
        }
        // We can use N to go to next unread unmuted/followed topic in a muted stream .
        const topics = stream_topic_history.get_recent_topic_names(stream_id);
        return topics.some((topic) => user_topics.is_topic_unmuted_or_followed(stream_id, topic));
    });

    function get_unmuted_topics(stream_id: number): string[] {
        const narrowed_steam_id = narrow_state.stream_id();
        const topics = stream_topic_history.get_recent_topic_names(stream_id);
        const narrowed_topic = narrow_state.topic();
        if (
            narrowed_steam_id !== undefined &&
            narrowed_topic !== undefined &&
            narrowed_steam_id === stream_id &&
            _.isEqual(narrow_state.filter()?.sorted_term_types(), ["stream", "topic"]) &&
            !user_topics.is_topic_unmuted_or_followed(stream_id, narrowed_topic)
        ) {
            // Here we're using N within a muted stream starting from
            // a muted topic; advance to the next not-explicitly-muted
            // unread topic in the stream, to allow using N within
            // muted streams. We'll jump back into the normal mode if
            // we land in a followed/unmuted topic, but that's OK.

            /* istanbul ignore next */
            return topics.filter((topic) => !user_topics.is_topic_muted(stream_id, topic));
        } else if (stream_data.is_muted(stream_id)) {
            return topics.filter((topic) =>
                user_topics.is_topic_unmuted_or_followed(stream_id, topic),
            );
        }
        return topics.filter((topic) => !user_topics.is_topic_muted(stream_id, topic));
    }

    function get_followed_topics(stream_id: number): string[] {
        let topics = stream_topic_history.get_recent_topic_names(stream_id);
        topics = topics.filter((topic) => user_topics.is_topic_followed(stream_id, topic));
        return topics;
    }

    if (only_followed_topics) {
        return next_topic(
            my_streams,
            get_followed_topics,
            unread.topic_has_any_unread,
            curr_stream_id,
            curr_topic,
        );
    }

    return next_topic(
        my_streams,
        get_unmuted_topics,
        unread.topic_has_any_unread,
        curr_stream_id,
        curr_topic,
    );
}

export function get_next_unread_pm_string(curr_pm: string | undefined): string | undefined {
    const my_pm_strings = pm_conversations.recent.get_strings();
    // undefined translates to "not found".
    let curr_pm_index = -1;
    if (curr_pm !== undefined) {
        curr_pm_index = my_pm_strings.indexOf(curr_pm);
    }

    for (let i = curr_pm_index + 1; i < my_pm_strings.length; i += 1) {
        if (unread.num_unread_for_user_ids_string(my_pm_strings[i]!) > 0) {
            return my_pm_strings[i];
        }
    }

    for (let i = 0; i < curr_pm_index; i += 1) {
        if (unread.num_unread_for_user_ids_string(my_pm_strings[i]!) > 0) {
            return my_pm_strings[i];
        }
    }

    return undefined;
}

export function get_next_stream(curr_stream_id: number): number | undefined {
    const my_streams = stream_list_sort.get_stream_ids();
    const curr_stream_index = my_streams.indexOf(curr_stream_id);
    return my_streams[
        curr_stream_index === -1 || curr_stream_index === my_streams.length - 1
            ? 0
            : curr_stream_index + 1
    ];
}

export function get_prev_stream(curr_stream_id: number): number | undefined {
    const my_streams = stream_list_sort.get_stream_ids();
    const curr_stream_index = my_streams.indexOf(curr_stream_id);
    return my_streams[curr_stream_index <= 0 ? my_streams.length - 1 : curr_stream_index - 1];
}
