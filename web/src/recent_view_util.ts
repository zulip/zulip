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

export function get_key_from_conversation_data(
    data:
        | {
              type: "private";
              to_user_ids: string;
          }
        | {
              type: "stream";
              stream_id: number;
              topic: string;
          },
): string {
    if (data.type === "private") {
        // The to_user_ids field on a direct message object is a
        // string containing the user IDs involved in the message in
        // sorted order.
        return data.to_user_ids;
    }

    // For messages with type = "stream".
    return get_topic_key(data.stream_id, data.topic);
}
