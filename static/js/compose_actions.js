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
        return 'new_message_content';
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
    $("#send-status").removeClass(status_classes).hide();
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
    compose.reset_user_acknowledged_all_everyone_flag();

    exports.clear_textarea();
    $("#new_message_content").removeData("draft-id");
    compose.autosize_textarea();
    $("#send-status").hide(0);
}

exports.autosize_message_content = function () {
    $("#new_message_content").autosize();
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
    narrow_state.set_compose_defaults(default_opts);
    opts = _.extend(default_opts, opts);
    return opts;
}

function same_recipient_as_before(msg_type, opts) {
    return (compose_state.composing() === msg_type) &&
            ((msg_type === "stream" &&
              opts.stream === compose.stream_name() &&
              opts.subject === compose.subject()) ||
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
    // If we are invoked by a compose hotkey (c or C), do not assume that we know
    // what the message's topic or PM recipient should be.
    if (opts.trigger === "compose_hotkey") {
        opts.subject = '';
        opts.private_message_recipient = '';
    }

    if (compose_state.composing() && !same_recipient_as_before(msg_type, opts)) {
        // Clear the compose box if the existing message is to a different recipient
        clear_box();
    }

    compose.stream_name(opts.stream);
    compose.subject(opts.subject);

    // Set the recipients with a space after each comma, so it looks nice.
    compose_state.recipient(opts.private_message_recipient.replace(/,\s*/g, ", "));

    // If the user opens the compose box, types some text, and then clicks on a
    // different stream/subject, we want to keep the text in the compose box
    if (opts.content !== undefined) {
        compose.message_content(opts.content);
    }

    compose.set_message_type(msg_type);

    // Show either stream/topic fields or "You and" field.
    show_box(msg_type, opts);

    exports.complete_starting_tasks(msg_type, opts);
};

exports.cancel = function () {
    $("#new_message_content").height(40 + "px");

    if (page_params.narrow !== undefined) {
        // Never close the compose box in narrow embedded windows, but
        // at least clear the subject and unfade.
        compose_fade.clear_compose();
        if (page_params.narrow_topic !== undefined) {
            compose.subject(page_params.narrow_topic);
        } else {
            compose.subject("");
        }
        return;
    }
    hide_box();
    $("#compose_close").hide();
    resize.resize_bottom_whitespace();
    clear_box();
    notifications.clear_compose_notifications();
    compose.abort_xhr();
    compose.set_message_type(false);
    $(document).trigger($.Event('compose_canceled.zulip'));
};


return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = compose_actions;
}
