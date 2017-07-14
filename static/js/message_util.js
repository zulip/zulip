var message_util = (function () {

var exports = {};

exports.do_unread_count_updates = function do_unread_count_updates(messages) {
    unread.process_loaded_messages(messages);
    unread_ui.update_unread_counts();
    resize.resize_page_components();
};

exports.add_messages = function add_messages(messages, msg_list, opts) {
    if (!messages) {
        return;
    }

    opts = _.extend({messages_are_new: false, delay_render: false}, opts);

    loading.destroy_indicator($('#page_loading_indicator'));
    $('#first_run_message').remove();

    msg_list.add_messages(messages, opts);

    if (msg_list === home_msg_list && opts.messages_are_new) {
        _.each(messages, function (message) {
            if (message.local_id === undefined) {
                compose.report_as_received(message);
            }
        });
    }
};


return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = message_util;
}
