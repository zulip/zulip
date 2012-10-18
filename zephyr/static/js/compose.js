var status_classes = 'alert-error alert-success alert-info';

function show_compose(tabname, focus_area) {
    if (reloading_app) {
        return;
    }
    $("#send-status").removeClass(status_classes).hide();
    $('#compose').css({visibility: "visible"});
    $('.message_comp').slideDown(100);
    $('#message-type-tabs a[href="#' + tabname + '-message"]').tab('show');
    focus_area.focus();
    focus_area.select();
}

function hide_compose() {
    $('input, textarea, button').blur();
    $('.message_comp').slideUp(100,
                              function() { $('#compose').css({visibility: "hidden"});});
}

function clear_compose_box() {
    $("#compose").find('input[type=text], textarea').val('');
}

function compose_button(tabname) {
    clear_compose_box();
    $('#sidebar a[href="#home"]').tab('show');
    show_compose(tabname, $("#" + tabname));
    set_compose_hotkey();
}

function toggle_compose() {
    if ($("#message-type-tabs li.active").find("a[href=#stream-message]").length !== 0) {
        // In stream tab, switch to personals.
        show_compose('personal', $("#huddle_recipient"));
    } else {
        show_compose('stream', $("#stream"));
    }
}

function composing_stream_message() {
    return $("#stream-message").is(":visible");
}

function composing_huddle_message() {
    return $("#personal-message").is(":visible");
}

function composing_message() {
    return composing_stream_message() || composing_huddle_message();
}

function compose_stream_name(newval) {
    var oldval = $.trim($("#stream").val());
    if (newval !== undefined) {
        $("#stream").val(newval);
    }
    return oldval;
}

function compose_subject(newval) {
    var oldval =  $.trim($("#subject").val());
    if (newval !== undefined) {
        $("#subject").val(newval);
    }
    return oldval;
}

function compose_message(newval) {
    var oldval = $.trim($("#new_message_content").val());
    if (newval !== undefined) {
        $("#new_message_content").val(newval);
    }
    return oldval;
}

function compose_recipient(newval) {
    var oldval = $.trim($("#huddle_recipient").val());
    if (newval !== undefined) {
        $("#huddle_recipient").val(newval);
    }
    return oldval;
}

function compose_huddle_message(newval) {
    return compose_message(newval);
}

function compose_error(error_text, bad_input) {
    $('#send-status').removeClass(status_classes)
               .addClass('alert-error')
               .text(error_text)
               .stop(true).fadeTo(0, 1);
    $('#compose').find('input[type="submit"]').removeAttr('disabled');
    bad_input.focus().select();
}

function submit_buttons() {
    return $('#compose').find('input[type="submit"]');
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
                submit_buttons().removeAttr('disabled');
                hide_compose();
                $('#create-it').focus();
            }
            $("#home-error").hide();
        },
        error: function (xhr) {
            okay = false;
            report_error("Error checking subscription", xhr, $("#home-error"));
            $("#stream").focus();
            submit_buttons().removeAttr('disabled');
        }
    });
    return okay;
}

function validate_stream_message() {
    var stream_name = compose_stream_name();
    if (stream_name === "") {
        compose_error("Please specify a stream", $("#stream"));
        return false;
    }

    if (compose_subject() === "") {
        compose_error("Please specify an subject", $("#subject"));
        return false;
    }

    if (compose_message() === "") {
        compose_error("You have nothing to send!", $("#new_message_content"));
        return false;
    }

    if (!check_stream_for_send(stream_name))
        return false;

    if (!subscribed_to(stream_name)) {
        // You're not subbed to the stream
        $('#send-status').removeClass(status_classes).show();
        $('#stream-nosub-name').text(stream_name);
        $('#stream-nosub').show();
        submit_buttons().removeAttr('disabled');
        hide_compose();
        $('#sub-it').focus();
        return false;
    }

    return true;
}

function validate_huddle_message() {
    if (compose_recipient() === "") {
        compose_error("Please specify at least one recipient", $("#huddle_recipient"));
        return false;
    }

    if (compose_huddle_message() === "") {
        compose_error("You have nothing to send!", $("#new_message_content"));
        return false;
    }

    return true;
}

function validate_message() {
    submit_buttons().attr('disabled', 'disabled').blur();

    if (composing_huddle_message()) {
        return validate_huddle_message();
    } else {
        return validate_stream_message();
    }
}
