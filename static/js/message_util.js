import $ from "jquery";

import * as loading from "./loading";
import * as resize from "./resize";
import * as unread from "./unread";
import * as unread_ui from "./unread_ui";

export function do_unread_count_updates(messages) {
    unread.process_loaded_messages(messages);
    unread_ui.update_unread_counts();
    resize.resize_page_components();
}

function add_messages(messages, msg_list, opts) {
    if (!messages) {
        return undefined;
    }

    loading.destroy_indicator($("#page_loading_indicator"));

    const render_info = msg_list.add_messages(messages, opts);

    return render_info;
}

export function add_old_messages(messages, msg_list) {
    return add_messages(messages, msg_list, {messages_are_new: false});
}

export function add_new_messages(messages, msg_list) {
    if (!msg_list.data.fetch_status.has_found_newest()) {
        // We don't render newly received messages for the message list,
        // if we haven't found the latest messages to be displayed in the
        // narrow. Otherwise the new message would be rendered just after
        // the previously fetched messages when that's inaccurate.
        msg_list.data.fetch_status.update_expected_max_message_id(messages);
        return undefined;
    }
    return add_messages(messages, msg_list, {messages_are_new: true});
}

export function add_new_messages_data(messages, msg_list_data) {
    if (!msg_list_data.fetch_status.has_found_newest()) {
        // The reasoning in add_new_messages applies here as well;
        // we're trying to maintain a data structure that's a
        // contiguous range of message history, so we can't append a
        // new message that might not be adjacent to that range.
        msg_list_data.fetch_status.update_expected_max_message_id(messages);
        return undefined;
    }
    return msg_list_data.add_messages(messages);
}
