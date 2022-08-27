import * as pm_conversations from "./pm_conversations";
import * as stream_data from "./stream_data";
import * as stream_sort from "./stream_sort";
import * as stream_topic_history from "./stream_topic_history";
import * as topic_list from "./topic_list";
import * as topic_list_data from "./topic_list_data";
import * as unread from "./unread";
import * as user_topics from "./user_topics";

export function next_topic(streams, get_topics, has_unread_messages, curr_stream, curr_topic) {
    // curr_stream_widget_id is used only for the TopicListWidget associated with left-sidebar filter
    const curr_stream_widget_id = topic_list.active_stream_id();
    const curr_stream_index = streams.indexOf(curr_stream); // -1 if not found

    if (curr_stream_index >= 0) {
        // Use 2 pass approach. First pass (filtered_topics_in_stream) iterates all topics that match
        // the left-sidebar filter. Second pass (all_topics_in_stream) iterates all topics in the
        // entire unfiltered stream. This 2 pass approach was made for users to jump to the next
        // unread topic (with respect to the left-sidebar filter) in a stream using 'n' hotkey aka
        // 'n_key', rather than jumping to the next unread topic overall, which disregards a filter.
        const stream = streams[curr_stream_index];
        const filtered_topics_in_stream = topic_list_data.get_list_info(
            curr_stream_widget_id,
            true,
        ).items;
        const all_topics_in_stream = get_topics(stream);
        // first "pass" --> check all filtered topics first for unread topics. Return topic if found.
        if (filtered_topics_in_stream.length > 0) {
            let curr_topic_index = -1; // assume topic not found intitially
            for (const [i, element] of filtered_topics_in_stream.entries()) {
                if (element.topic_name === curr_topic) {
                    curr_topic_index = i;
                }
            }

            for (let i = curr_topic_index + 1; i < filtered_topics_in_stream.length; i += 1) {
                const topic = filtered_topics_in_stream[i].topic_name;
                if (has_unread_messages(stream, topic)) {
                    return {stream, topic};
                }
            }

            for (let i = 0; i < curr_topic_index; i += 1) {
                const topic = filtered_topics_in_stream[i].topic_name;
                if (has_unread_messages(stream, topic)) {
                    return {stream, topic};
                }
            }
        }
        // Second "pass" --> Check all topics in current stream for unread topics. All filtered
        // messages should be read by this point, so this if statement will return the
        // next unread unfiltered topic in this stream.
        if (all_topics_in_stream.length > 0) {
            const curr_topic_index = all_topics_in_stream.indexOf(curr_topic); // -1 if not found
            for (let i = curr_topic_index + 1; i < all_topics_in_stream.length; i += 1) {
                const topic = all_topics_in_stream[i];
                if (has_unread_messages(stream, topic)) {
                    return {stream, topic};
                }
            }

            for (let i = 0; i < curr_topic_index; i += 1) {
                const topic = all_topics_in_stream[i];
                if (has_unread_messages(stream, topic)) {
                    return {stream, topic};
                }
            }
        }
    }

    // Find next unread message in all other streams. No left-sidebar topic filters are
    // applied to other streams since topic filters are stream-specific.
    for (let i = curr_stream_index + 1; i < streams.length; i += 1) {
        const stream = streams[i];
        for (const topic of get_topics(stream)) {
            if (has_unread_messages(stream, topic)) {
                return {stream, topic};
            }
        }
    }

    for (let i = 0; i < curr_stream_index; i += 1) {
        const stream = streams[i];
        for (const topic of get_topics(stream)) {
            if (has_unread_messages(stream, topic)) {
                return {stream, topic};
            }
        }
    }

    return undefined;
}

export function get_next_topic(curr_stream, curr_topic) {
    let my_streams = stream_sort.get_streams();

    my_streams = my_streams.filter((stream_name) => {
        if (!stream_data.is_stream_muted_by_name(stream_name)) {
            return true;
        }
        if (stream_name === curr_stream) {
            // We can use n within a muted stream if we are
            // currently narrowed to it.
            return true;
        }
        return false;
    });

    function get_unmuted_topics(stream_name) {
        const stream_id = stream_data.get_stream_id(stream_name);
        let topics = stream_topic_history.get_recent_topic_names(stream_id);
        topics = topics.filter((topic) => !user_topics.is_topic_muted(stream_id, topic));
        return topics;
    }

    function has_unread_messages(stream_name, topic) {
        const stream_id = stream_data.get_stream_id(stream_name);
        return unread.topic_has_any_unread(stream_id, topic);
    }

    return next_topic(my_streams, get_unmuted_topics, has_unread_messages, curr_stream, curr_topic);
}

export function get_next_unread_pm_string(curr_pm) {
    const my_pm_strings = pm_conversations.recent.get_strings();
    const curr_pm_index = my_pm_strings.indexOf(curr_pm); // -1 if not found

    for (let i = curr_pm_index + 1; i < my_pm_strings.length; i += 1) {
        if (unread.num_unread_for_person(my_pm_strings[i]) > 0) {
            return my_pm_strings[i];
        }
    }

    for (let i = 0; i < curr_pm_index; i += 1) {
        if (unread.num_unread_for_person(my_pm_strings[i]) > 0) {
            return my_pm_strings[i];
        }
    }

    return undefined;
}

export function get_next_stream(curr_stream) {
    const my_streams = stream_sort.get_streams();
    const curr_stream_index = my_streams.indexOf(curr_stream);
    return my_streams[
        curr_stream_index < 0 || curr_stream_index === my_streams.length - 1
            ? 0
            : curr_stream_index + 1
    ];
}

export function get_prev_stream(curr_stream) {
    const my_streams = stream_sort.get_streams();
    const curr_stream_index = my_streams.indexOf(curr_stream);
    return my_streams[curr_stream_index <= 0 ? my_streams.length - 1 : curr_stream_index - 1];
}
