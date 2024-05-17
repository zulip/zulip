import * as muted_users from "./muted_users";
import * as util from "./util";

// See docs/subsystems/typing-indicators.md for details on typing indicators.

const typists_dict = new Map<string, number[]>();
const inbound_timer_dict = new Map<string, ReturnType<typeof setInterval> | undefined>();

export function clear_for_testing(): void {
    typists_dict.clear();
    inbound_timer_dict.clear();
}

export function get_direct_message_conversation_key(group: number[]): string {
    const ids = util.sorted_ids(group);
    return "direct:" + ids.join(",");
}

export function get_topic_key(stream_id: number, topic: string): string {
    topic = topic.toLowerCase(); // Topics are case-insensitive
    return "topic:" + JSON.stringify({stream_id, topic});
}

export function add_typist(key: string, typist: number): void {
    const current = typists_dict.get(key) ?? [];
    if (!current.includes(typist)) {
        current.push(typist);
    }
    typists_dict.set(key, util.sorted_ids(current));
}

export function remove_typist(key: string, typist: number): boolean {
    let current = typists_dict.get(key) ?? [];

    if (!current.includes(typist)) {
        return false;
    }

    current = current.filter((user_id) => user_id !== typist);

    typists_dict.set(key, current);
    return true;
}

export function get_group_typists(group: number[]): number[] {
    const key = get_direct_message_conversation_key(group);
    const user_ids = typists_dict.get(key) ?? [];
    return muted_users.filter_muted_user_ids(user_ids);
}

export function get_all_direct_message_typists(): number[] {
    let typists: number[] = [];
    for (const [key, value] of typists_dict) {
        if (key.startsWith("direct:")) {
            typists.push(...value);
        }
    }
    typists = util.sorted_ids(typists);
    return muted_users.filter_muted_user_ids(typists);
}

export function get_topic_typists(stream_id: number, topic: string): number[] {
    const typists = typists_dict.get(get_topic_key(stream_id, topic)) ?? [];
    return muted_users.filter_muted_user_ids(typists);
}

export function clear_typing_data(): void {
    for (const [, timer] of inbound_timer_dict.entries()) {
        clearTimeout(timer);
    }
    inbound_timer_dict.clear();
    typists_dict.clear();
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
