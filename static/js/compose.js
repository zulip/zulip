var compose = (function () {

var exports = {};

/* Track the state of the @all warning. The user must acknowledge that they are spamming the entire
   stream before the warning will go away. If they try to send before explicitly dismissing the
   warning, they will get an error message too.

   undefined: no @all/@everyone in message;
   false: user typed @all/@everyone;
   true: user clicked YES */

var user_acknowledged_all_everyone;
var user_acknowledged_announce;

exports.all_everyone_warn_threshold = 15;
exports.announce_warn_threshold = 60;

exports.uploads_domain = document.location.protocol + '//' + document.location.host;
exports.uploads_path = '/user_uploads';
exports.uploads_re = new RegExp("\\]\\(" + exports.uploads_domain + "(" + exports.uploads_path + "[^\\)]+)\\)", 'g');

function make_uploads_relative(content) {
    // Rewrite uploads in markdown links back to domain-relative form
    return content.replace(exports.uploads_re, "]($1)");
}

function show_all_everyone_warnings() {
    var stream_count = stream_data.get_subscriber_count(compose_state.stream_name()) || 0;

    var all_everyone_template = templates.render("compose_all_everyone", {count: stream_count});
    var error_area_all_everyone = $("#compose-all-everyone");

    // only show one error for any number of @all or @everyone mentions
    if (!error_area_all_everyone.is(':visible')) {
        error_area_all_everyone.append(all_everyone_template);
    }

    error_area_all_everyone.show();
    user_acknowledged_all_everyone = false;
}

exports.clear_all_everyone_warnings = function () {
    $("#compose-all-everyone").hide();
    $("#compose-all-everyone").empty();
    $("#compose-send-status").hide();
};

function show_sending_indicator(whats_happening) {
    if (whats_happening === undefined) {
        whats_happening = 'Sending...';
    }
    $("#sending-indicator").html(i18n.t(whats_happening));
    $("#sending-indicator").show();
}

function show_announce_warnings() {
    var stream_count = stream_data.get_subscriber_count(compose_state.stream_name()) || 0;

    var announce_template = templates.render("compose_announce", {count: stream_count});
    var error_area_announce = $("#compose-announce");

    if (!error_area_announce.is(':visible')) {
        error_area_announce.append(announce_template);
    }

    error_area_announce.show();
    user_acknowledged_announce = false;
}

exports.clear_announce_warnings = function () {
    $("#compose-announce").hide();
    $("#compose-announce").empty();
    $("#compose-send-status").hide();
};

exports.clear_invites = function () {
    $("#compose_invite_users").hide();
    $("#compose_invite_users").empty();
};

exports.clear_private_stream_alert = function () {
    $("#compose_private_stream_alert").hide();
    $("#compose_private_stream_alert").empty();
};

exports.reset_user_acknowledged_all_everyone_flag = function () {
    user_acknowledged_all_everyone = undefined;
};

exports.reset_user_acknowledged_announce_flag = function () {
    user_acknowledged_announce = undefined;
};

exports.clear_preview_area = function () {
    $("#compose-textarea").show();
    $("#undo_markdown_preview").hide();
    $("#preview_message_area").hide();
    $("#preview_content").empty();
    $("#markdown_preview").show();
};

function update_fade() {
    if (!compose_state.composing()) {
        return;
    }

    var msg_type = compose_state.get_message_type();
    compose_fade.set_focused_recipient(msg_type);
    compose_fade.update_faded_messages();
}

exports.abort_xhr = function () {
    $("#compose-send-button").prop("disabled", false);
    var xhr = $("#compose").data("filedrop_xhr");
    if (xhr !== undefined) {
        xhr.abort();
        $("#compose").removeData("filedrop_xhr");
    }
};

exports.empty_topic_placeholder = function () {
    return i18n.t("(no topic)");
};

function create_message_object() {
    // Subjects are optional, and we provide a placeholder if one isn't given.
    var subject = compose_state.subject();
    if (subject === "") {
        subject = compose.empty_topic_placeholder();
    }

    var content = make_uploads_relative(compose_state.message_content());

    // Changes here must also be kept in sync with echo.try_deliver_locally
    var message = {
        type: compose_state.get_message_type(),
        content: content,
        sender_id: page_params.user_id,
        queue_id: page_params.queue_id,
        stream: '',
        subject: '',
    };

    if (message.type === "private") {
        // TODO: this should be collapsed with the code in composebox_typeahead.js
        var recipient = compose_state.recipient();
        var emails = util.extract_pm_recipients(recipient);
        message.to = emails;
        message.reply_to = recipient;
        message.private_message_recipient = recipient;
        message.to_user_ids = people.email_list_to_user_ids_string(emails);
    } else {
        var stream_name = compose_state.stream_name();
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
// Export for testing
exports.create_message_object = create_message_object;

function compose_error(error_text, bad_input) {
    $('#compose-send-status').removeClass(common.status_classes)
               .addClass('alert-error')
               .stop(true).fadeTo(0, 1);
    $('#compose-error-msg').html(error_text);
    $("#compose-send-button").prop('disabled', false);
    $("#sending-indicator").hide();
    if (bad_input !== undefined) {
        bad_input.focus().select();
    }
}

function nonexistent_stream_reply_error() {
    $("#nonexistent_stream_reply_error").show();
    $("#compose-reply-error-msg").html("There are no messages to reply to yet.");
    setTimeout(function () {
        $("#nonexistent_stream_reply_error").hide();
    }, 5000);
}

function compose_not_subscribed_error(error_text, bad_input) {
    $('#compose-send-status').removeClass(common.status_classes)
               .addClass('home-error-bar')
               .stop(true).fadeTo(0, 1);
    $('#compose-error-msg').html(error_text);
    $("#compose-send-button").prop('disabled', false);
    $("#sending-indicator").hide();
    $(".compose-send-status-close").hide();
    if (bad_input !== undefined) {
        bad_input.focus().select();
    }
}

exports.nonexistent_stream_reply_error = nonexistent_stream_reply_error;

function clear_compose_box() {
    $("#compose-textarea").val('').focus();
    drafts.delete_draft_after_send();
    compose_ui.autosize_textarea();
    $("#compose-send-status").hide(0);
    $("#compose-send-button").prop('disabled', false);
    $("#sending-indicator").hide();
    resize.resize_bottom_whitespace();
}

exports.send_message_success = function (local_id, message_id, locally_echoed) {
    if (!locally_echoed) {
        clear_compose_box();
    }

    echo.reify_message_id(local_id, message_id);
};

exports.send_message = function send_message(request) {
    if (request === undefined) {
        request = create_message_object();
    }

    if (request.type === "private") {
        request.to = JSON.stringify(request.to);
    } else {
        request.to = JSON.stringify([request.to]);
    }

    var local_id;
    var locally_echoed;

    local_id = echo.try_deliver_locally(request);
    if (local_id) {
        // We are rendering this message locally with an id
        // like 92l99.01 that corresponds to a reasonable
        // approximation of the id we'll get from the server
        // in terms of sorting messages.
        locally_echoed = true;
    } else {
        // We are not rendering this message locally, but we
        // track the message's life cycle with an id like
        // loc-1, loc-2, loc-3,etc.
        locally_echoed = false;
        local_id = sent_messages.get_new_local_id();
    }

    request.local_id = local_id;

    sent_messages.start_tracking_message({
        local_id: local_id,
        locally_echoed: locally_echoed,
    });

    request.locally_echoed = locally_echoed;

    function success(data) {
        exports.send_message_success(local_id, data.id, locally_echoed);
    }

    function error(response) {
        // If we're not local echo'ing messages, or if this message was not
        // locally echoed, show error in compose box
        if (!locally_echoed) {
            compose_error(response, $('#compose-textarea'));
            return;
        }

        echo.message_send_error(local_id, response);
    }

    transmit.send_message(request, success, error);
    server_events.assert_get_events_running("Restarting get_events because it was not running during send");

    if (locally_echoed) {
        clear_compose_box();
    }
};

exports.deferred_message_types = {
    scheduled: {
        delivery_type: 'send_later',
        test: /^\/schedule/,
        slash_command: '/schedule',
    },
    reminders: {
        delivery_type: 'remind',
        test: /^\/remind/,
        slash_command: '/remind',
    },
};

function is_deferred_delivery(message_content) {
    var reminders_test = exports.deferred_message_types.reminders.test;
    var scheduled_test = exports.deferred_message_types.scheduled.test;
    return (reminders_test.test(message_content) ||
            scheduled_test.test(message_content));
}

function patch_request_for_scheduling(request) {
    var new_request = request;
    var raw_message = request.content.split('\n');
    var command_line = raw_message[0];
    var message = raw_message.slice(1).join('\n');

    var deferred_message_type = _.filter(exports.deferred_message_types, function (props) {
        return command_line.match(props.test) !== null;
    })[0];
    var command = command_line.match(deferred_message_type.test)[0];

    var deliver_at = command_line.slice(command.length + 1);

    if (message.trim() === '' || deliver_at.trim() === '' ||
        command_line.slice(command.length, command.length + 1) !== ' ') {

        $("#compose-textarea").attr('disabled', false);
        if (command_line.slice(command.length, command.length + 1) !== ' ') {
            compose_error(i18n.t('Invalid slash command. Check if you are missing a space after the command.'), $('#compose-textarea'));
        } else if (deliver_at.trim() === '') {
            compose_error(i18n.t('Please specify time for your reminder.'), $('#compose-textarea'));
        } else {
            compose_error(i18n.t('Your reminder note is empty!'), $('#compose-textarea'));
        }
        return;
    }

    new_request.content = message;
    new_request.deliver_at = deliver_at;
    new_request.delivery_type = deferred_message_type.delivery_type;
    new_request.tz_guess = moment.tz.guess();
    return new_request;
}

exports.schedule_message = function schedule_message(request, success, error) {
    if (request === undefined) {
        request = create_message_object();
    }

    if (request.type === "private") {
        request.to = JSON.stringify(request.to);
    } else {
        request.to = JSON.stringify([request.to]);
    }

    /* success and error callbacks are kind of a package deal here. When scheduling
    a message either by means of slash command or from message feed, if we need to do
    something special on success then we will also need to know if our request errored
    and do something appropriate. Therefore we just check if success callback is not
    defined and just assume request to be coming from compose box. This is correct
    because we won't ever actually have success operate in different context than error. */
    if (success === undefined) {
        success = function (data) {
            notifications.notify_above_composebox('Scheduled your Message to be delivered at: ' + data.deliver_at);
            $("#compose-textarea").attr('disabled', false);
            clear_compose_box();
        };
        error = function (response) {
            $("#compose-textarea").attr('disabled', false);
            compose_error(response, $('#compose-textarea'));
        };
        /* We are adding a disable on compose under this block since it actually
        has its place with the branch of code which does stuff when slash command
        is incoming from compose_box */
        $("#compose-textarea").attr('disabled', true);
    }

    request = patch_request_for_scheduling(request);

    if (request === undefined) {
       return;
    }

    transmit.send_message(request, success, error);
};

exports.enter_with_preview_open = function () {
    exports.clear_preview_area();
    if (page_params.enter_sends) {
        // If enter_sends is enabled, we attempt to send the message
        exports.finish();
    } else {
        // Otherwise, we return to the compose box and focus it
        $("#compose-textarea").focus();
    }
};

exports.finish = function () {
    exports.clear_invites();
    exports.clear_private_stream_alert();
    notifications.clear_compose_notifications();

    if (! compose.validate()) {
        return false;
    }

    var message_content = compose_state.message_content();
    if (is_deferred_delivery(message_content)) {
        exports.schedule_message();
    } else {
        exports.send_message();
    }
    exports.clear_preview_area();
    // TODO: Do we want to fire the event even if the send failed due
    // to a server-side error?
    $(document).trigger($.Event('compose_finished.zulip'));
    return true;
};

exports.update_email = function (user_id, new_email) {
    var reply_to = compose_state.recipient();

    if (!reply_to) {
        return;
    }

    reply_to = people.update_email_in_reply_to(reply_to, user_id, new_email);

    compose_state.recipient(reply_to);
};

exports.get_invalid_recipient_emails = function () {
    var private_recipients = util.extract_pm_recipients(compose_state.recipient());
    var invalid_recipients = _.reject(private_recipients, people.is_valid_email_for_compose);

    return invalid_recipients;
};

function check_unsubscribed_stream_for_send(stream_name, autosubscribe) {
    var stream_obj = stream_data.get_sub(stream_name);
    var result;
    if (!stream_obj) {
        return "does-not-exist";
    }
    if (!autosubscribe) {
        return "not-subscribed";
    }

    // In the rare circumstance of the autosubscribe option, we
    // *Synchronously* try to subscribe to the stream before sending
    // the message.  This is deprecated and we hope to remove it; see
    // #4650.
    channel.post({
        url: "/json/subscriptions/exists",
        data: {stream: stream_name, autosubscribe: true},
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
}

function validate_stream_message_mentions(stream_name) {
    var stream_count = stream_data.get_subscriber_count(stream_name) || 0;

    // check if @all or @everyone is in the message
    if (util.is_all_or_everyone_mentioned(compose_state.message_content()) &&
        stream_count > compose.all_everyone_warn_threshold) {
        if (user_acknowledged_all_everyone === undefined ||
            user_acknowledged_all_everyone === false) {
            // user has not seen a warning message yet if undefined
            show_all_everyone_warnings();

            $("#compose-send-button").prop('disabled', false);
            $("#sending-indicator").hide();
            return false;
        }
    } else {
        // the message no longer contains @all or @everyone
        exports.clear_all_everyone_warnings();
    }
    // at this point, the user has either acknowledged the warning or removed @all / @everyone
    user_acknowledged_all_everyone = undefined;

    return true;
}

function validate_stream_message_announce(stream_name) {
    var stream_count = stream_data.get_subscriber_count(stream_name) || 0;

    if (stream_name === "announce" &&
        stream_count > compose.announce_warn_threshold) {
        if (user_acknowledged_announce === undefined ||
            user_acknowledged_announce === false) {
            // user has not seen a warning message yet if undefined
            show_announce_warnings();

            $("#compose-send-button").prop('disabled', false);
            $("#sending-indicator").hide();
            return false;
        }
    } else {
        exports.clear_announce_warnings();
    }
    // at this point, the user has acknowledged the warning
    user_acknowledged_announce = undefined;

    return true;
}

exports.validation_error = function (error_type, stream_name) {
    var response;

    var context = {};
    context.stream_name = Handlebars.Utils.escapeExpression(stream_name);

    switch (error_type) {
    case "does-not-exist":
        response = i18n.t("<p>The stream <b>__stream_name__</b> does not exist.</p><p>Manage your subscriptions <a href='#streams/all'>on your Streams page</a>.</p>", context);
        compose_error(response, $('#stream'));
        return false;
    case "error":
        compose_error(i18n.t("Error checking subscription"), $("#stream"));
        return false;
    case "not-subscribed":
        var new_row = templates.render("compose_not_subscribed");
        compose_not_subscribed_error(new_row, $('#stream'));
        return false;
    }
    return true;
};

exports.validate_stream_message_address_info = function (stream_name) {
    if (stream_data.is_subscribed(stream_name)) {
        return true;
    }
    var autosubscribe = page_params.narrow_stream !== undefined;
    var error_type = check_unsubscribed_stream_for_send(stream_name, autosubscribe);
    return exports.validation_error(error_type, stream_name);
};

function validate_stream_message() {
    var stream_name = compose_state.stream_name();
    if (stream_name === "") {
        compose_error(i18n.t("Please specify a stream"), $("#stream"));
        return false;
    }

    if (page_params.realm_mandatory_topics) {
        var topic = compose_state.subject();
        if (topic === "") {
            compose_error(i18n.t("Please specify a topic"), $("#subject"));
            return false;
        }
    }

    // If both `@all` is mentioned and it's in `#announce`, just validate
    // for `@all`. Users shouldn't have to hit "yes" more than once.
    if (util.is_all_or_everyone_mentioned(compose_state.message_content()) &&
        stream_name === "announce") {
        if (!exports.validate_stream_message_address_info(stream_name) ||
            !validate_stream_message_mentions(stream_name)) {
            return false;
        }
    // If either criteria isn't met, just do the normal validation.
    } else {
      if (!exports.validate_stream_message_address_info(stream_name) ||
          !validate_stream_message_mentions(stream_name) ||
          !validate_stream_message_announce(stream_name)) {
          return false;
      }
    }

    return true;
}

// The function checks whether the recipients are users of the realm or cross realm users (bots
// for now)
function validate_private_message() {
    if (compose_state.recipient().length === 0) {
        compose_error(i18n.t("Please specify at least one valid recipient"), $("#private_message_recipient"));
        return false;
    } else if (page_params.realm_is_zephyr_mirror_realm) {
        // For Zephyr mirroring realms, the frontend doesn't know which users exist
        return true;
    }

    var invalid_recipients = exports.get_invalid_recipient_emails();

    var context = {};
    if (invalid_recipients.length === 1) {
        context = {recipient: invalid_recipients.join()};
        compose_error(i18n.t("The recipient __recipient__ is not valid", context), $("#private_message_recipient"));
        return false;
    } else if (invalid_recipients.length > 1) {
        context = {recipients: invalid_recipients.join()};
        compose_error(i18n.t("The recipients __recipients__ are not valid", context), $("#private_message_recipient"));
        return false;
    }
    return true;
}

exports.validate = function () {
    $("#compose-send-button").attr('disabled', 'disabled').blur();
    var message_content = compose_state.message_content();
    if (is_deferred_delivery(message_content)) {
        show_sending_indicator('Scheduling...');
    } else {
        show_sending_indicator();
    }

    if (/^\s*$/.test(message_content)) {
        compose_error(i18n.t("You have nothing to send!"), $("#compose-textarea"));
        return false;
    }

    if ($("#zephyr-mirror-error").is(":visible")) {
        compose_error(i18n.t("You need to be running Zephyr mirroring in order to send messages!"));
        return false;
    }

    if (compose_state.get_message_type() === 'private') {
        return validate_private_message();
    }
    return validate_stream_message();
};

exports.handle_keydown = function (event) {
    var code = event.keyCode || event.which;
    var textarea = $("#compose-textarea");
    var range = textarea.range();
    var isBold = code === 66;
    var isItalic = code === 73 && !event.shiftKey;
    var isLink = code === 76 && event.shiftKey;

    // detect command and ctrl key
    var isCmdOrCtrl = /Mac/i.test(navigator.userAgent) ? event.metaKey : event.ctrlKey;

    if ((isBold || isItalic || isLink) && isCmdOrCtrl) {
        function add_markdown(markdown) {
            var textarea = $("#compose-textarea");
            var range = textarea.range();
            if (!document.execCommand('insertText', false, markdown)) {
                textarea.range(range.start, range.end).range(markdown);
            }
            event.preventDefault();
        }

        if (isBold) {
            // ctrl + b: Convert selected text to bold text
            add_markdown("**" + range.text + "**");
            if (!range.length) {
                textarea.caret(textarea.caret() - 2);
            }
        }
        if (isItalic) {
            // ctrl + i: Convert selected text to italic text
            add_markdown("*" + range.text + "*");
            if (!range.length) {
                textarea.caret(textarea.caret() - 1);
            }
        }
        if (isLink) {
            // ctrl + l: Insert a link to selected text
            add_markdown("[" + range.text + "](url)");
            var position = textarea.caret();
            var txt = document.getElementById("compose-textarea");

            // Include selected text in between [] parantheses and insert '(url)'
            // where "url" should be automatically selected.
            // Position of cursor depends on whether browser supports exec
            // command or not. So set cursor position accrodingly.
            if (range.length > 0) {
                if (document.queryCommandEnabled('insertText')) {
                    txt.selectionStart = position - 4;
                    txt.selectionEnd = position - 1;
                } else {
                    txt.selectionStart = position + range.length + 3;
                    txt.selectionEnd = position + range.length + 6;
                }
            } else {
                textarea.caret(textarea.caret() - 6);
            }
        }

        compose_ui.autosize_textarea();
        return;
    }
};

exports.initialize = function () {
    $('#stream,#subject,#private_message_recipient').on('keyup', update_fade);
    $('#stream,#subject,#private_message_recipient').on('change', update_fade);
    $('#compose-textarea').on('keydown', exports.handle_keydown);

    $("#compose form").on("submit", function (e) {
       e.preventDefault();
       compose.finish();
    });

    resize.watch_manual_resize("#compose-textarea");

    upload.feature_check($("#compose #attach_files"));

    // Show a warning if a user @-mentions someone who will not receive this message
    $(document).on('usermention_completed.zulip', function (event, data) {
        if (compose_state.get_message_type() !== 'stream') {
            return;
        }

        // Disable for Zephyr mirroring realms, since we never have subscriber lists there
        if (page_params.realm_is_zephyr_mirror_realm) {
            return;
        }

        if (data !== undefined && data.mentioned !== undefined) {
            var email = data.mentioned.email;

            // warn if @all, @everyone or @stream is mentioned
            if (data.mentioned.full_name  === 'all' || data.mentioned.full_name === 'everyone' || data.mentioned.full_name === 'stream') {
                return; // don't check if @all or @everyone is subscribed to a stream
            }

            if (compose_fade.would_receive_message(email) === false) {
                var error_area = $("#compose_invite_users");
                var existing_invites_area = $('#compose_invite_users .compose_invite_user');

                var existing_invites = _.map($(existing_invites_area), function (user_row) {
                    return $(user_row).data('useremail');
                });

                if (existing_invites.indexOf(email) === -1) {
                    var context = {email: email, name: data.mentioned.full_name};
                    var new_row = templates.render("compose-invite-users", context);
                    error_area.append(new_row);
                }

                error_area.show();
            }
        }

        // User group mentions will fall through here.  In the future,
        // we may want to add some sort of similar warning for cases
        // where nobody in the group is subscribed, but that decision
        // can wait on user feedback.
    });

    $("#compose-all-everyone").on('click', '.compose-all-everyone-confirm', function (event) {
        event.preventDefault();

        $(event.target).parents('.compose-all-everyone').remove();
        user_acknowledged_all_everyone = true;
        exports.clear_all_everyone_warnings();
        compose.finish();
    });

    $("#compose-announce").on('click', '.compose-announce-confirm', function (event) {
        event.preventDefault();

        $(event.target).parents('.compose-announce').remove();
        user_acknowledged_announce = true;
        exports.clear_announce_warnings();
        compose.finish();
    });

    $("#compose-send-status").on('click', '.sub_unsub_button', function (event) {
        event.preventDefault();

        var stream_name = $('#stream').val();
        if (stream_name === undefined) {
            return;
        }
        var sub = stream_data.get_sub(stream_name);
        subs.sub_or_unsub(sub);
        $("#compose-send-status").hide();
    });

    $("#compose-send-status").on('click', '#compose_not_subscribed_close', function (event) {
        event.preventDefault();

        $("#compose-send-status").hide();
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

        var stream_name = compose_state.stream_name();
        var sub = stream_data.get_sub(stream_name);
        if (!sub) {
            // This should only happen if a stream rename occurs
            // before the user clicks.  We could prevent this by
            // putting a stream id in the link.
            blueslip.warn('Stream no longer exists: ' + stream_name);
            failure();
            return;
        }

        stream_edit.invite_user_to_stream(email, sub, success, failure);
    });

    $("#compose_invite_users").on('click', '.compose_invite_close', function (event) {
        var invite_row = $(event.target).parents('.compose_invite_user');
        var all_invites = $("#compose_invite_users");

        invite_row.remove();

        if (all_invites.children().length === 0) {
            all_invites.hide();
        }
    });

    // Show a warning if a private stream is linked
    $(document).on('streamname_completed.zulip', function (event, data) {
        // For PMs, we don't warn about links to private streams, since
        // you are often specifically encouraging somebody to subscribe
        // to the stream over PMs.
        if (compose_state.get_message_type() !== 'stream') {
            return;
        }

        if (data === undefined || data.stream === undefined) {
            blueslip.error('Invalid options passed into handler.');
            return;
        }

        var compose_stream = stream_data.get_sub(compose_state.stream_name());
        if (compose_stream.subscribers && data.stream.subscribers) {
            var compose_stream_sub = compose_stream.subscribers.keys();
            var mentioned_stream_sub = data.stream.subscribers.keys();
            // Don't warn if subscribers list of current compose_stream is a subset of
            // mentioned_stream subscribers list.
            if (_.difference(compose_stream_sub, mentioned_stream_sub).length === 0) {
                return;
            }
        }

        // data.stream refers to the stream we're linking to in
        // typeahead.  If it's not invite-only, then it's public, and
        // there is no need to warn about it, since all users can already
        // see all the public streams.
        if (!data.stream.invite_only) {
            return;
        }

        var stream_name = data.stream.name;

        var warning_area = $("#compose_private_stream_alert");
        var context = { stream_name: stream_name };
        var new_row = templates.render("compose_private_stream_alert", context);

        warning_area.append(new_row);
        warning_area.show();
    });

    $("#compose_private_stream_alert").on('click', '.compose_private_stream_alert_close', function (event) {
        var stream_alert_row = $(event.target).parents('.compose_private_stream_alert');
        var stream_alert = $("#compose_private_stream_alert");

        stream_alert_row.remove();

        if (stream_alert.children().length === 0) {
            stream_alert.hide();
        }
    });

    // Click event binding for "Attach files" button
    // Triggers a click on a hidden file input field

    $("#compose").on("click", "#attach_files", function (e) {
        e.preventDefault();
        $("#compose #file_input").trigger("click");
    });

    // content is passed to check for status messages ("/me ...")
    // and will be undefined in case of errors
    function show_preview(rendered_content, content) {
        var rendered_preview_html;
        if (content !== undefined && markdown.is_status_message(content, rendered_content)) {
            // Handle previews of /me messages
            rendered_preview_html = "<strong>" + page_params.full_name + "</strong> " + rendered_content.slice(4 + 3, -4);
        } else {
            rendered_preview_html = rendered_content;
        }

        $("#preview_content").html(rendered_preview_html);
        if (page_params.emojiset === "text") {
            $("#preview_content").find(".emoji").replaceWith(function () {
                var text = $(this).attr("title");
                return ":" + text + ":";
            });
         }
    }

    $('#compose').on('click', '#video_link', function (e) {
        e.preventDefault();

        if (page_params.jitsi_server_url === null) {
            return;
        }

        var video_call_id = util.random_int(100000000000000, 999999999999999);
        var video_call_link = page_params.jitsi_server_url + "/" +  video_call_id;
        var video_call_link_text = '[' + _('Click to join video call') + '](' + video_call_link + ')';
        compose_ui.insert_syntax_and_focus(video_call_link_text);
    });

    $("#compose").on("click", "#markdown_preview", function (e) {
        e.preventDefault();
        var content = $("#compose-textarea").val();
        $("#compose-textarea").hide();
        $("#markdown_preview").hide();
        $("#undo_markdown_preview").show();
        $("#preview_message_area").show();

        if (content.length === 0) {
            show_preview(i18n.t("Nothing to preview"));
        } else {
            if (markdown.contains_backend_only_syntax(content))  {
                var spinner = $("#markdown_preview_spinner").expectOne();
                loading.make_indicator(spinner);
            } else {
                // For messages that don't appear to contain
                // bugdown-specific syntax not present in our
                // marked.js frontend processor, we render using the
                // frontend markdown processor message (but still
                // render server-side to ensure the preview is
                // accurate; if the `markdown.contains_backend_only_syntax` logic is
                // incorrect wrong, users will see a brief flicker).
                var message_obj = {
                    raw_content: content,
                };
                markdown.apply_markdown(message_obj);
            }
            channel.post({
                url: '/json/messages/render',
                idempotent: true,
                data: {content: content},
                success: function (response_data) {
                    if (markdown.contains_backend_only_syntax(content)) {
                        loading.destroy_indicator($("#markdown_preview_spinner"));
                    }
                    show_preview(response_data.rendered, content);
                },
                error: function () {
                    if (markdown.contains_backend_only_syntax(content)) {
                        loading.destroy_indicator($("#markdown_preview_spinner"));
                    }
                    show_preview(i18n.t("Failed to generate preview"));
                },
            });
        }
    });

    $("#compose").on("click", "#undo_markdown_preview", function (e) {
        e.preventDefault();
        exports.clear_preview_area();
    });

    $("#compose").filedrop(
        upload.options({
            mode: 'compose',
        })
    );

    if (page_params.narrow !== undefined) {
        if (page_params.narrow_topic !== undefined) {
            compose_actions.start("stream", {subject: page_params.narrow_topic});
        } else {
            compose_actions.start("stream", {});
        }
    }
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = compose;
}
