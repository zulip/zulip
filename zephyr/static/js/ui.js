function register_huddle_onclick(zephyr_row, sender) {
    zephyr_row.find(".zephyr_sender").click(function (e) {
        select_zephyr_by_id(zephyr_row.attr('zid'));
        // populate the stream box
        respond_to_zephyr();
        // but we really want to be in huddle mode
        prepare_huddle(sender);
        // The sender span is inside the messagebox, which also has an
        // onclick handler. We don't want to trigger the messagebox
        // handler.
        e.stopPropagation();

        // switch to the replybox hotkey handler
        set_keydown_in_input(true);
    });
}

function register_onclick(zephyr_row, zephyr_id) {
    zephyr_row.find(".messagebox").click(function (e) {
        if (!(clicking && mouse_moved)) {
            // Was a click (not a click-and-drag).
            select_zephyr_by_id(zephyr_id);
            respond_to_zephyr();
        }
        mouse_moved = false;
        clicking = false;
    });
}

/* We use 'visibility' rather than 'display' and jQuery's show() / hide(),
   because we want to reserve space for the email address.  This avoids
   things jumping around slightly when the email address is shown. */

function hide_email() {
    $('.zephyr_sender_email').addClass('invisible');
}

function show_email(zephyr_id) {
    hide_email();
    get_zephyr_row(zephyr_id).find('.zephyr_sender_email').removeClass('invisible');
}

function report_error(response, xhr, status_box) {
    if (xhr.status.toString().charAt(0) === "4") {
        // Only display the error response for 4XX, where we've crafted
        // a nice response.
        response += ": " + $.parseJSON(xhr.responseText).msg;
    }

    status_box.removeClass(status_classes).addClass('alert-error')
              .text(response).stop(true).fadeTo(0, 1);
    status_box.show();
}

var clicking = false;
var mouse_moved = false;

function zephyr_mousedown() {
    mouse_moved = false;
    clicking = true;
}

function zephyr_mousemove() {
    if (clicking) {
        mouse_moved = true;
    }
}

var autocomplete_needs_update = false;

function update_autocomplete() {
    class_list.sort();
    instance_list.sort();
    people_list.sort();

    // limit number of items so the list doesn't fall off the screen
    $( "#class" ).typeahead({
        source: class_list,
        items: 3
    });
    $( "#instance" ).typeahead({
        source: instance_list,
        items: 2
    });
    $( "#recipient" ).typeahead({
        source: people_list,
        items: 4
    });

    autocomplete_needs_update = false;
}

$(function () {
    // NB: This just binds to current elements, and won't bind to elements
    // created after ready() is called.
    $('input, textarea, button').focus(function () {
        set_keydown_in_input(true);
    });
    $('input, textarea, button').blur(function () {
        set_keydown_in_input(false);
    });

    $('#zephyr-type-tabs a[href="#class-message"]').on('shown', function (e) {
        $('#class-message input:not(:hidden):first').focus().select();
    });
    $('#zephyr-type-tabs a[href="#personal-message"]').on('shown', function (e) {
        $('#personal-message input:not(:hidden):first').focus().select();
    });

    // Prepare the click handler for subbing to a new class to which
    // you have composed a zephyr.
    $('#create-it').click(function () {
        sub_from_home(compose_class_name(), $('#class-dne'));
    });

    // Prepare the click handler for subbing to an existing class.
    $('#sub-it').click(function () {
        sub_from_home(compose_class_name(), $('#class-nosub'));
    });

    var last_mousewheel_or_scroll = 0;
    function do_mousewheel_or_scroll () {
        var time = $.now();
        if (time - last_mousewheel_or_scroll > 50) {
            keep_pointer_in_view();
            last_mousewheel_or_scroll = time;
        }
    }
    $(window).mousewheel(do_mousewheel_or_scroll);
    $(window).scroll(do_mousewheel_or_scroll);

    $('.button-slide').click(function () {
        show_compose('class', $("#class"));
    });

    $('#sidebar a[href="#subscriptions"]').click(fetch_subs);

    var settings_status = $('#settings-status');
    settings_status.hide();

    $("#current_settings form").ajaxForm({
        dataType: 'json', // This seems to be ignored. We still get back an xhr.
        success: function (resp, statusText, xhr, form) {
            var message = "Updated settings!";
            var result = $.parseJSON(xhr.responseText);
            if ((result.full_name !== undefined) || (result.short_name !== undefined)) {
                message = "Updated settings!  You will need to reload the page for your changes to take effect.";
            }
            settings_status.removeClass(status_classes)
                .addClass('alert-success')
                .text(message).stop(true).fadeTo(0,1);
            // TODO: In theory we should auto-reload or something if
            // you changed the email address or other fields that show
            // up on all screens
        },
        error: function (xhr, error_type, xhn) {
            var response = "Error changing settings";
            if (xhr.status.toString().charAt(0) === "4") {
                // Only display the error response for 4XX, where we've crafted
                // a nice response.
                response += ": " + $.parseJSON(xhr.responseText).msg;
            }
            settings_status.removeClass(status_classes)
                .addClass('alert-error')
                .text(response).stop(true).fadeTo(0,1);
        }
    });
});
