import * as buddy_data from "./buddy_data";
import * as hash_util from "./hash_util";
import * as narrow_state from "./narrow_state";
import * as people from "./people";
import * as pm_conversations from "./pm_conversations";
import * as unread from "./unread";
import * as user_status from "./user_status";

export function get_active_user_ids_string() {
    const filter = narrow_state.filter();

    if (!filter) {
        return undefined;
    }

    const emails = filter.operands("pm-with")[0];

    if (!emails) {
        return undefined;
    }

    return people.emails_strings_to_user_ids_string(emails);
}

export function get_convos() {
    const private_messages = pm_conversations.recent.get();
    const display_messages = [];
    const active_user_ids_string = get_active_user_ids_string();

    for (const private_message_obj of private_messages) {
        const user_ids_string = private_message_obj.user_ids_string;
        const reply_to = people.user_ids_string_to_emails_string(user_ids_string);
        const recipients_string = people.get_recipients(user_ids_string);

        const num_unread = unread.num_unread_for_person(user_ids_string);

        const is_group = user_ids_string.includes(",");

        const is_active = user_ids_string === active_user_ids_string;

        let user_circle_class;
        let status_emoji_info;

        if (!is_group) {
            const user_id = Number.parseInt(user_ids_string, 10);
            user_circle_class = buddy_data.get_user_circle_class(user_id);
            const recipient_user_obj = people.get_by_user_id(user_id);

            if (recipient_user_obj.is_bot) {
                user_circle_class = "user_circle_green";
                // bots do not have status emoji
            } else {
                status_emoji_info = user_status.get_status_emoji(user_id);
            }
        }

        const display_message = {
            recipients: recipients_string,
            user_ids_string,
            unread: num_unread,
            is_zero: num_unread === 0,
            is_active,
            url: hash_util.pm_with_url(reply_to),
            status_emoji_info,
            user_circle_class,
            is_group,
        };
        display_messages.push(display_message);
    }

    return display_messages;
}

export function is_all_privates() {
    const filter = narrow_state.filter();

    if (!filter) {
        return false;
    }

    return filter.operands("is").includes("private");
}
