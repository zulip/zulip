var message_util = (function () {

var exports = {};

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

    var render_info = msg_list.add_messages(messages, opts);

    return render_info;
}

exports.add_old_messages = function (messages, msg_list) {
    return add_messages(messages, msg_list, {messages_are_new: false});
};
exports.add_new_messages = function (messages, msg_list) {
    return add_messages(messages, msg_list, {messages_are_new: true});
};


return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = message_util;
}
window.message_util = message_util;
