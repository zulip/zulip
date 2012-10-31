var compose = (function () {

var exports = {};
var is_composing_message = false;

exports.start = function (msg_type, opts) {
    opts = $.extend({ message_type:     msg_type,
                      stream:           '',
                      subject:          '',
                      huddle_recipient: '',
                      message:          ''
                    }, opts);

    $("#stream").val(opts.stream);
    $("#subject").val(opts.subject);
    $("#huddle_recipient").val(opts.huddle_recipient);
    $("#new_message_content").val(opts.message);

    $('#sidebar a[href="#home"]').tab('show');

    if (msg_type !== 'stream') {
        // TODO: Just to make sure that compose.composing() output is
        // consistent.  We really should just standardize our
        // terminology
        msg_type = "huddle";
    }

    var focus_area;
    if (opts.stream && ! opts.subject) {
        focus_area = 'subject';
    } else if (opts.stream || opts.huddle_recipient) {
        focus_area = 'new_message_content';
    }

    if (msg_type === 'stream') {
        exports.show('stream', $("#" + (focus_area || 'stream')));
    } else {
        exports.show('personal', $("#" + (focus_area || 'huddle_recipient')));
    }

    hotkeys.set_compose();
    is_composing_message = msg_type;
    $(document).trigger($.Event('compose_started.zephyr', opts));
};

exports.cancel = function () {
    compose.hide();
    is_composing_message = false;
    $(document).trigger($.Event('compose_canceled.zephyr'));
};

var send_options;

$(function () {
    var send_status = $('#send-status');

    send_options = {
        dataType: 'json', // This seems to be ignored. We still get back an xhr.
        success: function (resp, statusText, xhr, form) {
            form.find('textarea').val('');
            send_status.hide();
            compose.hide();
            $("#compose-send-button").removeAttr('disabled');
        },
        error: function (xhr, error_type) {
            if (error_type !== 'timeout' && get_updates_params.reload_pending) {
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
            send_status.removeClass(status_classes)
                       .addClass('alert-error')
                       .text(response)
                       .append($('<span />')
                           .addClass('send-status-close').html('&times;')
                           .click(function () { send_status.stop(true).fadeOut(500); }))
                       .stop(true).fadeTo(0,1);

            $("#compose-send-button").removeAttr('disabled');
        }
    };

    send_status.hide();
});

exports.finish = function () {
    if (! compose.validate()) {
        return false;
    }
    $("#compose form").ajaxSubmit(send_options);
    is_composing_message = false;
    $(document).trigger($.Event('compose_finished.zephyr'));
    return true;
};

$(function () {
    $("#compose form").on("submit", function (e) {
       e.preventDefault();
       compose.finish();
    });
});

exports.show = function (tabname, focus_area) {
    if (reload.is_in_progress()) {
        return;
    }
    $("#send-status").removeClass(status_classes).hide();
    $('#compose').css({visibility: "visible"});
    $("#new_message_content").trigger("autosize");
    $('.message_comp').slideDown(100);
    $('#message-type-tabs a[href="#' + tabname + '-message"]').tab('show');
    focus_area.focus();
    focus_area.select();
};

exports.hide = function () {
    $('input, textarea, button').blur();
    $('.message_comp').slideUp(100,
                              function() { $('#compose').css({visibility: "hidden"});});
};

exports.clear = function () {
    $("#compose").find('input[type=text], textarea').val('');
};

exports.set_message_type = function (tabname) {
    is_composing_message = tabname;
    $("#send-status").removeClass(status_classes).hide();
    if (tabname === "stream") {
        $('#personal-message').hide();
        $('#stream-message').show();
        $('#new_message_type').val('stream');
        $("#stream").focus();
    } else {
        $('#personal-message').show();
        $('#stream-message').hide();
        $('#new_message_type').val('personal');
        $("#huddle_recipient").focus();
    }
};


exports.toggle_mode = function () {
    if ($("#message-type-tabs li.active").find("a[href=#stream-message]").length !== 0) {
        // In stream tab, switch to personals.
        exports.show('personal', $("#huddle_recipient"));
    } else {
        exports.show('stream', $("#stream"));
    }
};

exports.composing = function () {
    return is_composing_message;
};

function get_or_set(fieldname) {
    // We can't hoist the assignment of 'elem' out of this lambda,
    // because the DOM element might not exist yet when get_or_set
    // is called.
    return function (newval) {
        var elem = $('#'+fieldname);
        var oldval = $.trim(elem.val());
        if (newval !== undefined) {
            elem.val(newval);
        }
        return oldval;
    };
}

exports.stream_name     = get_or_set('stream');
exports.subject         = get_or_set('subject');
exports.message_content = get_or_set('new_message_content');
exports.recipient       = get_or_set('huddle_recipient');

function compose_error(error_text, bad_input) {
    $('#send-status').removeClass(status_classes)
               .addClass('alert-error')
               .text(error_text)
               .stop(true).fadeTo(0, 1);
    $("#compose-send-button").removeAttr('disabled');
    bad_input.focus().select();
}

// *Synchronously* check if a stream exists.
// If not, displays an error and returns false.
function check_stream_for_send(stream_name) {
    var okay = true;
    $.ajax({
        type: "POST",
        url: "/json/subscriptions/exists",
        data: {'stream': stream_name},
        async: false,
        success: function (data) {
            if (!data.exists) {
                // The stream doesn't exist
                okay = false;
                $('#send-status').removeClass(status_classes).show();
                $('#stream-dne-name').text(stream_name);
                $('#stream-dne').show();
                $("#compose-send-button").removeAttr('disabled');
                exports.hide();
                $('#create-it').focus();
            }
            $("#home-error").hide();
        },
        error: function (xhr) {
            okay = false;
            report_error("Error checking subscription", xhr, $("#home-error"));
            $("#stream").focus();
            $("#compose-send-button").removeAttr('disabled');
        }
    });
    return okay;
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

    if (exports.message_content() === "") {
        compose_error("You have nothing to send!", $("#new_message_content"));
        return false;
    }

    if (!subs.have(stream_name)) {
        if (!check_stream_for_send(stream_name)) {
            return false;
        }
        // You're not subbed to the stream
        $('#send-status').removeClass(status_classes).show();
        $('#stream-nosub-name').text(stream_name);
        $('#stream-nosub').show();
        $("#compose-send-button").removeAttr('disabled');
        exports.hide();
        $('#sub-it').focus();
        return false;
    }

    return true;
}

function validate_huddle_message() {
    if (exports.recipient() === "") {
        compose_error("Please specify at least one recipient", $("#huddle_recipient"));
        return false;
    }

    if (exports.message_content() === "") {
        compose_error("You have nothing to send!", $("#new_message_content"));
        return false;
    }

    return true;
}

exports.validate = function () {
    $("#compose-send-button").attr('disabled', 'disabled').blur();

    if (exports.composing() === 'huddle') {
        return validate_huddle_message();
    } else {
        return validate_stream_message();
    }
};

$(function () {
    $("#new_message_content").autosize();
});

return exports;

}());
