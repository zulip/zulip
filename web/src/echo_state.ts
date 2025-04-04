import assert from "minimalistic-assert";

import type {Message} from "./message_store.ts";

const waiting_for_id = new Map<string, Message>();
let waiting_for_ack = new Map<string, Message>();

export function set_message_waiting_for_id(local_id: string, message: Message): void {
    waiting_for_id.set(local_id, message);
}

export function set_message_waiting_for_ack(local_id: string, message: Message): void {
    waiting_for_ack.set(local_id, message);
}

export function get_message_waiting_for_id(local_id: string): Message | undefined {
    return waiting_for_id.get(local_id);
}

export function get_message_waiting_for_ack(local_id: string): Message | undefined {
    return waiting_for_ack.get(local_id);
}

export function remove_message_from_waiting_for_id(local_id: string): void {
    waiting_for_id.delete(local_id);
}

export function remove_message_from_waiting_for_ack(local_id: string): void {
    waiting_for_ack.delete(local_id);
}

export function _patch_waiting_for_ack(data: Map<string, Message>): void {
    // Only for testing
    waiting_for_ack = data;
}

export function get_waiting_for_ack_local_ids_by_topic(channel_id: number): Map<string, number> {
    const max_message_id_by_topic = new Map<string, number>();

    const channel_messages_waiting_for_ack = [...waiting_for_ack.values()].filter(
        (message) => message.type === "stream" && message.stream_id === channel_id,
    );

    for (const message of channel_messages_waiting_for_ack) {
        assert(message.type === "stream");
        const topic = message.topic;
        const existing_id = max_message_id_by_topic.get(topic);

        // Here we're accessing message.id === float(message.local_id),
        // since these are all local message IDs.
        if (existing_id === undefined || message.id > existing_id) {
            max_message_id_by_topic.set(topic, message.id);
        }
    }
    return max_message_id_by_topic;
}
