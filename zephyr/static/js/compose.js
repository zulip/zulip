var status_classes = 'alert-error alert-success alert-info';

function show_compose(tabname, focus_area) {
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

function compose_button() {
    clear_compose_box();
    $('#sidebar a[href="#home"]').tab('show');
    show_compose('stream', $("#class"));
}

function toggle_compose() {
    if ($("#message-type-tabs li.active").find("a[href=#stream-message]").length !== 0) {
        // In class tab, switch to personals.
        show_compose('personal', $("#huddle_recipient"));
    } else {
        show_compose('stream', $("#class"));
    }
}

function composing_class_message() {
    return $("#stream-message").is(":visible");
}

function composing_huddle_message() {
    return $("#personal-message").is(":visible");
}

function compose_stream_name() {
    return $.trim($("#class").val());
}

function compose_instance() {
    return $.trim($("#instance").val());
}

function compose_message() {
    return $.trim($("#new_message_content").val());
}

function compose_recipient() {
    return $.trim($("#huddle_recipient").val());
}

function compose_huddle_message() {
    return $.trim($("#new_message_content").val());
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

// *Synchronously* check if a class exists.
// If not, displays an error and returns false.
function check_class_for_send(stream_name) {
    var okay = true;
    $.ajax({
        url: "subscriptions/exists/" + stream_name,
        async: false,
        success: function (data) {
            if (data === "False") {
                // The class doesn't exist
                okay = false;
                $('#send-status').removeClass(status_classes).show();
                $('#class-dne-name').text(stream_name);
                $('#class-dne').show();
                submit_buttons().removeAttr('disabled');
                hide_compose();
                $('#create-it').focus();
            }
            $("#home-error").hide();
        },
        error: function (xhr) {
            okay = false;
            report_error("Error checking subscription", xhr, $("#home-error"));
            $("#class").focus();
            submit_buttons().removeAttr('disabled');
        }
    });
    return okay;
}

function validate_class_message() {
    var stream_name = compose_stream_name();
    if (stream_name === "") {
        compose_error("Please specify a class", $("#class"));
        return false;
    }

    if (compose_instance() === "") {
        compose_error("Please specify an instance", $("#instance"));
        return false;
    }

    if (compose_message() === "") {
        compose_error("You have nothing to send!", $("#new_message_content"));
        return false;
    }

    if (!check_class_for_send(stream_name))
        return false;

    if (!subscribed_to(stream_name)) {
        // You're not subbed to the class
        $('#send-status').removeClass(status_classes).show();
        $('#class-nosub-name').text(stream_name);
        $('#class-nosub').show();
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
        return validate_class_message();
    }
}
