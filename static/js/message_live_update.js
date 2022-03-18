import * as message_list from "./message_list";
import * as message_lists from "./message_lists";
import * as message_store from "./message_store";
import * as people from "./people";

export function rerender_messages_view() {
    for (const list of [message_lists.home, message_list.narrowed]) {
        if (list === undefined) {
            continue;
        }
        if (list.table_name !== undefined) {
            list.rerender_view();
        }
    }
}

function rerender_messages_view_for_user(user_id) {
    for (const list of [message_lists.home, message_list.narrowed]) {
        if (list?.table_name === undefined) {
            continue;
        }
        const messages = list.data.get_messages_sent_by_user(user_id);
        if (messages.length === 0) {
            continue;
        }
        list.view.rerender_messages(messages);
    }
}

export function update_stream_name(stream_id, new_name) {
    message_store.update_property("stream_name", new_name, {stream_id});
    rerender_messages_view();
}

export function update_user_full_name(user_id, full_name) {
    message_store.update_property("sender_full_name", full_name, {user_id});
    rerender_messages_view_for_user(user_id);
}

export function update_avatar(user_id, avatar_url) {
    let url = avatar_url;
    url = people.format_small_avatar_url(url);
    message_store.update_property("small_avatar_url", url, {user_id});
    rerender_messages_view_for_user(user_id);
}

export function update_user_status_emoji(user_id, status_emoji_info) {
    message_store.update_property("status_emoji_info", status_emoji_info, {user_id});
    rerender_messages_view_for_user(user_id);
}
