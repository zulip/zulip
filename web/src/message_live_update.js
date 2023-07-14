import * as message_lists from "./message_lists";
import * as message_store from "./message_store";
import * as people from "./people";

export function rerender_messages_view() {
    for (const list of message_lists.all_rendered_message_lists()) {
        list.rerender_view();
    }
}

export function rerender_messages_view_by_message_ids(message_ids) {
    const messages_to_render = [];
    for (const id of message_ids) {
        const message = message_store.get(id);
        if (message !== undefined) {
            messages_to_render.push(message);
        }
    }
    for (const list of message_lists.all_rendered_message_lists()) {
        list.view.rerender_messages(messages_to_render);
    }
}

function rerender_messages_view_for_user(user_id) {
    for (const list of message_lists.all_rendered_message_lists()) {
        const messages = list.data.get_messages_sent_by_user(user_id);
        if (messages.length === 0) {
            continue;
        }
        list.view.rerender_messages(messages);
    }
}

export function update_message_in_all_views(message_id, callback) {
    for (const msg_list of message_lists.all_rendered_message_lists()) {
        const $row = msg_list.get_row(message_id);
        if ($row === undefined) {
            // The row may not exist, e.g. if you do an action on a message in
            // a narrowed view
            continue;
        }
        callback($row);
    }
}

export function update_starred_view(message_id, new_value) {
    const starred = new_value;

    // Avoid a full re-render, but update the star in each message
    // table in which it is visible.
    update_message_in_all_views(message_id, ($row) => {
        const $elt = $row.find(".star");
        const $star_container = $row.find(".star_container");
        if (starred) {
            $elt.addClass("zulip-icon-star-filled").removeClass("zulip-icon-star");
            $star_container.removeClass("empty-star");
        } else {
            $elt.removeClass("zulip-icon-star-filled").addClass("zulip-icon-star");
            $star_container.addClass("empty-star");
        }
        const data_template_id = starred
            ? "unstar-message-tooltip-template"
            : "star-message-tooltip-template";
        $star_container.attr("data-tooltip-template-id", data_template_id);
    });
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
