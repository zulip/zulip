var message_array = [];
var message_dict = {};
var message_in_table = {zhome: {}, zfilt: {}};
var subject_dict = {};

var viewport = $(window);

var selected_message_id = -1;  /* to be filled in on document.ready */
var selected_message;  // = rows.get(selected_message_id)
var get_updates_params = {
    last: -1,
    pointer: -1,
    failures: 0,
    server_generation: -1, /* to be filled in on document.ready */
    reload_pending: 0
};

$(function () {
    composebox_typeahead.update_all_recipients(people_list);
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

function get_huddle_recipient(message, attr) {
    var recipient, i;
    var other_recipients = $.grep(message.display_recipient,
                                  function (element, index) {
                                      return element.email !== email;
                                  });
    if (other_recipients.length === 0) {
        // huddle with oneself
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
    if (reply_type === "personal" && message.type === "huddle") {
        // reply_to for huddle messages is the whole huddle, so for
        // personals replies we need to set the the huddle recipient
        // to just the sender
        pm_recipient = message.sender_email;
    }
    if (reply_type === 'personal'
        || message.type === 'personal'
        || message.type === 'huddle')
    {
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

var last_message_id_sent = -1;
var message_id_to_send = -1;
// We only send pointer updates every second to avoid hammering the
// server
function send_pointer_update() {
    if (message_id_to_send !== last_message_id_sent) {
        $.post("/json/update_pointer", {pointer: message_id_to_send});
        last_message_id_sent = message_id_to_send;
    }
    setTimeout(send_pointer_update, 1000);
}

$(function () {
    setTimeout(send_pointer_update, 1000);
});

function update_selected_message(message, opts) {
    opts = $.extend({}, {
        update_server: true,
        for_narrow: narrow.active()
    }, opts);

    var cls = opts.for_narrow ? 'narrowed_selected_message' : 'selected_message';
    $('.' + cls).removeClass(cls);
    message.addClass(cls);

    var new_selected_id = rows.id(message);
    if (opts.update_server && !narrow.active()
        && new_selected_id !== message_id_to_send)
    {
        // Narrowing is a temporary view on top of the home view and
        // doesn't permanently affect where you are.
        //
        // We also don't want to post if there's no effective change.
        message_id_to_send = new_selected_id;
    }
    selected_message_id = new_selected_id;
    selected_message = message;
}

function select_message(next_message, opts) {
    opts = $.extend({}, {then_scroll: false, update_server: true}, opts);

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
    case 'huddle':
        return a.recipient_id === b.recipient_id;
    case 'personal':
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
    // Rather than using time.toLocaleString(), which varies by
    // browser, just do our own hardcoded formatting.
    message.full_date_str = time.toDateString() + " " + time.toTimeString();
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
        last_message_id = rows.id(table.find('tr:last-child'));
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
        row.find('.message_content a').each(function (index, link) {
            link = $(link);
            link.attr('target',  '_blank')
                .attr('title',   link.attr('href'));
        });
        var id = row.attr('zid');
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
    get_updates_params.last = Math.max(get_updates_params.last, message.id);

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

    case 'huddle':
        message.is_huddle = true;
        message.reply_to = get_huddle_recipient(message, 'email');
        message.display_reply_to = get_huddle_recipient(message, 'full_name');

        involved_people = message.display_recipient;

        if (message.sender_email === email) {
            composebox_typeahead.update_your_recipients(involved_people);
        } else {
            composebox_typeahead.update_all_recipients(involved_people);
        }
        break;

    case 'personal':
        message.is_personal = true;

        involved_people = [message.display_recipient,
                           {'email': message.sender_email,
                            'full_name': message.sender_full_name}];

        if (message.sender_email === email) { // that is, we sent the original message
            message.reply_to = message.display_recipient.email;
            message.display_reply_to = message.display_recipient.full_name;
            composebox_typeahead.update_your_recipients(involved_people);
        } else {
            message.reply_to = message.sender_email;
            message.display_reply_to = message.sender_full_name;
            composebox_typeahead.update_all_recipients(involved_people);
        }

        break;
    }

    // Add new people involved in this message to the people list
    $.each(involved_people, function (idx, person) {
        // Do the hasOwnProperty() call via the prototype to avoid problems
        // with keys like "hasOwnProperty"
        if (! composebox_typeahead.known_to_typeahead(person)) {
            people_list.push(person);
            typeahead_helper.autocomplete_needs_update(true);
        }
    });

    message_dict[message.id] = message;
    return message;
}

function add_messages(messages, add_to_home) {
    var prepended = false;
    if (!messages)
        return;

    if (loading_spinner) {
        loading_spinner.stop();
        $('#loading_indicator').hide();
        loading_spinner = undefined;
    }
    messages = $.map(messages, add_message_metadata);

    if (add_to_home) {
        var top_messages_home = $.grep(messages, function (elem, idx) {
            return (elem.id < selected_message_id && ! message_in_table.zhome[elem.id]);
        });
        var bottom_messages_home = $.grep(messages, function (elem, idx) {
            return (elem.id > selected_message_id && ! message_in_table.zhome[elem.id]);
        });
        message_array = top_messages_home.concat(message_array).concat(bottom_messages_home);
        add_to_table(top_messages_home,    'zhome', function () { return true; }, "top",    true);
        add_to_table(bottom_messages_home, 'zhome', function () { return true; }, "bottom", true);
        if ((top_messages_home.length > 0) && !narrow.active()) {
            prepended = true;
        }
    }

    if (narrow.active()) {
        var top_messages_narrow = $.grep(messages, function (elem, idx) {
            return (elem.id < selected_message_id && ! message_in_table.zfilt[elem.id]);
        });
        var bottom_messages_narrow = $.grep(messages, function (elem, idx) {
            return (elem.id > selected_message_id && ! message_in_table.zfilt[elem.id]);
        });
        add_to_table(top_messages_narrow,    'zfilt', narrow.predicate(), "top",    narrow.allow_collapse());
        add_to_table(bottom_messages_narrow, 'zfilt', narrow.predicate(), "bottom", narrow.allow_collapse());
        if (top_messages_narrow.length > 0) {
            prepended = true;
        }
    }

    // If we received the initially selected message, select it on the client side,
    // but not if the user has already selected another one during load.
    if ((selected_message_id === -1) && (message_dict.hasOwnProperty(initial_pointer))) {
        select_message_by_id(initial_pointer,
                             {then_scroll: true, update_server: false});
    }

    if ((selected_message_id === -1) && ! have_initial_messages) {
        select_message_by_id(message_array[0].id,
                             {then_scroll: false, update_server: true});
    }

    // If we prepended messages, then we need to scroll back to the pointer.
    // This will mess with the user's scrollwheel use; possibly we should be
    // more clever here.  However (for now) we only prepend on page load,
    // so maybe it's okay.
    //
    // We also need to re-select the message by ID, because we might have
    // removed and re-added the row as part of prepend collapsing.
    if (prepended && (selected_message_id >= 0)) {
        select_message_by_id(selected_message_id,
                             {then_scroll: true, update_server: false});
    }

    if (typeahead_helper.autocomplete_needs_update()) {
        typeahead_helper.update_autocomplete();
    }
}

var get_updates_xhr;
var get_updates_timeout;
function get_updates(options) {
    var defaults = {dont_block: false};
    options = $.extend({}, defaults, options);

    get_updates_params.pointer = selected_message_id;
    get_updates_params.reload_pending = Number(reload.is_pending());
    get_updates_params.dont_block = options.dont_block;

    get_updates_xhr = $.ajax({
        type:     'POST',
        url:      '/json/get_updates',
        data:     get_updates_params,
        dataType: 'json',
        timeout:  55*1000, // 55 seconds in ms -- needs to be under a
                           // minute to deal with crappy home wireless
                           // routers that kill "inactive" http connections.
        success: function (data) {
            if (! data) {
                // The server occationally returns no data during a
                // restart.  Ignore those responses so the page keeps
                // working
                get_updates_timeout = setTimeout(get_updates, 0);
                return;
            }

            get_updates_params.failures = 0;
            $('#connection-error').hide();

            if (get_updates_params.server_generation === -1) {
                get_updates_params.server_generation = data.server_generation;
            } else if (data.server_generation !== get_updates_params.server_generation) {
                reload.initiate();
            }

            if (data.messages.length !== 0) {
                add_messages(data.messages, true);
                notifications.received_messages(data.messages);
            }

            if (data.zephyr_mirror_active === false) {
                $('#zephyr-mirror-error').show();
            } else {
                $('#zephyr-mirror-error').hide();
            }

            // Pointer sync is disabled for now
            // if (data.new_pointer !== undefined
            //     && data.new_pointer !== selected_message_id)
            // {
            //     select_message_by_id(data.new_pointer,
            //                          {then_scroll: true, update_server: false});
            // }

            // Pause for 25 milliseconds before restarting the request.
            // This gives the browser (especially, our frontend test browser)
            // time to perform other scheduled actions.
            get_updates_timeout = setTimeout(get_updates, 25);
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

function load_old_messages(anchor, num_before, num_after, cont, because_button) {
    var narrow_str;
    if (because_button === undefined) {
        because_button = false;
    }
    if (because_button && narrow.active()) {
        narrow_str = JSON.stringify(narrow.data());
    } else {
        narrow_str = JSON.stringify({});
    }

    $.ajax({
        type:     'POST',
        url:      '/json/get_old_messages',
        data:     {anchor: anchor, num_before: num_before, num_after: num_after,
                   narrow: narrow_str},
        dataType: 'json',
        success: function (data) {
            if (! data) {
                // The server occationally returns no data during a
                // restart.  Ignore those responses and try again
                setTimeout(function () {
                    load_old_messages(anchor, num_before, num_after, cont, because_button);
                }, 0);
                return;
            }

            $('#connection-error').hide();

            if (data.messages.length !== 0) {
                var add_to_home = !narrow.active() || !because_button;
                add_messages(data.messages, add_to_home);
            }

            if (cont !== undefined) {
                cont(data.messages);
            }
        },
        error: function (xhr, error_type, exn) {
            // We might want to be more clever here
            $('#connection-error').show();
            setTimeout(function () {
                load_old_messages(anchor, num_before, num_after, cont, because_button);
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
        load_old_messages(initial_pointer, 200, 200,
                          function (messages) {
                              // TODO: We can't tell after the initial load
                              // whether we need the "load more" button or not.
                              $('#load_more').show();
                              load_more(messages);
                          });
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

function load_more_messages() {
    var batch_size = 400;
    load_old_messages(message_array[0].id, batch_size, 0,
                      function (messages) {
                          if (messages.length !== batch_size + 1) {
                              $('#load_more').hide();
                          }
                      }, true);
}

var watchdog_time = $.now();
setInterval(function () {
    var new_time = $.now();
    if ((new_time - watchdog_time) > 20000) { // 20 seconds.
        // Our app's JS wasn't running (the machine was probably
        // asleep). Now that we're running again, immediately poll for
        // new updates.
        get_updates_params.failures = 0;
        restart_get_updates();
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

    update_selected_message(next_message, {update_server: true});
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
