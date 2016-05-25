var home_msg_list = new message_list.MessageList('zhome',
    new Filter([{operator: "in", operand: "home"}]), {muting_enabled: true}
);
var current_msg_list = home_msg_list;

var recent_subjects = new Dict({fold_case: true});

var queued_mark_as_read = [];
var queued_flag_timer;


function recenter_view(message, opts) {
    opts = opts || {};

    // Barnowl-style recentering: if the pointer is too high, move it to
    // the 1/2 marks. If the pointer is too low, move it to the 1/7 mark.
    // See keep_pointer_in_view() in pointer.js for related logic to keep the pointer onscreen.

    var viewport_info = viewport.message_viewport_info();
    var top_threshold = viewport_info.visible_top;

    var bottom_threshold = viewport_info.visible_top + viewport_info.visible_height;

    var message_top = message.offset().top;
    var message_height = message.outerHeight(true);
    var message_bottom = message_top + message_height;

    var is_above = message_top < top_threshold;
    var is_below = message_bottom > bottom_threshold;

    if (opts.from_scroll) {
        // If the message you're trying to center on is already in view AND
        // you're already trying to move in the direction of that message,
        // don't try to recenter. This avoids disorienting jumps when the
        // pointer has gotten itself outside the threshold (e.g. by
        // autoscrolling).
        if (is_above && viewport.last_movement_direction >= 0) {
            return;
        }
        if (is_below && viewport.last_movement_direction <= 0) {
            return;
        }
    }

    if (is_above || opts.force_center) {
        viewport.set_message_position(message_top, message_height, viewport_info, 1/2);
    } else if (is_below) {
        viewport.set_message_position(message_top, message_height, viewport_info, 1/7);
    }
}

function scroll_to_selected() {
    var selected_row = current_msg_list.selected_row();
    if (selected_row && (selected_row.length !== 0)) {
        recenter_view(selected_row);
    }
}

function maybe_scroll_to_selected() {
    // If we have been previously instructed to re-center to the
    // selected message, then do so
    if (pointer.recenter_pointer_on_display) {
        scroll_to_selected();
        pointer.recenter_pointer_on_display = false;
    }
}

function get_private_message_recipient(message, attr, fallback_attr) {
    var recipient, i;
    var other_recipients = _.filter(message.display_recipient,
                                  function (element) {
                                      return element.email !== page_params.email;
                                  });
    if (other_recipients.length === 0) {
        // private message with oneself
        return message.display_recipient[0][attr];
    }

    recipient = other_recipients[0][attr];
    if (recipient === undefined && fallback_attr !== undefined) {
        recipient = other_recipients[0][fallback_attr];
    }
    for (i = 1; i < other_recipients.length; i++) {
        var attr_value = other_recipients[i][attr];
        if (attr_value === undefined && fallback_attr !== undefined) {
            attr_value = other_recipients[i][fallback_attr];
        }
        recipient += ', ' + attr_value;
    }
    return recipient;
}

function respond_to_message(opts) {
    var message, msg_type;
    // Before initiating a reply to a message, if there's an
    // in-progress composition, snapshot it.
    compose.snapshot_message();

    message = current_msg_list.selected_message();

    if (message === undefined) {
        return;
    }

    unread.mark_message_as_read(message);

    var stream = '';
    var subject = '';
    if (message.type === "stream") {
        stream = message.stream;
        subject = message.subject;
    }

    var pm_recipient = message.reply_to;
    if (opts.reply_type === "personal" && message.type === "private") {
        // reply_to for private messages is everyone involved, so for
        // personals replies we need to set the the private message
        // recipient to just the sender
        pm_recipient = message.sender_email;
    }
    if (opts.reply_type === 'personal' || message.type === 'private') {
        msg_type = 'private';
    } else {
        msg_type = message.type;
    }
    compose.start(msg_type, {'stream': stream, 'subject': subject,
                             'private_message_recipient': pm_recipient,
                             'replying_to_message': message,
                             'trigger': opts.trigger});

}





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
