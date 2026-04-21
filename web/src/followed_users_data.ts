/**
 * Client-side store for the set of user IDs that the current user follows.
 *
 * Initialized from state_data.followed_users on page load and kept in sync via
 * "followed_users" server events (emitted by do_follow_user / do_unfollow_user
 * on the backend).
 *
 * This module intentionally mirrors the structure of muted_users.ts so that
 * future maintainers can use it as a reference.
 */

import type {StateData} from "./state_data.ts";

// Map from followed user_id → unix timestamp of the follow action.
const followed_users = new Map<number, number>();

export function add_followed_user(user_id: number, timestamp?: number): void {
    if (user_id) {
        followed_users.set(user_id, timestamp ?? 0);
    }
}

export function remove_followed_user(user_id: number): void {
    if (user_id) {
        followed_users.delete(user_id);
    }
}

/** Returns true if the current user is following user_id. */
export function is_user_followed(user_id: number): boolean {
    if (user_id === undefined) {
        return false;
    }
    return followed_users.has(user_id);
}

export function set_followed_users(list: {id: number; timestamp: number}[]): void {
    followed_users.clear();
    for (const entry of list) {
        add_followed_user(entry.id, entry.timestamp);
    }
}

/** Called once during app startup with the initial state from the server. */
export function initialize(params: StateData["followed_users"]): void {
    set_followed_users(params.followed_users);
}
