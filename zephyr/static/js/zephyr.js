var all_msg_list = new MessageList();
var home_msg_list = new MessageList('zhome', new narrow.Filter([["in", "home"]]));
var narrowed_msg_list;
var current_msg_list = home_msg_list;
var subject_dict = {};
var people_dict = {};
var recent_subjects = {};

var queued_mark_as_read = [];
var queued_flag_timer;

var viewport = $(window);

var get_updates_params = {
    pointer: -1
};
var get_updates_failures = 0;

var load_more_enabled = true;
// If the browser hasn't scrolled away from the top of the page
// since the last time that we ran load_more_messages(), we do
// not load_more_messages().
var have_scrolled_away_from_top = true;

var disable_pointer_movement = false;

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

function add_person(person) {
    page_params.people_list.push(person);
    people_dict[person.email] = person;
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
    });
    // The special account feedback@humbughq.com is used for in-app
    // feedback and should always show up as an autocomplete option.
    typeahead_helper.update_your_recipients([{"email": "feedback@humbughq.com",
                    "full_name": "Humbug Feedback Bot"}]);

    $.each(page_params.initial_presences, function (email, presence) {
        activity.set_user_status(email, presence);
    });

});

function within_viewport(message_row) {
    // Returns true if a message is fully within the viewport.
    var message_top = message_row.offset().top;
    var message_bottom  = message_top + message_row.height();
    var viewport_top = viewport.scrollTop();
    var viewport_bottom = viewport_top + viewport.height();
    return (message_top > viewport_top) && (message_bottom < viewport_bottom);
}

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

function recenter_view(message, from_scroll) {
    // Barnowl-style recentering: if the pointer is too high, center
    // in the middle of the screen. If the pointer is too low, center
    // on the 1/5-mark.

    // If this logic changes, above_view_threshold andd
    // below_view_threshold must also change.
    var selected_row = current_msg_list.selected_row();
    var selected_row_top = selected_row.offset().top;

    if (from_scroll !== undefined && from_scroll &&
        ((above_view_threshold(message, true) &&
          (last_viewport_movement_direction >= 0)) ||
         (below_view_threshold(message) &&
          (last_viewport_movement_direction <= 0)))) {
        // If the message you're trying to center on is already in view AND
        // you're already trying to move in the direction of that message,
        // don't try to recenter. This avoids disorienting jumps when the
        // pointer has gotten itself outside the threshold (e.g. by
        // autoscrolling).
        return;
    }

    if (above_view_threshold(message, true)) {
        // We specifically say useTop=true here, because suppose you're using
        // the arrow keys to arrow up and you've moved up to a huge message.
        // The message is so big that the bottom part of makes it not
        // "above the view threshold". But since we're using the arrow keys
        // to get here, the reason we selected this message is because
        // we want to read it; so here we care about the top part.
        viewport.scrollTop(selected_row_top - viewport.height() / 2);
    } else if (below_view_threshold(message)) {
        viewport.scrollTop(selected_row_top - viewport.height() / 5);
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

function respond_to_message(reply_type) {
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
                             'private_message_recipient': pm_recipient,
                             'replying_to_message': message});
}

function message_range(msg_list, start, end) {
    // Returns messages from the given message list in the specified range, inclusive
    var result = [];
    var i;

    for (i = start; i <= end; i++) {
        if (msg_list.get(i) !== undefined) {
            result.push(msg_list.get(i));
        }
    }

    return result;
}

function send_queued_flags() {
    if (queued_mark_as_read.length === 0) {
        return;
    }

    $.ajax({
        type:     'POST',
        url:      '/json/update_message_flags',
        data:     {messages: JSON.stringify(queued_mark_as_read),
                   op:       'add',
                   flag:     'read'},
        dataType: 'json'});

    queued_mark_as_read = [];
}

var unread_counts = {'stream': {}, 'private': {}};
var home_unread_messages = 0;

function unread_in_current_view() {
    var unread = 0;
    if (!narrow.active()) {
        unread = home_unread_messages;
    } else {
        $.each(current_msg_list.all(), function (idx, msg) {
            if (message_unread(msg) && msg.id > current_msg_list.selected_id()) {
                unread += 1;
            }
        });
    }
    return unread;
}

function message_unread(message) {
    if (message === undefined) {
        return false;
    }

    var sent_by_human = ['website', 'iphone', 'android']
                            .indexOf(message.client.toLowerCase()) !== -1;

    if (message.sender_email === page_params.email && sent_by_human) {
        return false;
    }

    return message.flags === undefined ||
           message.flags.indexOf('read') === -1;
}

function update_unread_counts() {
    home_unread_messages = 0;

    function newer_than_pointer_count(msgids) {
        var valid = $.grep(msgids, function (msgid) {
            return all_msg_list.get(msgid).id > home_msg_list.selected_id();
        });
        return valid.length;
    }

    function only_in_home_view(msgids) {
        return $.grep(msgids, function (msgid) {
            return home_msg_list.get(msgid) !== undefined;
        });
    }

    $.each(unread_counts.stream, function(index, obj) {
        var count = Object.keys(obj).length;
        ui.set_count("stream", index, count);
        if (narrow.stream_in_home(index)) {
            home_unread_messages += newer_than_pointer_count(only_in_home_view(Object.keys(obj)));
        }
    });

    var pm_count = 0;
    $.each(unread_counts["private"], function(index, obj) {
        pm_count += newer_than_pointer_count(only_in_home_view(Object.keys(obj)));
    });
    ui.set_count("global", "private", pm_count);
    home_unread_messages += pm_count;

}

function mark_all_as_read(cont) {
    $.each(all_msg_list.all(), function (idx, msg) {
        msg.flags = msg.flags || [];
        msg.flags.push('read');
    });
    unread_counts = {'stream': {}, 'private': {}};
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

function unread_hashkey(message) {
    var hashkey;
    if (message.type === 'stream') {
        hashkey = message.stream;
    } else {
        hashkey = message.display_reply_to;
    }

    if (unread_counts[message.type][hashkey] === undefined) {
        unread_counts[message.type][hashkey] = {};
    }

    return hashkey;
}

function process_loaded_for_unread(messages) {
    $.each(messages, function (idx, message) {
        var unread = message_unread(message);
        if (!unread) {
            return;
        }

        var hashkey = unread_hashkey(message);
        unread_counts[message.type][hashkey][message.id] = true;
    });

    update_unread_counts();
}

// Takes a list of messages and marks them as read
function process_read_messages(messages) {
    var processed = [];
    $.each(messages, function (idx, message) {
        var hashkey = unread_hashkey(message);

        message.flags = message.flags || [];
        message.flags.push('read');
        processed.push(message.id);

        delete unread_counts[message.type][hashkey][message.id];
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

function process_visible_unread_messages() {
    // For any messages visible on the screen, make sure they have been marked
    // as unread.
    if (! notifications.window_has_focus()) {
        return;
    }

    var selected = current_msg_list.selected_message();
    var top = viewport.scrollTop();
    var height = viewport.height();
    var bottom = top + height;
    var middle = top + (height / 2);

    // Being simplistic about this, the smallest message is 30 px high.
    var selected_row = rows.get(current_msg_list.selected_id(), current_msg_list.table_name);
    var num_neighbors = Math.floor(height / 30);
    var candidates = $.merge(selected_row.prevAll("tr.message_row[zid]:lt(" + num_neighbors + ")"),
                             selected_row.nextAll("tr.message_row[zid]:lt(" + num_neighbors + ")"));

    var visible_messages = candidates.filter(function (idx, message) {
        var row = $(message);
        // Mark very tall messages as read once we've gotten past them
        return (row.height() > height && row.offset().top > top) || within_viewport(row);
    });

    var mark_as_read = $.map(visible_messages, function(msg) {
        var message = current_msg_list.get(rows.id($(msg)));
        if (! message_unread(message)) {
            return undefined;
        } else {
            return message;
        }
    });

    if (message_unread(selected)) {
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
            if (message_unread(msg)) {
                mark_as_read.push(msg);
            }
    });
    process_read_messages(mark_as_read);
}

function send_pointer_update() {
    if (!pointer_update_in_flight &&
        furthest_read > server_furthest_read) {
        pointer_update_in_flight = true;
        $.ajax({
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
    });
});

function case_insensitive_find(term, array) {
    var lowered_term = term.toLowerCase();
    return $.grep(array, function (elt) {
        return elt.toLowerCase() === lowered_term;
    }).length !== 0;
}

var update_recent_subjects = $.debounce(100, ui.update_recent_subjects);

function process_message_for_recent_subjects(message) {
    var current_timestamp = 0;
    var max_subjects = 5;

    if (! recent_subjects.hasOwnProperty(message.stream)) {
        recent_subjects[message.stream] = [];
    } else {
        recent_subjects[message.stream] =
            $.grep(recent_subjects[message.stream], function (item) {
                if (item.subject === message.subject) {
                    current_timestamp = item.timestamp;
                }

                return item.subject !== message.subject;
            });
    }

    var recents = recent_subjects[message.stream];
    recents.push({subject: message.subject,
                  timestamp: Math.max(message.timestamp, current_timestamp)});

    recents.sort(function (a, b) {
        return b.timestamp - a.timestamp;
    });

    recents = recents.slice(0, max_subjects);

    recent_subjects[message.stream] = recents;
    update_recent_subjects();
}

function add_message_metadata(message, dummy) {
    var cached_msg = all_msg_list.get(message.id);
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

    message.flags = message.flags || [];
    message.historical = (message.flags !== undefined &&
                          message.flags.indexOf('historical') !== -1);
    message.starred = message.flags.indexOf("starred") !== -1;

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
        break;

    case 'private':
        message.is_private = true;
        message.reply_to = get_private_message_recipient(message, 'email').replace(/ /g, "");
        message.display_reply_to = get_private_message_recipient(message, 'full_name');

        involved_people = message.display_recipient;

        if (message.sender_email === page_params.email) {
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
    messages = $.map(messages, add_message_metadata);

    if (add_messages_helper(messages, msg_list, msg_list.filter.predicate())) {
        prepended = true;
    }

    process_loaded_for_unread(messages);

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

    // If the new messages are off the screen, show a notification
    notifications_bar.update();
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

            messages = $.grep(messages, function (elem) {
                return ($.inArray(elem.id, data.msg_ids) !== -1);
            });

            add_messages(messages, msg_list);
            process_visible_unread_messages();
            compose.update_faded_messages();
        },
        error: function (xhr) {
            // We might want to be more clever here
            $('#connection-error').show();
            setTimeout(function () {
                if (msg_list === current_msg_list) {
                    // Don't actually try again if we unnarrowed
                    // while waiting
                    maybe_add_narrowed_messages(messages, msg_list);
                }
            }, 5000);
        }});
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

            var messages = [];
            var new_pointer;

            $.each(data.events, function (idx, event) {
                get_updates_params.last_event_id = Math.max(get_updates_params.last_event_id,
                                                            event.id);

                switch (event.type) {
                case 'message':
                    messages.push(event.message);
                    break;
                case 'pointer':
                    new_pointer = event.pointer;
                    break;
                case 'restart':
                    reload.initiate();
                    break;
                case 'realm_user':
                    if (event.op === 'add') {
                        add_person(event.person);
                        typeahead_helper.update_all_recipients([event.person]);
                    } else if (event.op === 'remove') {
                        remove_person(event.person);
                        typeahead_helper.remove_recipient([event.person]);
                    }
                    typeahead_helper.autocomplete_needs_update(true);
                    break;
                case 'subscription':
                    if (event.op === 'add') {
                        $(document).trigger($.Event('subscription_add.zephyr',
                                                    {subscription: event.subscription}));
                    } else if (event.op === 'remove') {
                        $(document).trigger($.Event('subscription_remove.zephyr',
                                                    {subscription: event.subscription}));
                    }
                    break;
                case 'presence':
                    activity.set_user_status(event.email, event.presence);
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

                if (narrow.active()) {
                    if (narrow.filter().can_apply_locally()) {
                        add_messages(messages, narrowed_msg_list);
                    } else {
                        maybe_add_narrowed_messages(messages, narrowed_msg_list);
                    }
                }
                add_messages(messages, all_msg_list);
                add_messages(messages, home_msg_list);
                process_visible_unread_messages();
                notifications.received_messages(messages);
                compose.update_faded_messages();
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

            get_updates_timeout = setTimeout(get_updates, 0);
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
        $('#connection-error').hide();

        if ((messages.length === 0) && (current_msg_list === narrowed_msg_list) &&
            narrowed_msg_list.empty()) {
            // Even after trying to load more messages, we have no
            // messages to display in this narrow.
            narrow.show_empty_narrow_message();
        }

        // If we're loading more messages into the home view, save them to
        // the all_msg_list as well, as the home_msg_list is reconstructed
        // from all_msg_list.
        if (opts.msg_list === home_msg_list) {
            add_messages(messages, all_msg_list);
        }

        if (messages.length !== 0 && !opts.cont_will_add_messages) {
            add_messages(messages, opts.msg_list);
        }

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
            $('#connection-error').show();
            setTimeout(function () {
                load_old_messages(opts);
            }, 5000);
        }
    });
}

// get the initial message list
$(function () {
    function load_more(messages) {
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
    var batch_size = 400;
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

function at_top_of_viewport() {
    return (viewport.scrollTop() === 0);
}

function at_bottom_of_viewport() {
    // outerHeight(true): Include margin
    return (viewport.scrollTop() + viewport.height() >= $("#main_div").outerHeight(true));
}

function keep_pointer_in_view() {
    var candidate;
    var next_row = current_msg_list.selected_row();

    if (disable_pointer_movement) {
        return;
    }

    if (next_row.length === 0)
        return;

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

    if (! adjust(above_view_threshold, at_top_of_viewport, rows.next_visible))
        adjust(below_view_threshold, at_bottom_of_viewport, rows.prev_visible);

    current_msg_list.select_id(rows.id(next_row), {from_scroll: true});
}

// The idea here is when you've scrolled to the very
// bottom of the page, e.g., the scroll handler isn't
// going to fire anymore. But if I continue to use
// the scrollwheel, the selection should advance until
// I'm at the very top or the very bottom of the page.
function move_pointer_at_page_top_and_bottom(delta) {
    if (delta !== 0 && (at_top_of_viewport() || at_bottom_of_viewport())) {
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

function fast_forward_pointer(btn) {
    btn = $(btn);

    btn.attr('disabled', 'disabled');

    btn.after($("<div>").addClass("alert alert-info settings_committed")
                        .text("Working…"));

    $.ajax({
        type: 'POST',
        url: '/json/get_profile',
        data: {email: page_params.email},
        dataType: 'json',
        success: function (data) {
            mark_all_as_read(function () {
                furthest_read = data.max_message_id;
                send_pointer_update();
                ui.change_tab_to('#home');
                reload.initiate({immediate: true});
            });
        }
    });
}
