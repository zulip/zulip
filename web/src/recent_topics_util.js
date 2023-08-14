let is_rt_visible = false;

export function set_visible(value) {
    is_rt_visible = value;
}

export function is_visible() {
    return is_rt_visible;
}

export function get_topic_key(stream_id, topic) {
    return stream_id + ":" + topic.toLowerCase();
}

export function get_key_from_message(msg) {
    if (msg.type === "private") {
        // The to_user_ids field on a direct message object is a
        // string containing the user IDs involved in the message in
        // sorted order.
        return msg.to_user_ids;
    } else if (msg.type === "stream") {
        return get_topic_key(msg.stream_id, msg.topic);
    }
    throw new Error(`Invalid message type ${msg.type}`);
}
