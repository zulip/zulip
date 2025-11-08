import type {Message} from "./message_store.ts";

let is_view_visible = false;

export function set_visible(value: boolean): void {
    is_view_visible = value;
}

export function is_visible(): boolean {
    return is_view_visible;
}

export function get_topic_key(stream_id: number, topic: string): string {
    return stream_id + ":" + topic.toLowerCase();
}

export function get_key_from_message(msg: Message): string {
    if (msg.type === "private") {
        // The to_user_ids field on a direct message object is a
        // string containing the user IDs involved in the message in
        // sorted order.
        return msg.to_user_ids;
    }

    // For messages with type = "stream".
    return get_topic_key(msg.stream_id, msg.topic);
}
