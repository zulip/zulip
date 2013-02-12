var message_array = [];
var message_dict = {};
var message_in_table = {zhome: {}, zfilt: {}};
var subject_dict = {};
var people_dict = {};

var viewport = $(window);

// For tracking where you are in the home view
var persistent_message_id = -1;

var selected_message_id = -1;  /* to be filled in on document.ready */
var selected_message = $();    /* = rows.get(selected_message_id)   */
var get_updates_params = {
    pointer: -1,
    server_generation: -1 /* to be filled in on document.ready */
};
var get_updates_failures = 0;

var load_more_enabled = true;
// If the browser hasn't scrolled away from the top of the page
// since the last time that we ran load_more_messages(), we do
// not load_more_messages().
var have_scrolled_away_from_top = true;

// The "message groups", i.e. blocks of messages collapsed by recipient.
// Each message table has a list of lists.
var message_groups = {
    zhome: [],
    zfilt: []
};

var disable_pointer_movement = false;

// Toggles re-centering the pointer in the window
// when Home is next clicked by the user
var recenter_pointer_on_display = false;
var suppress_scroll_pointer_update = false;

function add_person(person) {
    people_list.push(person);
    people_dict[person.email] = person;
}

$(function () {
    $.each(people_list, function (idx, person) {
        people_dict[person.email] = person;
    });
});

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
        // outerHeight(true): Include margin
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
    if (selected_message && (selected_message.length !== 0))
        recenter_view(selected_message);
}

function maybe_scroll_to_selected() {
    // If we have been previously instructed to re-center to the
    // selected message, then do so
    if (recenter_pointer_on_display) {
        scroll_to_selected();
        recenter_pointer_on_display = false;
    }
}

function get_private_message_recipient(message, attr) {
    var recipient, i;
    var other_recipients = $.grep(message.display_recipient,
                                  function (element, index) {
                                      return element.email !== email;
                                  });
    if (other_recipients.length === 0) {
        // private message with oneself
        return message.display_recipient[0][attr];
    }

    recipient = other_recipients[0][attr];
    for (i = 1; i < other_recipients.length; i++) {
        recipient += ', ' + other_recipients[i][attr];
    }
    return recipient;
}

function respond_to_message(reply_type) {
    var message, msg_type;
    message = message_dict[selected_message_id];

    var stream = '';
    var subject = '';
    if (message.type === "stream") {
        stream = message.display_recipient;
        subject = message.subject;
    }

    var pm_recipient = message.reply_to;
    if (reply_type === "personal" && message.type === "private") {
        // reply_to for private messages is everyone involved, so for
        // personals replies we need to set the the private message
        // recipient to just the sender
        pm_recipient = message.sender_email;
    }
    if (reply_type === 'personal' || message.type === 'private') {
        msg_type = 'private';
    } else {
        msg_type = message.type;
    }
    compose.start(msg_type, {'stream': stream, 'subject': subject,
                             'private_message_recipient': pm_recipient});
}

// Called by mouseover etc.
function select_message_by_id(message_id, opts) {
    return select_message(rows.get(message_id), opts);
}

var furthest_read = -1;
var server_furthest_read = -1;
// We only send pointer updates when the user has been idle for a
// short while to avoid hammering the server
function send_pointer_update() {
    if (furthest_read > server_furthest_read) {
        $.post("/json/update_pointer",
               {pointer: furthest_read},
               function () {
                   server_furthest_read = furthest_read;
               });
    }
}

$(function () {
    persistent_message_id = initial_pointer;
    furthest_read = initial_pointer;
    server_furthest_read = initial_pointer;
    $(document).idle({idle: 1000,
                      onIdle: send_pointer_update,
                      keepTracking: true});
});

function message_range(start, end) {
    // Returns messages from the global message_dict in the specified range, inclusive
    var result = [];
    var i;

    for (i = start; i <= end; i++) {
        if (message_dict[i] !== undefined) {
            result.push(message_dict[i]);
        }
    }

    return result;
}

var unread_filters = {'stream': {}, 'private': {}};
var total_unread_messages = 0;

// Record each message in the array 'messages' as either read or
// unread, depending on the value of the 'is_read' flag.
function process_unread_counts(messages, is_read) {
    $.each(messages, function (index, message) {
        if (message.id <= furthest_read && is_read !== true) {
            return;
        }

        if (message.sender_email === email) {
            return;
        }

        if (is_read === true &&
            !narrow.active() &&
            !narrow.in_home(message)) {
            return;
        }

        var hashkey;
        if (message.type === 'stream') {
            hashkey = message.display_recipient;
        } else {
            hashkey = message.display_reply_to;
        }
        if (unread_filters[message.type][hashkey] === undefined) {
            unread_filters[message.type][hashkey] = {};
        }
        if (is_read) {
            delete unread_filters[message.type][hashkey][message.id];
        } else {
            unread_filters[message.type][hashkey][message.id] = true;
        }
    });

    total_unread_messages = 0;

    $.each(unread_filters.stream, function(index, obj) {
        var count = Object.keys(obj).length;
        ui.set_count("stream", index, count);
        total_unread_messages += count;
    });

    var pm_count = 0;
    $.each(unread_filters["private"], function(index, obj) {
        pm_count += Object.keys(obj).length;
    });
    ui.set_count("global", "private", pm_count);
    total_unread_messages += pm_count;
}

function update_selected_message(message, opts) {
    var cls = 'selected_message';
    $('.' + cls).removeClass(cls);
    message.addClass(cls);

    var new_selected_id = rows.id(message);
    // Narrowing is a temporary view on top of the home view and
    // doesn't affect your pointer in the home view.
    // Similarly, lurk mode does not affect your pointer.
    process_unread_counts(message_range(furthest_read + 1, new_selected_id), true);
    if (! narrow.active() && lurk_stream === undefined) {
        persistent_message_id = new_selected_id;
        if (new_selected_id > furthest_read)
        {
            furthest_read = new_selected_id;
        }
    }

    selected_message_id = new_selected_id;
    selected_message = message;
}

function select_message(next_message, opts) {
    opts = $.extend({}, {then_scroll: false}, opts);

    /* If the message exists but is hidden, try to find the next visible one. */
    if (next_message.is(':hidden')) {
        next_message = rows.next_visible(next_message);
    }

    /* Fall back to the last visible message. */
    if (next_message.length === 0) {
        next_message = rows.last_visible();
        if (next_message.length === 0) {
            // There are no messages!
            return false;
        }
    }

    if (next_message.id !== selected_message_id) {
        update_selected_message(next_message, opts);
    }

    if (opts.then_scroll) {
        recenter_view(next_message);
    }

    return true;
}

function same_stream_and_subject(a, b) {
    // Streams and subjects are case-insensitive. Streams have
    // already been forced to the canonical case.
    return ((a.recipient_id === b.recipient_id) &&
            (a.subject.toLowerCase() === b.subject.toLowerCase()));
}

function same_recipient(a, b) {
    if ((a === undefined) || (b === undefined))
        return false;
    if (a.type !== b.type)
        return false;

    switch (a.type) {
    case 'private':
        return a.reply_to === b.reply_to;
    case 'stream':
        return same_stream_and_subject(a, b);
    }

    // should never get here
    return false;
}

function same_sender(a, b) {
    return ((a !== undefined) && (b !== undefined) &&
            (a.sender_email === b.sender_email));
}

function clear_table(table_name) {
    // We do not want to call .empty() because that also clears
    // jQuery data.  This does mean, however, that we need to be
    // mindful of memory leaks.
    rows.get_table(table_name).children().detach();
    message_groups[table_name] = [];
    message_in_table[table_name] = {};
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

    // NB: timestr is HTML, inserted into the document without escaping.
    if (include_date) {
        message.timestr = time.toString("MMM dd") + "&nbsp;&nbsp;" +
            time.toString("HH:mm");
    } else {
        message.timestr = time.toString("HH:mm");
    }

    // Convert to number of hours ahead/behind UTC.
    // The sign of getTimezoneOffset() is reversed wrt
    // the conventional meaning of UTC+n / UTC-n
    var tz_offset = -time.getTimezoneOffset() / 60;

    message.full_date_str = time.toLocaleDateString();
    message.full_time_str = time.toLocaleTimeString() +
        ' (UTC' + ((tz_offset < 0) ? '' : '+') + tz_offset + ')';
}

function add_to_table(messages, table_name, filter_function, where, allow_collapse) {
    if (messages.length === 0)
        return;

    var table = rows.get_table(table_name);
    var messages_to_render = [];
    var ids_where_next_is_same_sender = {};
    var prev;
    var last_message_id;

    var current_group = [];
    var new_message_groups = [];

    if (where === 'top' && narrow.allow_collapse() && message_groups[table_name].length > 0) {
        // Delete the current top message group, and add it back in with these
        // messages, in order to collapse properly.
        //
        // This means we redraw the entire view on each update when narrowed by
        // subject, which could be a problem down the line.  For now we hope
        // that subject views will not be very big.

        var top_group = message_groups[table_name][0];
        var top_messages = [];
        $.each(top_group, function (index, id) {
            rows.get(id, table_name).remove();
            top_messages.push(message_dict[id]);
        });
        messages = messages.concat(top_messages);

        // Delete the leftover recipient label.
        table.find('.recipient_row:first').remove();
    } else {
        last_message_id = rows.id(table.find('tr[zid]:last'));
        prev = message_dict[last_message_id];
    }

    $.each(messages, function (index, message) {
        if (! filter_function(message))
            return;

        message_in_table[table_name][message.id] = true;

        message.include_recipient = false;
        message.include_bookend   = false;
        if (same_recipient(prev, message) && allow_collapse) {
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
            ids_where_next_is_same_sender[prev.id] = true;
        }

        add_display_time(message, prev);

        message.dom_id = table_name + message.id;

        if (message.sender_email === email) {
            message.stamp = ui.get_gravatar_stamp();
        }

        if (message.is_stream) {
            message.background_color = subs.get_color(message.display_recipient);
            message.color_class = subs.get_color_class(message.background_color);
            message.invite_only = subs.get_invite_only(message.display_recipient);
        }

        messages_to_render.push(message);
        prev = message;
    });

    if (messages_to_render.length === 0) {
        return;
    }

    if (current_group.length > 0)
        new_message_groups.push(current_group);

    if (where === 'top') {
        message_groups[table_name] = new_message_groups.concat(message_groups[table_name]);
    } else {
        message_groups[table_name] = message_groups[table_name].concat(new_message_groups);
    }

    var rendered_elems = $(templates.message({
        messages: messages_to_render,
        include_layout_row: (table.find('tr:first').length === 0)
    }));

    $.each(rendered_elems, function (index, elem) {
        var row = $(elem);
        if (! row.hasClass('message_row')) {
            return;
        }
        var id = rows.id(row);
        if (ids_where_next_is_same_sender[id]) {
            row.find('.messagebox').addClass("next_is_same_sender");
        }
    });

    // The message that was last before this batch came in has to be
    // handled specially because we didn't just render it and
    // therefore have to lookup its associated element
    if (last_message_id !== undefined
        && ids_where_next_is_same_sender[last_message_id])
    {
        var row = rows.get(last_message_id, table_name);
        row.find('.messagebox').addClass("next_is_same_sender");
    }

    if (where === 'top' && table.find('.ztable_layout_row').length > 0) {
        // If we have a totally empty narrow, there may not
        // be a .ztable_layout_row.
        table.find('.ztable_layout_row').after(rendered_elems);
    } else {
        table.append(rendered_elems);

        // XXX: This is absolutely awful.  There is a firefox bug
        // where when table rows as DOM elements are appended (as
        // opposed to as a string) a border is sometimes added to the
        // row.  This border goes away if we add a dummy row to the
        // top of the table (it doesn't go away on any reflow,
        // though, as resizing the window doesn't make them go away).
        // So, we add an empty row and then garbage collect them
        // later when the user is idle.
        var dummy = $("<tr></tr>");
        table.find('.ztable_layout_row').after(dummy);
        $(document).idle({'idle': 1000*10,
                          'onIdle': function () {
                              dummy.remove();
                          }});
    }
}

function case_insensitive_find(term, array) {
    var lowered_term = term.toLowerCase();
    return $.grep(array, function (elt) {
        return elt.toLowerCase() === lowered_term;
    }).length !== 0;
}

function add_message_metadata(message, dummy) {
    if (message_dict[message.id]) {
        return message_dict[message.id];
    }
    get_updates_params.last = Math.max(get_updates_params.last || 0, message.id);

    var involved_people;

    switch (message.type) {
    case 'stream':
        message.is_stream = true;
        if (! subject_dict.hasOwnProperty(message.display_recipient)) {
            subject_dict[message.display_recipient] = [];
        }
        if (! case_insensitive_find(message.subject, subject_dict[message.display_recipient])) {
            subject_dict[message.display_recipient].push(message.subject);
            subject_dict[message.display_recipient].sort();
            // We don't need to update the autocomplete after this because
            // the subject box's source is a function
        }
        message.reply_to = message.sender_email;

        involved_people = [{'full_name': message.sender_full_name,
                            'email': message.sender_email}];
        break;

    case 'private':
        message.is_private = true;
        message.reply_to = get_private_message_recipient(message, 'email');
        message.display_reply_to = get_private_message_recipient(message, 'full_name');

        involved_people = message.display_recipient;

        if (message.sender_email === email) {
            typeahead_helper.update_your_recipients(involved_people);
        } else {
            typeahead_helper.update_all_recipients(involved_people);
        }
        break;
    }

    // Add new people involved in this message to the people list
    $.each(involved_people, function (idx, person) {
        // Do the hasOwnProperty() call via the prototype to avoid problems
        // with keys like "hasOwnProperty"
        if (!typeahead_helper.known_to_typeahead(person) && people_dict[person.email] === undefined) {
            add_person(person);
            typeahead_helper.autocomplete_needs_update(true);
        }
    });

    message_dict[message.id] = message;
    return message;
}

function add_messages_helper(messages, table, center_message_id,
                             predicate, allow_collapse, append_new_messages) {
    // center_message_id is guaranteed to be between the top and bottom
    var top_messages = $.grep(messages, function (elem, idx) {
        return (elem.id < center_message_id && ! message_in_table[table][elem.id]);
    });
    var bottom_messages = $.grep(messages, function (elem, idx) {
        return (elem.id >= center_message_id && ! message_in_table[table][elem.id]);
    });
    if (table === "zhome" && append_new_messages) {
        message_array = top_messages.concat(message_array).concat(bottom_messages);
    }
    add_to_table(top_messages,    table, predicate, "top",    allow_collapse);
    add_to_table(bottom_messages, table, predicate, "bottom", allow_collapse);
    return top_messages.length > 0;
}

function add_messages(messages, opts) {
    var prepended = false;
    if (!messages)
        return;

    opts = $.extend({}, {update_unread_counts: true}, opts);

    util.destroy_loading_indicator($('#page_loading_indicator'));
    util.destroy_first_run_message();
    messages = $.map(messages, add_message_metadata);

    if (opts.add_to_home) {
        if (add_messages_helper(messages, "zhome", persistent_message_id,
                                narrow.in_home, true, opts.append_new_messages)
            && !narrow.active()) {
            prepended = true;
        }

        if (opts.update_unread_counts) {
            process_unread_counts(messages, false);
        }
    }

    if (narrow.active()) {
        if (add_messages_helper(messages, "zfilt", selected_message_id,
                                narrow.predicate(), narrow.allow_collapse(), opts.append_new_messages)) {
            prepended = true;
        }
    }

    // If we received the initially selected message, select it on the client side,
    // but not if the user has already selected another one during load.
    if ((selected_message_id === -1) && (message_dict.hasOwnProperty(initial_pointer))) {
        select_message_by_id(initial_pointer, {then_scroll: true});
    }

    if ((selected_message_id === -1) && ! have_initial_messages) {
        select_message_by_id(message_array[0].id, {then_scroll: false});
    }

    // If we prepended messages, then we need to scroll back to the pointer.
    // This will mess with the user's scrollwheel use; possibly we should be
    // more clever here.  However (for now) we only prepend on page load,
    // so maybe it's okay.
    //
    // We also need to re-select the message by ID, because we might have
    // removed and re-added the row as part of prepend collapsing.
    if (prepended && (selected_message_id >= 0)) {
        select_message_by_id(selected_message_id, {then_scroll: true});
    }

    if (typeahead_helper.autocomplete_needs_update()) {
        typeahead_helper.update_autocomplete();
    }

    // If the new messages are off the screen, show a notification
    notifications_bar.update();
}

var get_updates_xhr;
var get_updates_timeout;
function get_updates(options) {
    var defaults = {dont_block: false};
    options = $.extend({}, defaults, options);

    get_updates_params.pointer = furthest_read;
    get_updates_params.dont_block = options.dont_block || get_updates_failures > 0;
    if (lurk_stream !== undefined)
        get_updates_params.stream_name = lurk_stream;
    if (reload.is_pending()) {
        // We only send a server_generation to the server if we're
        // interested in an immediate reply to tell us if we need to
        // reload.  Once we're already reloading, we need to not
        // submit the parameter, so that the server will process our
        // future requests in longpolling mode.
        delete get_updates_params.server_generation;
    }

    get_updates_xhr = $.ajax({
        type:     'POST',
        url:      '/json/get_updates',
        data:     get_updates_params,
        dataType: 'json',
        timeout:  poll_timeout,
        success: function (data) {
            if (! data) {
                // The server occationally returns no data during a
                // restart.  Ignore those responses so the page keeps
                // working
                get_updates_timeout = setTimeout(get_updates, 0);
                return;
            }

            get_updates_failures = 0;
            $('#connection-error').hide();

            if (get_updates_params.server_generation === -1) {
                get_updates_params.server_generation = data.server_generation;
            } else if (data.server_generation !== get_updates_params.server_generation) {
                reload.initiate();
            }

            if (data.messages.length !== 0) {
                add_messages(data.messages, {add_to_home: true, append_new_messages: true});
                notifications.received_messages(data.messages);
            }

            if (data.zephyr_mirror_active === false) {
                $('#zephyr-mirror-error').show();
            } else {
                $('#zephyr-mirror-error').hide();
            }

            if (data.new_pointer !== undefined
                && data.new_pointer > furthest_read)
            {
                furthest_read = data.new_pointer;
                server_furthest_read = data.new_pointer;
                select_message_by_id(data.new_pointer, {then_scroll: true});
            }

            get_updates_timeout = setTimeout(get_updates, 0);
        },
        error: function (xhr, error_type, exn) {
            // If we are old enough to have messages outside of the Tornado
            // cache, immediately reload.
            if ((xhr.status === 400) &&
                ($.parseJSON(xhr.responseText).msg.indexOf("too old") !== -1)) {
                reload.initiate({immediate: true});
            }

            if (error_type === 'timeout') {
                // Retry indefinitely on timeout.
                get_updates_failures = 0;
                $('#connection-error').hide();
            } else {
                get_updates_failures += 1;
            }

            if (get_updates_failures >= 5) {
                $('#connection-error').show();
            } else {
                $('#connection-error').hide();
            }

            var retry_sec = Math.min(90, Math.exp(get_updates_failures/2));
            get_updates_timeout = setTimeout(get_updates, retry_sec*1000);
        }
    });
}

function load_old_messages(anchor, num_before, num_after, cont, for_narrow,
                           cont_will_add_messages) {
    if (for_narrow === undefined) {
        for_narrow = false;
    }
    if (cont_will_add_messages === undefined) {
        cont_will_add_messages = false;
    }

    var data = {anchor: anchor, num_before: num_before, num_after: num_after};

    if (lurk_stream !== undefined)
        data.stream = lurk_stream;

    if (for_narrow && narrow.active())
        data.narrow = JSON.stringify(narrow.public_operators());

    function process_result(messages) {
        $('#connection-error').hide();

        if (messages.length !== 0 && !cont_will_add_messages) {
            add_messages(messages, {add_to_home: !for_narrow, append_new_messages: true});
        }

        if (cont !== undefined) {
            cont(messages);
        }
    }

    $.ajax({
        type:     'POST',
        url:      '/json/get_old_messages',
        data:     data,
        dataType: 'json',
        success: function (data) {
            if (! data) {
                // The server occationally returns no data during a
                // restart.  Ignore those responses and try again
                setTimeout(function () {
                    load_old_messages(anchor, num_before, num_after, cont, for_narrow,
                                      cont_will_add_messages);
                }, 0);
                return;
            }

            process_result(data.messages);
        },
        error: function (xhr, error_type, exn) {
            if (xhr.status === 400) {
                // Bad request: We probably specified a narrow operator
                // for a nonexistent stream or something.  We shouldn't
                // retry or display a connection error.
                //
                // FIXME: Warn the user when this has happened?
                process_result([]);
                return;
            }

            // We might want to be more clever here
            $('#connection-error').show();
            setTimeout(function () {
                load_old_messages(anchor, num_before, num_after, cont, for_narrow,
                                  cont_will_add_messages);
            }, 5000);
        }
    });
}

// get the initial message list
$(function () {
    function load_more(messages) {
        // catch the user up
        if (messages.length !== 1) {
            var latest_id = messages[messages.length-1].id;
            load_old_messages(latest_id, 0, 400, load_more);
            return;
        }
        // now start subscribing to updates
        get_updates();

        // backfill more messages after the user is idle
        var backfill_batch_size = 1000;
        $(document).idle({'idle': 1000*10,
                          'onIdle': function () {
                              var first_id = message_array[0].id;
                              load_old_messages(first_id, backfill_batch_size, 0);
                          }});
    }

    if (have_initial_messages) {
        load_old_messages(initial_pointer, 200, 200, load_more);
    } else {
        get_updates();
    }
});

function restart_get_updates(options) {
    if (get_updates_xhr !== undefined)
        get_updates_xhr.abort();

    if (get_updates_timeout !== undefined)
        clearTimeout(get_updates_timeout);

    get_updates(options);
}

function reset_load_more_status() {
    load_more_enabled = true;
    have_scrolled_away_from_top = true;
}

function load_more_messages() {
    var batch_size = 400;
    var table, oldest_message_id;
    if (!load_more_enabled) {
        return;
    }
    ui.show_loading_more_messages_indicator();
    load_more_enabled = false;
    table = narrow.active() ? "zfilt" : "zhome";
    oldest_message_id = rows.id(rows.get_table(table).find("tr[zid]:first"));
    if (isNaN(oldest_message_id)) {
        if (selected_message_id === -1) {
            // If we arrived on the page via a #narrow URL, selected_message_id
            // will still be -1, so use the initial_pointer as our anchor
            oldest_message_id = initial_pointer;
        } else {
            oldest_message_id = selected_message_id;
        }
    }
    load_old_messages(oldest_message_id, batch_size, 0,
                      function (messages) {
                          ui.hide_loading_more_messages_indicator();
                          if (messages.length === batch_size + 1) {
                              load_more_enabled = true;
                          }
                      }, narrow.active());
}

var watchdog_time = $.now();
setInterval(function () {
    var new_time = $.now();
    if ((new_time - watchdog_time) > 20000) { // 20 seconds.
        // Our app's JS wasn't running (the machine was probably
        // asleep). Now that we're running again, immediately poll for
        // new updates.
        get_updates_failures = 0;
        restart_get_updates({dont_block: true});
    }
    watchdog_time = new_time;
}, 5000);

function at_top_of_viewport() {
    return (viewport.scrollTop() === 0);
}

function at_bottom_of_viewport() {
    // outerHeight(true): Include margin
    return (viewport.scrollTop() + viewport.height() >= $("#main_div").outerHeight(true));
}

function keep_pointer_in_view() {
    var candidate;
    var next_message = selected_message;

    if (disable_pointer_movement) {
        return;
    }

    if (next_message.length === 0)
        return;

    function adjust(past_threshold, at_end, advance) {
        if (!past_threshold(next_message) || at_end())
            return false;  // try other side
        while (past_threshold(next_message)) {
            candidate = advance(next_message);
            if (candidate.length === 0)
                break;
            next_message = candidate;
        }
        return true;
    }

    if (! adjust(above_view_threshold, at_top_of_viewport, rows.next_visible))
        adjust(below_view_threshold, at_bottom_of_viewport, rows.prev_visible);

    update_selected_message(next_message);
}

// The idea here is when you've scrolled to the very
// bottom of the page, e.g., the scroll handler isn't
// going to fire anymore. But if I continue to use
// the scrollwheel, the selection should advance until
// I'm at the very top or the very bottom of the page.
function move_pointer_at_page_top_and_bottom(delta) {
    if (delta !== 0 && (at_top_of_viewport() || at_bottom_of_viewport())) {
        var next_message = selected_message;
        if (delta > 0) {
            // Scrolling up (want older messages)
            next_message = rows.prev_visible(next_message);
        } else {
            // We're scrolling down (we want more recent messages)
            next_message = rows.next_visible(next_message);
        }
        if (next_message.length !== 0) {
            update_selected_message(next_message);
        }
    }
}
