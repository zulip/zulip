/*jslint browser: true, devel: true, sloppy: true,
    plusplus: true, nomen: true, regexp: true */
/*global $: false, jQuery: false, ich: false,
    zephyr_json: false, initial_pointer: false, email: false,
    class_list: false, instance_list: false, people_list: false */

function register_huddle_onclick(zephyr_row, sender) {
    zephyr_row.find(".zephyr_sender").click(function (e) {
        prepare_huddle(sender);
        // The sender span is inside the messagebox, which also has an
        // onclick handler. We don't want to trigger the messagebox
        // handler.
        e.stopPropagation();
    });
}

var zephyr_dict = {};

$(function () {
    $('#zephyr-type-tabs a[href="#class-message"]').on('shown', function (e) {
        $('#class-message input:not(:hidden):first').focus().select();
    });
    $('#zephyr-type-tabs a[href="#personal-message"]').on('shown', function (e) {
        $('#personal-message input:not(:hidden):first').focus().select();
    });

    // Prepare the click handler for subbing to a new class to which
    // you have composed a zephyr.
    $('#create-it').click(function () {
        sub(compose_class_name());
        $("#class-message form").ajaxSubmit();
        $('#class-dne').stop(true).fadeOut(500);
    });

    // Prepare the click handler for subbing to an existing class.
    $('#sub-it').click(function () {
        sub(compose_class_name());
        $("#class-message form").ajaxSubmit();
        $('#class-nosub').stop(true).fadeOut(500);
    });

    $('#sidebar a[href="#subscriptions"]').click(function () {
        $.ajax({
            type:     'GET',
            url:      'json/subscriptions/',
            dataType: 'json',
            timeout:  10*1000,
            success: function (data) {
                $('#subscriptions_table tr').remove();
                if (data) {
                    $.each(data.subscriptions, function (index, name) {
                        $('#subscriptions_table').append(ich.subscription({subscription: name}));
                    });
                }
                $('#new_subscriptions').focus().select();
            },
            // TODO: error handling
        });
    });
});

$.ajaxSetup({
    beforeSend: function (xhr, settings) {
        function getCookie(name) {
            var i, cookies, cookieValue = null;
            if (document.cookie && document.cookie !== '') {
                cookies = document.cookie.split(';');
                for (i = 0; i < cookies.length; i++) {
                    var cookie = jQuery.trim(cookies[i]);
                    // Does this cookie string begin with the name we want?
                    if (cookie.substring(0, name.length + 1) === (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        }
        if (!(/^http:.*/.test(settings.url) || /^https:.*/.test(settings.url))) {
            // Only send the token to relative URLs i.e. locally.
            xhr.setRequestHeader("X-CSRFToken", getCookie('csrftoken'));
        }
    }
});

function sub(zephyr_class) {
    // TODO: check the return value and handle an error condition
    $.post('/subscriptions/add', {new_subscription: zephyr_class});
}

function compose_button() {
    $('#sidebar a[href="#home"]').tab('show');
    show_compose('class', $("#class"));
}

function hide_compose() {
    $('input, textarea, button').blur();
    $('.zephyr_compose').slideUp('fast');
}

function show_compose(tabname, focus_area) {
    $('.zephyr_compose').slideDown('fast');
    $('#zephyr-type-tabs a[href="#' + tabname + '-message"]').tab('show');
    focus_area.focus();
    focus_area.select();
}

function compose_class_name() {
    return $.trim($("#class").val());
}

$(function () {
    var status_classes = 'alert-error alert-success alert-info';
    var send_status = $('#send-status');
    var buttons = $('#class-message, #personal-message').find('input[type="submit"]');

    var options = {
        dataType: 'json', // This seems to be ignored. We still get back an xhr.
        beforeSubmit: function (form, _options) {
            send_status.removeClass(status_classes)
                       .addClass('alert-info')
                       .text('Sending')
                       .stop(true).fadeTo(0,1);
            buttons.attr('disabled', 'disabled');
            buttons.blur();

            if ($("#class-message:visible")[0] === undefined) {// we're not dealing with classes
                return true;
            }

            var zephyr_class = compose_class_name();
            if (zephyr_class === "") {
                // You can't try to send to an empty class.
                send_status.removeClass(status_classes)
                           .addClass('alert-error')
                           .text('Please specify a class')
                           .stop(true).fadeTo(0,1);
                buttons.removeAttr('disabled');
                $('#class-message input:not(:hidden):first').focus().select();
                return false;
            }

            var okay = true;
            $.ajax({
                url: "subscriptions/exists/" + zephyr_class,
                async: false,
                success: function (data) {
                    if (data === "False") {
                        // The class doesn't exist
                        okay = false;
                        send_status.removeClass(status_classes);
                        send_status.toggle();
                        $('#class-dne-name').text(zephyr_class);
                        $('#class-dne').show();
                        $('#create-it').focus();
                        buttons.removeAttr('disabled');
                        hide_compose();
                    }
                }
            });
            if (okay && class_list.indexOf(zephyr_class) === -1) {
                // You're not subbed to the class
                okay = false;
                send_status.removeClass(status_classes);
                send_status.toggle();
                $('#class-nosub-name').text(zephyr_class);
                $('#class-nosub').show();
                $('#sub-it').focus();
                buttons.removeAttr('disabled');
                hide_compose();
            }
            return okay;
        },
        success: function (resp, statusText, xhr, form) {
            form.find('textarea').val('');
            send_status.removeClass(status_classes)
                       .addClass('alert-success')
                       .text('Sent message')
                       .stop(true).fadeTo(0,1).delay(250).fadeOut(250, hide_compose);
            buttons.removeAttr('disabled');
            clear_compose_box();
        },
        error: function (xhr) {
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

            buttons.removeAttr('disabled');
        }
    };

    send_status.hide();
    $("#class-message form").ajaxForm(options);
    $("#personal-message form").ajaxForm(options);
});

$(function () {
    var options = {
        dataType: 'json', // This seems to be ignored. We still get back an xhr.
        success: function (resp, statusText, xhr, form) {
            var name = $.parseJSON(xhr.responseText).data;
            $('#subscriptions_table').find('button[value=' + name + ']').parents('tr').remove();
        },
        // TODO: error handling
    };
    $("#current_subscriptions").ajaxForm(options);
});

$(function () {
    var options = {
        dataType: 'json', // This seems to be ignored. We still get back an xhr.
        success: function (resp, statusText, xhr, form) {
            $("#new_subscription").val("");
            var name = $.parseJSON(xhr.responseText).data;
            $('#subscriptions_table').prepend(ich.subscription({subscription: name}));
            class_list.push(name);
        },
        // TODO: error handling
    };
    $("#add_new_subscription").ajaxForm(options);
});

$(function () {
    var status_classes = 'alert-error alert-success alert-info';
    var settings_status = $('#settings-status');
    settings_status.hide();
    var options = {
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
        },
    };
    $("#current_settings form").ajaxForm(options);
});

var selected_zephyr_id = 0;  /* to be filled in on document.ready */
var selected_zephyr;  // = get_zephyr(selected_zephyr_id)
var last_received = -1;
var narrowed = false;
// For tracking where you were before you narrowed.
var persistent_zephyr_id = 0;

function get_all_zephyr_rows() {
    return $('tr.zephyr_row');
}

function get_next_visible(zephyr_row) {
    return zephyr_row.nextAll('tr.zephyr_row:visible:first');
}

function get_prev_visible(zephyr_row) {
    return zephyr_row.prevAll('tr.zephyr_row:visible:first');
}

function get_id(zephyr_row) {
    return zephyr_row.attr('zid');
}

function get_zephyr(zephyr_id) {
    return $('#' + (narrowed ? 'zfilt' : 'zhome') + zephyr_id);
}

function scroll_to_selected() {
    var main_div = $('#main_div');
    main_div.scrollTop(0);
    main_div.scrollTop(selected_zephyr.offset().top - main_div.height()/1.5);
}

function get_huddle_recipient(zephyr) {
    var recipient, i;

    recipient = zephyr.display_recipient[0].name;
    for (i = 1; i < zephyr.display_recipient.length; i++) {
        recipient += ', ' + zephyr.display_recipient[i].name;
    }
    return recipient;
}

function respond_to_zephyr() {
    var zephyr, recipient, recipients;
    zephyr = zephyr_dict[selected_zephyr_id];

    if (zephyr.type === 'class') {
        $('#zephyr-type-tabs a[href="#class-message"]').tab('show');
        $("#class").val(zephyr.display_recipient);
        $("#instance").val(zephyr.instance);
        show_compose('class', $("#new_zephyr"));
    } else if (zephyr.type === 'huddle') {
        $('#zephyr-type-tabs a[href="#personal-message"]').tab('show');
        prepare_huddle(zephyr.reply_to);
    } else if (zephyr.type === 'personal') {
        // Until we allow sending zephyrs based on multiple meaningful
        // representations of a user (name, username, email, etc.), just
        // deal with emails.
        recipient = zephyr.display_recipient;
        if (recipient === email) { // that is, we sent the original message
            recipient = zephyr.sender_email;
        }
        prepare_huddle(recipient);
    }


}

function select_zephyr_by_id(zephyr_id, scroll_to) {
    if (zephyr_id === selected_zephyr_id) {
        return;
    }
    select_zephyr(get_zephyr(zephyr_id), scroll_to);
}

function select_zephyr(next_zephyr, scroll_to) {
    var main_div = $("#main_div");

    /* If the zephyr exists but is hidden, try to find the next visible one. */
    if (next_zephyr.length !== 0 && next_zephyr.is(':hidden')) {
        next_zephyr = get_next_visible(next_zephyr);
    }

    /* Fall back to the first visible zephyr. */
    if (next_zephyr.length === 0) {
        next_zephyr = $('tr:not(:hidden):first');
    }
    if (next_zephyr.length === 0) {
        // There are no zephyrs!
        return false;
    }

    $('.selected_zephyr').removeClass('selected_zephyr');
    next_zephyr.addClass('selected_zephyr');

    var new_selected_id = get_id(next_zephyr);
    if (!narrowed && new_selected_id !== selected_zephyr_id) {
        // Narrowing is a temporary view on top of the home view and
        // doesn't permanently affect where you are.
        //
        // We also don't want to post if there's no effecive change.
        $.post("update", { pointer: new_selected_id });
    }
    selected_zephyr_id = new_selected_id;
    selected_zephyr = next_zephyr;

    if (scroll_to &&
        ((next_zephyr.offset().top < main_div.offset().top) ||
         (next_zephyr.offset().top + next_zephyr.height() >
             main_div.offset().top + main_div.height()))) {
        scroll_to_selected();
    }
}


/* We use 'visibility' rather than 'display' and jQuery's show() / hide(),
   because we want to reserve space for the email address.  This avoids
   things jumping around slightly when the email address is shown. */

function hide_email() {
    $('.zephyr_sender_email').addClass('invisible');
}

function show_email() {
    hide_email();
    selected_zephyr.find('.zephyr_sender_email').removeClass('invisible');
}


function process_hotkey(code) {
    var next_zephyr;

    switch (code) {
    case 40: // down arrow
    case 38: // up arrow
        if (code === 40) {
            next_zephyr = get_next_visible(selected_zephyr);
        } else {
            next_zephyr = get_prev_visible(selected_zephyr);
        }
        if (next_zephyr.length !== 0) {
            select_zephyr(next_zephyr, true);
        }
        if ((next_zephyr.length === 0) && (code === 40)) {
            // At the last zephyr, scroll to the bottom so we have
            // lots of nice whitespace for new zephyrs coming in.
            $("#main_div").scrollTop($("#main_div").prop("scrollHeight"));
        }
        return process_hotkey;

    case 27: // Esc: hide compose pane
        hide_compose();
        return process_hotkey;

    case 82: // 'r': respond to zephyr
        respond_to_zephyr();
        return process_key_in_input;

    case 71: // 'g': start of "go to" command
        return process_goto_hotkey;
    }

    return false;
}

function narrow_by_recipient(zephyr) {
    if (zephyr === undefined) {
        zephyr = zephyr_dict[selected_zephyr_id];
    }

    // called when the narrow-class keycode is typed
    if (zephyr.type === 'personal') {
        narrow_personals();
    } else if (zephyr.type === 'huddle') {
        narrow_huddle();
    } else if (zephyr.type === 'class') {
        narrow_class();
    }
}

function process_goto_hotkey(code) {
    var zephyr = zephyr_dict[selected_zephyr_id];
    switch (code) {
    case 67: // 'c': narrow by recipient
        narrow_by_recipient(zephyr);
        break;

    case 73: // 'i': narrow by instance
        if (zephyr.type === 'class') {
            narrow_instance();
        }
        break;

    case 80: // 'p': narrow to personals
        narrow_all_personals();
        break;

    case 65: // 'a': un-narrow
        show_all_messages();
        break;

    case 27: // Esc: hide compose pane
        hide_compose();
        break;
    }

    /* Always return to the initial hotkey mode, even
       with an unrecognized "go to" command. */
    return process_hotkey;
}

function process_key_in_input(code) {
    if (code === 27) {
        // User hit Escape key
        hide_compose();
        return process_hotkey;
    }
    return false;
}

/* The current handler function for keydown events.
   It should return a new handler, or 'false' to
   decline to handle the event. */
var keydown_handler = process_hotkey;

$(document).keydown(function (event) {
    var result = keydown_handler(event.keyCode);
    if (typeof result === 'function') {
        keydown_handler = result;
        event.preventDefault();
    }
});

// NB: This just binds to current elements, and won't bind to elements
// created after ready() is called.

$(function () {
    $('input, textarea, button').focus(function () {
        keydown_handler = process_key_in_input;
    });
    $('input, textarea, button').blur(function () {
        keydown_handler = process_hotkey;
    });
});

function home_view(element) {
    return true;
}

var current_view_predicate = home_view;
var current_view_original_message;

function prepare_huddle(recipients) {
    // Used for both personals and huddles.
    show_compose('personal', $("#new_personal_zephyr"));
    $("#recipient").val(recipients);

}

function do_narrow(description, original_message, filter_function) {
    // Your pointer isn't changed when narrowed.
    narrowed = true;
    persistent_zephyr_id = selected_zephyr_id;

    current_view_predicate = filter_function;
    current_view_original_message = original_message;


    // We want the zephyr on which the narrow happened to stay in the same place if possible.
    var old_top = $("#main_div").offset().top - selected_zephyr.offset().top;
    var parent;

    // Empty the filtered table right before we fill it again
    $("#zfilt").empty();
    $.each(initial_zephyr_array, function (dummy, zephyr) {
        if (filter_function(zephyr, original_message)) {
            // It matched the filter, push it on to the array.
            add_to_tables(zephyr, parent, 'zfilt');
            parent = zephyr;
        }
    });

    // Show the new set of messages.
    $("#zfilt").addClass("focused_table");

    $("#show_all_messages").removeAttr("disabled");
    $("#narrowbox").show();
    $("#main_div").addClass("narrowed_view");
    $("#currently_narrowed_to").html(description);
    $("#zhome").removeClass("focused_table");

    select_zephyr_by_id(selected_zephyr_id, true);
    scroll_to_selected();
}

function narrow_huddle() {
    var parent = zephyr_dict[selected_zephyr_id];

    var message = "Group chats with " + parent.reply_to;

    do_narrow(message, parent, function (other, original) {
        return other.reply_to === original.reply_to;
    });
}

function narrow_all_personals() {
    // Narrow to all personals
    var message = "All huddles with you";
    do_narrow(message, undefined, function (other, original) {
        return other.type === "personal" || other.type === "huddle";
    });
}

function narrow_personals() {
    // Narrow to personals with a specific user
    var zephyr_obj = zephyr_dict[selected_zephyr_id];
    var other_party;
    if (zephyr_obj.display_recipient === email) {
        other_party = zephyr_obj.sender_email;
    } else {
        other_party = zephyr_obj.display_recipient;
    }
    var message = "Huddles with " + other_party;

    do_narrow(message, zephyr_dict[selected_zephyr_id], function (other, original) {
        return (other.type === 'personal') &&
            (((other.display_recipient === original.display_recipient) && (other.sender_email === original.sender_email)) ||
             ((other.display_recipient === original.sender_email) && (other.sender_email === original.display_recipient)));
    });

}

function narrow_class() {
    var parent = zephyr_dict[selected_zephyr_id];
    var message = "<span class='zephyr_class'>" + parent.display_recipient + "</span>";
    do_narrow(message, parent, function (other, original) {
        return (other.type === 'class' &&
                original.recipient_id === other.recipient_id);
    });
}

function narrow_instance() {
    var parent = zephyr_dict[selected_zephyr_id];
    var message = "<span class='zephyr_class'>" + parent.display_recipient
        + "</span> | <span class='zephyr_instance'>" + parent.instance
        + "</span>";
    do_narrow(message, parent, function (other, original) {
        return (other.type === 'class' &&
                original.recipient_id === other.recipient_id &&
                original.instance === other.instance);
    });
}

function show_all_messages() {
    if (!narrowed) {
        return;
    }
    narrowed = false;

    current_view_predicate = home_view;
    current_view_original_message = undefined;

    $("#zfilt").removeClass('focused_table');
    $("#zhome").addClass('focused_table');
    $("#narrowbox").hide();
    $("#main_div").removeClass('narrowed_view');
    $("#show_all_messages").attr("disabled", "disabled");
    $("#currently_narrowed_to").html("");

    // Includes scrolling.
    select_zephyr_by_id(persistent_zephyr_id, true);

    scroll_to_selected();
}

function update_autocomplete() {
    class_list.sort();
    instance_list.sort();
    people_list.sort();

    // limit number of items so the list doesn't fall off the screen
    $( "#class" ).typeahead({
        source: class_list,
        items: 3,
    });
    $( "#instance" ).typeahead({
        source: instance_list,
        items: 2,
    });
    $( "#recipient" ).typeahead({
        source: people_list,
        items: 4,
    });
}

function add_to_tables(zephyr, parent, table_name) {
    var table = $('#' + table_name);

    if (parent !== undefined &&
            zephyr.type === parent.type && (
                (zephyr.is_huddle) && (parent.recipient_id === zephyr.recipient_id) ||
                (zephyr.is_personal) && (parent.reply_to === zephyr.reply_to) ||
                ((zephyr.is_class) && (parent.recipient_id === zephyr.recipient_id) &&
                        (parent.instance === zephyr.instance))
            )) {
        zephyr.include_recipient = false;
    } else {
        zephyr.include_recipient = true;
        if (parent !== undefined) {
            // add a space to the table, but not if we have no parent because
            // we don't want a bookend as the first element.
            table.append('<tr><td /><td /><td class="bookend" /></tr>');
        }
    }

    if (parent !== undefined && !zephyr.include_recipient && zephyr.sender_email === parent.sender_email) {
        zephyr.include_sender = false;

        table.find('tr:last-child td:last-child').addClass("collapsed_parent");
    } else {
        zephyr.include_sender = true;
    }

    zephyr.dom_id = table_name + zephyr.id;

    var new_tr = ich.zephyr(zephyr);
    table.append(new_tr);
    register_huddle_onclick(new_tr, zephyr.sender_email);
}


function add_message(index, zephyr) {
    last_received = Math.max(last_received, zephyr.id);

    if (zephyr.type === 'class') {
        zephyr.is_class = true;
        if ($.inArray(zephyr.display_recipient, class_list) === -1) {
            class_list.push(zephyr.display_recipient);
            update_autocomplete();
        }
        if ($.inArray(zephyr.instance, instance_list) === -1) {
            instance_list.push(zephyr.instance);
            update_autocomplete();
        }
    } else if (zephyr.type === "huddle") {
        zephyr.is_huddle = true;
        zephyr.reply_to = get_huddle_recipient(zephyr);
    } else {
        zephyr.is_personal = true;

        if (zephyr.display_recipient === email) { // that is, we sent the original message
            zephyr.reply_to = zephyr.sender_email;
        } else {
            zephyr.reply_to = zephyr.display_recipient;
        }

        if (zephyr.reply_to !== email &&
                $.inArray(zephyr.reply_to, people_list) === -1) {
            people_list.push(zephyr.reply_to);
            update_autocomplete();
        }
    }


    var time = new Date(zephyr.timestamp * 1000);
    var two_digits = function (x) { return ('0' + x).slice(-2); };
    zephyr.timestr = two_digits(time.getHours())
                   + ':' + two_digits(time.getMinutes());
    zephyr.full_date_str = time.toLocaleString();

    var parent = zephyr_dict[$('#zhome tr:last-child').attr('zid')];

    add_to_tables(zephyr, parent, 'zhome');

    // now lets see if the filter applies to the message
    var parent_filtered = zephyr_dict[$('#zfilt tr:last-child').attr('zid')];

    if (current_view_predicate(zephyr, current_view_original_message)) {
        add_to_tables(zephyr, parent_filtered, 'zfilt');
    }


    // save the zephyr object, with computed values for various is_*
    zephyr_dict[zephyr.id] = zephyr;
}

$(function () {
    $(initial_zephyr_array).each(add_message);
    select_zephyr_by_id(initial_pointer, true);
    get_updates_longpoll();
});

function clear_compose_box() {
    $("#zephyr_compose").find('input[type=text], textarea').val('');
}

var longpoll_failures = 0;
function get_updates_longpoll() {
    console.log(new Date() + ': longpoll started');
    $.ajax({
        type:     'POST',
        url:      'get_updates_longpoll',
        data:     { last_received: last_received },
        dataType: 'json',
        timeout:  10*60*1000, // 10 minutes in ms
        success: function (data) {
            console.log(new Date() + ': longpoll success');
            longpoll_failures = 0;
            $('#connection-error').hide();

            if (data && data.zephyrs) {
                $.each(data.zephyrs, function (dummy, zephyr) {
                    add_message(dummy, zephyr);
                    zephyr_dict[zephyr.id] = zephyr;
                    initial_zephyr_array.push(zephyr);
                });
            }
            setTimeout(get_updates_longpoll, 0);
        },
        error: function (xhr, error_type, exn) {
            if (error_type === 'timeout') {
                // Retry indefinitely on timeout.
                console.log(new Date() + ': longpoll timed out');
                longpoll_failures = 0;
                $('#connection-error').hide();
            } else {
                console.log(new Date() + ': longpoll failed with ' + error_type +
                            ' (' + longpoll_failures + ' failures)');
                longpoll_failures += 1;
            }

            if (longpoll_failures >= 5) {
                $('#connection-error').show();
            } else {
                $('#connection-error').hide();
            }

            var retry_sec = Math.min(90, Math.exp(longpoll_failures/2));
            console.log(new Date() + ': longpoll retrying in ' + retry_sec + ' seconds');
            setTimeout(get_updates_longpoll, retry_sec*1000);
        }
    });
}

$(function () {
    update_autocomplete();
    $('.button-slide').click(function () {
        show_compose('class', $("#class"));
    });
});
