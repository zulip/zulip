/*jslint browser: true, devel: true, sloppy: true,
    plusplus: true, nomen: true, regexp: true */
/*global $: false, jQuery: false, ich: false,
    zephyr_json: false, initial_pointer: false, username: false,
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
            url:      'json/subscriptions',
            dataType: 'json',
            timeout:  10*1000,
            success: function (data) {
                $('#current_subscriptions_table tr').remove();
                if (data) {
                    $.each(data.subscriptions, function (index, name) {
                        $('#current_subscriptions_table').append(ich.subscription({subscription: name}));
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
    // Supports multiple classes, separate by commas.
    // TODO: check the return value and handle an error condition
    $.post('/subscriptions/add/', {new_subscriptions: zephyr_class});
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
            $.each($.parseJSON(xhr.responseText).data, function (index, name) {
                $('#current_subscriptions_table').find('input[value=' + name + ']').parents('tr').remove();
            });
        },
        // TODO: error handling
    };
    $("#current_subscriptions form").ajaxForm(options);
});

$(function () {
    var options = {
        dataType: 'json', // This seems to be ignored. We still get back an xhr.
        success: function (resp, statusText, xhr, form) {
            $("#new_subscriptions").val("");
            $.each($.parseJSON(xhr.responseText).data, function (index, name) {
                $('#current_subscriptions_table').append(ich.subscription({subscription: name}));
                class_list.push(name);
            });
        },
        // TODO: error handling
    };
    $("#add_new_subscriptions form").ajaxForm(options);
});

var selected_zephyr_id = 0;  /* to be filled in on document.ready */
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
    return $("table.focused_table [zid=" + zephyr_id + "]");
}

function scroll_to_selected() {
    var main_div = $('#main_div');
    main_div.scrollTop(0);
    main_div.scrollTop(get_zephyr(selected_zephyr_id).offset().top - main_div.height()/1.5);
}

function get_huddle_recipient(zephyr) {
    var recipient, i;

    recipient = '';
    for (i = 0; i < zephyr.display_recipient.length; i++) {
        recipient += zephyr.display_recipient[i].name + ', ';
    }
    return recipient;
}

function respond_to_zephyr() {
    var parent, zephyr;
    var recipient, recipients;
    parent = get_zephyr(selected_zephyr_id);
    zephyr = zephyr_dict[parent.attr('zid')];

    if (zephyr.type === 'class') {
        $('#zephyr-type-tabs a[href="#class-message"]').tab('show');
        $("#class").val(zephyr.display_recipient);
        $("#instance").val(zephyr.instance);
        show_compose('class', $("#new_zephyr"));
    } else if (zephyr.type === 'huddle') {
        $('#zephyr-type-tabs a[href="#personal-message"]').tab('show');
        recipient = get_huddle_recipient(zephyr);
        prepare_huddle(recipient);
    } else if (zephyr.type === 'personal') {
        // Until we allow sending zephyrs based on multiple meaningful
        // representations of a user (name, username, email, etc.), just
        // deal with usernames.
        recipient = zephyr.display_recipient;
        if (recipient === username) { // that is, we sent the original message
            recipient = zephyr.sender;
        }
        prepare_huddle(recipient);
    }


}

function update_pointer(zephyr) {
    $('.selected_zephyr').removeClass('selected_zephyr');
    zephyr.addClass('selected_zephyr');

    var new_selected = get_id(zephyr);
    if (!narrowed && new_selected !== selected_zephyr_id) {
        // Narrowing is a temporary view on top of the home view and
        // doesn't permanently affect where you are.
        //
        // We also don't want to post if there's no effecive change.
        $.post("update", { pointer: selected_zephyr_id });
    }
    selected_zephyr_id = new_selected;

}

function update_pointer_by_id(zephyr_id) {
    update_pointer(get_zephyr(zephyr_id));
}

function select_zephyr(zephyr_id) {
    var next_zephyr = get_zephyr(zephyr_id);
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

    update_pointer(next_zephyr);

    if ((next_zephyr.offset().top < main_div.offset().top) ||
            (next_zephyr.offset().top + next_zephyr.height() >
             main_div.offset().top + main_div.height())) {
        scroll_to_selected();
    }
}


/* We use 'visibility' rather than 'display' and jQuery's show() / hide(),
   because we want to reserve space for the email address.  This avoids
   things jumping around slightly when the email address is shown. */

function show_email(zephyr_id) {
    get_zephyr(zephyr_id).find('.zephyr_sender_email').removeClass('invisible');
}

function hide_email(zephyr_id) {
    get_zephyr(zephyr_id).find('.zephyr_sender_email').addClass('invisible');
}


function process_hotkey(code) {
    var next_zephyr;

    switch (code) {
    case 40: // down arrow
    case 38: // up arrow
        if (code === 40) {
            next_zephyr = get_next_visible(get_zephyr(selected_zephyr_id));
        } else {
            next_zephyr = get_prev_visible(get_zephyr(selected_zephyr_id));
        }
        if (next_zephyr.length !== 0) {
            select_zephyr(get_id(next_zephyr));
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

function process_goto_hotkey(code) {
    var zephyr = zephyr_dict[selected_zephyr_id];
    switch (code) {
    case 67: // 'c': narrow by recipient
        if (zephyr.type === 'personal') {
            narrow_personals();
        } else if (zephyr.type === 'huddle') {
            narrow_huddle();
        } else if (zephyr.type === 'class') {
            narrow_class();
        }
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
    var old_top = $("#main_div").offset().top - get_zephyr(selected_zephyr_id).offset().top;
    var parent;

    // Empty the filtered table right before we fill it again
    $("#filtered_table").empty();
    $.each(initial_zephyr_array, function (dummy, zephyr) {
        if (filter_function(zephyr, original_message)) {
            // It matched the filter, push it on to the array.
            add_to_tables(zephyr, parent, $("#filtered_table"));
            parent = zephyr;
        }
    });

    // Show the new set of messages.
    $("#filtered_table").addClass("focused_table");

    $("#show_all_messages").removeAttr("disabled");
    $("#narrowbox").show();
    $("#main_div").addClass("narrowed_view");
    $("#currently_narrowed_to").html(description);
    $("#table").removeClass("focused_table");

    select_zephyr(selected_zephyr_id);
    scroll_to_selected();
}

function narrow_huddle() {
    var parent = zephyr_dict[selected_zephyr_id];

    var message = "Group chats with " + get_huddle_recipient(parent);

    do_narrow(message, parent, function (other, original) {
        return get_huddle_recipient(other) === get_huddle_recipient(original);
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
    var target_zephyr = get_zephyr(selected_zephyr_id);
    var zephyr_obj = zephyr_dict[target_zephyr.attr('zid')];
    var other_party;
    if (zephyr_obj.display_recipient === username) {
        other_party = zephyr_obj.sender;
    } else {
        other_party = zephyr_obj.display_recipient;
    }
    var message = "Huddles with " + other_party;

    do_narrow(message, zephyr_dict[selected_zephyr_id], function (other, original) {
        return (other.type === 'personal') &&
            (((other.display_recipient === original.display_recipient) && (other.sender === original.sender)) ||
             ((other.display_recipient === original.sender) && (other.sender === original.display_recipient)));
    });

}

function narrow_class() {
    var parent = zephyr_dict[selected_zephyr_id];
    var message = "<span class='zephyr_class'>" + parent.display_recipient + "</span>";
    do_narrow(message, parent, function (other, original) {
        return (other.type === 'class' &&
                original.display_recipient === other.display_recipient);
    });
}

function narrow_instance() {
    var parent = zephyr_dict[selected_zephyr_id];
    var message = "<span class='zephyr_class'>" + parent.display_recipient
        + "</span> | <span class='zephyr_instance'>" + parent.instance
        + "</span>";
    do_narrow(message, parent, function (other, original) {
        return (other.type === 'class' &&
                original.display_recipient === other.display_recipient &&
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

    $("#filtered_table").removeClass('focused_table');
    $("#table").addClass('focused_table');
    $("#narrowbox").hide();
    $("#main_div").removeClass('narrowed_view');
    $("#show_all_messages").attr("disabled", "disabled");
    $("#currently_narrowed_to").html("");

    // Includes scrolling.
    select_zephyr(persistent_zephyr_id);

    scroll_to_selected();
}

function update_autocomplete() {
    class_list.sort();
    instance_list.sort();
    people_list.sort();

    $( "#class" ).autocomplete({
        source: class_list
    });
    $( "#instance" ).autocomplete({
        source: instance_list
    });
    $( "#recipient" ).autocomplete({
        source: people_list
    });
}

function add_to_tables(zephyr, parent, table) {
    if (parent !== undefined &&
            zephyr.type === parent.type && (
                (zephyr.is_huddle && parent.name === zephyr.name) ||
                (zephyr.is_personal && parent.display_recipient === zephyr.display_recipient) ||
                (zephyr.is_class && parent.display_recipient === zephyr.display_recipient &&
                        parent.instance === zephyr.instance)
            )) {
        zephyr.include_recipient = false;
    } else {
        zephyr.include_recipient = true;
        // add a space to the table
        table.append($('<tr />').append($('<td />')).append($('<td />')).append($('<td />').html('<br/>').addClass('bookend')));
    }

    if (parent !== undefined && !zephyr.include_recipient && zephyr.sender === parent.sender) {
        zephyr.include_sender = false;
        table.children('tr:last-child td:last-child').addClass("collapsed_parent");
    } else {
        zephyr.include_sender = true;
    }

    var new_tr = ich.zephyr(zephyr);
    table.append(new_tr);
    register_huddle_onclick(new_tr, zephyr.sender);
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
    } else {
        zephyr.is_personal = true;

        if (zephyr.display_recipient !== username &&
                $.inArray(zephyr.display_recipient, people_list) === -1) {
            people_list.push(zephyr.display_recipient);
            update_autocomplete();
        }
        if (zephyr.sender !== username &&
                $.inArray(zephyr.sender, people_list) === -1) {
            people_list.push(zephyr.sender);
            update_autocomplete();
        }
    }

    var time = new Date(zephyr.timestamp * 1000);
    var two_digits = function (x) { return ('0' + x).slice(-2); };
    zephyr.timestr = two_digits(time.getHours())
                   + ':' + two_digits(time.getMinutes());
    zephyr.full_date_str = time.toLocaleString();

    var parent = zephyr_dict[$('#table tr:last-child').attr('zid')];

    add_to_tables(zephyr, parent, $('#table'));

    // now lets see if the filter applies to the message
    var parent_filtered = zephyr_dict[$('#filtered_table tr:last-child').attr('zid')];

    if (current_view_predicate(zephyr, current_view_original_message)) {
        add_to_tables(zephyr, parent_filtered, $('#filtered_table'));
    }


    // save the zephyr object, with computed values for various is_*
    zephyr_dict[zephyr.id] = zephyr;
}

$(function () {
    $(initial_zephyr_array).each(add_message);
    select_zephyr(initial_pointer);
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
                    add_message(zephyr);
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
