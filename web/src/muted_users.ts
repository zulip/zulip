import * as channel from "./channel";
import * as timerender from "./timerender";
import {get_time_from_date_muted} from "./util";

export type RawMutedUser = {
    id: number;
    timestamp: number;
};

type MutedUser = {
    id: number;
    date_muted: number;
    date_muted_str: string;
};

const muted_users = new Map<number, number>();

export const add_muted_user = (user_id: number, date_muted?: number): void => {
    const time = get_time_from_date_muted(date_muted);
    if (user_id) {
        muted_users.set(user_id, time);
    }
};

export const remove_muted_user = (user_id: number): void => {
    if (user_id) {
        muted_users.delete(user_id);
    }
};

export const is_user_muted = (user_id: number): boolean => {
    if (user_id === undefined) {
        return false;
    }

    return muted_users.has(user_id);
};

export const filter_muted_user_ids = (user_ids: number[]): number[] => {
    // Returns a copy of the user ID list, after removing muted user IDs.
    const base_user_ids = [...user_ids];
    return base_user_ids.filter((user_id) => !is_user_muted(user_id));
};

export const filter_muted_users = <T extends {user_id: number}>(persons: T[]): T[] => {
    // Returns a copy of the people list, after removing muted users.
    const base_users = [...persons];
    return base_users.filter((person) => !is_user_muted(person.user_id));
};

export const get_muted_users = (): MutedUser[] => {
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
};

export const set_muted_users = (list: RawMutedUser[]): void => {
    muted_users.clear();

    for (const user of list) {
        add_muted_user(user.id, user.timestamp);
    }
};

export const mute_user = (user_id: number): void => {
    void channel.post({
        url: "/json/users/me/muted_users/" + user_id,
    });
};

export const unmute_user = (user_id: number): void => {
    void channel.del({
        url: "/json/users/me/muted_users/" + user_id,
    });
};

export const initialize = (params: {muted_users: RawMutedUser[]}): void => {
    set_muted_users(params.muted_users);
};
