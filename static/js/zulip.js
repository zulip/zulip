// This file is being eliminated as part of the general purge of
// global variables from Zulip (everything is being moved into
// modules).  Please don't add things here.

var home_msg_list = new message_list.MessageList('zhome',
    new Filter([{operator: "in", operand: "home"}]), {muting_enabled: true}
);
var current_msg_list = home_msg_list;

var queued_mark_as_read = [];
var queued_flag_timer;

function consider_bankruptcy() {
    // Until we've handled possibly declaring bankruptcy, don't show
    // unread counts since they only consider messages that are loaded
    // client side and may be different from the numbers reported by
    // the server.

    if (!page_params.furthest_read_time) {
        // We've never read a message.
        unread.enable();
        return;
    }

    var now = new XDate(true).getTime() / 1000;
    if ((page_params.unread_count > 500) &&
        (now - page_params.furthest_read_time > 60 * 60 * 24 * 2)) { // 2 days.
        var unread_info = templates.render('bankruptcy_modal',
                                           {"unread_count": page_params.unread_count});
        $('#bankruptcy-unread-count').html(unread_info);
        $('#bankruptcy').modal('show');
    } else {
        unread.enable();
    }
}

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

    // Before trying to load messages: is this user way behind?
    consider_bankruptcy();

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
