import * as people from "./people";
import * as user_status from "./user_status";

export function get_recipients_with_status_emoji_info(user_ids_string) {
    const {user_ids, other_ids} = people._calc_user_and_other_ids(user_ids_string);

    if (other_ids.length === 0) {
        // private message with oneself
        const full_name = people.my_full_name();
        return [
            {
                full_name,
                status_emoji_info: user_status.get_status_emoji(user_ids[0]),
            },
        ];
    }

    const users = user_ids.map((user_id) => ({
        full_name: people.get_display_full_name(user_id),
        status_emoji_info: user_status.get_status_emoji(user_id),
    }));
    const sorted_users = users.sort((user1, user2) => user1 >= user2);
    return sorted_users;
}
