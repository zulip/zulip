import type {Message} from "./types";

let is_view_visible = false;
let current_stream_id: number | null = null;

export function set_visible(value: boolean, stream_id: number | null = null): void {
    is_view_visible = value;
    current_stream_id = stream_id;
}

export function is_visible(): boolean {
    return is_view_visible;
}

export function is_main_view_visible(): boolean {
    return is_view_visible && current_stream_id === null;
}

export function is_stream_view_visible(stream_id: number = -1): boolean {
    // If no stream_id is provided, we return true if *any* stream view is visible.
    if (stream_id !== -1) {
        return is_view_visible && stream_id === current_stream_id;
    }
    return is_view_visible && current_stream_id !== null;
}

export function get_stream_view_id(): number | null {
    return current_stream_id;
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
