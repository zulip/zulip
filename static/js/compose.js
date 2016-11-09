var compose = (function () {

var exports = {};
var is_composing_message = false;

/* Track the state of the @all warning. The user must acknowledge that they are spamming the entire
   stream before the warning will go away. If they try to send before explicitly dismissing the
   warning, they will get an error message too.

   undefined: no @all/@everyone in message;
   false: user typed @all/@everyone;
   true: user clicked YES */

var user_acknowledged_all_everyone;

exports.all_everyone_warn_threshold = 15;

var uploads_domain = document.location.protocol + '//' + document.location.host;
var uploads_path = '/user_uploads';
var uploads_re = new RegExp("\\]\\(" + uploads_domain + "(" + uploads_path + "[^\\)]+)\\)", 'g');

function make_upload_absolute(uri) {
    if (uri.indexOf(uploads_path) === 0) {
        // Rewrite the URI to a usable link
        return uploads_domain + uri;
    }
    return uri;
}

function make_uploads_relative(content) {
    // Rewrite uploads in markdown links back to domain-relative form
    return content.replace(uploads_re, "]($1)");
}

// This function resets an input type="file".  Pass in the
// jquery object.
function clear_out_file_list(jq_file_list) {
    var clone_for_ie_sake = jq_file_list.clone(true);
    jq_file_list.replaceWith(clone_for_ie_sake);

    // Hack explanation:
    // IE won't let you do this (untested, but so says StackOverflow):
    //    $("#file_input").val("");
}

exports.autosize_textarea = function () {
    $("#new_message_content").trigger("autosize.resize");
};

// Show the compose box.
function show_box(tabname, focus_area, opts) {
    if (tabname === "stream") {
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

    if (focus_area !== undefined &&
        (window.getSelection().toString() === "" ||
         opts.trigger !== "message click")) {
        focus_area.focus().select();
    }

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

}

function show_all_everyone_warnings() {
    var current_stream = stream_data.get_sub(compose.stream_name());
    var stream_count = current_stream.subscribers.num_items();

    var all_everyone_template = templates.render("compose_all_everyone", {count: stream_count});
    var error_area_all_everyone = $("#compose-all-everyone");

    // only show one error for any number of @all or @everyone mentions
    if (!error_area_all_everyone.is(':visible')) {
        error_area_all_everyone.append(all_everyone_template);
    }

    error_area_all_everyone.show();
    user_acknowledged_all_everyone = false;
}

function clear_all_everyone_warnings() {
    $("#compose-all-everyone").hide();
    $("#compose-all-everyone").empty();
    $("#send-status").hide();
}

function clear_invites() {
    $("#compose_invite_users").hide();
    $("#compose_invite_users").empty();
}

function clear_box() {
    clear_invites();
    clear_all_everyone_warnings();
    user_acknowledged_all_everyone = undefined;
    $("#compose").find('input[type=text], textarea').val('');
    $("#new_message_content").removeData("draft-id");
    exports.autosize_textarea();
    $("#send-status").hide(0);
}

function clear_preview_area() {
    $("#new_message_content").show();
    $("#undo_markdown_preview").hide();
    $("#preview_message_area").hide();
    $("#preview_content").empty();
    $("#markdown_preview").show();
}

function hide_box() {
    $('.message_comp').find('input, textarea, button').blur();
    $('#stream-message').hide();
    $('#private-message').hide();
    $(".new_message_textarea").css("min-height", "");
    compose_fade.clear_compose();
    $('.message_comp').hide();
    $("#compose_controls").show();
    clear_preview_area();
}

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

function update_fade() {
    if (!is_composing_message) {
        return;
    }

    // Legacy strangeness: is_composing_message can be false, "stream", or "private"
    var msg_type = is_composing_message;
    compose_fade.set_focused_recipient(msg_type);
    compose_fade.update_faded_messages();
}

$(function () {
    $('#stream,#subject,#private_message_recipient').bind({
         keyup: update_fade,
         change: update_fade,
    });
});

function fill_in_opts_from_current_narrowed_view(msg_type, opts) {
    var default_opts = {
        message_type:     msg_type,
        stream:           '',
        subject:          '',
        private_message_recipient: '',
        trigger:          'unknown',
    };

    // Set default parameters based on the current narrowed view.
    narrow.set_compose_defaults(default_opts);
    opts = _.extend(default_opts, opts);
    return opts;
}

function same_recipient_as_before(msg_type, opts) {
    return (compose.composing() === msg_type) &&
            ((msg_type === "stream" &&
              opts.stream === compose.stream_name() &&
              opts.subject === compose.subject()) ||
             (msg_type === "private" &&
              opts.private_message_recipient === compose.recipient()));
}

function show_box_for_msg_type(msg_type, opts) {
    var focus_area;

    if (msg_type === 'stream' && opts.stream && ! opts.subject) {
        focus_area = 'subject';
    } else if ((msg_type === 'stream' && opts.stream)
               || (msg_type === 'private' && opts.private_message_recipient)) {
        focus_area = 'new_message_content';
    }

    if (msg_type === 'stream') {
        show_box('stream', $("#" + (focus_area || 'stream')), opts);
    } else {
        show_box('private', $("#" + (focus_area || 'private_message_recipient')), opts);
    }
}

exports.start = function (msg_type, opts) {
    $("#new_message_content").autosize();

    if (reload.is_in_progress()) {
        return;
    }
    notifications.clear_compose_notifications();
    $("#compose_close").show();
    $("#compose_controls").hide();
    $('.message_comp').show();

    opts = fill_in_opts_from_current_narrowed_view(msg_type, opts);
    // If we are invoked by a compose hotkey (c or C), do not assume that we know
    // what the message's topic or PM recipient should be.
    if (opts.trigger === "compose_hotkey") {
        opts.subject = '';
        opts.private_message_recipient = '';
    }

    if (compose.composing() && !same_recipient_as_before(msg_type, opts)) {
        // Clear the compose box if the existing message is to a different recipient
        clear_box();
    }

    compose.stream_name(opts.stream);
    compose.subject(opts.subject);

    // Set the recipients with a space after each comma, so it looks nice.
    compose.recipient(opts.private_message_recipient.replace(/,\s*/g, ", "));

    // If the user opens the compose box, types some text, and then clicks on a
    // different stream/subject, we want to keep the text in the compose box
    if (opts.content !== undefined) {
        compose.message_content(opts.content);
    }

    ui.change_tab_to("#home");

    is_composing_message = msg_type;

    // Set focus to "Topic" when narrowed to a stream+topic and "New topic" button clicked.
    if (opts.trigger === "new topic button") {
        show_box('stream', $("#subject"), opts);
    } else {
        // Show either stream/topic fields or "You and" field.
        show_box_for_msg_type(msg_type, opts);
    }

    compose_fade.start_compose(msg_type);

    exports.decorate_stream_bar(opts.stream);
    $(document).trigger($.Event('compose_started.zulip', opts));
    resize.resize_bottom_whitespace();
};

function abort_xhr() {
    $("#compose-send-button").removeAttr("disabled");
    var xhr = $("#compose").data("filedrop_xhr");
    if (xhr !== undefined) {
        xhr.abort();
        $("#compose").removeData("filedrop_xhr");
    }
}

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
    abort_xhr();
    is_composing_message = false;
    $(document).trigger($.Event('compose_canceled.zulip'));
};

exports.empty_topic_placeholder = function () {
    return i18n.t("(no topic)");
};

function create_message_object() {
    // Subjects are optional, and we provide a placeholder if one isn't given.
    var subject = compose.subject();
    if (subject === "") {
        subject = compose.empty_topic_placeholder();
    }

    var content = make_uploads_relative(compose.message_content());

    // Changes here must also be kept in sync with echo.try_deliver_locally
    var message = {
        type: compose.composing(),
        content: content,
        sender_id: page_params.user_id,
        queue_id: page_params.event_queue_id,
        stream: '',
        subject: '',
    };

    if (message.type === "private") {
        // TODO: this should be collapsed with the code in composebox_typeahead.js
        var recipient = compose.recipient();
        var emails = util.extract_pm_recipients(recipient);
        message.to = emails;
        message.reply_to = recipient;
        message.private_message_recipient = recipient;
        message.to_user_ids = people.email_list_to_user_ids_string(emails);
    } else {
        var stream_name = compose.stream_name();
        message.to = stream_name;
        message.stream = stream_name;
        var sub = stream_data.get_sub(stream_name);
        if (sub) {
            message.stream_id = sub.stream_id;
        }
        message.subject = subject;
    }
    return message;
}

exports.snapshot_message = function () {
    if (!exports.composing() || (exports.message_content() === "")) {
        // If you aren't in the middle of composing the body of a
        // message, don't try to snapshot.
        return;
    }

    // Save what we can.
    return create_message_object();
};

function compose_error(error_text, bad_input) {
    $('#send-status').removeClass(status_classes)
               .addClass('alert-error')
               .stop(true).fadeTo(0, 1);
    $('#error-msg').html(error_text);
    $("#compose-send-button").removeAttr('disabled');
    $("#sending-indicator").hide();
    if (bad_input !== undefined) {
        bad_input.focus().select();
    }
}

function send_message_ajax(request, success, error) {
    channel.post({
        url: '/json/messages',
        data: request,
        success: success,
        error: function (xhr, error_type) {
            if (error_type !== 'timeout' && reload.is_pending()) {
                // The error might be due to the server changing
                reload.initiate({immediate: true,
                                 save_pointer: true,
                                 save_narrow: true,
                                 save_compose: true,
                                 send_after_reload: true});
                return;
            }

            var response = channel.xhr_error_message("Error sending message", xhr);
            error(response);
        },
    });
}

function report_send_time(send_time, receive_time, display_time, locally_echoed, rendered_changed) {
    var data = {time: send_time.toString(),
                received: receive_time.toString(),
                displayed: display_time.toString(),
                locally_echoed: locally_echoed};
    if (locally_echoed) {
        data.rendered_content_disparity = rendered_changed;
    }
    channel.post({
        url: '/json/report_send_time',
        data: data,
    });
}

var socket;
if (page_params.use_websockets) {
    socket = new Socket("/sockjs");
}
// For debugging.  The socket will eventually move out of this file anyway.
exports._socket = socket;

function send_message_socket(request, success, error) {
    request.socket_user_agent = navigator.userAgent;
    socket.send(request, success, function (type, resp) {
        var err_msg = "Error sending message";
        if (type === 'response') {
            err_msg += ": " + resp.msg;
        }
        error(err_msg);
    });
}

exports.send_times_log = [];
exports.send_times_data = {};
function maybe_report_send_times(message_id) {
    var data = exports.send_times_data[message_id];
    if (data.send_finished === undefined || data.received === undefined ||
        data.displayed === undefined) {
        // We report the data once we have both the send and receive times
        return;
    }
    report_send_time(data.send_finished - data.start,
                     data.received - data.start,
                     data.displayed - data.start,
                     data.locally_echoed,
                     data.rendered_content_disparity || false);
}

function mark_end_to_end_receive_time(message_id) {
    if (exports.send_times_data[message_id] === undefined) {
        exports.send_times_data[message_id] = {};
    }
    exports.send_times_data[message_id].received = new Date();
    maybe_report_send_times(message_id);
}

function mark_end_to_end_display_time(message_id) {
    if (exports.send_times_data[message_id] === undefined) {
        exports.send_times_data[message_id] = {};
    }
    exports.send_times_data[message_id].displayed = new Date();
    maybe_report_send_times(message_id);
}

exports.mark_rendered_content_disparity = function (message_id, changed) {
    if (exports.send_times_data[message_id] === undefined) {
        exports.send_times_data[message_id] = {};
    }
    exports.send_times_data[message_id].rendered_content_disparity = changed;
};

exports.report_as_received = function report_as_received(message) {
    if (message.sent_by_me) {
        mark_end_to_end_receive_time(message.id);
        setTimeout(function () {
            mark_end_to_end_display_time(message.id);
        }, 0);
    }
};

function process_send_time(message_id, start_time, locally_echoed) {
    var send_finished = new Date();
    var send_time = (send_finished - start_time);
    if (feature_flags.log_send_times) {
        blueslip.log("send time: " + send_time);
    }
    if (feature_flags.collect_send_times) {
        exports.send_times_log.push(send_time);
    }
    if (exports.send_times_data[message_id] === undefined) {
        exports.send_times_data[message_id] = {};
    }
    exports.send_times_data[message_id].start = start_time;
    exports.send_times_data[message_id].send_finished = send_finished;
    exports.send_times_data[message_id].locally_echoed  = locally_echoed;
    maybe_report_send_times(message_id);
}

function clear_compose_box() {
    $("#new_message_content").val('').focus();
    drafts.delete_draft_after_send();
    exports.autosize_textarea();
    $("#send-status").hide(0);
    $("#compose-send-button").removeAttr('disabled');
    $("#sending-indicator").hide();
    resize.resize_bottom_whitespace();
}

exports.send_message_success = function (local_id, message_id, start_time, locally_echoed) {
    if (! feature_flags.local_echo || !locally_echoed) {
        clear_compose_box();
    }

    process_send_time(message_id, start_time, locally_echoed);

    if (feature_flags.local_echo) {
        echo.reify_message_id(local_id, message_id);
    }

    setTimeout(function () {
        if (exports.send_times_data[message_id].received === undefined) {
            blueslip.log("Restarting get_events due to delayed receipt of sent message " + message_id);
            server_events.restart_get_events();
        }
    }, 5000);
};

exports.transmit_message = function (request, success, error) {
    delete exports.send_times_data[request.id];
    if (page_params.use_websockets) {
        send_message_socket(request, success, error);
    } else {
        send_message_ajax(request, success, error);
    }
};

function send_message(request) {
    if (request === undefined) {
        request = create_message_object();
    }

    if (request.type === "private") {
        request.to = JSON.stringify(request.to);
    } else {
        request.to = JSON.stringify([request.to]);
    }

    var start_time = new Date();
    var local_id;
    if (feature_flags.local_echo) {
        local_id = echo.try_deliver_locally(request);
        if (local_id !== undefined) {
            // We delivered this message locally
            request.local_id = local_id;
        }
    }
    var locally_echoed = local_id !== undefined;

    function success(data) {
        exports.send_message_success(local_id, data.id, start_time, locally_echoed);
    }

    function error(response) {
        // If we're not local echo'ing messages, or if this message was not
        // locally echoed, show error in compose box
        if (!feature_flags.local_echo || request.local_id === undefined) {
            compose_error(response, $('#new_message_content'));
            return;
        }

        echo.message_send_error(local_id, response);
    }

    exports.transmit_message(request, success, error);
    server_events.assert_get_events_running("Restarting get_events because it was not running during send");

    if (feature_flags.local_echo && locally_echoed) {
        clear_compose_box();
    }
}

exports.enter_with_preview_open = function () {
    clear_preview_area();
    if (page_params.enter_sends) {
        // If enter_sends is enabled, we just send the message
        send_message();
    } else {
        // Otherwise, we return to the compose box and focus it
        $("#new_message_content").focus();
    }
};

exports.respond_to_message = function (opts) {
    var message;
    var msg_type;
    // Before initiating a reply to a message, if there's an
    // in-progress composition, snapshot it.
    drafts.update_draft();

    message = current_msg_list.selected_message();

    if (message === undefined) {
        return;
    }

    unread_ui.mark_message_as_read(message);

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
    compose.start(msg_type, {stream: stream, subject: subject,
                             private_message_recipient: pm_recipient,
                             replying_to_message: message,
                             trigger: opts.trigger});

};

exports.reply_with_mention = function (opts) {
    exports.respond_to_message(opts);
    var message = current_msg_list.selected_message();
    var mention = '@**' + message.sender_full_name + '**';
    $('#new_message_content').val(mention + ' ');
};

// This function is for debugging / data collection only.  Arguably it
// should live in debug.js, but then it wouldn't be able to call
// send_message() directly below.
exports.test_send_many_messages = function (stream, subject, count) {
    var num_sent = 0;

    function do_send_one() {
        var message = {};
        num_sent += 1;

        message.type = "stream";
        message.to = stream;
        message.subject = subject;
        message.content = num_sent.toString();

        send_message(message);

        if (num_sent === count) {
            return;
        }

        setTimeout(do_send_one, 1000);
    }

    do_send_one();
};

exports.finish = function () {
    clear_invites();

    if (! compose.validate()) {
        return false;
    }
    send_message();
    clear_preview_area();
    // TODO: Do we want to fire the event even if the send failed due
    // to a server-side error?
    $(document).trigger($.Event('compose_finished.zulip'));
    return true;
};

$(function () {
    $("#compose form").on("submit", function (e) {
       e.preventDefault();
       compose.finish();
    });
});

exports.composing = function () {
    return is_composing_message;
};

function get_or_set(fieldname, keep_leading_whitespace) {
    // We can't hoist the assignment of 'elem' out of this lambda,
    // because the DOM element might not exist yet when get_or_set
    // is called.
    return function (newval) {
        var elem = $('#'+fieldname);
        var oldval = elem.val();
        if (newval !== undefined) {
            elem.val(newval);
        }
        return keep_leading_whitespace ? util.rtrim(oldval) : $.trim(oldval);
    };
}

exports.stream_name     = get_or_set('stream');
exports.subject         = get_or_set('subject');
// We can't trim leading whitespace in `new_message_content` because
// of the indented syntax for multi-line code blocks.
exports.message_content = get_or_set('new_message_content', true);
exports.recipient       = get_or_set('private_message_recipient');

exports.has_message_content = function () {
    return exports.message_content() !== "";
};

exports.update_email = function (user_id, new_email) {
    var reply_to = exports.recipient();

    if (!reply_to) {
        return;
    }

    reply_to = people.update_email_in_reply_to(reply_to, user_id, new_email);

    exports.recipient(reply_to);
};

// *Synchronously* check if a stream exists.
exports.check_stream_existence = function (stream_name, autosubscribe) {
    var result = "error";
    var request = {stream: stream_name};
    if (autosubscribe) {
        request.autosubscribe = true;
    }
    channel.post({
        url: "/json/subscriptions/exists",
        data: request,
        async: false,
        success: function (data) {
            if (data.subscribed) {
                result = "subscribed";
            } else {
                result = "not-subscribed";
            }
        },
        error: function (xhr) {
            if (xhr.status === 404) {
                result = "does-not-exist";
            } else {
                result = "error";
            }
        },
    });
    return result;
};


// Checks if a stream exists. If not, displays an error and returns
// false.
function check_stream_for_send(stream_name, autosubscribe) {
    var result = exports.check_stream_existence(stream_name, autosubscribe);

    if (result === "error") {
        compose_error(i18n.t("Error checking subscription"), $("#stream"));
        $("#compose-send-button").removeAttr('disabled');
        $("#sending-indicator").hide();
    }

    return result;
}

function validate_stream_message_mentions(stream_name) {
    var current_stream = stream_data.get_sub(stream_name);
    var stream_count = current_stream.subscribers.num_items();

    // check if @all or @everyone is in the message
    if (util.is_all_or_everyone_mentioned(exports.message_content()) &&
        stream_count > compose.all_everyone_warn_threshold) {
        if (user_acknowledged_all_everyone === undefined ||
            user_acknowledged_all_everyone === false) {
            // user has not seen a warning message yet if undefined
            show_all_everyone_warnings();

            $("#compose-send-button").removeAttr('disabled');
            $("#sending-indicator").hide();
            return false;
        }
    } else {
        // the message no longer contains @all or @everyone
        clear_all_everyone_warnings();
    }
    // at this point, the user has either acknowledged the warning or removed @all / @everyone
    user_acknowledged_all_everyone = undefined;

    return true;
}

function validate_stream_message_address_info(stream_name) {
    var response;

    if (!stream_data.is_subscribed(stream_name)) {
        switch (check_stream_for_send(stream_name, page_params.narrow_stream !== undefined)) {
        case "does-not-exist":
            response = "<p>The stream <b>" +
                Handlebars.Utils.escapeExpression(stream_name) + "</b> does not exist.</p>" +
                "<p>Manage your subscriptions <a href='#streams/all'>on your Streams page</a>.</p>";
            compose_error(response, $('#stream'));
            return false;
        case "error":
            return false;
        case "not-subscribed":
            response = "<p>You're not subscribed to the stream <b>" +
                Handlebars.Utils.escapeExpression(stream_name) + "</b>.</p>" +
                "<p>Manage your subscriptions <a href='#streams/all'>on your Streams page</a>.</p>";
            compose_error(response, $('#stream'));
            return false;
        }
    }

    return true;
}

function validate_stream_message() {
    var stream_name = exports.stream_name();
    if (stream_name === "") {
        compose_error(i18n.t("Please specify a stream"), $("#stream"));
        return false;
    }

    if (page_params.mandatory_topics) {
        var topic = exports.subject();
        if (topic === "") {
            compose_error(i18n.t("Please specify a topic"), $("#subject"));
            return false;
        }
    }

    if (!validate_stream_message_address_info(stream_name) ||
        !validate_stream_message_mentions(stream_name)) {
        return false;
    }

    return true;
}
// The function checks whether the recipients are users of the realm or cross realm users (bots
// for now)
function validate_private_message() {
    if (exports.recipient() === "") {
        compose_error(i18n.t("Please specify at least one recipient"), $("#private_message_recipient"));
        return false;
    } else if (page_params.is_zephyr_mirror_realm) {
        // For Zephyr mirroring realms, the frontend doesn't know which users exist
        return true;
    }
    var private_recipients = util.extract_pm_recipients(compose.recipient());
    var invalid_recipients = [];
    var context = {};
    _.each(private_recipients, function (email) {
        // This case occurs when exports.recipient() ends with ','
        if (email === "") {
            return;
        }
        if (people.realm_get(email) !== undefined) {
            return;
        }
        if (people.is_cross_realm_email(email)) {
            return;
        }
        invalid_recipients.push(email);
    });
    if (invalid_recipients.length === 1) {
        context = {recipient: invalid_recipients.join()};
        compose_error(i18n.t("The recipient __recipient__ is not valid ", context), $("#private_message_recipient"));
        return false;
    } else if (invalid_recipients.length > 1) {
        context = {recipients: invalid_recipients.join()};
        compose_error(i18n.t("The recipients __recipients__ are not valid ", context), $("#private_message_recipient"));
        return false;
    }
    return true;
}

exports.validate = function () {
    $("#compose-send-button").attr('disabled', 'disabled').blur();
    $("#sending-indicator").show();

    if (/^\s*$/.test(exports.message_content())) {
        compose_error(i18n.t("You have nothing to send!"), $("#new_message_content"));
        return false;
    }

    if ($("#zephyr-mirror-error").is(":visible")) {
        compose_error(i18n.t("You need to be running Zephyr mirroring in order to send messages!"));
        return false;
    }

    if (exports.composing() === 'private') {
        return validate_private_message();
    }
    return validate_stream_message();
};

$(function () {
    (function on_compose_resize(cb) {
        var meta = {
            compose_box: document.querySelector("#new_message_content"),
            height: null,
            mousedown: false,
        };

        meta.compose_box.addEventListener("mousedown", function () {
            meta.mousedown = true;
            meta.height = meta.compose_box.clientHeight;
        });

        // If the user resizes the compose box manually, we use the
        // callback to stop autosize from adjusting the compose box height.
        document.body.addEventListener("mouseup", function () {
            if (meta.mousedown === true) {
                meta.mousedown = false;
                if (meta.height !== meta.compose_box.clientHeight) {
                    meta.height = meta.compose_box.clientHeight;
                    cb.call(meta.compose_box, meta.height);
                }
            }
        });
    }(function (height) {
        // This callback disables autosize on the compose box.  It
        // will be re-enabled when the compose box is next opened.
        $("#new_message_content").trigger("autosize.destroy")
            .height(height + "px");
    }));

    // Run a feature test and decide whether to display
    // the "Attach files" button
    if (window.XMLHttpRequest && (new XMLHttpRequest()).upload) {
        $("#compose #attach_files").removeClass("notdisplayed");
    }

    // Lazy load the Dropbox script, since it can slow our page load
    // otherwise, and isn't enabled for all users. Also, this Dropbox
    // script isn't under an open source license, so we can't (for legal
    // reasons) minify it with our own code.
    if (feature_flags.dropbox_integration) {
        LazyLoad.js('https://www.dropbox.com/static/api/1/dropins.js', function () {
            // Successful load. We should now have window.Dropbox.
            if (! _.has(window, 'Dropbox')) {
                blueslip.error('Dropbox script reports loading but window.Dropbox undefined');
            } else if (Dropbox.isBrowserSupported()) {
                Dropbox.init({appKey: window.dropboxAppKey});
                $("#compose #attach_dropbox_files").removeClass("notdisplayed");
            }
        });
    }

    // Show a warning if a user @-mentions someone who will not receive this message
    $(document).on('usermention_completed.zulip', function (event, data) {
        // Legacy strangeness: is_composing_message can be false, "stream", or "private"
        // Disable for Zephyr mirroring realms, since we never have subscriber lists there
        if (is_composing_message !== "stream" || page_params.is_zephyr_mirror_realm) {
            return;
        }

        if (data !== undefined && data.mentioned !== undefined) {
            var email = data.mentioned.email;

            // warn if @all or @everyone is mentioned
            if (data.mentioned.full_name  === 'all' || data.mentioned.full_name === 'everyone') {
                return; // don't check if @all or @everyone is subscribed to a stream
            }

            if (compose_fade.would_receive_message(email) === false) {
                var new_row = templates.render("compose-invite-users",
                                               {email: email, name: data.mentioned.full_name});
                var error_area = $("#compose_invite_users");

                var existing_invites = _.map($(".compose_invite_user", error_area), function (user_row) {
                    return $(user_row).data('useremail');
                });

                if (existing_invites.indexOf(email) === -1) {
                    error_area.append(new_row);
                }

                error_area.show();
            }
        }

    });

    $("#compose-all-everyone").on('click', '.compose-all-everyone-confirm', function (event) {
        event.preventDefault();

        $(event.target).parents('.compose-all-everyone').remove();
        user_acknowledged_all_everyone = true;
        clear_all_everyone_warnings();
        compose.finish();
    });

    $("#compose_invite_users").on('click', '.compose_invite_link', function (event) {
        event.preventDefault();

        var invite_row = $(event.target).parents('.compose_invite_user');

        var email = $(invite_row).data('useremail');
        if (email === undefined) {
            return;
        }

        function success() {
            var all_invites = $("#compose_invite_users");
            invite_row.remove();

            if (all_invites.children().length === 0) {
                all_invites.hide();
            }
        }

        function failure() {
            var error_msg = invite_row.find('.compose_invite_user_error');
            error_msg.show();

            $(event.target).attr('disabled', true);
        }

        var stream_name = compose.stream_name();
        var sub = stream_data.get_sub(stream_name);
        if (!sub) {
            // This should only happen if a stream rename occurs
            // before the user clicks.  We could prevent this by
            // putting a stream id in the link.
            blueslip.warn('Stream no longer exists: ' + stream_name);
            failure();
            return;
        }

        subs.invite_user_to_stream(email, sub, success, failure);
    });

    $("#compose_invite_users").on('click', '.compose_invite_close', function (event) {
        var invite_row = $(event.target).parents('.compose_invite_user');
        var all_invites = $("#compose_invite_users");

        invite_row.remove();

        if (all_invites.children().length === 0) {
            all_invites.hide();
        }
    });

    // Click event binding for "Attach files" button
    // Triggers a click on a hidden file input field

    $("#compose").on("click", "#attach_files", function (e) {
        e.preventDefault();
        $("#compose #file_input").trigger("click");
    } );


    $("#compose").on("click", "#markdown_preview", function (e) {
        e.preventDefault();
        var message = $("#new_message_content").val();
        $("#new_message_content").hide();
        $("#markdown_preview").hide();
        $("#undo_markdown_preview").show();
        $("#preview_message_area").show();

        if (message.length === 0) {
            $("#preview_content").html(i18n.t("Nothing to preview"));
        } else {
            if (echo.contains_bugdown(message))  {
                var spinner = $("#markdown_preview_spinner").expectOne();
                loading.make_indicator(spinner);
            } else {
                // For messages that don't appear to contain
                // bugdown-specific syntax not present in our
                // marked.js frontend processor, we render using the
                // frontend markdown processor message (but still
                // render server-side to ensure the preview is
                // accurate; if the `echo.contains_bugdown` logic is
                // incorrect wrong, users will see a brief flicker).
                $("#preview_content").html(echo.apply_markdown(message));
            }
            channel.post({
                url: '/json/messages/render',
                idempotent: true,
                data: {content: message},
                success: function (response_data) {
                    if (echo.contains_bugdown(message)) {
                        loading.destroy_indicator($("#markdown_preview_spinner"));
                    }
                    $("#preview_content").html(response_data.rendered);
                },
                error: function () {
                    if (echo.contains_bugdown(message)) {
                        loading.destroy_indicator($("#markdown_preview_spinner"));
                    }
                    $("#preview_content").html(i18n.t("Failed to generate preview"));
                },
            });
        }
    });

    $("#compose").on("click", "#undo_markdown_preview", function (e) {
        e.preventDefault();
        clear_preview_area();
    });

    $("#compose").on("click", "#attach_dropbox_files", function (e) {
        e.preventDefault();
        var options = {
            // Required. Called when a user selects an item in the Chooser.
            success: function (files) {
                var textbox = $("#new_message_content");
                var links = _.map(files, function (file) { return '[' + file.name + '](' + file.link +')'; })
                             .join(' ') + ' ';
                textbox.val(textbox.val() + links);
            },
            // Optional. A value of false (default) limits selection to a single file, while
            // true enables multiple file selection.
            multiselect: true,
            iframe: true,
        };
        Dropbox.choose(options);
    });

    function uploadStarted() {
        $("#compose-send-button").attr("disabled", "");
        $("#send-status").addClass("alert-info")
                         .show();
        $(".send-status-close").one('click', abort_xhr);
        $("#error-msg").html(
            $("<p>").text(i18n.t("Uploading…"))
                    .after('<div class="progress progress-striped active">' +
                           '<div class="bar" id="upload-bar" style="width: 00%;"></div>' +
                           '</div>'));
    }

    function progressUpdated(i, file, progress) {
        $("#upload-bar").width(progress + "%");
    }

    function uploadError(err, file) {
        var msg;
        $("#send-status").addClass("alert-error")
                        .removeClass("alert-info");
        $("#compose-send-button").removeAttr("disabled");
        switch (err) {
        case 'BrowserNotSupported':
            msg = i18n.t("File upload is not yet available for your browser.");
            break;
        case 'TooManyFiles':
            msg = i18n.t("Unable to upload that many files at once.");
            break;
        case 'FileTooLarge':
            // sanitization not needed as the file name is not potentially parsed as HTML, etc.
            msg = "\"" + file.name + "\"" + i18n.t(" was too large; the maximum file size is 25MiB.");
            break;
        case 'REQUEST ENTITY TOO LARGE':
            msg = i18n.t("Sorry, the file was too large.");
            break;
        case 'QuotaExceeded':
            msg = i18n.t("Upload would exceed your maximum quota."
                      + " Consider deleting some previously uploaded files.");
            break;
        default:
            msg = i18n.t("An unknown error occured.");
            break;
        }
        $("#error-msg").text(msg);
    }

    function uploadFinished(i, file, response) {
        if (response.uri === undefined) {
            return;
        }
        var textbox = $("#new_message_content");
        var split_uri = response.uri.split("/");
        var filename = split_uri[split_uri.length - 1];
        // Urgh, yet another hack to make sure we're "composing"
        // when text gets added into the composebox.
        if (!compose.composing()) {
            compose.start('stream');
        }

        var uri = make_upload_absolute(response.uri);

        if (i === -1) {
            // This is a paste, so there's no filename. Show the image directly
            textbox.val(textbox.val() + "[pasted image](" + uri + ") ");
        } else {
            // This is a dropped file, so make the filename a link to the image
            textbox.val(textbox.val() + "[" + filename + "](" + uri + ")" + " ");
        }
        exports.autosize_textarea();
        $("#compose-send-button").removeAttr("disabled");
        $("#send-status").removeClass("alert-info")
                         .hide();

        // In order to upload the same file twice in a row, we need to clear out
        // the #file_input element, so that the next time we use the file dialog,
        // an actual change event is fired.  This is extracted to a function
        // to abstract away some IE hacks.
        clear_out_file_list($("#file_input"));
    }

    // Expose the internal file upload functions to the desktop app,
    // since the linux/windows QtWebkit based apps upload images
    // directly to the server
    if (window.bridge) {
        exports.uploadStarted = uploadStarted;
        exports.progressUpdated = progressUpdated;
        exports.uploadError = uploadError;
        exports.uploadFinished = uploadFinished;
    }

    $("#compose").filedrop({
        url: "/json/upload_file",
        fallback_id: "file_input",
        paramname: "file",
        maxfilesize: page_params.maxfilesize,
        data: {
            // the token isn't automatically included in filedrop's post
            csrfmiddlewaretoken: csrf_token,
        },
        raw_droppable: ['text/uri-list', 'text/plain'],
        drop: uploadStarted,
        progressUpdated: progressUpdated,
        error: uploadError,
        uploadFinished: uploadFinished,
        rawDrop: function (contents) {
            var textbox = $("#new_message_content");
            if (!compose.composing()) {
                compose.start('stream');
            }
            textbox.val(textbox.val() + contents);
            exports.autosize_textarea();
        },
    });

    if (page_params.narrow !== undefined) {
        if (page_params.narrow_topic !== undefined) {
            compose.start("stream", {subject: page_params.narrow_topic});
        } else {
            compose.start("stream", {});
        }
    }

    $(document).on('message_id_changed', function (event) {
        if (exports.send_times_data[event.old_id] !== undefined) {
            var value = exports.send_times_data[event.old_id];
            delete exports.send_times_data[event.old_id];
            exports.send_times_data[event.new_id] =
                _.extend({}, exports.send_times_data[event.old_id], value);
        }
    });
});

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = compose;
}
