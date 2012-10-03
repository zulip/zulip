/*jslint browser: true, devel: true, sloppy: true,
    plusplus: true, nomen: true, regexp: true,
    white: true, undef: true */
/*global $: false, jQuery: false, Handlebars: false,
    zephyr_json: false, initial_pointer: false, email: false,
    class_list: false, instance_list: false, people_list: false,
    have_initial_messages: false, narrowed: false,
    autocomplete_needs_update: true */

var zephyr_array = [];
var zephyr_dict = {};
var instance_list = [];
var status_classes = 'alert-error alert-success alert-info';

function validate_class_message() {
    if (compose_class_name() === "") {
        compose_error("Please specify a class", $("#class"));
        return false;
    } else if (compose_instance() === "") {
        compose_error("Please specify an instance", $("#instance"));
        return false;
    } else if (compose_message() === "") {
        compose_error("You have nothing to send!", $("#new_zephyr"));
        return false;
    }
    return true;
}

function validate_huddle_message() {
    if (compose_recipient() === "") {
        compose_error("Please specify at least one recipient", $("#recipient"));
        return false;
    } else if (compose_huddle_message() === "") {
        compose_error("You have nothing to send!", $("#new_personal_zephyr"));
        return false;
    }
    return true;
}

$(function () {
    var send_status = $('#send-status');
    var buttons = $('#class-message, #personal-message').find('input[type="submit"]');

    var options = {
        dataType: 'json', // This seems to be ignored. We still get back an xhr.
        beforeSubmit: function (form, _options) {
            send_status.hide();
            buttons.attr('disabled', 'disabled');
            buttons.blur();

            // If validation fails, the validate function will pop up
            // an error message.
            if (composing_huddle_message()) {
                if (!validate_huddle_message()) {
                    return false;
                }
                // We have nothing else to check.
                return true;
            }

            if (composing_class_message()) {
                if (!validate_class_message()) {
                    return false;
                }
            }

            var zephyr_class = compose_class_name();
            var okay = true;
            $.ajax({
                url: "subscriptions/exists/" + zephyr_class,
                async: false,
                success: function (data) {
                    if (data === "False") {
                        // The class doesn't exist
                        okay = false;
                        send_status.removeClass(status_classes);
                        send_status.show();
                        $('#class-dne-name').text(zephyr_class);
                        $('#class-dne').show();
                        $('#create-it').focus();
                        buttons.removeAttr('disabled');
                        hide_compose();
                    }
                    $("#home-error").hide();
                },
                error: function (xhr) {
                    okay = false;
                    report_error("Error checking subscription", xhr, $("#home-error"));
                    $("#class").focus();
                    buttons.removeAttr('disabled');
                }
            });
            if (okay && class_list.indexOf(zephyr_class.toLowerCase()) === -1) {
                // You're not subbed to the class
                okay = false;
                send_status.removeClass(status_classes);
                send_status.show();
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
            send_status.hide();
            hide_compose();
            buttons.removeAttr('disabled');
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
        },
    });
});

var selected_zephyr_id = -1;  /* to be filled in on document.ready */
var selected_zephyr;  // = get_zephyr_row(selected_zephyr_id)
var received = {
    first: -1,
    last:  -1,
    failures: 0,
};

// The "message groups", i.e. blocks of messages collapsed by recipient.
// Each message table has a list of lists.
var message_groups = {
    zhome: [],
    zfilt: []
};

// For tracking where you were before you narrowed.
var persistent_zephyr_id = 0;
var high_water_mark = 0;

function scroll_to_selected() {
    var main_div = $('#main_div');
    main_div.scrollTop(0);
    main_div.scrollTop(selected_zephyr.offset().top - main_div.height()/1.5);
}

function get_huddle_recipient(zephyr) {
    var recipient, i;

    recipient = zephyr.display_recipient[0].email;
    for (i = 1; i < zephyr.display_recipient.length; i++) {
        recipient += ', ' + zephyr.display_recipient[i].email;
    }
    return recipient;
}

function get_huddle_recipient_names(zephyr) {
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

    switch (zephyr.type) {
    case 'class':
        $('#zephyr-type-tabs a[href="#class-message"]').tab('show');
        $("#class").val(zephyr.display_recipient);
        $("#instance").val(zephyr.instance);
        show_compose('class', $("#new_zephyr"));
        break;

    case 'huddle':
        $('#zephyr-type-tabs a[href="#personal-message"]').tab('show');
        prepare_huddle(zephyr.reply_to);
        break;

    case 'personal':
        // Until we allow sending zephyrs based on multiple meaningful
        // representations of a user (name, username, email, etc.), just
        // deal with emails.
        recipient = zephyr.display_recipient;
        if (recipient === email) { // that is, we sent the original message
            recipient = zephyr.sender_email;
        }
        prepare_huddle(recipient);
        break;
    }
}

// Called by mouseover etc.
function select_zephyr_by_id(zephyr_id) {
    if (zephyr_id === selected_zephyr_id) {
        return;
    }
    select_zephyr(get_zephyr_row(zephyr_id), false);
}

// Called on page load and when we [un]narrow.
// Forces a call to select_zephyr even if the id has not changed,
// because the visible table might have.
function select_and_show_by_id(zephyr_id) {
    select_zephyr(get_zephyr_row(zephyr_id), true);
}

function update_selected_zephyr(zephyr) {
    $('.selected_zephyr').removeClass('selected_zephyr');
    zephyr.addClass('selected_zephyr');

    var new_selected_id = get_id(zephyr);
    if (!narrowed && new_selected_id !== selected_zephyr_id) {
        // Narrowing is a temporary view on top of the home view and
        // doesn't permanently affect where you are.
        //
        // We also don't want to post if there's no effective change.
        $.post("update", {pointer: new_selected_id});
    }
    selected_zephyr_id = new_selected_id;
    selected_zephyr = zephyr;

    if (parseInt(selected_zephyr_id, 10) > high_water_mark) {
        high_water_mark = parseInt(selected_zephyr_id, 10);
    }

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

    update_selected_zephyr(next_zephyr);

    if (scroll_to &&
        ((next_zephyr.offset().top < main_div.offset().top) ||
         (next_zephyr.offset().top + next_zephyr.height() >
             main_div.offset().top + main_div.height()))) {
        scroll_to_selected();
    }
}

function prepare_huddle(recipients) {
    // Used for both personals and huddles.
    show_compose('personal', $("#new_personal_zephyr"));
    $("#recipient").val(recipients);
}

function same_recipient(a, b) {
    if ((a === undefined) || (b === undefined))
        return false;
    if (a.type !== b.type)
        return false;

    switch (a.type) {
    case 'huddle':
        return a.recipient_id === b.recipient_id;
    case 'personal':
        return a.reply_to === b.reply_to;
    case 'class':
        return (a.recipient_id === b.recipient_id) &&
               (a.instance     === b.instance);
    }

    // should never get here
    return false;
}

function same_sender(a, b) {
    return ((a !== undefined) && (b !== undefined) &&
            (a.sender_email === b.sender_email));
}

function clear_table(table_name) {
    $('#' + table_name).empty();
    message_groups[table_name] = [];
}

function add_to_table(zephyrs, table_name, filter_function, where) {
    if (zephyrs.length === 0)
        return;

    var table = $('#' + table_name);
    var zephyrs_to_render = [];
    var ids_where_next_is_same_sender = [];
    var prev;

    var current_group = [];
    var new_message_groups = [];

    if (where === 'top') {
        // Assumption: We never get a 'top' update as the first update.

        // Delete the current top message group, and add it back in with these
        // messages, in order to collapse properly.
        //
        // This means we redraw the entire view on each update when narrowed by
        // instance, which could be a problem down the line.  For now we hope
        // that instance views will not be very big.

        var top_group = message_groups[table_name][0];
        var top_messages = [];
        $.each(top_group, function (index, id) {
            get_zephyr_row(id, table_name).remove();
            top_messages.push(zephyr_dict[id]);
        });
        zephyrs = zephyrs.concat(top_messages);

        // Delete the leftover recipient label.
        table.find('.recipient_row:first').remove();
    } else {
        prev = zephyr_dict[table.find('tr:last-child').attr('zid')];
    }

    $.each(zephyrs, function (index, zephyr) {
        if (! filter_function(zephyr))
            return;

        zephyr.content = linkify(zephyr.content, {
            callback: function (text, href) {
                    return href ? '<a href="' + href + '" target="_blank" title="' +
                    href + '" onclick="event.cancelBubble = true;"">' + text + '</a>' : text;
                }
            });

        zephyr.include_recipient = false;
        zephyr.include_bookend   = false;
        if (same_recipient(prev, zephyr)) {
            current_group.push(zephyr.id);
        } else {
            if (current_group.length > 0)
                new_message_groups.push(current_group);
            current_group = [zephyr.id];

            // Add a space to the table, but not for the first element.
            zephyr.include_recipient = true;
            zephyr.include_bookend   = (prev !== undefined);
        }

        zephyr.include_sender = true;
        if (same_sender(prev, zephyr) && !zephyr.include_recipient) {
            zephyr.include_sender = false;
            ids_where_next_is_same_sender.push(prev.id);
        }

        zephyr.dom_id = table_name + zephyr.id;

        zephyrs_to_render.push(zephyr);
        prev = zephyr;
    });

    if (current_group.length > 0)
        new_message_groups.push(current_group);

    if (where === 'top') {
        message_groups[table_name] = new_message_groups.concat(message_groups[table_name]);
    } else {
        message_groups[table_name] = message_groups[table_name].concat(new_message_groups);
    }

    var rendered = templates.zephyr({
        zephyrs: zephyrs_to_render,
        include_layout_row: (table.find('tr:first').length == 0)
    });

    if (where === 'top') {
        table.find('.ztable_layout_row').after(rendered);
    } else {
        table.append(rendered);
    }

    $.each(zephyrs_to_render, function (index, zephyr) {
        var row = get_zephyr_row(zephyr.id);
        register_huddle_onclick(row, zephyr.sender_email);
        register_onclick(row, zephyr.id);
    });

    $.each(ids_where_next_is_same_sender, function (index, id) {
        get_zephyr_row(id).find('.messagebox').addClass("next_is_same_sender");
    });
}

function add_zephyr_metadata(dummy, zephyr) {
    if (received.first === -1)
        received.first = zephyr.id;
    else
        received.first = Math.min(received.first, zephyr.id);

    received.last = Math.max(received.last, zephyr.id);

    switch (zephyr.type) {
    case 'class':
        zephyr.is_class = true;
        if ($.inArray(zephyr.display_recipient.toLowerCase(), class_list) === -1) {
            class_list.push(zephyr.display_recipient.toLowerCase());
            autocomplete_needs_update = true;
        }
        if ($.inArray(zephyr.instance, instance_list) === -1) {
            instance_list.push(zephyr.instance);
            autocomplete_needs_update = true;
        }
        break;

    case 'huddle':
        zephyr.is_huddle = true;
        zephyr.reply_to = get_huddle_recipient(zephyr);
        zephyr.display_reply_to = get_huddle_recipient_names(zephyr);
        break;

    case 'personal':
        zephyr.is_personal = true;

        if (zephyr.display_recipient === email) { // that is, we sent the original message
            zephyr.reply_to = zephyr.sender_email;
        } else {
            zephyr.reply_to = zephyr.display_recipient;
        }
        zephyr.display_reply_to = zephyr.reply_to;

        if (zephyr.reply_to !== email &&
                $.inArray(zephyr.reply_to, people_list) === -1) {
            people_list.push(zephyr.reply_to);
            autocomplete_needs_update = true;
        }
        break;
    }

    var time = new Date(zephyr.timestamp * 1000);
    var two_digits = function (x) { return ('0' + x).slice(-2); };
    zephyr.timestr = two_digits(time.getHours())
                   + ':' + two_digits(time.getMinutes());
    zephyr.full_date_str = time.toLocaleString();

    zephyr_dict[zephyr.id] = zephyr;
}

function add_messages(data) {
    if (!data || !data.zephyrs)
        return;

    $.each(data.zephyrs, add_zephyr_metadata);

    if (loading_spinner) {
        loading_spinner.stop();
        $('#loading_indicator').hide();
        loading_spinner = undefined;
    }

    if (data.where === 'top') {
        zephyr_array = data.zephyrs.concat(zephyr_array);
    } else {
        zephyr_array = zephyr_array.concat(data.zephyrs);
    }

    if (narrowed)
        add_to_table(data.zephyrs, 'zfilt', narrowed, data.where);

    // Even when narrowed, add messages to the home view so they exist when we un-narrow.
    add_to_table(data.zephyrs, 'zhome', function () { return true; }, data.where);

    // If we received the initially selected message, select it on the client side,
    // but not if the user has already selected another one during load.
    if ((selected_zephyr_id === -1) && (initial_pointer in zephyr_dict)) {
        select_and_show_by_id(initial_pointer);
    }

    // If we prepended messages, then we need to scroll back to the pointer.
    // This will mess with the user's scrollwheel use; possibly we should be
    // more clever here.  However (for now) we only prepend on page load,
    // so maybe it's okay.
    //
    // We also need to re-select the message by ID, because we might have
    // removed and re-added the row as part of prepend collapsing.
    if ((data.where === 'top') && (selected_zephyr_id >= 0)) {
        select_and_show_by_id(selected_zephyr_id);
    }

    if (autocomplete_needs_update)
        update_autocomplete();
}

function get_updates() {
    console.log(new Date() + ': longpoll started');
    $.ajax({
        type:     'POST',
        url:      'get_updates',
        data:     received,
        dataType: 'json',
        timeout:  10*60*1000, // 10 minutes in ms
        success: function (data) {
            console.log(new Date() + ': longpoll success');
            received.failures = 0;
            $('#connection-error').hide();

            add_messages(data);
            setTimeout(get_updates, 0);
        },
        error: function (xhr, error_type, exn) {
            if (error_type === 'timeout') {
                // Retry indefinitely on timeout.
                console.log(new Date() + ': longpoll timed out');
                received.failures = 0;
                $('#connection-error').hide();
            } else {
                console.log(new Date() + ': longpoll failed with ' + error_type +
                            ' (' + received.failures + ' failures)');
                received.failures += 1;
            }

            if (received.failures >= 5) {
                $('#connection-error').show();
            } else {
                $('#connection-error').hide();
            }

            var retry_sec = Math.min(90, Math.exp(received.failures/2));
            console.log(new Date() + ': longpoll retrying in ' + retry_sec + ' seconds');
            setTimeout(get_updates, retry_sec*1000);
        }
    });
}

$(get_updates);

function above_view(zephyr) {
    return zephyr.offset().top < $("#main_div").offset().top;
}

function below_view(zephyr) {
    var main_div = $("#main_div");
    return zephyr.offset().top + zephyr.height() > main_div.offset().top + main_div.height();
}

function keep_pointer_in_view() {
    var main_div = $("#main_div");
    var next_zephyr = get_zephyr_row(selected_zephyr_id);

    if (above_view(next_zephyr)) {
        while (above_view(next_zephyr)) {
            next_zephyr = get_next_visible(next_zephyr);
        }
    } else if (below_view(next_zephyr)) {
        while (below_view(next_zephyr)) {
            next_zephyr = get_prev_visible(next_zephyr);
        }
    }

    if ((main_div.scrollTop() === 0) && (next_zephyr.attr("zid") > get_first_visible().attr("zid"))) {
        // If we've scrolled to the top, keep inching the selected
        // zephyr up to the top instead of just the latest one that is
        // still on the screen.
        next_zephyr = get_prev_visible(next_zephyr);
    } else if ((main_div.scrollTop() + main_div.innerHeight() >= main_div[0].scrollHeight) &&
               (next_zephyr.attr("zid") < get_last_visible().attr("zid"))) {
        next_zephyr = get_next_visible(next_zephyr);
    }
    update_selected_zephyr(next_zephyr);
}
