/*
    We keep a set of user_ids for all people
    who have sent stream messages or who have
    been on direct messages sent by the user.

    We will use this in search to prevent really
    large result sets for realms that have lots
    of users who haven't sent messages recently.

    We'll likely eventually want to replace this with
    accessing some combination of data from recent_senders
    and pm_conversations for better accuracy.
*/
const user_set = new Set<number>();

export const clear_for_testing = (): void => {
    user_set.clear();
};

export const user_ids = (): number[] => [...user_set];

export const add_user_id = (user_id: number): void => {
    user_set.add(user_id);
};
