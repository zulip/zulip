import * as loading from "./loading";
import * as message_store from "./message_store";
import * as resize from "./resize";
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

// We need to check if the message content contains the specified HTML
// elements.  We wrap the message.content in a <div>; this is
// important because $("Text <a>link</a>").find("a") returns nothing;
// one needs an outer element wrapping an object to use this
// construction.
function is_element_in_message_content(message, element_selector) {
    return $(`<div>${message.content}</div>`).find(`${element_selector}`).length > 0;
}

export function message_has_link(message) {
    return is_element_in_message_content(message, "a");
}

export function message_has_image(message) {
    return is_element_in_message_content(message, ".message_inline_image");
}

export function message_has_attachment(message) {
    return is_element_in_message_content(message, "a[href^='/user_uploads']");
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

export function get_messages_in_topic(stream_id, topic) {
    return message_list.all
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
    for (const msg of message_list.all.all_messages()) {
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
