var scheduled_messages = (function () {

var exports = {};
var curr_scheduled_message_id;

var scheduled_message_model = (function () {
    var exports = {};

    // the key that the scheduled_messages are stored under.
    var KEY = "scheduled_messages";
    var ls = localstorage();
    ls.version = 1;

    function getTimestamp() {
        return new Date().getTime();
    }

    function get() {
        return ls.get(KEY) || {};
    }
    exports.get = get;

    exports.getScheduledMessage = function (id) {
        return get()[id] || false;
    };

    function save(scheduled_messages) {
        ls.set(KEY, scheduled_messages);
    }

    exports.addScheduledMessage = function (scheduled_message) {
        var scheduled_messages = get();

        // use the base16 of the current time + a random string to reduce
        // collisions to essentially zero.
        var id = getTimestamp().toString(16) + "-" + Math.random().toString(16).split(/\./).pop();

        scheduled_message.updatedAt = getTimestamp();
        scheduled_messages[id] = scheduled_message;
        save(scheduled_messages);

        return id;
    };

    exports.editScheduledMessage = function (id, scheduled_message) {
        var scheduled_messages = get();

        if (scheduled_messages[id]) {
            scheduled_message.updatedAt = getTimestamp();
            scheduled_messages[id] = scheduled_message;
            save(scheduled_messages);
        }
    };

    exports.deleteScheduledMessage = function (id) {
        var scheduled_messages = get();
        delete scheduled_messages[id];
        save(scheduled_messages);
        curr_scheduled_message_id = undefined;
    };

    return exports;
}());

exports.scheduled_message_model = scheduled_message_model;

exports.get_curr_scheduled_message_id = function () {
    return curr_scheduled_message_id;
};

exports.snapshot_message = function () {
    var message = {
        type: compose_state.get_message_type(),
        content: compose_state.message_content(),
    };
    if (message.type === "private") {
        var recipient = compose_state.recipient();
        message.reply_to = recipient;
        message.private_message_recipient = recipient;
    } else {
        message.stream = compose_state.stream_name();
        message.topic = compose_state.topic();
    }
    return message;
};

exports.restore_message = function (scheduled_message) {
    // This is kinda the inverse of snapshot_message, and
    // we are essentially making a deep copy of the scheduled_message,
    // being explicit about which fields we send to the compose
    // system.
    var compose_args;

    if (scheduled_message.type === "stream") {
        compose_args = {
            type: 'stream',
            stream: scheduled_message.stream,
            topic: util.get_scheduled_message_topic(scheduled_message),
            content: scheduled_message.content,
        };

    } else {
        compose_args = {
            type: scheduled_message.type,
            private_message_recipient: scheduled_message.private_message_recipient,
            content: scheduled_message.content,
        };
    }

    return compose_args;
};

function scheduled_message_notify() {
    $(".alert-scheduled-message").css("display", "inline-block");
    $(".alert-scheduled-message").delay(1000).fadeOut(300);
}

exports.update_scheduled_message = function () {
    var message = scheduled_messages.snapshot_message();
    if (curr_scheduled_message_id !== undefined) {
        if (message !== undefined) {
            scheduled_message_model.editScheduledMessage(curr_scheduled_message_id, message);
            scheduled_message_notify();
        } else {
            scheduled_message_model.deleteScheduledMessage(curr_scheduled_message_id);
        }
    } else {
        if (message !== undefined) {
            scheduled_message_model.addScheduledMessage(message);
            scheduled_message_notify();
        }
    }
    curr_scheduled_message_id = undefined;
};

exports.restore_scheduled_message = function (scheduled_message_id) {
    curr_scheduled_message_id = scheduled_message_id;
    var scheduled_message = scheduled_message_model.getScheduledMessage(scheduled_message_id);
    if (!scheduled_message) {
        return;
    }
    var compose_args = exports.restore_message(scheduled_message);

    if (compose_args.type === "stream") {
        if (scheduled_message.stream !== "") {
            narrow.activate(
                [
                    {operator: "stream", operand: compose_args.stream},
                    {operator: "topic", operand: compose_args.topic},
                ],
                {trigger: "restore scheduled_message"}
            );
        }
    } else {
        if (compose_args.private_message_recipient !== "") {
            narrow.activate(
                [
                    {operator: "pm-with", operand: compose_args.private_message_recipient},
                ],
                {trigger: "restore scheduled_message"}
            );
        }
    }
    overlays.close_overlay("scheduled_messages");
    compose_fade.clear_compose();
    compose.clear_preview_area();
    if (scheduled_message.type === "stream" && scheduled_message.stream === "") {
        compose_args.topic = "";
    }
    compose_actions.start(compose_args.type, compose_args);
    compose_ui.autosize_textarea();
};

exports.format_scheduled_message = function (scheduled_message) {
    var id = scheduled_message.id;
    var formatted;
    var time = new XDate(scheduled_message.updatedAt);
    var time_stamp = timerender.render_now(time).time_str;
    if (time_stamp === i18n.t("Today")) {
        time_stamp = timerender.stringify_time(time);
    }
    if (scheduled_message.type === "stream") {
        // In case there is no stream for the scheduled_message, we need a
        // single space char for proper rendering of the stream label
        var space_string = new Handlebars.SafeString("&nbsp;");
        var stream = scheduled_message.stream.length > 0 ? scheduled_message.stream : space_string;
        var scheduled_message_topic = util.get_scheduled_message_topic(scheduled_message);
        var scheduled_message_stream_color = stream_data.get_color(scheduled_message.stream);

        if (scheduled_message_topic === '') {
            scheduled_message_topic = compose.empty_topic_placeholder();
        }

        formatted = {
            scheduled_message_id: scheduled_message.id,
            is_stream: true,
            stream: stream,
            stream_color: scheduled_message_stream_color,
            dark_background: stream_color.get_color_class(scheduled_message_stream_color),
            topic: scheduled_message_topic,
            raw_content: scheduled_message.content,
            time_stamp: time_stamp,
        };
    } else {
        var emails = util.extract_pm_recipients(scheduled_message.private_message_recipient);
        var recipients = _.map(emails, function (email) {
            email = email.trim();
            var person = people.get_by_email(email);
            if (person !== undefined) {
                return person.full_name;
            }
            return email;
        }).join(', ');

        formatted = {
            scheduled_message_id: scheduled_message.id,
            is_stream: false,
            recipients: recipients,
            raw_content: scheduled_message.content,
            time_stamp: time_stamp,
        };
    }
    try {
        markdown.apply_markdown(formatted);
    } catch (error) {
        // In the unlikely event that there is syntax in the
        // scheduled_message content which our markdown processor is
        // unable to process, we delete the scheduled_message, so that the
        // scheduled_messages overlay can be opened without any errors.
        // We also report the exception to the server so that
        // the bug can be fixed.
        scheduled_message_model.deleteScheduledMessage(id);
        blueslip.error("Error in rendering scheduled_message.", {
            scheduled_message_content: scheduled_message.content,
        }, error.stack);
        return;
    }

    return formatted;
};

function row_with_focus() {
    var focused_scheduled_message = $(".scheduled-message-info-box:focus")[0];
    return $(focused_scheduled_message).parent(".scheduled-message-row");
}

function row_before_focus() {
    var focused_row = row_with_focus();
    return focused_row.prev(".scheduled-message-row:visible");
}

function row_after_focus() {
    var focused_row = row_with_focus();
    return focused_row.next(".scheduled-message-row:visible");
}

function remove_scheduled_message(scheduled_message_row) {
    // Deletes the scheduled_message and removes it from the list
    var scheduled_message_id = scheduled_message_row.data("scheduled-message-id");

    scheduled_messages.scheduled_message_model.deleteScheduledMessage(scheduled_message_id);

    scheduled_message_row.remove();

    if ($("#scheduled_messages_table .scheduled-message-row").length === 0) {
        $('#scheduled_messages_table .no-scheduled-messages').show();
    }
}

exports.format_scheduled_messages = function (data) {
    _.each(data, function (scheduled_message, id) {
        scheduled_message.id = id;
    });

    var unsorted_raw_messages = _.values(data);

    var sorted_raw_messages = unsorted_raw_messages.sort(function (message_a, message_b) {
        return message_b.updatedAt - message_a.updatedAt;
    });

    var sorted_formatted_messages = _.filter(
        _.map(sorted_raw_messages, exports.format_scheduled_message)
    );

    return sorted_formatted_messages;
};

exports.render_widgets = function (scheduled_messages) {
    $('#scheduled_messages_table').empty();
    var rendered = templates.render('scheduled_message_table_body', {
        scheduled_messages: scheduled_messages,
    });
    $('#scheduled_messages_table').append(rendered);
    if ($("#scheduled_messages_table .scheduled-message-row").length > 0) {
        $('#scheduled_messages_table .no-scheduled-messages').hide();
    }
};

exports.launch = function () {
    function setup_event_handlers() {
        $(".restore-scheduled-message").on("click", function (e) {
            e.stopPropagation();
            var scheduled_message_row = $(this).closest(".scheduled-message-row");
            var scheduled_message_id = scheduled_message_row.data("scheduled-message-id");
            exports.restore_scheduled_message(scheduled_message_id);
        });

        $(".scheduled_message_controls .delete-scheduled-message").on("click", function () {
            var scheduled_message_row = $(this).closest(".scheduled-message-row");

            remove_scheduled_message(scheduled_message_row);
        });
    }
    var scheduled_messages = exports.format_scheduled_messages(scheduled_message_model.get());
    exports.render_widgets(scheduled_messages);

    // We need to force a style calculation on the newly created
    // element in order for the CSS transition to take effect.
    $('#scheduled_message_overlay').css('opacity');

    exports.open_modal();
    exports.set_initial_element(scheduled_messages);
    setup_event_handlers();
};

function activate_element(elem) {
    $('.scheduled-message-info-box').removeClass('active');
    $(elem).expectOne().addClass('active');
    elem.focus();
}

function scheduled_messages_initialize_focus(event_name) {
    // If a scheduled_message is not focused in scheduled_message modal,
    // then focus the last scheduled_message
    // if up_arrow is clicked or the first scheduled_message if down_arrow is clicked.
    if (event_name !== "up_arrow" && event_name !== "down_arrow" || $(".scheduled-message-info-box:focus")[0]) {
        return;
    }

    var scheduled_message_arrow = scheduled_message_model.get();
    var scheduled_message_id_arrow = Object.getOwnPropertyNames(scheduled_message_arrow);
    if (scheduled_message_id_arrow.length === 0) { // empty scheduled_messages modal
        return;
    }

    var scheduled_message_element;
    if (event_name === "up_arrow") {
        scheduled_message_element = document.querySelectorAll('[data-scheduled-message-id="' + scheduled_message_id_arrow[scheduled_message_id_arrow.length - 1] + '"]');
    } else if (event_name === "down_arrow") {
        scheduled_message_element = document.querySelectorAll('[data-scheduled-message-id="' + scheduled_message_id_arrow[0] + '"]');
    }
    var focus_element = scheduled_message_element[0].children[0];

    activate_element(focus_element);
}

function scheduled_messages_scroll(next_focus_scheduled_message_row) {
    if (next_focus_scheduled_message_row[0] === undefined) {
        return;
    }
    if (next_focus_scheduled_message_row[0].children[0] === undefined) {
        return;
    }
    activate_element(next_focus_scheduled_message_row[0].children[0]);

    // If focused scheduled_message is first scheduled_message, scroll to the top.
    if ($(".scheduled-message-info-box:first")[0].parentElement === next_focus_scheduled_message_row[0]) {
        $(".scheduled-messages-list")[0].scrollTop = 0;
    }

    // If focused scheduled_message is the last scheduled_message, scroll to the bottom.
    if ($(".scheduled-message-info-box:last")[0].parentElement === next_focus_scheduled_message_row[0]) {
        $(".scheduled-messages-list")[0].scrollTop = $('.scheduled-messages-list')[0].scrollHeight - $('.scheduled-messages-list').height();
    }

    // If focused scheduled_message is cut off from the top, scroll up halfway
    // in scheduled_message modal.
    if (next_focus_scheduled_message_row.position().top < 55) {
        // 55 is the minimum distance from the top that will require extra scrolling.
        $(".scheduled-messages-list")[0].scrollTop -= $(".scheduled-messages-list")[0].clientHeight / 2;
    }

    // If focused scheduled_message is cut off from the bottom, scroll down halfway
    // in scheduled_message modal.
    var dist_from_top = next_focus_scheduled_message_row.position().top;
    var total_dist = dist_from_top + next_focus_scheduled_message_row[0].clientHeight;
    var dist_from_bottom = $(".scheduled-messages-container")[0].clientHeight - total_dist;
    if (dist_from_bottom < -4) {
        //-4 is the min dist from the bottom that will require extra scrolling.
        $(".scheduled-messages-list")[0].scrollTop += $(".scheduled-messages-list")[0].clientHeight / 2;
    }
}

exports.scheduled_messages_handle_events = function (e, event_key) {
    var message_arrow = scheduled_message_model.get();
    var message_id_arrow = Object.getOwnPropertyNames(message_arrow);
    scheduled_messages_initialize_focus(event_key);

    // This detects up arrow key presses when the scheduled_message overlay
    // is open and scrolls through the scheduled_messages.
    if (event_key === "up_arrow") {
        scheduled_messages_scroll(row_before_focus());
    }

    // This detects down arrow key presses when the scheduled_message overlay
    // is open and scrolls through the scheduled_messages.
    if (event_key === "down_arrow") {
        scheduled_messages_scroll(row_after_focus());
    }

    var focused_message_id = row_with_focus().data("scheduled-message-id");
    // Allows user to delete scheduled_messages with backspace
    if (event_key === "backspace" || event_key === "delete") {
        if (focused_message_id !== undefined) {
            var message_row = row_with_focus();
            var next_message_row = row_after_focus();
            var prev_message_row = row_before_focus();
            var message_to_be_focused_id;

            // Try to get the next scheduled_message in the list and 'focus' it
            // Use previous scheduled_message as a fallback
            if (next_message_row[0] !== undefined) {
                message_to_be_focused_id = next_message_row.data("scheduled-message-id");
            } else if (prev_message_row[0] !== undefined) {
                message_to_be_focused_id = prev_message_row.data("scheduled-message-id");
            }

            var new_focus_element = document.querySelectorAll('[data-scheduled-message-id="' + message_to_be_focused_id + '"]');
            if (new_focus_element[0] !== undefined) {
                activate_element(new_focus_element[0].children[0]);
            }

            remove_scheduled_message(message_row);
        }
    }

    // This handles when pressing enter while looking at scheduled_messages.
    // It restores scheduled_message that is focused.
    if (event_key === "enter") {
        if (document.activeElement.parentElement.hasAttribute("data-scheduled-message-id")) {
            exports.restore_scheduled_message(focused_message_id);
        } else {
            var first_message = message_id_arrow[message_id_arrow.length - 1];
            exports.restore_scheduled_message(first_message);
        }
    }
};

exports.open_modal = function () {
    overlays.open_overlay({
        name: 'scheduled_messages',
        overlay: $('#scheduled_message_overlay'),
        on_close: function () {
            hashchange.exit_overlay();
        },
    });
};

exports.set_initial_element = function (scheduled_messages) {
    if (scheduled_messages.length > 0) {
        var curr_scheduled_message_id = scheduled_messages[0].scheduled_message_id;
        var selector = '[data-scheduled-message-id="' + curr_scheduled_message_id + '"]';
        var curr_scheduled_message_element = document.querySelectorAll(selector);
        var focus_element = curr_scheduled_message_element[0].children[0];
        activate_element(focus_element);
        $(".scheduled-messages-list")[0].scrollTop = 0;
    }
};

exports.initialize = function () {
    $('body').on('focus', '.scheduled-message-info-box', function (e) {
        activate_element(e.target);
    });
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = scheduled_messages;
}
window.scheduled_messages = scheduled_messages;
