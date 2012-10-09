var message_array = [];
var message_dict = {};
var instance_list = [];

$(function () {
    var i;
    var send_status = $('#send-status');
    var buttons = $('#compose').find('input[type="submit"]');

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
    $("#compose form").ajaxForm(options);

    // Populate class_list_hash with data handed over to client-side template.
    for (i = 0; i < class_list.length; i++) {
        class_list_hash[class_list[i].toLowerCase()] = true;
    }
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

function respond_to_zephyr(reply_type) {
    var zephyr, tabname;
    zephyr = message_dict[selected_zephyr_id];
    if (zephyr.type === "class") {
        $("#class").val(zephyr.display_recipient);
        $("#instance").val(zephyr.instance);
    } else {
        $("#class").val("");
        $("#instance").val("");
    }
    $("#huddle_recipient").val(zephyr.reply_to);
    if (reply_type === "personal" && zephyr.type === "huddle") {
        // reply_to for huddle messages is the whole huddle, so for
        // personals replies we need to set the the huddle recipient
        // to just the sender
        $("#huddle_recipient").val(zephyr.sender_email);
    }
    tabname = reply_type;
    if (tabname === undefined) {
        tabname = zephyr.type;
    }
    if (tabname === "huddle") {
        // Huddle messages use the personals compose box
        tabname = "personal";
    }
    show_compose(tabname, $("#new_message_content"));
}

// Called by mouseover etc.
function select_message_by_id(zephyr_id) {
    if (zephyr_id === selected_zephyr_id) {
        return;
    }
    select_message(get_zephyr_row(zephyr_id), false);
}

// Called on page load and when we [un]narrow.
// Forces a call to select_message even if the id has not changed,
// because the visible table might have.
function select_and_show_by_id(zephyr_id) {
    select_message(get_zephyr_row(zephyr_id), true);
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

function select_message(next_message, scroll_to) {
    var viewport = $(window);

    /* If the zephyr exists but is hidden, try to find the next visible one. */
    if (next_message.length !== 0 && next_message.is(':hidden')) {
        next_message = get_next_visible(next_message);
    }

    /* Fall back to the first visible zephyr. */
    if (next_message.length === 0) {
        next_message = $('tr:not(:hidden):first');
    }
    if (next_message.length === 0) {
        // There are no zephyrs!
        return false;
    }

    update_selected_zephyr(next_message);

    if (scroll_to) {
        recenter_view(next_message);
    }
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
            top_messages.push(message_dict[id]);
        });
        zephyrs = zephyrs.concat(top_messages);

        // Delete the leftover recipient label.
        table.find('.recipient_row:first').remove();
    } else {
        prev = message_dict[table.find('tr:last-child').attr('zid')];
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
        register_onclick(row, zephyr.id);

        row.find('.message_content a').each(function (index, link) {
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
        if ($.inArray(zephyr.instance, instance_list) === -1) {
            instance_list.push(zephyr.instance);
            autocomplete_needs_update = true;
        }
        zephyr.reply_to = zephyr.sender_email;
        break;

    case 'huddle':
        zephyr.is_huddle = true;
        zephyr.reply_to = get_huddle_recipient(zephyr);
        zephyr.display_reply_to = get_huddle_recipient_names(zephyr);
        break;

    case 'personal':
        zephyr.is_personal = true;

        if (zephyr.sender_email === email) { // that is, we sent the original message
            zephyr.reply_to = zephyr.display_recipient;
        } else {
            zephyr.reply_to = zephyr.sender_email;
        }
        zephyr.display_reply_to = zephyr.reply_to;

        if (zephyr.reply_to !== email &&
                $.inArray(zephyr.reply_to, people_list) === -1) {
            people_list.push(zephyr.reply_to);
            autocomplete_needs_update = true;
        }
        break;
    }

    message_dict[zephyr.id] = zephyr;
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
        message_array = data.messages.concat(message_array);
    } else {
        message_array = message_array.concat(data.messages);
    }

    if (narrowed)
        add_to_table(data.messages, 'zfilt', narrowed, data.where);

    // Even when narrowed, add messages to the home view so they exist when we un-narrow.
    add_to_table(data.messages, 'zhome', function () { return true; }, data.where);

    // If we received the initially selected message, select it on the client side,
    // but not if the user has already selected another one during load.
    if ((selected_zephyr_id === -1) && (message_dict.hasOwnProperty(initial_pointer))) {
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
    var next_message = get_zephyr_row(selected_zephyr_id);

    if (above_view_threshold(next_message) && (!at_top_of_viewport())) {
        while (above_view_threshold(next_message)) {
            candidate = get_next_visible(next_message);
            if (candidate.length === 0) {
                break;
            } else {
                next_message = candidate;
            }
        }
    } else if (below_view_threshold(next_message) && (!at_bottom_of_viewport())) {
        while (below_view_threshold(next_message)) {
            candidate = get_prev_visible(next_message);
            if (candidate.length === 0) {
                break;
            } else {
                next_message = candidate;
            }
        }
    }

    if (at_top_of_viewport() && (parseInt(get_id(next_message), 10) >
                                 parseInt(get_id(get_first_visible()), 10))) {
        // If we've scrolled to the top, keep inching the selected
        // zephyr up to the top instead of just the latest one that is
        // still on the screen.
        next_message = get_prev_visible(next_message);
    } else if (at_bottom_of_viewport() && (parseInt(get_id(next_message), 10) <
                                           parseInt(get_id(get_last_visible()), 10))) {
        // If we've scrolled to the bottom already, keep advancing the
        // pointer until we're at the last message (by analogue to the
        // above)
        next_message = get_next_visible(next_message);
    }
    update_selected_zephyr(next_message);
}
