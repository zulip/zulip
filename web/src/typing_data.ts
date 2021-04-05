import * as muted_users from "./muted_users";
import * as util from "./util";

// See docs/subsystems/typing-indicators.md for details on typing indicators.

const typist_dct = new Map<string, number[]>();
const inbound_timer_dict = new Map<string, ReturnType<typeof setInterval> | undefined>();

export function clear_for_testing(): void {
    typist_dct.clear();
    inbound_timer_dict.clear();
}

export function get_direct_message_conversation_key(group: number[]): string {
    const ids = util.sorted_ids(group);
    return ids.join(",");
}

export function add_typist(key: string, typist: number): void {
    const current = typist_dct.get(key) ?? [];
    if (!current.includes(typist)) {
        current.push(typist);
    }
    typist_dct.set(key, util.sorted_ids(current));
}

export function remove_typist(key: string, typist: number): boolean {
    let current = typist_dct.get(key) ?? [];

    if (!current.includes(typist)) {
        return false;
    }

    current = current.filter((user_id) => user_id !== typist);

    typist_dct.set(key, current);
    return true;
}

export function get_group_typists(group: number[]): number[] {
    const key = get_direct_message_conversation_key(group);
    const user_ids = typist_dct.get(key) ?? [];
    return muted_users.filter_muted_user_ids(user_ids);
}

export function get_all_direct_message_typists(): number[] {
    let typists = [...typist_dct.values()].flat();
    typists = util.sorted_ids(typists);
    return muted_users.filter_muted_user_ids(typists);
}

// The next functions aren't pure data, but it is easy
// enough to mock the setTimeout/clearTimeout functions.
export function clear_inbound_timer(key: string): void {
    const timer = inbound_timer_dict.get(key);
    if (timer) {
        clearTimeout(timer);
        inbound_timer_dict.set(key, undefined);
    }
}

export function kickstart_inbound_timer(key: string, delay: number, callback: () => void): void {
    clear_inbound_timer(key);
    const timer = setTimeout(callback, delay);
    inbound_timer_dict.set(key, timer);
}
