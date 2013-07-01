// zephyr/lib/minify.py will look for this comment in order to tell when it's
// producing app.js:
//
// MINIFY-FILE-ID: zephyr.js

var all_msg_list = new MessageList();
var home_msg_list = new MessageList('zhome', new narrow.Filter([["in", "home"]]));
var narrowed_msg_list;
var current_msg_list = home_msg_list;
var subject_dict = {};
var people_dict = {};
var recent_subjects = {};

var queued_mark_as_read = [];
var queued_flag_timer;

var respond_to_cursor = false;
var respond_to_sent_message = false;

var get_updates_params = {
    pointer: -1
};
var get_updates_failures = 0;

var load_more_enabled = true;
// If the browser hasn't scrolled away from the top of the page
// since the last time that we ran load_more_messages(), we do
// not load_more_messages().
var have_scrolled_away_from_top = true;

// Toggles re-centering the pointer in the window
// when Home is next clicked by the user
var recenter_pointer_on_display = false;
var suppress_scroll_pointer_update = false;
// Includes both scroll and arrow events. Negative means scroll up,
// positive means scroll down.
var last_viewport_movement_direction = 1;

var furthest_read = -1;
var server_furthest_read = -1;
var pointer_update_in_flight = false;

var events_stored_during_tutorial = [];

function add_person(person) {
    page_params.people_list.push(person);
    people_dict[person.email] = person;
    person.pm_recipient_count = 0;
}

function remove_person(person) {
    var i;
    for (i = 0; i < page_params.people_list.length; i++) {
        if (page_params.people_list[i].email === person.email) {
            page_params.people_list.splice(i, 1);
            break;
        }
    }
    delete people_dict[person.email];
}

$(function () {
    $.each(page_params.people_list, function (idx, person) {
        people_dict[person.email] = person;
        person.pm_recipient_count = 0;
    });

    // The special account feedback@humbughq.com is used for in-app
    // feedback and should always show up as an autocomplete option.
    if (people_dict['feedback@humbughq.com'] === undefined){
        add_person({"email": "feedback@humbughq.com",
                    "full_name": "Humbug Feedback Bot"});
    }

    $.each(page_params.initial_presences, function (email, presence) {
        activity.set_user_status(email, presence, page_params.initial_servertime);
    });

});

function within_viewport(row_offset, row_height) {
    // Returns true if a message is fully within the effectively visible
    // part of the viewport.
    var message_top = row_offset.top;
    var message_bottom  = message_top + row_height;
    var info = viewport.message_viewport_info();
    var viewport_top = info.visible_top;
    var viewport_bottom = viewport_top + info.visible_height;
    return (message_top > viewport_top) && (message_bottom < viewport_bottom);
}

function keep_pointer_in_view() {
    // See recenter_view() for related logic to keep the pointer onscreen.
    // This function mostly comes into place for mouse scrollers, and it
    // keeps the pointer in view.  For people who purely scroll with the
    // mouse, the pointer is kind of meaningless to them, but keyboard
    // users will occasionally do big mouse scrolls, so this gives them
    // a pointer reasonably close to the middle of the screen.
    var candidate;
    var next_row = current_msg_list.selected_row();

    if (next_row.length === 0)
        return;

    var info = viewport.message_viewport_info();
    var top_threshold = info.visible_top + (1/10 * info.visible_height);
    var bottom_threshold = info.visible_top + (9/10 * info.visible_height);

    function above_view_threshold() {
        var bottom_offset = next_row.offset().top + next_row.outerHeight(true);
        return bottom_offset < top_threshold;
    }

    function below_view_threshold() {
        return next_row.offset().top > bottom_threshold;
    }

    function adjust(past_threshold, at_end, advance) {
        if (!past_threshold(next_row) || at_end())
            return false;  // try other side
        while (past_threshold(next_row)) {
            candidate = advance(next_row);
            if (candidate.length === 0)
                break;
            next_row = candidate;
        }
        return true;
    }

    if (! adjust(above_view_threshold, viewport.at_top, rows.next_visible))
        adjust(below_view_threshold, viewport.at_bottom, rows.prev_visible);

    current_msg_list.select_id(rows.id(next_row), {from_scroll: true});
}

function recenter_view(message, from_scroll) {
    // Barnowl-style recentering: if the pointer is too high, move it to
    // the 1/2 marks. If the pointer is too low, move it to the 1/7 mark.
    // See keep_pointer_in_view() for related logic to keep the pointer onscreen.

    var viewport_info = viewport.message_viewport_info();
    var top_threshold = viewport_info.visible_top;

    var bottom_threshold = viewport_info.visible_top + viewport_info.visible_height;

    var message_top = message.offset().top;
    var message_height = message.outerHeight(true);
    var message_bottom = message_top + message_height;

    var is_above = message_top < top_threshold;
    var is_below = message_bottom > bottom_threshold;

    if (from_scroll) {
        // If the message you're trying to center on is already in view AND
        // you're already trying to move in the direction of that message,
        // don't try to recenter. This avoids disorienting jumps when the
        // pointer has gotten itself outside the threshold (e.g. by
        // autoscrolling).
        if (is_above && last_viewport_movement_direction >= 0) {
            return;
        }
        if (is_below && last_viewport_movement_direction <= 0) {
            return;
        }
    }

    if (is_above) {
        viewport.set_message_position(message_top, message_height, viewport_info, 1/2);
    } else if (is_below) {
        viewport.set_message_position(message_top, message_height, viewport_info, 1/7);
    }
}

function scroll_to_selected() {
    var selected_row = current_msg_list.selected_row();
    if (selected_row && (selected_row.length !== 0))
        recenter_view(selected_row);
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
                                      return element.email !== page_params.email;
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

function respond_to_message(opts) {
    var message, msg_type;
    // Before initiating a reply to a message, if there's an
    // in-progress composition, snapshot it.
    compose.snapshot_message();

    message = current_msg_list.selected_message();

    if (message === undefined) {
        return;
    }

    var stream = '';
    var subject = '';
    if (message.type === "stream") {
        stream = message.stream;
        subject = message.subject;
    }

    var pm_recipient = message.reply_to;
    if (opts.reply_type === "personal" && message.type === "private") {
        // reply_to for private messages is everyone involved, so for
        // personals replies we need to set the the private message
        // recipient to just the sender
        pm_recipient = message.sender_email;
    }
    if (opts.reply_type === 'personal' || message.type === 'private') {
        msg_type = 'private';
    } else {
        msg_type = message.type;
    }
    compose.start(msg_type, {'stream': stream, 'subject': subject,
                             'private_message_recipient': pm_recipient,
                             'replying_to_message': message,
                             'trigger': opts.trigger});

}

// Returns messages from the given message list in the specified range, inclusive
function message_range(msg_list, start, end) {
    if (start === -1) {
        blueslip.error("message_range given a start of -1");
    }

    var all = msg_list.all();
    var compare = function (a, b) { return a.id < b; };

    var start_idx = util.lower_bound(all, start, compare);
    var end_idx   = util.lower_bound(all, end,   compare);
    return all.slice(start_idx, end_idx + 1);
}

function send_queued_flags() {
    if (queued_mark_as_read.length === 0) {
        return;
    }

    function on_success(data, status, jqXHR) {
        if (data ===  undefined || data.messages === undefined) return;

        queued_mark_as_read = $.grep(queued_mark_as_read, function (message, idx) {
            return data.messages.indexOf(message) === -1;
        });
    }

    $.ajax({
        type:     'POST',
        url:      '/json/update_message_flags',
        data:     {messages: JSON.stringify(queued_mark_as_read),
                   op:       'add',
                   flag:     'read'},
        dataType: 'json',
        success:  on_success});
}

function update_unread_counts() {
    // Pure computation:
    var res = unread.get_counts();

    // Side effects from here down:
    // This updates some DOM elements directly, so try to
    // avoid excessive calls to this.
    stream_list.update_dom_with_unread_counts(res);
    notifications.update_title_count(res.unread_in_current_view);
    notifications.update_pm_count(res.private_message_count);
    notifications_bar.update(res.unread_in_current_view);
}

function mark_all_as_read(cont) {
    $.each(all_msg_list.all(), function (idx, msg) {
        msg.flags = msg.flags || [];
        msg.flags.push('read');
    });
    unread.declare_bankruptcy();
    update_unread_counts();

    $.ajax({
        type:     'POST',
        url:      '/json/update_message_flags',
        data:     {messages: JSON.stringify([]),
                   all:      true,
                   op:       'add',
                   flag:     'read'},
        dataType: 'json',
        success:  cont});
}

function process_loaded_for_unread(messages) {
    unread.process_loaded_messages(messages);
    update_unread_counts();
}

// Takes a list of messages and marks them as read
function process_read_messages(messages) {
    var processed = [];
    $.each(messages, function (idx, message) {

        message.flags = message.flags || [];
        message.flags.push('read');
        processed.push(message.id);
        message.unread = false;
        unread.process_read_message(message);
        home_msg_list.show_message_as_read(message);
        all_msg_list.show_message_as_read(message);
        if (narrowed_msg_list) narrowed_msg_list.show_message_as_read(message);

    });

    if (processed.length > 0) {
        queued_mark_as_read = queued_mark_as_read.concat(processed);

        if (queued_flag_timer !== undefined) {
            clearTimeout(queued_flag_timer);
        }

        queued_flag_timer = setTimeout(send_queued_flags, 1000);
    }

    update_unread_counts();
}

// If we ever materially change the algorithm for this function, we
// may need to update notifications.received_messages as well.
function process_visible_unread_messages(update_cursor) {
    // For any messages visible on the screen, make sure they have been marked
    // as unread.
    if (! notifications.window_has_focus()) {
        return;
    }

    var selected = current_msg_list.selected_message();
    var vp = viewport.message_viewport_info();
    var top = vp.visible_top;
    var height = vp.visible_height;

    // Being simplistic about this, the smallest message is 30 px high.
    var selected_row = rows.get(current_msg_list.selected_id(), current_msg_list.table_name);
    var num_neighbors = Math.floor(height / 30);
    var candidates = $.merge(selected_row.prevAll("tr.message_row[zid]:lt(" + num_neighbors + ")"),
                             selected_row.nextAll("tr.message_row[zid]:lt(" + num_neighbors + ")"));

    var visible_messages = candidates.filter(function (idx, message) {
        var row = $(message);
        var row_offset = row.offset();
        var row_height = row.height();
        // Mark very tall messages as read once we've gotten past them
        return (row_height > height && row_offset.top > top) || within_viewport(row_offset, row_height);
    });

    if (update_cursor) {
        //save the state of respond_to_cursor, and reapply it every time we move the cursor
        var probably_from_sent_message = respond_to_cursor;
        $.map(visible_messages, function(msg) {
            if ((current_msg_list.get(rows.id($(msg))).sent_by_me) &&
                (current_msg_list.selected_message().id < rows.id($(msg)))) {
                // every time we move the cursor, we set respond_to_cursor to false. This should only
                // happen if the user initiated the cursor move, not us, so we reset it when processing
                // these messages
                current_msg_list.select_id(rows.id($(msg)), {then_scroll: true,
                                                             from_scroll: true});
                respond_to_cursor = probably_from_sent_message;
            }
        });
    }

    var mark_as_read = $.map(visible_messages, function(msg) {
        var message = current_msg_list.get(rows.id($(msg)));
        if (! unread.message_unread(message)) {
            return undefined;
        } else {
            return message;
        }
    });

    if (unread.message_unread(selected)) {
        mark_as_read.push(selected);
    }

    if (mark_as_read.length > 0) {
        process_read_messages(mark_as_read);
    }
}

function mark_read_between(msg_list, start_id, end_id) {
    var mark_as_read = [];
    $.each(message_range(msg_list, start_id, end_id),
        function (idx, msg) {
            if (unread.message_unread(msg)) {
                mark_as_read.push(msg);
            }
    });
    process_read_messages(mark_as_read);
}

function update_pointer() {
    if (!pointer_update_in_flight) {
        pointer_update_in_flight = true;
        return $.ajax({
            type:     'POST',
            url:      '/json/update_pointer',
            data:     {pointer: furthest_read},
            dataType: 'json',
            success: function () {
                server_furthest_read = furthest_read;
                pointer_update_in_flight = false;
            },
            error: function () {
                pointer_update_in_flight = false;
            }
        });
    } else {
        // Return an empty, resolved Deferred.
        return $.when();
    }
}

function send_pointer_update() {
    // Only bother if you've read new messages.
    if (furthest_read > server_furthest_read) {
        update_pointer();
    }
}

function unconditionally_send_pointer_update() {
    if (pointer_update_in_flight) {
        // Keep trying.
        return unconditionally_send_pointer_update();
    } else {
        return update_pointer();
    }
}

$(function () {
    furthest_read = page_params.initial_pointer;
    server_furthest_read = page_params.initial_pointer;

    // We only send pointer updates when the user has been idle for a
    // short while to avoid hammering the server
    $(document).idle({idle: 1000,
                      onIdle: send_pointer_update,
                      keepTracking: true});

    $(document).on('message_selected.zephyr', function (event) {

        // Narrowing is a temporary view on top of the home view and
        // doesn't affect your pointer in the home view.
        if (event.msg_list === home_msg_list
            && event.id > furthest_read)
        {
            furthest_read = event.id;
        }

        // If we move the pointer, we don't want to respond to what's at the pointer
        if (event.previously_selected !== event.id) {
            respond_to_cursor = false;
        }

        if (event.previously_selected !== -1) {
            // Mark messages between old pointer and new pointer as read
            if (event.id < event.previously_selected) {
                mark_read_between(event.msg_list, event.id, event.previously_selected);
            } else {
                mark_read_between(event.msg_list, event.previously_selected, event.id);
            }
        }
    });
});

function case_insensitive_find(term, array) {
    var lowered_term = term.toLowerCase();
    return $.grep(array, function (elt) {
        return elt.toLowerCase() === lowered_term;
    }).length !== 0;
}

function process_message_for_recent_subjects(message, remove_message) {
    var current_timestamp = 0;
    var count = 0;
    var canon_stream = subs.canonicalized_name(message.stream);
    var canon_subject = subs.canonicalized_name(message.subject);

    if (! recent_subjects.hasOwnProperty(canon_stream)) {
        recent_subjects[canon_stream] = [];
    } else {
        recent_subjects[canon_stream] =
            $.grep(recent_subjects[canon_stream], function (item) {
                var is_duplicate = (item.canon_subject.toLowerCase() === canon_subject.toLowerCase());
                if (is_duplicate) {
                    current_timestamp = item.timestamp;
                    count = item.count;
                }

                return !is_duplicate;
            });
    }

    var recents = recent_subjects[canon_stream];

    if (remove_message !== undefined) {
        count = count - 1;
    } else {
        count = count + 1;
    }

    if (count !== 0) {
        recents.push({subject: message.subject,
                      canon_subject: canon_subject,
                      count: count,
                      timestamp: Math.max(message.timestamp, current_timestamp)});
    }

    recents.sort(function (a, b) {
        return b.timestamp - a.timestamp;
    });

    recent_subjects[canon_stream] = recents;
}

var msg_metadata_cache = {};
function add_message_metadata(message, dummy) {
    var cached_msg = msg_metadata_cache[message.id];
    if (cached_msg !== undefined) {
        // Copy the match subject and content over if they exist on
        // the new message
        if (message.match_subject !== undefined) {
            cached_msg.match_subject = message.match_subject;
            cached_msg.match_content = message.match_content;
        }
        return cached_msg;
    }
    get_updates_params.last = Math.max(get_updates_params.last || 0, message.id);

    var involved_people;

    message.sent_by_me = (message.sender_email === page_params.email);

    message.flags = message.flags || [];
    message.historical = (message.flags !== undefined &&
                          message.flags.indexOf('historical') !== -1);
    message.starred = message.flags.indexOf("starred") !== -1;
    message.mentioned = message.flags.indexOf("mentioned") !== -1 ||
                        message.flags.indexOf("wildcard_mentioned") !== -1;
    message.collapsed = message.flags.indexOf("collapsed") !== -1;

    switch (message.type) {
    case 'stream':
        message.is_stream = true;
        message.stream = message.display_recipient;
        if (! subject_dict.hasOwnProperty(message.stream)) {
            subject_dict[message.stream] = [];
        }
        if (! case_insensitive_find(message.subject, subject_dict[message.stream])) {
            subject_dict[message.stream].push(message.subject);
            subject_dict[message.stream].sort();
            // We don't need to update the autocomplete after this because
            // the subject box's source is a function
        }
        message.reply_to = message.sender_email;

        process_message_for_recent_subjects(message);

        involved_people = [{'full_name': message.sender_full_name,
                            'email': message.sender_email}];

        if ((message.subject === compose.empty_subject_placeholder()) &&
            message.sent_by_me) {
            // You can only edit messages you sent, so only show the edit hint
            // for empty subjects on messages you sent.
            message.your_empty_subject = true;
        } else {
            message.your_empty_subject = false;
        }
        break;

    case 'private':
        message.is_private = true;
        message.reply_to = get_private_message_recipient(message, 'email').replace(/ /g, "");
        message.display_reply_to = get_private_message_recipient(message, 'full_name');

        involved_people = message.display_recipient;
        break;
    }

    // Add new people involved in this message to the people list
    $.each(involved_people, function (idx, person) {
        // Do the hasOwnProperty() call via the prototype to avoid problems
        // with keys like "hasOwnProperty"
        if (people_dict[person.email] === undefined) {
            add_person(person);
            typeahead_helper.autocomplete_needs_update(true);
        }

        if (message.type === 'private' && message.sent_by_me) {
            // Track the number of PMs we've sent to this person to improve autocomplete
            people_dict[person.email].pm_recipient_count += 1;
        }
    });

    msg_metadata_cache[message.id] = message;
    return message;
}

function add_messages_helper(messages, msg_list, predicate) {
    var top_messages = [];
    var bottom_messages = [];
    var interior_messages = [];

    // If we're initially populating the list, save the messages in
    // bottom_messages regardless
    if (msg_list.selected_id() === -1 && msg_list.empty()) {
        bottom_messages = $.grep(messages, predicate);
    } else {
        $.each(messages, function (idx, msg) {
            // Filter out duplicates that are already in msg_list, and all messages
            // that fail our filter predicate
            if (! (msg_list.get(msg.id) === undefined && predicate(msg))) {
                return;
            }

            // Put messages in correct order on either side of the message list
            if (msg_list.empty() || (msg.id < msg_list.first().id)) {
                top_messages.push(msg);
            } else if (msg.id > msg_list.last().id) {
                bottom_messages.push(msg);
            } else {
                interior_messages.push(msg);
            }
        });
    }

    if (interior_messages.length > 0) {
        msg_list.add_and_rerender(top_messages.concat(interior_messages).concat(bottom_messages));
        return true;
    }
    msg_list.prepend(top_messages);
    msg_list.append(bottom_messages);
    return top_messages.length > 0;
}

function add_messages(messages, msg_list) {
    var prepended = false;
    if (!messages)
        return;

    util.destroy_loading_indicator($('#page_loading_indicator'));
    util.destroy_first_run_message();

    if (add_messages_helper(messages, msg_list, msg_list.filter.predicate())) {
        prepended = true;
    }

    if ((msg_list === narrowed_msg_list) && !msg_list.empty() &&
        (msg_list.selected_id() === -1)) {
        // If adding some new messages to the message tables caused
        // our current narrow to no longer be empty, hide the empty
        // feed placeholder text.
        narrow.hide_empty_narrow_message();
        // And also select the newly arrived message.
        msg_list.select_id(msg_list.selected_id(), {then_scroll: true, use_closest: true});
    }

    // If we prepended messages, then we need to scroll back to the pointer.
    // This will mess with the user's scrollwheel use; possibly we should be
    // more clever here.  However (for now) we only prepend on page load,
    // so maybe it's okay.
    //
    // We also need to re-select the message by ID, because we might have
    // removed and re-added the row as part of prepend collapsing.
    //
    // We select the closest id as a fallback in case the previously selected
    // message is no longer in the list
    if (prepended && (msg_list.selected_id() >= 0)) {
        msg_list.select_id(msg_list.selected_id(), {then_scroll: true, use_closest: true});
    }

    if (typeahead_helper.autocomplete_needs_update()) {
        typeahead_helper.update_autocomplete();
    }

    // There are some other common tasks that happen when adding messages, but these
    // happen higher up in the stack, notably logic related to unread counts.
}

function deduplicate_messages(messages) {
    var new_message_ids = {};
    return $.grep(messages, function (msg, idx) {
        if (new_message_ids[msg.id] === undefined
            && all_msg_list.get(msg.id) === undefined)
        {
            new_message_ids[msg.id] = true;
            return true;
        }
        return false;
    });
}

function maybe_add_narrowed_messages(messages, msg_list) {
    var ids = [];
    $.each(messages, function (idx, elem) {
        ids.push(elem.id);
    });

    $.ajax({
        type:     'POST',
        url:      '/json/messages_in_narrow',
        data:     {msg_ids: JSON.stringify(ids),
                   narrow:  JSON.stringify(narrow.public_operators())},
        dataType: 'json',
        timeout:  5000,
        success: function (data) {
            if (msg_list !== current_msg_list) {
                // We unnarrowed in the mean time
                return;
            }

            var new_messages = [];
            $.each(messages, function (idx, elem) {
                if (data.messages.hasOwnProperty(elem.id)) {
                    elem.match_subject = data.messages[elem.id].match_subject;
                    elem.match_content = data.messages[elem.id].match_content;
                    new_messages.push(elem);
                }
            });

            new_messages = $.map(new_messages, add_message_metadata);
            add_messages(new_messages, msg_list);
            process_visible_unread_messages();
            compose.update_faded_messages();
        },
        error: function (xhr) {
            // We might want to be more clever here
            setTimeout(function () {
                if (msg_list === current_msg_list) {
                    // Don't actually try again if we unnarrowed
                    // while waiting
                    maybe_add_narrowed_messages(messages, msg_list);
                }
            }, 5000);
        }});
}

function update_messages(events) {
    $.each(events, function (idx, event) {
        var msg = all_msg_list.get(event.message_id);
        if (msg === undefined) {
            return;
        }

        if (event.rendered_content !== undefined) {
            msg.content = event.rendered_content;
        }

        if (event.subject !== undefined) {
            // Remove the recent subjects entry for the old subject;
            // must be called before we update msg.subject
            process_message_for_recent_subjects(msg, true);
            // Update the unread counts; again, this must be called
            // before we update msg.subject
            unread.update_unread_subjects(msg, event);

            msg.subject = event.subject;
            if (msg.subject === compose.empty_subject_placeholder()) {
                msg.your_empty_subject = true;
            } else {
                msg.your_empty_subject = false;
            }
            // Add the recent subjects entry for the new subject; must
            // be called after we update msg.subject
            process_message_for_recent_subjects(msg);
        }

        var row = rows.get(event.message_id, current_msg_list.table_name);
        if (row.length > 0) {
            message_edit.end(row);
        }

        msg.last_edit_timestamp = event.edit_timestamp;
        delete msg.last_edit_timestr;
    });

    home_msg_list.rerender();
    if (current_msg_list === narrowed_msg_list) {
        narrowed_msg_list.rerender();
    }
    compose.update_faded_messages();
    update_unread_counts();
    stream_list.update_streams_sidebar();
}

function get_updates_success(data) {
    var messages = [];
    var messages_to_update = [];
    var new_pointer;

    if (tutorial.is_running()) {
        events_stored_during_tutorial = events_stored_during_tutorial.concat(data.events);
        return;
    }

    if (events_stored_during_tutorial.length > 0) {
        data.events = events_stored_during_tutorial.concat(data.events);
        events_stored_during_tutorial = [];
    }

    $.each(data.events, function (idx, event) {
        get_updates_params.last_event_id = Math.max(get_updates_params.last_event_id,
                                                    event.id);

        switch (event.type) {
        case 'message':
            var msg = event.message;
            msg.flags = event.flags;
            messages.push(msg);
            break;
        case 'pointer':
            new_pointer = event.pointer;
            break;
        case 'restart':
            reload.initiate({message: "The application has been updated; reloading!"});
            break;
        case 'onboarding_steps':
            onboarding.set_step_info(event.steps);
            break;
        case 'update_message':
            messages_to_update.push(event);
            break;
        case 'realm_user':
            if (event.op === 'add') {
                add_person(event.person);
            } else if (event.op === 'remove') {
                remove_person(event.person);
            }
            typeahead_helper.autocomplete_needs_update(true);
            break;
        case 'subscriptions':
            if (event.op === 'add') {
                $.each(event.subscriptions, function(index, subscription) {
                    $(document).trigger($.Event('subscription_add.zephyr',
                                                {subscription: subscription}));
                });
            } else if (event.op === 'remove') {
                $.each(event.subscriptions, function(index, subscription) {
                    $(document).trigger($.Event('subscription_remove.zephyr',
                                                {subscription: subscription}));
                });
            }
            break;
        case 'presence':
            activity.set_user_status(event.email, event.presence, event.server_timestamp);
            break;
        }
    });

    if (typeahead_helper.autocomplete_needs_update()) {
        typeahead_helper.update_autocomplete();
    }

    if (messages.length !== 0) {
        // There is a known bug (#1062) in our backend
        // whereby duplicate messages are delivered during a
        // server update.  Once that bug is fixed, this
        // should no longer be needed
        messages = deduplicate_messages(messages);
        messages = $.map(messages, add_message_metadata);

        // You must add add messages to home_msg_list BEFORE
        // calling process_loaded_for_unread.
        add_messages(messages, home_msg_list);
        process_loaded_for_unread(messages);

        add_messages(messages, all_msg_list);

        if (narrow.active()) {
            if (narrow.filter().can_apply_locally()) {
                add_messages(messages, narrowed_msg_list);
            } else {
                maybe_add_narrowed_messages(messages, narrowed_msg_list);
            }
        }

        // notifications.received_messages uses values set by
        // process_visible_unread_messages and thus must
        // be called after it
        var i;
        var update_cursor = false;
        // check if we need to update the cursor, and do so if needed.
        for (i = 0; i < messages.length; i++) {
            if (messages[i].sent_by_me && narrow.narrowed_by_reply()) {
                update_cursor = true;
            }
        }

        process_visible_unread_messages(update_cursor);
        notifications.received_messages(messages);
        compose.update_faded_messages();
        stream_list.update_streams_sidebar();
    }

    if (new_pointer !== undefined
        && new_pointer > furthest_read)
    {
        furthest_read = new_pointer;
        server_furthest_read = new_pointer;
        home_msg_list.select_id(new_pointer, {then_scroll: true, use_closest: true});
    }

    if ((home_msg_list.selected_id() === -1) && !home_msg_list.empty()) {
        home_msg_list.select_id(home_msg_list.first().id, {then_scroll: false});
    }

    if (messages_to_update.length !== 0) {
        update_messages(messages_to_update);
    }
}

var get_updates_xhr;
var get_updates_timeout;
function get_updates(options) {
    var defaults = {dont_block: false};
    options = $.extend({}, defaults, options);

    get_updates_params.pointer = furthest_read;
    get_updates_params.dont_block = options.dont_block || get_updates_failures > 0;
    if (get_updates_params.queue_id === undefined) {
        get_updates_params.queue_id = page_params.event_queue_id;
        get_updates_params.last_event_id = page_params.last_event_id;
    }

    get_updates_xhr = $.ajax({
        type:     'POST',
        url:      '/json/get_events',
        data:     get_updates_params,
        dataType: 'json',
        timeout:  page_params.poll_timeout,
        success: function (data) {
            if (! data) {
                // The server occasionally returns no data during a
                // restart.  Ignore those responses so the page keeps
                // working
                get_updates_timeout = setTimeout(get_updates, 0);
                return;
            }

            get_updates_failures = 0;
            $('#connection-error').hide();

            get_updates_success(data);

            if (tutorial.is_running()) {
                get_updates_timeout = setTimeout(get_updates, 5000);
            } else {
                get_updates_timeout = setTimeout(get_updates, 0);
            }
        },
        error: function (xhr, error_type, exn) {
            // If we are old enough to have messages outside of the
            // Tornado cache or if we're old enough that our message
            // queue has been garbage collected, immediately reload.
            if ((xhr.status === 400) &&
                ($.parseJSON(xhr.responseText).msg.indexOf("too old") !== -1 ||
                 $.parseJSON(xhr.responseText).msg.indexOf("Bad event queue id") !== -1)) {
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

function force_get_updates() {
    get_updates_timeout = setTimeout(get_updates, 0);
}

function load_old_messages(opts) {
    opts = $.extend({}, {
        cont_will_add_messages: false
    }, opts);

    var data = {anchor: opts.anchor,
                num_before: opts.num_before,
                num_after: opts.num_after};

    if (opts.msg_list.narrowed && narrow.active())
        data.narrow = JSON.stringify(narrow.public_operators());

    function process_result(messages) {
        $('#get_old_messages_error').hide();

        if ((messages.length === 0) && (current_msg_list === narrowed_msg_list) &&
            narrowed_msg_list.empty()) {
            // Even after trying to load more messages, we have no
            // messages to display in this narrow.
            narrow.show_empty_narrow_message();
        }

        messages = $.map(messages, add_message_metadata);

        // If we're loading more messages into the home view, save them to
        // the all_msg_list as well, as the home_msg_list is reconstructed
        // from all_msg_list.
        if (opts.msg_list === home_msg_list) {
            process_loaded_for_unread(messages);
            add_messages(messages, all_msg_list);
        }

        if (messages.length !== 0 && !opts.cont_will_add_messages) {
            add_messages(messages, opts.msg_list);
        }

        stream_list.update_streams_sidebar();

        if (opts.cont !== undefined) {
            opts.cont(messages);
        }
    }

    $.ajax({
        type:     'POST',
        url:      '/json/get_old_messages',
        data:     data,
        dataType: 'json',
        success: function (data) {
            if (opts.msg_list.narrowed && opts.msg_list !== current_msg_list) {
                // We unnarrowed before receiving new messages so
                // don't bother processing the newly arrived messages.
                return;
            }
            if (! data) {
                // The server occationally returns no data during a
                // restart.  Ignore those responses and try again
                setTimeout(function () {
                    load_old_messages(opts);
                }, 0);
                return;
            }

            process_result(data.messages);
        },
        error: function (xhr, error_type, exn) {
            if (opts.msg_list.narrowed && opts.msg_list !== current_msg_list) {
                // We unnarrowed before getting an error so don't
                // bother trying again or doing further processing.
                return;
            }
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
            $('#get_old_messages_error').show();
            setTimeout(function () {
                load_old_messages(opts);
            }, 5000);
        }
    });
}

// get the initial message list
$(function () {
    function load_more(messages) {

        // Before trying to load anything: is this user way behind?
        var last_read_message = home_msg_list.get(home_msg_list.closest_id(page_params.initial_pointer));
        if (last_read_message !== undefined) {
            var now = new XDate().getTime() / 1000;
            var num_unread = unread.get_counts().home_unread_messages;

            if ((num_unread > 500) &&
                (now - last_read_message.timestamp > 60 * 60 * 24 * 2)) { // 2 days.
                var unread_info = templates.render('bankruptcy_modal',
                                                   {"unread_count": num_unread});
                $('#bankruptcy-unread-count').html(unread_info);
                $('#bankruptcy').modal('show');
            }
        }

        // If we received the initially selected message, select it on the client side,
        // but not if the user has already selected another one during load.
        //
        // We fall back to the closest selected id, as the user may have removed
        // a stream from the home before already
        if (home_msg_list.selected_id() === -1) {
            home_msg_list.select_id(page_params.initial_pointer,
                {then_scroll: true, use_closest: true});
        }

        // catch the user up
        if (messages.length !== 0) {
            var latest_id = messages[messages.length-1].id;
            if (latest_id < page_params.max_message_id) {
                load_old_messages({
                    anchor: latest_id,
                    num_before: 0,
                    num_after: 400,
                    msg_list: home_msg_list,
                    cont: load_more
                });
                return;
            }
        }
        // now start subscribing to updates
        get_updates();

        // backfill more messages after the user is idle
        var backfill_batch_size = 1000;
        $(document).idle({'idle': 1000*10,
                          'onIdle': function () {
                              var first_id = all_msg_list.first().id;
                              load_old_messages({
                                  anchor: first_id,
                                  num_before: backfill_batch_size,
                                  num_after: 0,
                                  msg_list: home_msg_list
                              });
                          }});
    }

    if (page_params.have_initial_messages) {
        load_old_messages({
            anchor: page_params.initial_pointer,
            num_before: 200,
            num_after: 200,
            msg_list: home_msg_list,
            cont: load_more
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

function reset_load_more_status() {
    load_more_enabled = true;
    have_scrolled_away_from_top = true;
    ui.hide_loading_more_messages_indicator();
}

function load_more_messages(msg_list) {
    var batch_size = 100;
    var oldest_message_id;
    if (!load_more_enabled) {
        return;
    }
    ui.show_loading_more_messages_indicator();
    load_more_enabled = false;
    if (msg_list.first() === undefined) {
        oldest_message_id = page_params.initial_pointer;
    } else {
        oldest_message_id = msg_list.first().id;
    }
    load_old_messages({
        anchor: oldest_message_id,
        num_before: batch_size,
        num_after: 0,
        msg_list: msg_list,
        cont: function (messages) {
            ui.hide_loading_more_messages_indicator();
            if (messages.length >= batch_size) {
                load_more_enabled = true;
            }
        }
    });
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

// The idea here is when you've scrolled to the very
// bottom of the page, e.g., the scroll handler isn't
// going to fire anymore. But if I continue to use
// the scrollwheel, the selection should advance until
// I'm at the very top or the very bottom of the page.
function move_pointer_at_page_top_and_bottom(delta) {
    if (delta !== 0 && (viewport.at_top() || viewport.at_bottom())) {
        var next_row = current_msg_list.selected_row();
        if (delta > 0) {
            // Scrolling up (want older messages)
            next_row = rows.prev_visible(next_row);
        } else {
            // We're scrolling down (we want more recent messages)
            next_row = rows.next_visible(next_row);
        }
        if (next_row.length !== 0) {
            current_msg_list.select_id(rows.id(next_row));
        }
    }
}

function fast_forward_pointer() {
    $.ajax({
        type: 'POST',
        url: '/json/get_profile',
        data: {email: page_params.email},
        dataType: 'json',
        success: function (data) {
            mark_all_as_read(function () {
                furthest_read = data.max_message_id;
                unconditionally_send_pointer_update().then(function () {
                    ui.change_tab_to('#home');
                    reload.initiate({immediate: true});
                });
            });
        }
    });
}
