import * as people from "./people";
import {get_key_from_message} from "./recent_topics_util";

export const topics = new Map(); // Key is stream-id:topic.

export function process_message(msg) {
    // This function returns if topic_data
    // has changed or not.

    // Initialize topic and pm data
    // Key for private message is the user id's
    // to whom the message is begin sent.
    const key = get_key_from_message(msg);
    if (!topics.has(key)) {
        topics.set(key, {
            last_msg_id: -1,
            participated: false,
            type: msg.type,
        });
    }
    // Update topic data
    const is_ours = people.is_my_user_id(msg.sender_id);
    const topic_data = topics.get(key);
    if (topic_data.last_msg_id < msg.id) {
        // NOTE: This also stores locally echoed msg_id which
        // has not been successfully received from the server.
        // We store it now and reify it when response is available
        // from server.
        topic_data.last_msg_id = msg.id;
    }
    // TODO: Add backend support for participated topics.
    // Currently participated === recently participated
    // i.e. Only those topics are participated for which we have the user's
    // message fetched in the topic. Ideally we would want this to be attached
    // to topic info fetched from backend, which is currently not a thing.
    topic_data.participated = is_ours || topic_data.participated;
    return true;
}

function get_sorted_topics() {
    // Sort all recent topics by last message time.
    return new Map(
        Array.from(topics.entries()).sort((a, b) => b[1].last_msg_id - a[1].last_msg_id),
    );
}

export function get() {
    return get_sorted_topics();
}

export function reify_message_id_if_available(opts) {
    // We don't need to reify the message_id of the topic
    // if a new message arrives in the topic from another user,
    // since it replaces the last_msg_id of the topic which
    // we were trying to reify.
    for (const [, value] of topics.entries()) {
        if (value.last_msg_id === opts.old_id) {
            value.last_msg_id = opts.new_id;
            return true;
        }
    }
    return false;
}
