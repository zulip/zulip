exports.do_unread_count_updates = function do_unread_count_updates(messages) {
    unread.process_loaded_messages(messages);
    unread_ui.update_unread_counts();
    resize.resize_page_components();
};

function add_messages(messages, msg_list, opts) {
    if (!messages) {
        return;
    }

    loading.destroy_indicator($("#page_loading_indicator"));

    const render_info = msg_list.add_messages(messages, opts);

    return render_info;
}

exports.message_has_link = function (message) {
    return $(message.content).find("a").length > 0;
};

exports.message_has_image = function (message) {
    return $(message.content).find(".message_inline_image").length > 0;
};

exports.message_has_attachment = function (message) {
    return $(message.content).find("a[href^='/user_uploads']").length > 0;
};

exports.add_old_messages = function (messages, msg_list) {
    return add_messages(messages, msg_list, {messages_are_new: false});
};

exports.add_new_messages = function (messages, msg_list) {
    if (!msg_list.data.fetch_status.has_found_newest()) {
        // We don't render newly received messages for the message list,
        // if we haven't found the latest messages to be displayed in the
        // narrow. Otherwise the new message would be rendered just after
        // the previously fetched messages when that's inaccurate.
        msg_list.data.fetch_status.update_expected_max_message_id(messages);
        return;
    }
    return add_messages(messages, msg_list, {messages_are_new: true});
};

exports.get_messages_in_topic = function (stream_id, topic) {
    // This function is very expensive since it searches
    // all the messages. Please only use it in case of
    // very rare events like topic edits. Its primary
    // use case is the new experimental Recent Topics UI.
    return message_list.all
        .all_messages()
        .filter(
            (x) =>
                x.type === "stream" &&
                x.stream_id === stream_id &&
                x.topic.toLowerCase() === topic.toLowerCase(),
        );
};

window.message_util = exports;
