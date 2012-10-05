// We want to remember how far we were scrolled on each 'tab'.
// To do so, we need to save away the old position of the
// scrollbar when we switch to a new tab (and restore it
// when we switch back.)
var scroll_positions = {};

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
            set_keydown_in_input(true);
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
        items: 4,
        matcher: function (item) {
            // Assumes we are matching on email addresses, not
            // e.g. full names which would have spaces.
            var current_recipient = $(this.query.split(" ")).last()[0];
            // Case-insensitive (from Bootstrap's default matcher).
            return (item.toLowerCase().indexOf(current_recipient.toLowerCase()) !== -1);
        },
        updater: function (item) {
            var previous_recipients = this.query.split(" ");
            previous_recipients.pop();
            previous_recipients = previous_recipients.join(" ");
            if (previous_recipients.length !== 0) {
                previous_recipients += " ";
            }
            return previous_recipients + item;
        }

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
        $('#personal-message').hide();
        $('#class-message').show();
        $('#new_message_type').val('class');
    });
    $('#zephyr-type-tabs a[href="#personal-message"]').on('shown', function (e) {
        $('#personal-message').show();
        $('#class-message').hide();
        $('#new_message_type').val('personal');
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

    var throttled_scrollhandler = $.throttle(50, function() {
        if ($('#home').hasClass('active')) {
                keep_pointer_in_view();
        }
    });
    $(window).mousewheel(throttled_scrollhandler);
    $(window).scroll(throttled_scrollhandler);

    $('#sidebar a[data-toggle="pill"]').on('show', function (e) {
        // Save the position of our old tab away, before we switch
        var viewport = $(window);
        var old_tab = $(e.relatedTarget).attr('href');
        scroll_positions[old_tab] = viewport.scrollTop();
    });
    $('#sidebar a[data-toggle="pill"]').on('shown', function (e) {
        // Right after we show the new tab, restore its old scroll position
        var viewport = $(window);
        var target_tab = $(e.target).attr('href');
        if (scroll_positions.hasOwnProperty(target_tab)) {
            viewport.scrollTop(scroll_positions[target_tab]);
        } else {
            viewport.scrollTop(0);
        }
    });

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
