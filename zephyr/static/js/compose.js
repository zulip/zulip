var compose = (function () {

var exports = {};
var is_composing_message = false;
var faded_to;

function show(tabname, focus_area) {
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
    $("#new_message_content").trigger("autosize");
    $('.message_comp').slideDown(100, function () {
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
            disable_pointer_movement = true;
            // We use $('html, body') because you can't animate window.scrollTop
            // on Chrome (http://bugs.jquery.com/ticket/10419).
            $('html, body').animate({
                scrollTop: viewport.scrollTop() + cover + 5
            }, {
                complete: function () {
                    // The complete callback is actually called before the
                    // scrolling has completed, so we try to let scrolling
                    // finish before allowing pointer movements again or the
                    // pointer may still move.
                    setTimeout(function () {
                        disable_pointer_movement = false;
                    }, 50);
                }
            });
        }
    });
    focus_area.focus();
    focus_area.select();
    // Disable the notifications bar if it overlaps with the composebox
    notifications_bar.maybe_disable();
}

// In an attempt to decrease mixing, make the composebox's
// stream bar look like what you're replying to.
// (In particular, if there's a color associated with it,
//  have that color be reflected here too.)
exports.decorate_stream_bar = function (stream_name) {
    var color = subs.get_color(stream_name);
    $("#stream-message .message_header_stream")
        .css('background-color', color)
        .removeClass(subs.color_classes)
        .addClass(subs.get_color_class(color));
};

function messages_to_fade() {
    var all_elts = rows.get_table(current_msg_list.table_name).find(".recipient_row, .messagebox");
    var i, elts_to_fade = [];
    var different_recipient = false;
    // Note: The below algorithm relies on the fact that all_elts is
    // sorted as it would be displayed in the message view
    for (i = 0; i < all_elts.length; i++) {
        var elt = $(all_elts[i]);
        if (elt.hasClass("recipient_row")) {
            if (!util.same_recipient(faded_to, current_msg_list.get(rows.id(elt)))) {
                elts_to_fade.push(elt);
                different_recipient = true;
            } else {
                different_recipient = false;
            }
        } else if (different_recipient) {
            elts_to_fade.push(elt);
        }
    }
    return elts_to_fade;
}

exports.unfade_messages = function (clear_state) {
    if (faded_to === undefined) {
        return;
    }

    var fade_class = narrow.active() ? "message_reply_fade_narrowed" : "message_reply_fade";
    rows.get_table(current_msg_list.table_name).find(".recipient_row, .messagebox").removeClass(fade_class);
    if (clear_state === true) {
        faded_to = undefined;
    }
    ui.enable_floating_recipient_bar();
};

exports.update_faded_messages = function () {
    if (faded_to === undefined) {
        return;
    }

    var i, fade_class, elts_to_fade;

    fade_class = narrow.active() ? "message_reply_fade_narrowed" : "message_reply_fade";
    elts_to_fade = messages_to_fade();

    for (i = 0; i < elts_to_fade.length; i++) {
        $(elts_to_fade[i]).addClass(fade_class);
    }
    ui.disable_floating_recipient_bar();
};

exports.update_recipient_on_narrow = function() {
    if (!compose.composing()) {
        return;
    }
    if (compose.message_content() !== "") {
        return;
    }
    var compose_opts = {};
    narrow.set_compose_defaults(compose_opts);
    if (compose_opts.stream) {
        compose.start("stream");
    } else {
        compose.start("private");
    }
};

function do_fade(reply_message, fade_type) {
    compose.unfade_messages();

    // Construct faded_to as a mocked up element which has all the
    // fields of a message used by util.same_recipient()
    faded_to = {
        type: fade_type
    };
    if (fade_type === "stream") {
        faded_to.recipient_id = reply_message.recipient_id;
        faded_to.subject = reply_message.subject;
    } else {
        faded_to.reply_to = reply_message.reply_to;
    }
    exports.update_faded_messages();
}

exports.start = function (msg_type, opts) {
    if (reload.is_in_progress()) {
        return;
    }

    var default_opts = {
        message_type:     msg_type,
        stream:           '',
        subject:          '',
        private_message_recipient: ''
    };

    // Set default parameters based on the current narrowed view.
    narrow.set_compose_defaults(default_opts);

    opts = $.extend(default_opts, opts);

    if (!(compose.composing() === msg_type &&
          ((msg_type === "stream" &&
            opts.stream === compose.stream_name() &&
            opts.subject === compose.subject()) ||
           (msg_type === "private" &&
            opts.private_message_recipient === compose.recipient())))) {
        // Clear the compose box if the existing message is to a different recipient
        compose.clear();
    }

    compose.stream_name(opts.stream);
    compose.subject(opts.subject);
    compose.recipient(opts.private_message_recipient);
    // If the user opens the compose box, types some text, and then clicks on a
    // different stream/subject, we want to keep the text in the compose box
    if (opts.message !== undefined) {
        compose.message_content(opts.message);
    }

    ui.change_tab_to("#home");

    var focus_area;
    if (opts.stream && ! opts.subject) {
        focus_area = 'subject';
    } else if (opts.stream || opts.private_message_recipient) {
        focus_area = 'new_message_content';
    }

    if (msg_type === 'stream') {
        show('stream', $("#" + (focus_area || 'stream')));
    } else {
        show('private', $("#" + (focus_area || 'private_message_recipient')));
    }

    if (opts.replying_to_message !== undefined) {
        do_fade(opts.replying_to_message, msg_type);
    }

    is_composing_message = msg_type;
    exports.decorate_stream_bar(opts.stream);
    $(document).trigger($.Event('compose_started.zephyr', opts));
};

function abort_xhr () {
    $("#compose-send-button").removeAttr("disabled");
    var xhr = $("#compose").data("filedrop_xhr");
    if (xhr !== undefined) {
        xhr.abort();
        $("#compose").removeData("filedrop_xhr");
    }
}

exports.cancel = function () {
    compose.hide();
    abort_xhr();
    is_composing_message = false;
    $(document).trigger($.Event('compose_canceled.zephyr'));
};

function compose_error(error_text, bad_input) {
    $('#send-status').removeClass(status_classes)
               .addClass('alert-error')
               .stop(true).fadeTo(0, 1);
    $('#error-msg').html(error_text);
    $("#compose-send-button").removeAttr('disabled');
    $("#sending-indicator").hide();
    bad_input.focus().select();
}

var send_options;

function send_message() {
    var send_status = $('#send-status');

    // TODO: this should be collapsed with the code in composebox_typeahead.js
    var recipients = compose.recipient().split(/\s*[,;]\s*/);

    var request = {client: 'website',
                   type:        compose.composing(),
                   subject:     compose.subject(),
                   content:     compose.message_content()};
    if (request.type === "private") {
        request.to = JSON.stringify(recipients);
    } else {
        request.to = JSON.stringify([compose.stream_name()]);
    }

    if (tutorial.is_running()) {
        // We make a new copy of the request object for the tutorial so that we
        // don't mess up the request we're actually sending to the server
        var tutorial_copy_of_message = $.extend({}, request, {to: compose.stream_name()});
        if (request.type === "private") {
            $.extend(tutorial_copy_of_message, {to: recipients});
        }
        tutorial.message_was_sent(tutorial_copy_of_message);
    }

    $.ajax({
        dataType: 'json', // This seems to be ignored. We still get back an xhr.
        url: '/json/send_message',
        type: 'POST',
        data: request,
        success: function (resp, statusText, xhr) {
            compose.clear();
            send_status.hide();
            is_composing_message = false;
            compose.hide();
            $("#compose-send-button").removeAttr('disabled');
            $("#sending-indicator").hide();
        },
        error: function (xhr, error_type) {
            if (error_type !== 'timeout' && reload.is_pending()) {
                // The error might be due to the server changing
                reload.initiate({immediate: true, send_after_reload: true});
                return;
            }
            var response = "Error sending message";
            if (xhr.status.toString().charAt(0) === "4") {
                // Only display the error response for 4XX, where we've crafted
                // a nice response.
                response += ": " + $.parseJSON(xhr.responseText).msg;
            }
            compose_error(response, $('#new_message_content'));
        }
    });

    send_status.hide();
}

exports.finish = function () {
    if (! compose.validate()) {
        return false;
    }
    send_message();
    // TODO: Do we want to fire the event even if the send failed due
    // to a server-side error?
    $(document).trigger($.Event('compose_finished.zephyr'));
    return true;
};

$(function () {
    $("#compose form").on("submit", function (e) {
       e.preventDefault();
       compose.finish();
    });
});

exports.hide = function () {
    $('.message_comp').find('input, textarea, button').blur();
    $('.message_comp').slideUp(100,
                              function() { $('#compose').css({visibility: "hidden"});});
    notifications_bar.enable();
    exports.unfade_messages(true);
};

exports.clear = function () {
    $("#compose").find('input[type=text], textarea').val('');
};

// Set the mode of a compose already in progress.
// Does not clear the input fields.
exports.set_mode = function (mode) {
    ui.change_tab_to('#home');
    if (!is_composing_message) {
        exports.start(mode);
    }
    if (mode === 'private') {
        show('private', $("#private_message_recipient"));
        is_composing_message = "private";
    } else {
        show('stream', $("#stream"));
        is_composing_message = "stream";
    }
};

exports.composing = function () {
    return is_composing_message;
};

function get_or_set(fieldname, keep_outside_whitespace) {
    // We can't hoist the assignment of 'elem' out of this lambda,
    // because the DOM element might not exist yet when get_or_set
    // is called.
    return function (newval) {
        var elem = $('#'+fieldname);
        var oldval = elem.val();
        if (newval !== undefined) {
            elem.val(newval);
        }
        return keep_outside_whitespace ? oldval : $.trim(oldval);
    };
}

exports.stream_name     = get_or_set('stream');
exports.subject         = get_or_set('subject');
exports.message_content = get_or_set('new_message_content', true);
exports.recipient       = get_or_set('private_message_recipient');

// *Synchronously* check if a stream exists.
exports.check_stream_existence = function (stream_name) {
    var result = "error";
    $.ajax({
        type: "POST",
        url: "/json/subscriptions/exists",
        data: {'stream': stream_name},
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
        }
    });
    return result;
};


// Checks if a stream exists. If not, displays an error and returns
// false.
function check_stream_for_send(stream_name) {
    var result = exports.check_stream_existence(stream_name);

    if (result === "error") {
        compose_error("Error checking subscription", $("#stream"));
        $("#compose-send-button").removeAttr('disabled');
        $("#sending-indicator").hide();
    }

    return result;
}

function validate_stream_message() {
    var stream_name = exports.stream_name();
    if (stream_name === "") {
        compose_error("Please specify a stream", $("#stream"));
        return false;
    }

    if (exports.subject() === "") {
        compose_error("Please specify a subject", $("#subject"));
        return false;
    }

    var response;

    if (!subs.have(stream_name)) {
        switch(check_stream_for_send(stream_name)) {
        case "does-not-exist":
            response = "<p>The stream <b>" +
                Handlebars.Utils.escapeExpression(stream_name) + "</b> does not exist.</p>" +
                "<p>Manage your subscriptions <a href='#subscriptions'>on your Streams page</a>.</p>";
            compose_error(response, $('#stream'));
            return false;
        case "error":
            return false;
        case "subscribed":
            // You're actually subscribed to the stream, but this
            // browser window doesn't know it.
            return true;
        case "not-subscribed":
            response = "<p>You're not subscribed to the stream <b>" +
                Handlebars.Utils.escapeExpression(stream_name) + "</b>.</p>" +
                "<p>Manage your subscriptions <a href='#subscriptions'>on your Streams page</a>.</p>";
            compose_error(response, $('#stream'));
            return false;
        }
    }

    return true;
}

function validate_private_message() {
    if (exports.recipient() === "") {
        compose_error("Please specify at least one recipient", $("#private_message_recipient"));
        return false;
    }

    return true;
}

exports.validate = function () {
    $("#compose-send-button").attr('disabled', 'disabled').blur();
    $("#sending-indicator").show();

    if (exports.message_content() === "") {
        compose_error("You have nothing to send!", $("#new_message_content"));
        return false;
    }

    if (exports.composing() === 'private') {
        return validate_private_message();
    } else {
        return validate_stream_message();
    }
};

$(function () {
    $("#new_message_content").autosize();
    $("#compose").filedrop({
        url: "json/upload_file",
        paramname: "file",
        maxfilesize: 25,
        data: {
            // the token isn't automatically included in filedrop's post
            csrfmiddlewaretoken: csrf_token
        },
        drop: function (i, file, len) {
            $("#compose-send-button").attr("disabled", "");
            $("#send-status").addClass("alert-info")
                             .show();
            $(".send-status-close").one('click', abort_xhr);
            $("#error-msg").html(
                $("<p>").text("Uploading…")
                        .after('<div class="progress progress-striped active">' +
                               '<div class="bar" id="upload-bar" style="width: 00%;"></div>' +
                               '</div>'));
        },
        progressUpdated: function (i, file, progress) {
            $("#upload-bar").width(progress + "%");
        },
        error: function (err, file) {
            var msg;
            $("#send-status").addClass("alert-error")
                            .removeClass("alert-info");
            $("#compose-send-button").removeAttr("disabled");
            switch(err) {
                case 'BrowserNotSupported':
                    msg = "File upload is not yet available for your browser.";
                    break;
                case 'TooManyFiles':
                    msg = "Unable to upload that many files at once.";
                    break;
                case 'FileTooLarge':
                    // sanitizatio not needed as the file name is not potentially parsed as HTML, etc.
                    msg = "\"" + file.name + "\" was too large; the maximum file size is 25MiB.";
                    break;
                default:
                    msg = "An unknown error occured.";
                    break;
            }
            $("#error-msg").text(msg);
        },
        uploadFinished: function (i, file, response, time) {
            var textbox = $("#new_message_content");
            textbox.val(textbox.val() + " " + response.uri);
            $("#new_message_content").trigger("autosize");
            $("#compose-send-button").removeAttr("disabled");
            $("#send-status").removeClass("alert-info")
                             .hide();
        }
    });
});

return exports;

}());
