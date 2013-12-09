var all_msg_list = new MessageList(
    undefined, undefined,
    {muting_enabled: false}
);
var home_msg_list = new MessageList('zhome',
    new Filter([["in", "home"]]),
    {
        muting_enabled: true,
        summarize_read: feature_flags.summarize_read_while_narrowed?'home':false
    }
);
var narrowed_msg_list;
var current_msg_list = home_msg_list;

// The following two Dicts point to the same objects
// All people we've seen
var people_dict = new Dict();
// People in this realm
var realm_people_dict = new Dict();

var recent_subjects = new Dict({fold_case: true});

var queued_mark_as_read = [];
var queued_flag_timer;

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
var unread_messages_read_in_narrow = false;
var pointer_update_in_flight = false;
var suppress_unread_counts = true;

var events_stored_during_tutorial = [];

var waiting_on_browser_scroll = true;

function add_person(person, in_realm) {
    page_params.people_list.push(person);
    people_dict.set(person.email, person);
    person.pm_recipient_count = 0;
}

function add_person_in_realm(person) {
    realm_people_dict.set(person.email, person);
    add_person(person);
}

function remove_person(person) {
    var i;
    for (i = 0; i < page_params.people_list.length; i++) {
        if (page_params.people_list[i].email === person.email) {
            page_params.people_list.splice(i, 1);
            break;
        }
    }
    people_dict.del(person.email);
    realm_people_dict.del(person.email);
}

function update_person(person) {
    // Currently the only attribute that can change is full_name, so
    // we just push out changes to that field.  As we add more things
    // that can change, this will need to either get complicated or be
    // replaced by MVC
    var i;
    if (! people_dict.has(person.email)) {
        blueslip.error("Got update_person event for unexpected user",
                       {email: person.email});
        return;
    }
    people_dict.get(person.email).full_name = person.full_name;
    // This should be the same object, but...
    realm_people_dict.get(person.email).full_name = person.full_name;
    for (i = 0; i < page_params.people_list.length; i++) {
        if (page_params.people_list[i].email === person.email) {
            page_params.people_list[i].full_name = person.full_name;
            break;
        }
    }
    if (person.email === page_params.email) {
        page_params.fullname = person.full_name;
    }
    activity.set_user_statuses([]);

    // TODO: update sender names on messages
}

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

    if (next_row.length === 0) {
        return;
    }

    var info = viewport.message_viewport_info();
    var top_threshold = info.visible_top + (1/10 * info.visible_height);
    var bottom_threshold = info.visible_top + (9/10 * info.visible_height);

    function message_is_far_enough_down() {
        if (viewport.at_top()) {
            return true;
        }

        var message_top = next_row.offset().top;

        // If the message starts after the very top of the screen, we just
        // leave it alone.  This avoids bugs like #1608, where overzealousness
        // about repositioning the pointer can cause users to miss messages.
        if (message_top >= info.visible_top) {
            return true;
        }


        // If at least part of the message is below top_threshold (10% from
        // the top), then we also leave it alone.
        var bottom_offset = message_top + next_row.outerHeight(true);
        if (bottom_offset >= top_threshold) {
            return true;
        }

        // If we got this far, the message is not "in view."
        return false;
    }

    function message_is_far_enough_up() {
        return viewport.at_bottom() ||
            (next_row.offset().top <= bottom_threshold);
    }

    function adjust(in_view, get_next_row) {
        // return true only if we make an actual adjustment, so
        // that we know to short circuit the other direction
        if (in_view(next_row)) {
            return false;  // try other side
        }
        while (!in_view(next_row)) {
            candidate = get_next_row(next_row);
            if (candidate.length === 0) {
                break;
            }
            next_row = candidate;
        }
        return true;
    }

    if (!adjust(message_is_far_enough_down, rows.next_visible)) {
        adjust(message_is_far_enough_up, rows.prev_visible);
    }

    current_msg_list.select_id(rows.id(next_row), {from_scroll: true});
}

function recenter_view(message, opts) {
    opts = opts || {};

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

    if (opts.from_scroll) {
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

    if (is_above || opts.force_center) {
        viewport.set_message_position(message_top, message_height, viewport_info, 1/2);
    } else if (is_below) {
        viewport.set_message_position(message_top, message_height, viewport_info, 1/7);
    }
}

function scroll_to_selected() {
    var selected_row = current_msg_list.selected_row();
    if (selected_row && (selected_row.length !== 0)) {
        recenter_view(selected_row);
    }
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
    var other_recipients = _.filter(message.display_recipient,
                                  function (element) {
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

function batched_flag_updater(flag, op) {
    var queue = [];

    function on_success(data, status, jqXHR) {
        if (data ===  undefined || data.messages === undefined) {
            return;
        }

        queue = _.filter(queue, function (message) {
            return data.messages.indexOf(message) === -1;
        });
    }

    function server_request() {
        $.ajax({
            type:     'POST',
            url:      '/json/update_message_flags',
            data:     {messages: JSON.stringify(queue),
                       op:       op,
                       flag:     flag},
            dataType: 'json',
            success:  on_success
        });
    }

    var start = _.debounce(server_request, 1000);

    function add(message) {
        if (message.flags === undefined) {
            message.flags = [];
        }
        if (op === 'add')  {
            message.flags.push(flag);
        } else {
            message.flags = _.without(message.flags, flag);
        }
        queue.push(message.id);
        start();
    }

    return add;
}

var send_read = batched_flag_updater('read', 'add');
var send_summarize_in_stream = batched_flag_updater('summarize_in_stream', 'add');
var send_summarize_in_home = batched_flag_updater('summarize_in_home', 'add');

function update_unread_counts() {
    if (suppress_unread_counts) {
        return;
    }

    // Pure computation:
    var res = unread.get_counts();

    // Side effects from here down:
    // This updates some DOM elements directly, so try to
    // avoid excessive calls to this.
    stream_list.update_dom_with_unread_counts(res);
    notifications.update_title_count(res.home_unread_messages);
    notifications.update_pm_count(res.private_message_count);
    notifications_bar.update(res.home_unread_messages);
}

function enable_unread_counts() {
    suppress_unread_counts = false;
    update_unread_counts();
}

function mark_all_as_read(cont) {
    _.each(all_msg_list.all(), function (msg) {
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
    activity.process_loaded_messages(messages);
    activity.update_huddles();
    unread.process_loaded_messages(messages);
    update_unread_counts();
    ui.resize_page_components();
}

// Takes a list of messages and marks them as read
function mark_messages_as_read(messages, options) {
    options = options || {};
    var processed = false;

    _.each(messages, function (message) {
        if (!unread.message_unread(message)) {
            // Don't do anything if the message is already read.
            return;
        }
        if (current_msg_list === narrowed_msg_list) {
            unread_messages_read_in_narrow = true;
        }

        send_read(message);
        summary.maybe_mark_summarized(message);

        message.unread = false;
        unread.process_read_message(message, options);
        home_msg_list.show_message_as_read(message, options);
        all_msg_list.show_message_as_read(message, options);
        if (narrowed_msg_list) {
            narrowed_msg_list.show_message_as_read(message, options);
        }
        notifications.close_notification(message);
        processed = true;
    });

    if (processed) {
        update_unread_counts();
    }
}

function mark_message_as_read(message, options) {
    mark_messages_as_read([message], options);
}

// If we ever materially change the algorithm for this function, we
// may need to update notifications.received_messages as well.
function process_visible_unread_messages(update_cursor) {
    if (! notifications.window_has_focus()) {
        return;
    }

    if (feature_flags.mark_read_at_bottom) {
        if (viewport.bottom_message_visible()) {
            mark_current_list_as_read();
        }
    } else {
        mark_messages_as_read(viewport.visible_messages(true));
    }
}

function mark_current_list_as_read(options) {
    mark_messages_as_read(current_msg_list.all(), options);
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

    mark_message_as_read(message);

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
        var deferred = $.Deferred();

        setTimeout(function () {
            deferred.resolve(unconditionally_send_pointer_update());
        }, 100);
        return deferred;
    } else {
        return update_pointer();
    }
}

function process_message_for_recent_subjects(message, remove_message) {
    var current_timestamp = 0;
    var count = 0;
    var stream = message.stream;
    var canon_subject = stream_data.canonicalized_name(message.subject);

    if (! recent_subjects.has(stream)) {
        recent_subjects.set(stream, []);
    } else {
        recent_subjects.set(stream,
                            _.filter(recent_subjects.get(stream), function (item) {
                                var is_duplicate = (item.canon_subject.toLowerCase() === canon_subject.toLowerCase());
                                if (is_duplicate) {
                                    current_timestamp = item.timestamp;
                                    count = item.count;
                                }

                                return !is_duplicate;
                            }));
    }

    var recents = recent_subjects.get(stream);

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

    recent_subjects.set(stream, recents);
}

function set_topic_edit_properties(message) {
    message.always_visible_topic_edit = false;
    message.on_hover_topic_edit = false;
    if (feature_flags.disable_message_editing) {
        return;
    }

    // Messages with no topics should always have an edit icon visible
    // to encourage updating them. Admins can also edit any topic.
    if (message.subject === compose.empty_subject_placeholder()) {
        message.always_visible_topic_edit = true;
    } else if (page_params.is_admin) {
        message.on_hover_topic_edit = true;
    }
}

var msg_metadata_cache = {};
function add_message_metadata(message) {
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
    message.alerted = message.flags.indexOf("has_alert_word") !== -1;

    switch (message.type) {
    case 'stream':
        message.is_stream = true;
        message.stream = message.display_recipient;
        composebox_typeahead.add_topic(message.stream, message.subject);
        message.reply_to = message.sender_email;

        process_message_for_recent_subjects(message);

        involved_people = [{'full_name': message.sender_full_name,
                            'email': message.sender_email}];
        set_topic_edit_properties(message);
        break;

    case 'private':
        message.is_private = true;
        message.reply_to = util.normalize_recipients(
                get_private_message_recipient(message, 'email'));
        message.display_reply_to = get_private_message_recipient(message, 'full_name');

        involved_people = message.display_recipient;
        break;
    }

    // Add new people involved in this message to the people list
    _.each(involved_people, function (person) {
        // Do the hasOwnProperty() call via the prototype to avoid problems
        // with keys like "hasOwnProperty"
        if (! people_dict.has(person.email)) {
            add_person(person);
        }

        if (message.type === 'private' && message.sent_by_me) {
            // Track the number of PMs we've sent to this person to improve autocomplete
            people_dict.get(person.email).pm_recipient_count += 1;
        }
    });

    alert_words.process_message(message);
    msg_metadata_cache[message.id] = message;
    return message;
}

function add_messages(messages, msg_list, messages_are_new) {
    if (!messages) {
        return;
    }

    util.destroy_loading_indicator($('#page_loading_indicator'));
    util.destroy_first_run_message();

    msg_list.add_messages(messages, messages_are_new);

    if (msg_list === home_msg_list && messages_are_new) {
        _.each(messages, function (message) {
            if (message.sent_by_me) {
                compose.mark_end_to_end_receive_time(message.id);
                setTimeout(function () {
                    compose.mark_end_to_end_display_time(message.id);
                }, 0);
            }
        });
    }
}

function deduplicate_messages(messages) {
    var new_message_ids = {};
    return _.filter(messages, function (msg) {
        if (new_message_ids[msg.id] === undefined
            && all_msg_list.get(msg.id) === undefined)
        {
            new_message_ids[msg.id] = true;
            return true;
        }
        return false;
    });
}

function maybe_add_narrowed_messages(messages, msg_list, messages_are_new) {
    var ids = [];
    _.each(messages, function (elem) {
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
            var elsewhere_messages = [];
            _.each(messages, function (elem) {
                if (data.messages.hasOwnProperty(elem.id)) {
                    elem.match_subject = data.messages[elem.id].match_subject;
                    elem.match_content = data.messages[elem.id].match_content;
                    new_messages.push(elem);
                } else {
                    elsewhere_messages.push(elem);
                }
            });

            new_messages = _.map(new_messages, add_message_metadata);
            add_messages(new_messages, msg_list, messages_are_new);
            process_visible_unread_messages();
            notifications.possibly_notify_new_messages_outside_viewport(new_messages);
            notifications.notify_messages_outside_current_search(elsewhere_messages);
        },
        error: function (xhr) {
            // We might want to be more clever here
            setTimeout(function () {
                if (msg_list === current_msg_list) {
                    // Don't actually try again if we unnarrowed
                    // while waiting
                    maybe_add_narrowed_messages(messages, msg_list, messages_are_new);
                }
            }, 5000);
        }});
}

function update_messages(events) {
    _.each(events, function (event) {
        var msg = all_msg_list.get(event.message_id);
        if (msg === undefined) {
            return;
        }

        ui.un_cache_message_content_height(msg.id);

        if (event.rendered_content !== undefined) {
            msg.content = event.rendered_content;
        }

        if (event.subject !== undefined) {
            // A topic edit may affect multiple messages, listed in
            // event.message_ids. event.message_id is still the first message
            // where the user initiated the edit.
            _.each(event.message_ids, function (id) {
                var msg = all_msg_list.get(id);
                if (msg === undefined) {
                    return;
                }

                // Remove the recent subjects entry for the old subject;
                // must be called before we update msg.subject
                process_message_for_recent_subjects(msg, true);
                // Update the unread counts; again, this must be called
                // before we update msg.subject
                unread.update_unread_subjects(msg, event);

                msg.subject = event.subject;
                msg.subject_links = event.subject_links;
                set_topic_edit_properties(msg);
                // Add the recent subjects entry for the new subject; must
                // be called after we update msg.subject
                process_message_for_recent_subjects(msg);
            });
        }

        var row = current_msg_list.get_row(event.message_id);
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

    _.each(data.events, function (event) {
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
        case 'update_message':
            messages_to_update.push(event);
            break;
        case 'realm_user':
            if (event.op === 'add') {
                add_person_in_realm(event.person);
            } else if (event.op === 'remove') {
                remove_person(event.person);
            } else if (event.op === 'update') {
                update_person(event.person);
            }
            break;
        case 'subscriptions':
            if (event.op === 'add') {
                _.each(event.subscriptions, function (subscription) {
                    $(document).trigger($.Event('subscription_add.zulip',
                                                {subscription: subscription}));
                });
            } else if (event.op === 'remove') {
                _.each(event.subscriptions, function (subscription) {
                    $(document).trigger($.Event('subscription_remove.zulip',
                                                {subscription: subscription}));
                });
            } else if (event.op === 'update') {
                subs.update_subscription_properties(event.name, event.property, event.value);
            } else if (event.op === 'peer_add' || event.op === 'peer_remove') {
                _.each(event.subscriptions, function (sub) {
                    var js_event_type;
                    if (event.op === 'peer_add') {
                        js_event_type = 'peer_subscribe.zulip';

                        stream_data.add_subscriber(sub, event.user_email);
                    } else if (event.op === 'peer_remove') {
                        js_event_type = 'peer_unsubscribe.zulip';

                        stream_data.remove_subscriber(sub, event.user_email);
                    }

                    $(document).trigger(js_event_type, {stream_name: sub,
                                                        user_email: event.user_email});
                });

            }
            break;
        case 'presence':
            var users = {};
            users[event.email] = event.presence;
            activity.set_user_statuses(users, event.server_timestamp);
            break;
        case 'referral':
            referral.update_state(event.referrals.granted, event.referrals.used);
            break;
        case 'realm_emoji':
            emoji.update_emojis(event.realm_emoji);
            break;
        case 'alert_words':
            alert_words.words = event.alert_words;
            break;
        case 'muted_topics':
            muting_ui.handle_updates(event.muted_topics);
            break;
        }
    });

    if (messages.length !== 0) {
        // There is a known bug (#1062) in our backend
        // whereby duplicate messages are delivered during a
        // server update.  Once that bug is fixed, this
        // should no longer be needed
        messages = deduplicate_messages(messages);
        messages = _.map(messages, add_message_metadata);

        if (feature_flags.summarize_read_while_narrowed) {
            _.each(messages, function (message) {
                if (message.sent_by_me) {
                    summary.maybe_mark_summarized(message);
                }
            });
        }

        // You must add add messages to home_msg_list BEFORE
        // calling process_loaded_for_unread.
        add_messages(messages, home_msg_list, true);
        add_messages(messages, all_msg_list, true);

        if (narrow.active()) {
            if (narrow.filter().can_apply_locally()) {
                add_messages(messages, narrowed_msg_list, true);
                notifications.possibly_notify_new_messages_outside_viewport(messages);
            } else {
                // if we cannot apply locally, we have to wait for this callback to happen to notify
                maybe_add_narrowed_messages(messages, narrowed_msg_list, true);
            }
        } else {
            notifications.possibly_notify_new_messages_outside_viewport(messages);
        }

        process_loaded_for_unread(messages);

        if (narrow.narrowed_by_reply()) {
            // If you send a message when narrowed to a recipient, move the
            // pointer to it.

            var i;
            var selected_id = current_msg_list.selected_id();

            // Iterate backwards to find the last message sent_by_me, stopping at
            // the pointer position.
            for (i = messages.length-1; i>=0; i--){
                var id = messages[i].id;
                if (id <= selected_id) {
                    break;
                }
                if (messages[i].sent_by_me && current_msg_list.get(id) !== undefined) {
                    // If this is a reply we just sent, advance the pointer to it.
                    current_msg_list.select_id(messages[i].id, {then_scroll: true,
                                                                from_scroll: true});
                    break;
                }
            }
        }

        process_visible_unread_messages();
        notifications.received_messages(messages);
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
    options = _.extend({dont_block: false}, options);

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
                page_params.event_queue_expired = true;
                reload.initiate({immediate: true});
            }

            if (error_type === 'abort') {
                // Don't restart if we explicitly aborted
                return;
            } else if (error_type === 'timeout') {
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

function cleanup_event_queue() {
    // Submit a request to the server to cleanup our event queue
    if (page_params.event_queue_expired === true) {
        return;
    }
    $.ajax({
        type:     'DELETE',
        url:      '/json/events',
        data:     {queue_id: page_params.event_queue_id},
        dataType: 'json'
    });
}

window.addEventListener("beforeunload", function (event) {
    cleanup_event_queue();
});

function process_result(messages, opts) {
    $('#get_old_messages_error').hide();

    if ((messages.length === 0) && (current_msg_list === narrowed_msg_list) &&
        narrowed_msg_list.empty()) {
        // Even after trying to load more messages, we have no
        // messages to display in this narrow.
        narrow.show_empty_narrow_message();
    }

    messages = _.map(messages, add_message_metadata);

    // If we're loading more messages into the home view, save them to
    // the all_msg_list as well, as the home_msg_list is reconstructed
    // from all_msg_list.
    if (opts.msg_list === home_msg_list) {
        process_loaded_for_unread(messages);
        add_messages(messages, all_msg_list, false);
    }

    if (messages.length !== 0 && !opts.cont_will_add_messages) {
        add_messages(messages, opts.msg_list, false);
    }

    stream_list.update_streams_sidebar();

    if (opts.cont !== undefined) {
        opts.cont(messages);
    }
}

function get_old_messages_success(data, opts) {
    if (waiting_on_browser_scroll) {
        setTimeout(function () {
            get_old_messages_success(data, opts);
        }, 25);
        return;
    }
    if (tutorial.is_running()) {
        // Don't actually process the messages until the tutorial is
        // finished, but do disable the loading indicator so it isn't
        // distracting in the background
        util.destroy_loading_indicator($('#page_loading_indicator'));
        tutorial.defer(function () { get_old_messages_success(data, opts); });
        return;
    }

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

    process_result(data.messages, opts);
}

function load_old_messages(opts) {
    opts = _.extend({cont_will_add_messages: false}, opts);

    var data = {anchor: opts.anchor,
                num_before: opts.num_before,
                num_after: opts.num_after};

    if (opts.msg_list.narrowed && narrow.active()) {
        data.narrow = JSON.stringify(narrow.public_operators());
    }

    $.ajax({
        type:     'POST',
        url:      '/json/get_old_messages',
        data:     data,
        dataType: 'json',
        success: function (data) {
            get_old_messages_success(data, opts);
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
                process_result([], opts);
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

function restart_get_updates(options) {
    if (get_updates_xhr !== undefined) {
        get_updates_xhr.abort();
    }

    if (get_updates_timeout !== undefined) {
        clearTimeout(get_updates_timeout);
    }

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
        // Our app's JS wasn't running, which probably means the machine was
        // asleep.
        $(document).trigger($.Event('unsuspend'));
    }
    watchdog_time = new_time;
}, 5000);

$(function () {
    $(document).on('unsuspend', function () {
        // Immediately poll for new updates on unsuspend
        get_updates_failures = 0;
        restart_get_updates({dont_block: true});
    });
});

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
                    reload.initiate({immediate: true, save_state: false});
                });
            });
        }
    });
}

function consider_bankruptcy() {
    // Until we've handled possibly declaring bankruptcy, don't show
    // unread counts since they only consider messages that are loaded
    // client side and may be different from the numbers reported by
    // the server.

    if (!page_params.furthest_read_time) {
        // We've never read a message.
        enable_unread_counts();
        return;
    }

    var now = new XDate(true).getTime() / 1000;
    if ((page_params.unread_count > 500) &&
        (now - page_params.furthest_read_time > 60 * 60 * 24 * 2)) { // 2 days.
        var unread_info = templates.render('bankruptcy_modal',
                                           {"unread_count": page_params.unread_count});
        $('#bankruptcy-unread-count').html(unread_info);
        $('#bankruptcy').modal('show');
    } else {
        enable_unread_counts();
    }
}

_.each(page_params.people_list, function (person) {
    people_dict.set(person.email, person);
    realm_people_dict.set(person.email, person);
    person.pm_recipient_count = 0;
});

// The special account feedback@zulip.com is used for in-app
// feedback and should always show up as an autocomplete option.
if (! people_dict.has('feedback@zulip.com')){
    add_person({"email": "feedback@zulip.com",
                "full_name": "Zulip Feedback Bot"});
}

function main() {
    activity.set_user_statuses(page_params.initial_presences,
                               page_params.initial_servertime);

    server_furthest_read = page_params.initial_pointer;
    if (page_params.orig_initial_pointer !== undefined &&
        page_params.orig_initial_pointer > server_furthest_read) {
        server_furthest_read = page_params.orig_initial_pointer;
    }
    furthest_read = server_furthest_read;

    // Before trying to load messages: is this user way behind?
    consider_bankruptcy();

    // We only send pointer updates when the user has been idle for a
    // short while to avoid hammering the server
    $(document).idle({idle: 1000,
                      onIdle: send_pointer_update,
                      keepTracking: true});

    $(document).on('message_selected.zulip', function (event) {

        if ((event.msg_list === home_msg_list) || (event.msg_list === all_msg_list)) {
            if (event.id > furthest_read) {
                furthest_read = event.id;
            }
        }

        if (event.mark_read && event.previously_selected !== -1) {
            // Mark messages between old pointer and new pointer as read
            var messages;
            if (event.id < event.previously_selected) {
                messages = message_range(event.msg_list, event.id, event.previously_selected);
            } else {
                messages = message_range(event.msg_list, event.previously_selected, event.id);
            }
            mark_messages_as_read(messages, {from: 'pointer'});
        }
    });

    // get the initial message list
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
}

function install_main_scroll_handler() {
    waiting_on_browser_scroll = false;
    // Unregister this special un-throttled scroll handler.
    $(window).unbind("scroll");
    // Register the normal throttled scroll handler.
    ui.register_scroll_handler();
}

$(function () {
    // On a page load or reload, the browser will, at an idle time, scroll to
    // the top of the page. We can't intercept this browser-induced scroll, so
    // to make sure it doesn't in interfere with our scrolling to the correct
    // place in your message feed, we let the browser scroll happen first.

    // After some time, if we haven't seen the browser scroll, give up
    // and call main.
    var browser_scroll_timer = setTimeout(function () {
        install_main_scroll_handler();
    }, 500);

    $(window).scroll(function () {
        if (viewport.scrollTop() < viewport.height()) {
            // This is the browser-induced scroll to the top of the
            // page that we were waiting for. It only happens once,
            // so stop waiting and call main.
            install_main_scroll_handler();
            clearTimeout(browser_scroll_timer);
        }
    });

    main();
});
