var zephyr_array = [];
var zephyr_dict = {};
var instance_list = [];

$(function () {
    var send_status = $('#send-status');
    var buttons = $('#zephyr_compose').find('input[type="submit"]');

    var options = {
        dataType: 'json', // This seems to be ignored. We still get back an xhr.
        beforeSubmit: validate_message,
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
    $("#zephyr_compose form").ajaxForm(options);
});

var selected_zephyr_id = -1;  /* to be filled in on document.ready */
var selected_zephyr;  // = get_zephyr_row(selected_zephyr_id)
var received = {
    first: -1,
    last:  -1,
    failures: 0
};

// The "message groups", i.e. blocks of messages collapsed by recipient.
// Each message table has a list of lists.
var message_groups = {
    zhome: [],
    zfilt: []
};

function above_view_threshold(zephyr) {
    // Barnowl-style thresholds: the pointer is never above the
    // 1/5-mark.
    var viewport = $(window);
    return zephyr.offset().top < viewport.scrollTop() + viewport.height() / 5;
}

function below_view_threshold(zephyr) {
    // Barnowl-style thresholds: the pointer is never below the
    // 4/5-mark.
    var viewport = $(window);
    return zephyr.offset().top + zephyr.outerHeight(true) >
        viewport.scrollTop() + viewport.height() * 4 / 5;
}

function recenter_view(zephyr) {
    // Barnowl-style recentering: if the pointer is too high, center
    // in the middle of the screen. If the pointer is too low, center
    // on the 1/5-mark.

    // If this logic changes, above_view_threshold andd
    // below_view_threshold must also change.
    var viewport = $(window);
    if (above_view_threshold(zephyr)) {
        viewport.scrollTop(selected_zephyr.offset().top - viewport.height() / 2);
    } else if (below_view_threshold(zephyr)) {
        viewport.scrollTop(selected_zephyr.offset().top - viewport.height() / 5);
    }
}

function scroll_to_selected() {
    recenter_view(selected_zephyr);
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
        $("#huddle_recipient").val(zephyr.sender);
        break;

    case 'huddle':
        $('#zephyr-type-tabs a[href="#personal-message"]').tab('show');
        show_compose('personal', $("#new_zephyr"));
        $("#huddle_recipient").val(zephyr.reply_to);
        break;

    case 'personal':
        // Until we allow sending zephyrs based on multiple meaningful
        // representations of a user (name, username, email, etc.), just
        // deal with emails.
        recipient = zephyr.display_recipient;
        if (recipient === email) { // that is, we sent the original message
            recipient = zephyr.sender_email;
        }
        show_compose('personal', $("#new_zephyr"));
        $("#huddle_recipient").val(recipient);
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
}

function select_zephyr(next_zephyr, scroll_to) {
    var viewport = $(window);

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

    if (scroll_to) {
        recenter_view(next_zephyr);
    }
}

function prepare_huddle(recipients) {
    // Used for both personals and huddles.
    show_compose('personal', $("#new_zephyr"));
    $("#huddle_recipient").val(recipients);
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

function add_display_time(zephyr, prev) {
    var two_digits = function (x) { return ('0' + x).slice(-2); };
    var time = new XDate(zephyr.timestamp * 1000);
    var include_date = zephyr.include_recipient;

    if (prev !== undefined) {
        var prev_time = new XDate(prev.timestamp * 1000);
        if (time.toDateString() !== prev_time.toDateString()) {
            include_date = true;
        }
    }

    if (include_date) {
        zephyr.timestr = time.toString("MMM dd") + "&nbsp;&nbsp;" +
            time.toString("HH:mm");
    } else {
        zephyr.timestr = time.toString("HH:mm");
    }
    zephyr.full_date_str = time.toLocaleString();
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
        if (!zephyr.include_recipient &&
            same_sender(prev, zephyr) &&
            (Math.abs(zephyr.timestamp - prev.timestamp) < 60*10)) {
            zephyr.include_sender = false;
            ids_where_next_is_same_sender.push(prev.id);
        }

        add_display_time(zephyr, prev);

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
        include_layout_row: (table.find('tr:first').length === 0)
    });

    if (where === 'top') {
        table.find('.ztable_layout_row').after(rendered);
    } else {
        table.append(rendered);
    }

    $.each(zephyrs_to_render, function (index, zephyr) {
        var row = get_zephyr_row(zephyr.id, table_name);
        register_huddle_onclick(row, zephyr.sender_email);
        register_onclick(row, zephyr.id);

        row.find('.zephyr_content a').each(function (index, link) {
            link = $(link);
            link.attr('target',  '_blank')
                .attr('title',   link.attr('href'))
                .attr('onclick', 'event.cancelBubble = true;'); // would a closure work here?
        });
    });

    $.each(ids_where_next_is_same_sender, function (index, id) {
        get_zephyr_row(id, table_name).find('.messagebox').addClass("next_is_same_sender");
    });
}

function add_zephyr_metadata(dummy, zephyr) {
    if (received.first === -1) {
        received.first = zephyr.id;
    } else {
        received.first = Math.min(received.first, zephyr.id);
    }

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

    zephyr_dict[zephyr.id] = zephyr;
}

function add_messages(data) {
    if (!data || !data.messages)
        return;

    $.each(data.messages, add_zephyr_metadata);

    if (loading_spinner) {
        loading_spinner.stop();
        $('#loading_indicator').hide();
        loading_spinner = undefined;
    }

    if (data.where === 'top') {
        zephyr_array = data.messages.concat(zephyr_array);
    } else {
        zephyr_array = zephyr_array.concat(data.messages);
    }

    if (narrowed)
        add_to_table(data.messages, 'zfilt', narrowed, data.where);

    // Even when narrowed, add messages to the home view so they exist when we un-narrow.
    add_to_table(data.messages, 'zhome', function () { return true; }, data.where);

    // If we received the initially selected message, select it on the client side,
    // but not if the user has already selected another one during load.
    if ((selected_zephyr_id === -1) && (zephyr_dict.hasOwnProperty(initial_pointer))) {
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
    $.ajax({
        type:     'POST',
        url:      'get_updates',
        data:     received,
        dataType: 'json',
        timeout:  10*60*1000, // 10 minutes in ms
        success: function (data) {
            received.failures = 0;
            $('#connection-error').hide();

            add_messages(data);
            setTimeout(get_updates, 0);
        },
        error: function (xhr, error_type, exn) {
            if (error_type === 'timeout') {
                // Retry indefinitely on timeout.
                received.failures = 0;
                $('#connection-error').hide();
            } else {
                received.failures += 1;
            }

            if (received.failures >= 5) {
                $('#connection-error').show();
            } else {
                $('#connection-error').hide();
            }

            var retry_sec = Math.min(90, Math.exp(received.failures/2));
            setTimeout(get_updates, retry_sec*1000);
        }
    });
}

$(get_updates);

function at_top_of_viewport() {
    return ($(window).scrollTop() === 0);
}

function at_bottom_of_viewport() {
    var viewport = $(window);
    return (viewport.scrollTop() + viewport.height() >= $("#main_div").outerHeight(true));
}

function keep_pointer_in_view() {
    var candidate;
    var viewport = $(window);
    var next_zephyr = get_zephyr_row(selected_zephyr_id);

    if (above_view_threshold(next_zephyr) && (!at_top_of_viewport())) {
        while (above_view_threshold(next_zephyr)) {
            candidate = get_next_visible(next_zephyr);
            if (candidate.length === 0) {
                break;
            } else {
                next_zephyr = candidate;
            }
        }
    } else if (below_view_threshold(next_zephyr) && (!at_bottom_of_viewport())) {
        while (below_view_threshold(next_zephyr)) {
            candidate = get_prev_visible(next_zephyr);
            if (candidate.length === 0) {
                break;
            } else {
                next_zephyr = candidate;
            }
        }
    }

    if (at_top_of_viewport() && (parseInt(get_id(next_zephyr), 10) >
                                 parseInt(get_id(get_first_visible()), 10))) {
        // If we've scrolled to the top, keep inching the selected
        // zephyr up to the top instead of just the latest one that is
        // still on the screen.
        next_zephyr = get_prev_visible(next_zephyr);
    } else if (at_bottom_of_viewport() && (parseInt(get_id(next_zephyr), 10) <
                                           parseInt(get_id(get_last_visible()), 10))) {
        // If we've scrolled to the bottom already, keep advancing the
        // pointer until we're at the last message (by analogue to the
        // above)
        next_zephyr = get_next_visible(next_zephyr);
    }
    update_selected_zephyr(next_zephyr);
}
