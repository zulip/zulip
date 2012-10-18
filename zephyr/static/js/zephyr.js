var message_array = [];
var message_dict = {};
var subject_dict = {};
var people_hash = {};

var selected_message_class = 'selected_message';
var viewport = $(window);
var reloading_app = false;

var selected_message_id = -1;  /* to be filled in on document.ready */
var selected_message;  // = get_message_row(selected_message_id)
var get_updates_params = {
    first: -1,
    last:  -1,
    failures: 0,
    server_generation: -1, /* to be filled in on document.ready */
    reload_pending: false
};

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
            if (get_updates_params.reload_pending) {
                reload_app();
                return;
            }
        },
        error: function (xhr, error_type) {
            if (error_type !== 'timeout' && get_updates_params.reload_pending) {
                // The error might be due to the server changing
                reload_app_preserving_compose(true);
                return;
            }
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

    // Populate stream_list_hash with data handed over to client-side template.
    for (i = 0; i < stream_list.length; i++) {
        stream_list_hash[stream_list[i].toLowerCase()] = true;
    }

    $.each(people_list, function (idx, person) {
        people_hash[person.email] = 1;
    });
});

// The "message groups", i.e. blocks of messages collapsed by recipient.
// Each message table has a list of lists.
var message_groups = {
    zhome: [],
    zfilt: []
};

// Why do we look at the 'bottom' in above_view_threshold and the top
// in below_view_threshold as opposed to vice versa?  Mostly to handle
// the case of gigantic messages.  Imagine the case of a selected
// message that's so big that it takes up an two entire screens. The
// selector shouldn't move away from it until after the *bottom* of
// the message has gone too high up on the screen.  (Otherwise we'd
// move the pointer right after part of the first screenful.)
function above_view_threshold(message, useTop) {
    // Barnowl-style thresholds: the bottom of the pointer is never
    // above the 1/5 mark.
    // (if useTop = true, we look at the top of the pointer instead)
    var position = message.offset().top;
    if (!useTop) {
        position += message.outerHeight(true);
    }
    return position < viewport.scrollTop() + viewport.height() / 5;
}

function below_view_threshold(message) {
    // Barnowl-style thresholds: the top of the pointer is never below
    // the 2/3-mark.
    return message.offset().top > viewport.scrollTop() + viewport.height() * 2 / 3;
}

function recenter_view(message) {
    // Barnowl-style recentering: if the pointer is too high, center
    // in the middle of the screen. If the pointer is too low, center
    // on the 1/5-mark.

    // If this logic changes, above_view_threshold andd
    // below_view_threshold must also change.
    if (above_view_threshold(message, true)) {
        // We specifically say useTop=true here, because suppose you're using
        // the arrow keys to arrow up and you've moved up to a huge message.
        // The message is so big that the bottom part of makes it not
        // "above the view threshold". But since we're using the arrow keys
        // to get here, the reason we selected this message is because
        // we want to read it; so here we care about the top part.
        viewport.scrollTop(selected_message.offset().top - viewport.height() / 2);
    } else if (below_view_threshold(message)) {
        viewport.scrollTop(selected_message.offset().top - viewport.height() / 5);
    }
}

function scroll_to_selected() {
    recenter_view(selected_message);
}

function get_huddle_recipient(message) {
    var recipient, i;
    var other_recipients = $.grep(message.display_recipient,
                                  function (element, index) {
                                      return element.email !== email;
                                  });
    if (other_recipients.length === 0) {
        // huddle with oneself
        return message.display_recipient[0].email;
    }

    recipient = other_recipients[0].email;
    for (i = 1; i < other_recipients.length; i++) {
        recipient += ', ' + other_recipients[i].email;
    }
    return recipient;
}

function get_huddle_recipient_names(message) {
    var recipient, i;
    var other_recipients = $.grep(message.display_recipient,
                                  function (element, index) {
                                      return element.email !== email;
                                  });
    if (other_recipients.length === 0) {
        // huddle with oneself
        return message.display_recipient[0].full_name;
    }

    recipient = other_recipients[0].full_name;
    for (i = 1; i < other_recipients.length; i++) {
        recipient += ', ' + other_recipients[i].full_name;
    }
    return recipient;
}

function respond_to_message(reply_type) {
    var message, tabname;
    message = message_dict[selected_message_id];
    clear_compose_box();
    if (message.type === "stream") {
        $("#stream").val(message.display_recipient);
        $("#subject").val(message.subject);
    } else {
        $("#stream").val("");
        $("#subject").val("");
    }
    $("#huddle_recipient").val(message.reply_to);
    if (reply_type === "personal" && message.type === "huddle") {
        // reply_to for huddle messages is the whole huddle, so for
        // personals replies we need to set the the huddle recipient
        // to just the sender
        $("#huddle_recipient").val(message.sender_email);
    }
    tabname = reply_type;
    if (tabname === undefined) {
        tabname = message.type;
    }
    if (tabname === "huddle") {
        // Huddle messages use the personals compose box
        tabname = "personal";
    }
    show_compose(tabname, $("#new_message_content"));
}

// Called by mouseover etc.
function select_message_by_id(message_id) {
    if (message_id === selected_message_id) {
        return;
    }
    select_message(get_message_row(message_id), false);
}

// Called on page load and when we [un]narrow.
// Forces a call to select_message even if the id has not changed,
// because the visible table might have.
function select_and_show_by_id(message_id) {
    select_message(get_message_row(message_id), true);
}

function update_selected_message(message) {
    $('.' + selected_message_class).removeClass(selected_message_class);
    message.addClass(selected_message_class);

    var new_selected_id = get_id(message);
    if (!narrow.active() && new_selected_id !== selected_message_id) {
        // Narrowing is a temporary view on top of the home view and
        // doesn't permanently affect where you are.
        //
        // We also don't want to post if there's no effective change.
        $.post("json/update_pointer", {pointer: new_selected_id});
    }
    selected_message_id = new_selected_id;
    selected_message = message;
}

function select_message(next_message, scroll_to) {

    /* If the message exists but is hidden, try to find the next visible one. */
    if (next_message.length !== 0 && next_message.is(':hidden')) {
        next_message = get_next_visible(next_message);
    }

    /* Fall back to the first visible message. */
    if (next_message.length === 0) {
        next_message = $('tr:not(:hidden):first');
    }
    if (next_message.length === 0) {
        // There are no messages!
        return false;
    }

    update_selected_message(next_message);

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
    case 'stream':
        return (a.recipient_id === b.recipient_id) &&
               (a.subject     === b.subject);
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

function add_display_time(message, prev) {
    var two_digits = function (x) { return ('0' + x).slice(-2); };
    var time = new XDate(message.timestamp * 1000);
    var include_date = message.include_recipient;

    if (prev !== undefined) {
        var prev_time = new XDate(prev.timestamp * 1000);
        if (time.toDateString() !== prev_time.toDateString()) {
            include_date = true;
        }
    }

    if (include_date) {
        message.timestr = time.toString("MMM dd") + "&nbsp;&nbsp;" +
            time.toString("HH:mm");
    } else {
        message.timestr = time.toString("HH:mm");
    }
    message.full_date_str = time.toLocaleString();
}

function add_to_table(messages, table_name, filter_function, where) {
    if (messages.length === 0)
        return;

    var table = $('#' + table_name);
    var messages_to_render = [];
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
        // subject, which could be a problem down the line.  For now we hope
        // that subject views will not be very big.

        var top_group = message_groups[table_name][0];
        var top_messages = [];
        $.each(top_group, function (index, id) {
            get_message_row(id, table_name).remove();
            top_messages.push(message_dict[id]);
        });
        messages = messages.concat(top_messages);

        // Delete the leftover recipient label.
        table.find('.recipient_row:first').remove();
    } else {
        prev = message_dict[table.find('tr:last-child').attr('zid')];
    }

    $.each(messages, function (index, message) {
        if (! filter_function(message))
            return;

        message.include_recipient = false;
        message.include_bookend   = false;
        if (same_recipient(prev, message)) {
            current_group.push(message.id);
        } else {
            if (current_group.length > 0)
                new_message_groups.push(current_group);
            current_group = [message.id];

            // Add a space to the table, but not for the first element.
            message.include_recipient = true;
            message.include_bookend   = (prev !== undefined);
        }

        message.include_sender = true;
        if (!message.include_recipient &&
            same_sender(prev, message) &&
            (Math.abs(message.timestamp - prev.timestamp) < 60*10)) {
            message.include_sender = false;
            ids_where_next_is_same_sender.push(prev.id);
        }

        add_display_time(message, prev);

        message.dom_id = table_name + message.id;

        messages_to_render.push(message);
        prev = message;
    });

    if (current_group.length > 0)
        new_message_groups.push(current_group);

    if (where === 'top') {
        message_groups[table_name] = new_message_groups.concat(message_groups[table_name]);
    } else {
        message_groups[table_name] = message_groups[table_name].concat(new_message_groups);
    }

    var rendered = templates.message({
        messages: messages_to_render,
        include_layout_row: (table.find('tr:first').length === 0)
    });

    if (where === 'top') {
        table.find('.ztable_layout_row').after(rendered);
    } else {
        table.append(rendered);
    }

    $.each(messages_to_render, function (index, message) {
        var row = get_message_row(message.id, table_name);
        register_onclick(row, message.id);

        row.find('.message_content a').each(function (index, link) {
            link = $(link);
            link.attr('target',  '_blank')
                .attr('title',   link.attr('href'))
                .attr('onclick', 'event.cancelBubble = true;'); // would a closure work here?
        });
    });

    $.each(ids_where_next_is_same_sender, function (index, id) {
        get_message_row(id, table_name).find('.messagebox').addClass("next_is_same_sender");
    });
}

function add_message_metadata(dummy, message) {
    if (get_updates_params.first === -1) {
        get_updates_params.first = message.id;
    } else {
        get_updates_params.first = Math.min(get_updates_params.first, message.id);
    }

    get_updates_params.last = Math.max(get_updates_params.last, message.id);

    var involved_people;

    switch (message.type) {
    case 'stream':
        message.is_stream = true;
        if (! subject_dict.hasOwnProperty(message.display_recipient)) {
            subject_dict[message.display_recipient] = [];
        }
        if ($.inArray(message.subject, subject_dict[message.display_recipient]) === -1) {
            subject_dict[message.display_recipient].push(message.subject);
            subject_dict[message.display_recipient].sort();
            // We don't need to update the autocomplete after this because
            // the subject box's source is a function
        }
        message.reply_to = message.sender_email;

        involved_people = [{'full_name': message.sender_full_name,
                            'email': message.sender_email}];
        break;

    case 'huddle':
        message.is_huddle = true;
        message.reply_to = get_huddle_recipient(message);
        message.display_reply_to = get_huddle_recipient_names(message);

        involved_people = message.display_recipient;
        break;

    case 'personal':
        message.is_personal = true;

        if (message.sender_email === email) { // that is, we sent the original message
            message.reply_to = message.display_recipient.email;
            message.display_reply_to = message.display_recipient.full_name;
        } else {
            message.reply_to = message.sender_email;
            message.display_reply_to = message.sender_full_name;
        }

        involved_people = [message.display_recipient,
                           {'email': message.sender_email,
                            'full_name': message.sender_full_name}];

        break;
    }

    // Add new people involved in this message to the people list
    $.each(involved_people, function (idx, person) {
        // Do the hasOwnProperty() call via the prototype to avoid problems
        // with keys like "hasOwnProperty"
        if (! Object.prototype.hasOwnProperty.call(people_hash, person.email)) {
            people_hash[person.email] = 1;
            people_list.push(person);
            autocomplete_needs_update = true;
        }
    });

    message_dict[message.id] = message;
}

function add_messages(data) {
    if (!data || !data.messages)
        return;

    $.each(data.messages, add_message_metadata);

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

    if (narrow.active())
        add_to_table(data.messages, 'zfilt', narrow.predicate(), data.where);

    // Even when narrowed, add messages to the home view so they exist when we un-narrow.
    add_to_table(data.messages, 'zhome', function () { return true; }, data.where);

    // If we received the initially selected message, select it on the client side,
    // but not if the user has already selected another one during load.
    if ((selected_message_id === -1) && (message_dict.hasOwnProperty(initial_pointer))) {
        select_and_show_by_id(initial_pointer);
    }

    // If we prepended messages, then we need to scroll back to the pointer.
    // This will mess with the user's scrollwheel use; possibly we should be
    // more clever here.  However (for now) we only prepend on page load,
    // so maybe it's okay.
    //
    // We also need to re-select the message by ID, because we might have
    // removed and re-added the row as part of prepend collapsing.
    if ((data.where === 'top') && (selected_message_id >= 0)) {
        select_and_show_by_id(selected_message_id);
    }

    if (autocomplete_needs_update)
        update_autocomplete();
}

function do_reload_app() {
    // TODO: We need a better API for showing messages.
    report_message("The application has been updated; reloading!", $("#reloading-application"));
    reloading_app = true;
    window.location.reload(true);
}

function reload_app() {
    // If we can, reload the page immediately
    if (! composing_message()) {
        do_reload_app();
    }

    // If the user is composing a message, wait until he's done or
    // until a timeout expires
    setTimeout(function () { reload_app_preserving_compose(false); },
               1000 * 60 * 5); // 5 minutes
}

function reload_app_preserving_compose(send_after_reload) {
    var url = "#reload:send_after_reload=" + Number(send_after_reload);
    if (composing_stream_message()) {
        url += "+msg_type=stream";
        url += "+stream=" + encodeURIComponent(compose_stream_name());
        url += "+subject=" + encodeURIComponent(compose_subject());
    } else {
        url += "+msg_type=huddle";
        url += "+recipient=" + encodeURIComponent(compose_recipient());
    }
    url += "+msg="+ encodeURIComponent(compose_message());

    window.location.replace(url);
    do_reload_app();
}

// Check if we're doing a compose-preserving reload.  This must be
// done before the first call to get_updates
$(function () {
    var location = window.location.toString();
    window.location = '#';
    var fragment = location.substring(location.indexOf('#') + 1);
    if (fragment.search("reload:") !== 0) {
        return;
    }

    fragment = fragment.replace(/^reload:/, "");
    var keyvals = fragment.split("+");
    var vars = {};
    $.each(keyvals, function (idx, str) {
        var pair = str.split("=");
        vars[pair[0]] = decodeURIComponent(pair[1]);
    });

    var tab;
    var send_now = parseInt(vars.send_after_reload, 10);
    if (vars.msg_type === "stream") {
        if (! send_now) {
            show_compose("stream", $("#new_message_content"));
        }
        compose_stream_name(vars.stream);
        compose_subject(vars.subject);
    } else {
        if (! send_now) {
            show_compose("huddle", $("#new_message_content"));
        }
        show_compose("huddle", $("#new_message_content"));
        compose_recipient(vars.recipient);
    }
    compose_message(vars.msg);

    if (send_now) {
        $("#compose form").ajaxSubmit();
    }
});

var get_updates_xhr;
var get_updates_timeout;
function get_updates() {
    get_updates_xhr = $.ajax({
        type:     'POST',
        url:      '/json/get_updates',
        data:     get_updates_params,
        dataType: 'json',
        timeout:  10*60*1000, // 10 minutes in ms
        success: function (data) {
            get_updates_params.failures = 0;
            $('#connection-error').hide();

            if (get_updates_params.server_generation === -1) {
                get_updates_params.server_generation = data.server_generation;
            } else if (data.server_generation !== get_updates_params.server_generation) {
                get_updates_params.reload_pending = true;
                reload_app();
            }

            add_messages(data);
            get_updates_timeout = setTimeout(get_updates, 0);
        },
        error: function (xhr, error_type, exn) {
            if (error_type === 'timeout') {
                // Retry indefinitely on timeout.
                get_updates_params.failures = 0;
                $('#connection-error').hide();
            } else {
                get_updates_params.failures += 1;
            }

            if (get_updates_params.failures >= 5) {
                $('#connection-error').show();
            } else {
                $('#connection-error').hide();
            }

            var retry_sec = Math.min(90, Math.exp(get_updates_params.failures/2));
            get_updates_timeout = setTimeout(get_updates, retry_sec*1000);
        }
    });
}

$(get_updates);

var watchdog_time = $.now();
setInterval(function() {
    var new_time = $.now();
    if ((new_time - watchdog_time) > 20000) { // 20 seconds.
        // Our app's JS wasn't running (the machine was probably
        // asleep). Now that we're running again, immediately poll for
        // new updates.
        get_updates_xhr.abort();
        clearTimeout(get_updates_timeout);
        get_updates_params.failures = 0;
        get_updates();
    }
    watchdog_time = new_time;
}, 5000);

function at_top_of_viewport() {
    return (viewport.scrollTop() === 0);
}

function at_bottom_of_viewport() {
    return (viewport.scrollTop() + viewport.height() >= $("#main_div").outerHeight(true));
}

function keep_pointer_in_view() {
    var candidate;
    var next_message = get_message_row(selected_message_id);

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
    update_selected_message(next_message);
}

// The idea here is when you've scrolled to the very
// bottom of the page, e.g., the scroll handler isn't
// going to fire anymore. But if I continue to use
// the scrollwheel, the selection should advance until
// I'm at the very top or the very bottom of the page.
function move_pointer_at_page_top_and_bottom(delta) {
    if (delta !== 0 && (at_top_of_viewport() || at_bottom_of_viewport())) {
        var next_message = get_message_row(selected_message_id);
        if (delta > 0) {
            // Scrolling up (want older messages)
            next_message = get_prev_visible(next_message);
        } else {
            // We're scrolling down (we want more recent messages)
            next_message = get_next_visible(next_message);
        }
        if (next_message.length !== 0) {
            update_selected_message(next_message);
        }
    }
}
