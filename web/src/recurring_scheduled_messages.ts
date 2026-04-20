import * as blueslip from "./blueslip.ts";
import type {StateData, recurring_scheduled_message_schema} from "./state_data.ts";
import type * as z from "zod/mini";

export type RecurringScheduledMessage = z.infer<typeof recurring_scheduled_message_schema>;

let recurring_scheduled_messages_by_id = new Map<number, RecurringScheduledMessage>();

export function get_all(): RecurringScheduledMessage[] {
    return [...recurring_scheduled_messages_by_id.values()].sort(
        (a, b) => a.next_delivery - b.next_delivery,
    );
}

export function get_by_id(id: number): RecurringScheduledMessage | undefined {
    const rsm = recurring_scheduled_messages_by_id.get(id);
    if (rsm === undefined) {
        blueslip.error("Could not find recurring scheduled message", {id});
        return undefined;
    }
    return rsm;
}

export function add(rsm: RecurringScheduledMessage): void {
    recurring_scheduled_messages_by_id.set(rsm.id, rsm);
}

export function update(rsm: RecurringScheduledMessage): void {
    recurring_scheduled_messages_by_id.set(rsm.id, rsm);
}

export function remove(id: number): void {
    recurring_scheduled_messages_by_id.delete(id);
}

export function count(): number {
    return recurring_scheduled_messages_by_id.size;
}

export const initialize = (params: StateData["recurring_scheduled_messages"]): void => {
    recurring_scheduled_messages_by_id = new Map<number, RecurringScheduledMessage>(
        params.recurring_scheduled_messages.map((rsm) => [rsm.id, rsm]),
    );
};
