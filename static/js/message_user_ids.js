/*
    We keep a set of user_ids for all people
    who have sent stream messages or who have
    been on PMs sent by the user.

    We will use this in search to prevent really
    large result sets for realms that have lots
    of users who haven't sent messages recently.

    We'll likely eventually want to replace this with
    accessing some combination of data from recent_senders
    and pm_conversations for better accuracy.
*/
const user_set = new Set();

export function clear_for_testing() {
    user_set.clear();
}

export function user_ids() {
    return Array.from(user_set);
}

export function add_user_id(user_id) {
    user_set.add(user_id);
}
