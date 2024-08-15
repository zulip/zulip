import type {Message} from "./message_store";

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
