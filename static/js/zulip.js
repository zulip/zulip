// This file is being eliminated as part of the general purge of
// global variables from Zulip (everything is being moved into
// modules).  Please don't add things here.

var home_msg_list = new message_list.MessageList('zhome',
    new Filter([{operator: "in", operand: "home"}]), {muting_enabled: true}
);
var current_msg_list = home_msg_list;

// This is annoying to move to unread.js because the natural name
// would be unread.process_loaded_messages, which this calls
function process_loaded_for_unread(messages) {
    activity.process_loaded_messages(messages);
    activity.update_huddles();
    unread.process_loaded_messages(messages);
    unread.update_unread_counts();
    resize.resize_page_components();
}
