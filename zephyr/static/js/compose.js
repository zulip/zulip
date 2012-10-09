var status_classes = 'alert-error alert-success alert-info';

function show_compose(tabname, focus_area) {
    $('.zephyr_compose').slideDown(100);
    $('#zephyr-type-tabs a[href="#' + tabname + '-message"]').tab('show');
    focus_area.focus();
    focus_area.select();
}

function hide_compose() {
    $('input, textarea, button').blur();
    $('.zephyr_compose').slideUp(100);
}

function clear_compose_box() {
    $("#zephyr_compose").find('input[type=text], textarea').val('');
}

function compose_button() {
    clear_compose_box();
    $('#sidebar a[href="#home"]').tab('show');
    show_compose('class', $("#class"));
}

function toggle_compose() {
    if ($("#zephyr-type-tabs li.active").find("a[href=#class-message]").length !== 0) {
        // In class tab, switch to personals.
        show_compose('personal', $("#huddle_recipient"));
    } else {
        show_compose('class', $("#class"));
    }
}

function composing_class_message() {
    return $("#class-message").is(":visible");
}

function composing_huddle_message() {
    return $("#personal-message").is(":visible");
}

function compose_class_name() {
    return $.trim($("#class").val());
}

function compose_instance() {
    return $.trim($("#instance").val());
}

function compose_message() {
    return $.trim($("#new_zephyr").val());
}

function compose_recipient() {
    return $.trim($("#huddle_recipient").val());
}

function compose_huddle_message() {
    return $.trim($("#new_zephyr").val());
}

function compose_error(error_text, bad_input) {
    $('#send-status').removeClass(status_classes)
               .addClass('alert-error')
               .text(error_text)
               .stop(true).fadeTo(0, 1);
    $('#zephyr_compose').find('input[type="submit"]').removeAttr('disabled');
    bad_input.focus().select();
}

function submit_buttons() {
    return $('#zephyr_compose').find('input[type="submit"]');
}

// *Synchronously* check if a class exists.
// If not, displays an error and returns false.
function check_class_for_send(class_name) {
    var okay = true;
    $.ajax({
        url: "subscriptions/exists/" + class_name,
        async: false,
        success: function (data) {
            if (data === "False") {
                // The class doesn't exist
                okay = false;
                $('#send-status').removeClass(status_classes).show();
                $('#class-dne-name').text(class_name);
                $('#class-dne').show();
                $('#create-it').focus();
                submit_buttons().removeAttr('disabled');
                hide_compose();
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
    var class_name = compose_class_name();
    if (class_name === "") {
        compose_error("Please specify a class", $("#class"));
        return false;
    }

    if (compose_instance() === "") {
        compose_error("Please specify an instance", $("#instance"));
        return false;
    }

    if (compose_message() === "") {
        compose_error("You have nothing to send!", $("#new_zephyr"));
        return false;
    }

    if (!check_class_for_send(class_name))
        return false;

    if (class_list.indexOf(class_name.toLowerCase()) === -1) {
        // You're not subbed to the class
        $('#send-status').removeClass(status_classes).show();
        $('#class-nosub-name').text(class_name);
        $('#class-nosub').show();
        $('#sub-it').focus();
        submit_buttons().removeAttr('disabled');
        hide_compose();
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
        compose_error("You have nothing to send!", $("#new_zephyr"));
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
