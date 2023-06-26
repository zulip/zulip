import * as pm_conversations from "./pm_conversations";
import * as stream_data from "./stream_data";
import * as stream_list_sort from "./stream_list_sort";
import * as stream_topic_history from "./stream_topic_history";
import * as unread from "./unread";
import * as user_topics from "./user_topics";

export function next_topic(streams, get_topics, has_unread_messages, curr_stream, curr_topic) {
    const curr_stream_index = streams.indexOf(curr_stream); // -1 if not found

    if (curr_stream_index >= 0) {
        const stream = streams[curr_stream_index];
        const topics = get_topics(stream);
        const curr_topic_index = topics.indexOf(curr_topic); // -1 if not found

        for (let i = curr_topic_index + 1; i < topics.length; i += 1) {
            const topic = topics[i];
            if (has_unread_messages(stream, topic)) {
                return {stream, topic};
            }
        }

        for (let i = 0; i < curr_topic_index; i += 1) {
            const topic = topics[i];
            if (has_unread_messages(stream, topic)) {
                return {stream, topic};
            }
        }
    }

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
    let my_streams = stream_list_sort.get_streams();

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
        if (unread.num_unread_for_user_ids_string(my_pm_strings[i]) > 0) {
            return my_pm_strings[i];
        }
    }

    for (let i = 0; i < curr_pm_index; i += 1) {
        if (unread.num_unread_for_user_ids_string(my_pm_strings[i]) > 0) {
            return my_pm_strings[i];
        }
    }

    return undefined;
}

export function get_next_stream(curr_stream) {
    const my_streams = stream_list_sort.get_streams();
    const curr_stream_index = my_streams.indexOf(curr_stream);
    return my_streams[
        curr_stream_index < 0 || curr_stream_index === my_streams.length - 1
            ? 0
            : curr_stream_index + 1
    ];
}

export function get_prev_stream(curr_stream) {
    const my_streams = stream_list_sort.get_streams();
    const curr_stream_index = my_streams.indexOf(curr_stream);
    return my_streams[curr_stream_index <= 0 ? my_streams.length - 1 : curr_stream_index - 1];
}
