import type * as z from "zod/mini";

import * as channel from "./channel.ts";
import type {StateData, muted_user_schema} from "./state_data.ts";
import * as timerender from "./timerender.ts";
import {get_time_from_date_muted} from "./util.ts";

export type RawMutedUser = z.infer<typeof muted_user_schema>;

type MutedUser = {
    id: number;
    date_muted: number;
    date_muted_str: string;
};

const muted_users = new Map<number, number>();

export function add_muted_user(user_id: number, date_muted?: number): void {
    const time = get_time_from_date_muted(date_muted);
    if (user_id) {
        muted_users.set(user_id, time);
    }
}

export function remove_muted_user(user_id: number): void {
    if (user_id) {
        muted_users.delete(user_id);
    }
}

export function is_user_muted(user_id: number): boolean {
    if (user_id === undefined) {
        return false;
    }

    return muted_users.has(user_id);
}

export function filter_muted_user_ids(user_ids: number[]): number[] {
    // Returns a copy of the user ID list, after removing muted user IDs.
    const base_user_ids = [...user_ids];
    return base_user_ids.filter((user_id) => !is_user_muted(user_id));
}

export function filter_muted_users<T extends {user_id: number}>(persons: T[]): T[] {
    // Returns a copy of the people list, after removing muted users.
    const base_users = [...persons];
    return base_users.filter((person) => !is_user_muted(person.user_id));
}

export function get_muted_users(): MutedUser[] {
    const users = [];
    for (const [id, date_muted] of muted_users) {
        const date_muted_str = timerender.render_now(new Date(date_muted)).time_str;
        users.push({
            id,
            date_muted,
            date_muted_str,
        });
    }
    return users;
}

export function set_muted_users(list: RawMutedUser[]): void {
    muted_users.clear();

    for (const user of list) {
        add_muted_user(user.id, user.timestamp);
    }
}

export function mute_user(user_id: number): void {
    void channel.post({
        url: "/json/users/me/muted_users/" + user_id,
    });
}

export function unmute_user(user_id: number): void {
    void channel.del({
        url: "/json/users/me/muted_users/" + user_id,
    });
}

export function initialize(params: StateData["muted_users"]): void {
    set_muted_users(params.muted_users);
}
