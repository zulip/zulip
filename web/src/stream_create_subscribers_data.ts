import * as people from "./people";
import type {User} from "./people";
import {current_user} from "./state_data";

let user_id_set: Set<number>;

export const initialize_with_current_user = (): void => {
    user_id_set = new Set([current_user.user_id]);
};

export const sorted_user_ids = (): number[] => {
    const users = people.get_users_from_ids([...user_id_set]);
    people.sort_but_pin_current_user_on_top(users);
    return users.map((user) => user.user_id);
};

export const get_all_user_ids = (): number[] => {
    const potential_subscribers = people.get_realm_users();
    const user_ids = potential_subscribers.map((user) => user.user_id);
    // sort for determinism
    user_ids.sort((a, b) => a - b);
    return user_ids;
};

export const get_principals = (): number[] => [...user_id_set];

export const get_potential_subscribers = (): User[] => {
    const potential_subscribers = people.get_realm_users();
    return potential_subscribers.filter((user) => !user_id_set.has(user.user_id));
};

export const must_be_subscribed = (user_id: number): boolean =>
    !current_user.is_admin && user_id === current_user.user_id;

export const add_user_ids = (user_ids: number[]): void => {
    for (const user_id of user_ids) {
        if (!user_id_set.has(user_id)) {
            const user = people.maybe_get_user_by_id(user_id);
            if (user) {
                user_id_set.add(user_id);
            }
        }
    }
};

export const remove_user_ids = (user_ids: number[]): void => {
    for (const user_id of user_ids) {
        user_id_set.delete(user_id);
    }
};
