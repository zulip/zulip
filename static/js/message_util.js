import $ from "jquery";

import {all_messages_data} from "./all_messages_data";
import * as loading from "./loading";
import * as message_store from "./message_store";
import * as unread from "./unread";
import * as unread_ui from "./unread_ui";

export function do_unread_count_updates(messages, expect_no_new_unreads = false) {
    const any_new_unreads = unread.process_loaded_messages(messages, expect_no_new_unreads);

    if (any_new_unreads) {
        // The following operations are expensive, and thus should
        // only happen if we found any unread messages justifying it.
        unread_ui.update_unread_counts();
    }
}

export function add_messages(messages, msg_list, opts) {
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

export function get_messages_in_topic(stream_id, topic) {
    return all_messages_data
        .all_messages()
        .filter(
            (x) =>
                x.type === "stream" &&
                x.stream_id === stream_id &&
                x.topic.toLowerCase() === topic.toLowerCase(),
        );
}

export function get_max_message_id_in_stream(stream_id) {
    let max_message_id = 0;
    for (const msg of all_messages_data.all_messages()) {
        if (msg.type === "stream" && msg.stream_id === stream_id && msg.id > max_message_id) {
            max_message_id = msg.id;
        }
    }
    return max_message_id;
}

export function get_topics_for_message_ids(message_ids) {
    const topics = new Map(); // key = stream_id:topic
    for (const msg_id of message_ids) {
        // message_store still has data on deleted messages when this runs.
        const message = message_store.get(msg_id);
        if (message === undefined) {
            // We may not have the deleted message cached locally in
            // message_store; if so, we can just skip processing it.
            continue;
        }
        if (message.type === "stream") {
            // Create unique keys for stream_id and topic.
            const topic_key = message.stream_id + ":" + message.topic;
            topics.set(topic_key, [message.stream_id, message.topic]);
        }
    }
    return topics;
}
