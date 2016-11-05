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

function main() {
    activity.set_user_statuses(page_params.initial_presences,
                               page_params.initial_servertime);

    pointer.server_furthest_read = page_params.initial_pointer;
    if (page_params.orig_initial_pointer !== undefined &&
        page_params.orig_initial_pointer > pointer.server_furthest_read) {
        pointer.server_furthest_read = page_params.orig_initial_pointer;
    }
    pointer.furthest_read = pointer.server_furthest_read;

    // We only send pointer updates when the user has been idle for a
    // short while to avoid hammering the server
    $(document).idle({idle: 1000,
                      onIdle: pointer.send_pointer_update,
                      keepTracking: true});

    $(document).on('message_selected.zulip', function (event) {
        // Only advance the pointer when not narrowed
        if (event.id === -1) {
            return;
        }
        // Additionally, don't advance the pointer server-side
        // if the selected message is local-only
        if (event.msg_list === home_msg_list && page_params.narrow_stream === undefined) {
            if (event.id > pointer.furthest_read &&
                home_msg_list.get(event.id).local_id === undefined) {
                pointer.furthest_read = event.id;
            }
        }

        if (event.mark_read && event.previously_selected !== -1) {
            // Mark messages between old pointer and new pointer as read
            var messages;
            if (event.id < event.previously_selected) {
                messages = event.msg_list.message_range(event.id, event.previously_selected);
            } else {
                messages = event.msg_list.message_range(event.previously_selected, event.id);
            }
            unread.mark_messages_as_read(messages, {from: 'pointer'});
        }
    });
}

$(function () {
    main();
});
