"use strict";

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

// For the three message_has_* functions below message.content is html which is
// wrapped inside a <div> and passed to jquery so that jquery can parse html
// and create jQuery object which can be used to find certain html elements using
// built-in .find() which finds the descendants which match the selector passed to
// it.
//
// The reason for extra <div> wrapping is to make sure all the elements of
// message.content are descendants of the extra div and we can find any element in html
// without issue.
// Eg. message.content can be:
// <p>Some message</p><div class='message_inline_image'></div><p>some more</p>
// In above case without wrapper <div> around message.content won't find the
// .message_inline_image. Wrapping the above eg. html in <div> will make the
// .message_inline_image a descendant hence will be esaily found using find().
exports.message_has_link = function (message) {
    return $(`<div>${message.content}</div>`).find("a").length > 0;
};

exports.message_has_image = function (message) {
    return $(`<div>${message.content}</div>`).find(".message_inline_image").length > 0;
};

exports.message_has_attachment = function (message) {
    return $(`<div>${message.content}</div>`).find("a[href^='/user_uploads']").length > 0;
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
    return message_list.all
        .all_messages()
        .filter(
            (x) =>
                x.type === "stream" &&
                x.stream_id === stream_id &&
                x.topic.toLowerCase() === topic.toLowerCase(),
        );
};

exports.get_max_message_id_in_stream = function (stream_id) {
    let max_message_id = 0;
    for (const msg of message_list.all.all_messages()) {
        if (msg.type === "stream" && msg.stream_id === stream_id) {
            if (msg.id > max_message_id) {
                max_message_id = msg.id;
            }
        }
    }
    return max_message_id;
};

window.message_util = exports;
