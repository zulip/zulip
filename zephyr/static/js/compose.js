function compose_button() {
    clear_compose_box();
    $('#sidebar a[href="#home"]').tab('show');
    show_compose('class', $("#class"));
}

function hide_compose() {
    $('input, textarea, button').blur();
    $('.zephyr_compose').slideUp(100);
}

function show_compose(tabname, focus_area) {
    $('.zephyr_compose').slideDown(100);
    $('#zephyr-type-tabs a[href="#' + tabname + '-message"]').tab('show');
    focus_area.focus();
    focus_area.select();
}

function toggle_compose() {
    if ($("#zephyr-type-tabs li.active").find("a[href=#class-message]").length !== 0) {
        // In class tab, switch to personals.
        show_compose('personal', $("#recipient"));
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
    return $.trim($("#recipient").val());
}

function compose_huddle_message() {
    return $.trim($("#new_personal_zephyr").val());
}

function compose_error(error_text, bad_input) {
    $('#send-status').removeClass(status_classes)
               .addClass('alert-error')
               .text(error_text)
               .stop(true).fadeTo(0, 1);
    $('#class-message, #personal-message').find('input[type="submit"]').removeAttr('disabled');
    bad_input.focus().select();
}
