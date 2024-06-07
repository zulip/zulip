import type {Message} from "./message_store";

let is_view_visible = false;

export const set_visible = (value: boolean): void => {
    is_view_visible = value;
};

export const is_visible = (): boolean => is_view_visible;

export const get_topic_key = (stream_id: number, topic: string): string =>
    stream_id + ":" + topic.toLowerCase();

export const get_key_from_message = (msg: Message): string => {
    if (msg.type === "private") {
        // The to_user_ids field on a direct message object is a
        // string containing the user IDs involved in the message in
        // sorted order.
        return msg.to_user_ids;
    }

    // For messages with type = "stream".
    return get_topic_key(msg.stream_id, msg.topic);
};
