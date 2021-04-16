import {all_messages_data} from "./all_messages_data";
import * as message_store from "./message_store";

/*
    The functions in this module are highly deprecated.

    We should have their callers do a better job
    of tracking messages by topic internally.
*/

export function get_messages_in_topic(stream_id, topic) {
    return all_messages_data
        .all_messages()
        .filter(
            (x) =>
                x.type === "stream" &&
                x.stream_id === stream_id &&
                x.topic.toLowerCase() === topic.toLowerCase(),
        );
}

export function get_max_message_id_in_stream(stream_id) {
    let max_message_id = 0;
    for (const msg of all_messages_data.all_messages()) {
        if (msg.type === "stream" && msg.stream_id === stream_id && msg.id > max_message_id) {
            max_message_id = msg.id;
        }
    }
    return max_message_id;
}

export function get_topics_for_message_ids(message_ids) {
    const topics = new Map(); // key = stream_id:topic
    for (const msg_id of message_ids) {
        // message_store still has data on deleted messages when this runs.
        const message = message_store.get(msg_id);
        if (message === undefined) {
            // We may not have the deleted message cached locally in
            // message_store; if so, we can just skip processing it.
            continue;
        }
        if (message.type === "stream") {
            // Create unique keys for stream_id and topic.
            const topic_key = message.stream_id + ":" + message.topic;
            topics.set(topic_key, [message.stream_id, message.topic]);
        }
    }
    return topics;
}
