exports.do_unread_count_updates = function do_unread_count_updates(messages) {
    unread.process_loaded_messages(messages);
    unread_ui.update_unread_counts();
    resize.resize_page_components();
};

function add_messages(messages, msg_list, opts) {
    if (!messages) {
        return;
    }

    loading.destroy_indicator($('#page_loading_indicator'));
    $('#first_run_message').remove();

    const render_info = msg_list.add_messages(messages, opts);

    return render_info;
}

exports.add_old_messages = function (messages, msg_list) {
    return add_messages(messages, msg_list, {messages_are_new: false});
};
exports.add_new_messages = function (messages, msg_list) {
    return add_messages(messages, msg_list, {messages_are_new: true});
};

exports.get_messages_in_topic = function (stream_id, topic) {
    // This function is very expensive since it searches
    // all the messages. Please only use it in case of
    // very rare events like topic edits. Its primary
    // use case is the new experimental Recent Topics UI.
    return message_list.all.all_messages().filter(x => {
        return x.type === 'stream' &&
               x.stream_id === stream_id &&
               x.topic.toLowerCase() === topic.toLowerCase();
    });
};

exports.delete_message = function (msg_id) {
    const message = message_store.get(msg_id);
    if (message === undefined) {
        return;
    }

    // message is passed to unread.get_unread_messages,
    // which returns all the unread messages out of a given list.
    // So double marking something as read would not occur
    unread_ops.process_read_messages_event([msg_id]);
    if (message.type === 'stream') {
        stream_topic_history.remove_message({
            stream_id: message.stream_id,
            topic_name: message.topic,
        });
        stream_list.update_streams_sidebar();
    }
    ui.remove_message(msg_id);
};

window.message_util = exports;
