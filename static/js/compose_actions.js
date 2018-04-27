var compose_actions = (function () {

var exports = {};

function update_lock_icon_for_stream(stream_name) {
    var icon = $("#compose-lock-icon");
    var streamfield = $("#stream");
    if (stream_data.get_invite_only(stream_name)) {
        icon.show();
        streamfield.addClass("lock-padding");
    } else {
        icon.hide();
        streamfield.removeClass("lock-padding");
    }
}

exports.blur_textarea = function () {
    $('.message_comp').find('input, textarea, button').blur();
};

function hide_box() {
    exports.blur_textarea();
    $('#stream-message').hide();
    $('#private-message').hide();
    $(".new_message_textarea").css("min-height", "");
    compose_fade.clear_compose();
    $('.message_comp').hide();
    $("#compose_controls").show();
    compose.clear_preview_area();
}

function get_focus_area(msg_type, opts) {
    // Set focus to "Topic" when narrowed to a stream+topic and "New topic" button clicked.
    if (msg_type === 'stream' && opts.stream && ! opts.subject) {
        return 'subject';
    } else if ((msg_type === 'stream' && opts.stream)
               || (msg_type === 'private' && opts.private_message_recipient)) {
        if (opts.trigger === "new topic button") {
            return 'subject';
        }
        return 'compose-textarea';
    }

    if (msg_type === 'stream') {
        return 'stream';
    }
    return 'private_message_recipient';
}
// Export for testing
exports._get_focus_area = get_focus_area;

exports.set_focus = function (msg_type, opts) {
    var focus_area = get_focus_area(msg_type, opts);
    if (focus_area === undefined) {
        return;
    }

    if (window.getSelection().toString() === "" ||
         opts.trigger !== "message click") {
        var elt = $('#' + focus_area);
        elt.focus().select();
    }
};


// Show the compose box.
function show_box(msg_type, opts) {
    if (msg_type === "stream") {
        $('#private-message').hide();
        $('#stream-message').show();
        $("#stream_toggle").addClass("active");
        $("#private_message_toggle").removeClass("active");
    } else {
        $('#private-message').show();
        $('#stream-message').hide();
        $("#stream_toggle").removeClass("active");
        $("#private_message_toggle").addClass("active");
    }
    $("#compose-send-status").removeClass(common.status_classes).hide();
    $('#compose').css({visibility: "visible"});
    $(".new_message_textarea").css("min-height", "3em");

    exports.set_focus(msg_type, opts);
}

exports.clear_textarea = function () {
    $("#compose").find('input[type=text], textarea').val('');
};

function clear_box() {
    compose.clear_invites();

    // TODO: Better encapsulate at-mention warnings.
    compose.clear_all_everyone_warnings();
    compose.clear_announce_warnings();
    compose.clear_private_stream_alert();
    compose.reset_user_acknowledged_all_everyone_flag();
    compose.reset_user_acknowledged_announce_flag();

    exports.clear_textarea();
    $("#compose-textarea").removeData("draft-id");
    compose_ui.autosize_textarea();
    $("#compose-send-status").hide(0);
}

exports.autosize_message_content = function () {
    $("#compose-textarea").autosize();
};

exports.expand_compose_box = function () {
    $("#compose_close").show();
    $("#compose_controls").hide();
    $('.message_comp').show();
};

exports.complete_starting_tasks = function (msg_type, opts) {
    // This is sort of a kitchen sink function, and it's called only
    // by compose.start() for now.  Having this as a separate function
    // makes testing a bit easier.

    exports.maybe_scroll_up_selected_message();
    ui_util.change_tab_to("#home");
    compose_fade.start_compose(msg_type);
    exports.decorate_stream_bar(opts.stream);
    $(document).trigger($.Event('compose_started.zulip', opts));
    resize.resize_bottom_whitespace();
};

// In an attempt to decrease mixing, make the composebox's
// stream bar look like what you're replying to.
// (In particular, if there's a color associated with it,
//  have that color be reflected here too.)
exports.decorate_stream_bar = function (stream_name) {
    var color = stream_data.get_color(stream_name);
    update_lock_icon_for_stream(stream_name);
    $("#stream-message .message_header_stream")
        .css('background-color', color)
        .removeClass(stream_color.color_classes)
        .addClass(stream_color.get_color_class(color));
};

exports.maybe_scroll_up_selected_message = function () {
    // If the compose box is obscuring the currently selected message,
    // scroll up until the message is no longer occluded.
    if (current_msg_list.selected_id() === -1) {
        // If there's no selected message, there's no need to
        // scroll the compose box to avoid it.
        return;
    }
    var selected_row = current_msg_list.selected_row();

    if (selected_row.height() > message_viewport.height() - 100) {
        // For very tall messages whose height is close to the entire
        // height of the viewport, don't auto-scroll the viewport to
        // the end of the message (since that makes it feel annoying
        // to work with very tall messages).  See #8941 for details.
        return;
    }

    var cover = selected_row.offset().top + selected_row.height()
        - $("#compose").offset().top;
    if (cover > 0) {
        message_viewport.user_initiated_animate_scroll(cover+5);
    }
};

function fill_in_opts_from_current_narrowed_view(msg_type, opts) {
    var default_opts = {
        message_type:     msg_type,
        stream:           '',
        subject:          '',
        private_message_recipient: '',
        trigger:          'unknown',
    };

    // Set default parameters based on the current narrowed view.
    var compose_opts = narrow_state.set_compose_defaults();
    default_opts = _.extend(default_opts, compose_opts);
    opts = _.extend(default_opts, opts);
    return opts;
}

function same_recipient_as_before(msg_type, opts) {
    return (compose_state.get_message_type() === msg_type) &&
            ((msg_type === "stream" &&
              opts.stream === compose_state.stream_name() &&
              opts.subject === compose_state.subject()) ||
             (msg_type === "private" &&
              opts.private_message_recipient === compose_state.recipient()));
}

exports.start = function (msg_type, opts) {
    exports.autosize_message_content();

    if (reload.is_in_progress()) {
        return;
    }
    notifications.clear_compose_notifications();
    exports.expand_compose_box();

    opts = fill_in_opts_from_current_narrowed_view(msg_type, opts);
    // If we are invoked by a compose hotkey (c or x) or new topic button
    // or sidebar stream actions (in stream popover), do not assume that we know what
    // the message's topic or PM recipient should be.
    if ((opts.trigger === "compose_hotkey") ||
        (opts.trigger === "new topic button") ||
        (opts.trigger === "sidebar stream actions")) {
        opts.subject = '';
        opts.private_message_recipient = '';
    }

    if (compose_state.composing() && !same_recipient_as_before(msg_type, opts)) {
        // Clear the compose box if the existing message is to a different recipient
        clear_box();
    }

    compose_state.stream_name(opts.stream);
    compose_state.subject(opts.subject);

    // Set the recipients with a space after each comma, so it looks nice.
    compose_state.recipient(opts.private_message_recipient.replace(/,\s*/g, ", "));

    // If the user opens the compose box, types some text, and then clicks on a
    // different stream/subject, we want to keep the text in the compose box
    if (opts.content !== undefined) {
        compose_state.message_content(opts.content);
    }

    compose_state.set_message_type(msg_type);

    // Show either stream/topic fields or "You and" field.
    show_box(msg_type, opts);

    exports.complete_starting_tasks(msg_type, opts);
};

exports.cancel = function () {
    $("#compose-textarea").height(40 + "px");

    if (page_params.narrow !== undefined) {
        // Never close the compose box in narrow embedded windows, but
        // at least clear the subject and unfade.
        compose_fade.clear_compose();
        if (page_params.narrow_topic !== undefined) {
            compose_state.subject(page_params.narrow_topic);
        } else {
            compose_state.subject("");
        }
        return;
    }
    hide_box();
    $("#compose_close").hide();
    resize.resize_bottom_whitespace();
    clear_box();
    notifications.clear_compose_notifications();
    compose.abort_xhr();
    compose_state.set_message_type(false);
    compose_pm_pill.clear();
    $(document).trigger($.Event('compose_canceled.zulip'));
};

exports.respond_to_message = function (opts) {
    var message;
    var msg_type;
    // Before initiating a reply to a message, if there's an
    // in-progress composition, snapshot it.
    drafts.update_draft();

    message = current_msg_list.selected_message();

    if (message === undefined) { // empty narrow implementation
        if (!narrow_state.narrowed_by_pm_reply() &&
            !narrow_state.narrowed_by_stream_reply() &&
            !narrow_state.narrowed_by_topic_reply()) {
            compose.nonexistent_stream_reply_error();
            return;
        }
        var current_filter = narrow_state.get_current_filter();
        var first_term = current_filter.operators()[0];
        var first_operator = first_term.operator;
        var first_operand = first_term.operand;

        if ((first_operator === "stream") && !stream_data.is_subscribed(first_operand)) {
            compose.nonexistent_stream_reply_error();
            return;
        }

        msg_type = 'stream'; // Set msg_type to stream by default
                                 // in the case of an empty home view.
        if (narrow_state.narrowed_by_pm_reply()) {
            msg_type = 'private';
        }

        var new_opts = fill_in_opts_from_current_narrowed_view(msg_type, opts);
        exports.start(new_opts.message_type, new_opts);
        return;
    }

    unread_ops.notify_server_message_read(message);

    var stream = '';
    var subject = '';
    if (message.type === "stream") {
        stream = message.stream;
        subject = message.subject;
    }

    var pm_recipient = message.reply_to;
    if (message.type === "private") {
        if (opts.reply_type === "personal") {
            // reply_to for private messages is everyone involved, so for
            // personals replies we need to set the private message
            // recipient to just the sender
            pm_recipient = people.get_person_from_user_id(message.sender_id).email;
        } else {
            pm_recipient = people.pm_reply_to(message);
        }
    }
    if (opts.reply_type === 'personal' || message.type === 'private') {
        msg_type = 'private';
    } else {
        msg_type = message.type;
    }
    exports.start(msg_type, {stream: stream, subject: subject,
                             private_message_recipient: pm_recipient,
                             replying_to_message: message,
                             trigger: opts.trigger});

};

exports.reply_with_mention = function (opts) {
    exports.respond_to_message(opts);
    var message = current_msg_list.selected_message();
    var mention = '@**' + message.sender_full_name + '**';
    compose_ui.insert_syntax_and_focus(mention);
};

exports.on_topic_narrow = function () {
    if (!compose_state.composing()) {
        // If our compose box is closed, then just
        // leave it closed, assuming that the user is
        // catching up on their feed and not actively
        // composing.
        return;
    }

    if (compose_state.stream_name() !== narrow_state.stream()) {
        // If we changed streams, then we only leave the
        // compose box open if there is content.
        if (compose_state.has_message_content()) {
            compose_fade.update_message_list();
            return;
        }

        // Otherwise, avoid a mix.
        exports.cancel();
        return;
    }

    if (compose_state.subject() && compose_state.has_message_content()) {
        // If the user has written something to a different topic,
        // they probably want that content, so leave compose open.
        //
        // This effectively uses the heuristic of whether there is
        // content in compose to determine whether the user had firmly
        // decided to compose to the old topic or is just looking to
        // reply to what they see.
        compose_fade.update_message_list();
        return;
    }

    // If we got this far, then the compose box has the correct stream
    // filled in, and either compose is empty or no topic was set, so
    // we should update the compose topic to match the new narrow.
    // See #3300 for context--a couple users specifically asked for
    // this convenience.
    compose_state.subject(narrow_state.topic());
    compose_fade.set_focused_recipient("stream");
    compose_fade.update_message_list();
    $('#compose-textarea').focus().select();
};

exports.quote_and_reply = function (opts) {
    var textarea = $("#compose-textarea");
    var message_id = current_msg_list.selected_id();

    exports.respond_to_message(opts);
    channel.get({
        url: '/json/messages/' + message_id,
        idempotent: true,
        success: function (data) {
            if (textarea.val() === "") {
                textarea.val("```quote\n" + data.raw_content +"\n```\n");
            } else {
                textarea.val(textarea.val() + "\n```quote\n" + data.raw_content +"\n```\n");
            }
            $("#compose-textarea").trigger("autosize.resize");
        },
    });
};

exports.on_narrow = function (opts) {
    // We use force_close when jumping between PM narrows with the "p" key,
    // so that we don't have an open compose box that makes it difficult
    // to cycle quickly through unread messages.
    if (opts.force_close) {
        // This closes the compose box if it was already open, and it is
        // basically a noop otherwise.
        exports.cancel();
        return;
    }

    if (narrow_state.narrowed_by_topic_reply()) {
        exports.on_topic_narrow();
        return;
    }

    if (compose_state.has_message_content()) {
        compose_fade.update_message_list();
        return;
    }

    if (narrow_state.narrowed_by_pm_reply()) {
        exports.start('private');
        return;
    }

    // If we got this far, then we assume the user is now in "reading"
    // mode, so we close the compose box to make it easier to use navigation
    // hotkeys and to provide more screen real estate for messages.
    exports.cancel();
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = compose_actions;
}
