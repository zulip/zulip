var message_store = (function () {

var exports = {};
var stored_messages = {};

var load_more_enabled = true;
// If the browser hasn't scrolled away from the top of the page
// since the last time that we ran load_more_messages(), we do
// not load_more_messages().

// used for our URL rewriting in insert_new_messages
var humbug_images_re = new RegExp("https://humbug-user-uploads.s3.amazonaws.com/([^\"]+)", 'g');
exports.recent_private_messages = [];

exports.get = function get(message_id) {
    return stored_messages[message_id];
};

exports.get_private_message_recipient = function (message, attr, fallback_attr) {
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
    if (recipient === undefined && fallback_attr !== undefined) {
        recipient = other_recipients[0][fallback_attr];
    }
    for (i = 1; i < other_recipients.length; i++) {
        var attr_value = other_recipients[i][attr];
        if (attr_value === undefined && fallback_attr !== undefined) {
            attr_value = other_recipients[i][fallback_attr];
        }
        recipient += ', ' + attr_value;
    }
    return recipient;
};

exports.process_message_for_recent_subjects = function process_message_for_recent_subjects(message, remove_message) {
    var current_timestamp = 0;
    var count = 0;
    var stream = message.stream;
    var canon_subject = stream_data.canonicalized_name(message.subject);

    if (! stream_data.recent_subjects.has(stream)) {
        stream_data.recent_subjects.set(stream, []);
    } else {
        stream_data.recent_subjects.set(stream, _.filter(stream_data.recent_subjects.get(stream), function (item) {
            var is_duplicate = (item.canon_subject.toLowerCase() === canon_subject.toLowerCase());
            if (is_duplicate) {
                current_timestamp = item.timestamp;
                count = item.count;
            }
            return !is_duplicate;
        }));
    }

    var recents = stream_data.recent_subjects.get(stream);

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

    stream_data.recent_subjects.set(stream, recents);
};

exports.process_message_for_recent_private_messages = function process_message_for_recent_private_messages(message, remove_message) {
    var current_timestamp = 0;

    // If this conversation is already tracked, we'll replace with new timestamp,
    // so remove it from the current list.
    exports.recent_private_messages = _.filter(exports.recent_private_messages, function (recent_pm) {
        return recent_pm.reply_to !== message.reply_to;
    });

    var new_conversation = {reply_to: message.reply_to,
                            display_reply_to: message.display_reply_to,
                            timestamp: Math.max(message.timestamp, current_timestamp)};

    exports.recent_private_messages.push(new_conversation);
    exports.recent_private_messages.sort(function (a, b) {
        return b.timestamp - a.timestamp;
    });
};

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

function add_message_metadata(message) {
    var cached_msg = stored_messages[message.id];
    if (cached_msg !== undefined) {
        // Copy the match subject and content over if they exist on
        // the new message
        if (message.match_subject !== undefined) {
            cached_msg.match_subject = message.match_subject;
            cached_msg.match_content = message.match_content;
        }
        return cached_msg;
    }

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
    message.is_me_message = message.flags.indexOf("is_me_message") !== -1;

    switch (message.type) {
    case 'stream':
        message.is_stream = true;
        message.stream = message.display_recipient;
        composebox_typeahead.add_topic(message.stream, message.subject);
        message.reply_to = message.sender_email;

        exports.process_message_for_recent_subjects(message);

        involved_people = [{'full_name': message.sender_full_name,
                            'email': message.sender_email}];
        set_topic_edit_properties(message);
        break;

    case 'private':
        message.is_private = true;
        message.reply_to = util.normalize_recipients(
                exports.get_private_message_recipient(message, 'email'));
        message.display_reply_to = exports.get_private_message_recipient(message, 'full_name', 'email');

        exports.process_message_for_recent_private_messages(message);
        involved_people = message.display_recipient;
        break;
    }

    // Add new people involved in this message to the people list
    _.each(involved_people, function (person) {
        // Do the hasOwnProperty() call via the prototype to avoid problems
        // with keys like "hasOwnProperty"
        if (! people.get_by_email(person.email)) {
            people.add(person);
        }

        if (people.get_by_email(person.email).full_name !== person.full_name) {
            people.reify(person);
        }

        if (message.type === 'private' && message.sent_by_me) {
            // Track the number of PMs we've sent to this person to improve autocomplete
            people.get_by_email(person.email).pm_recipient_count += 1;
        }
    });

    alert_words.process_message(message);
    stored_messages[message.id] = message;
    return message;
}

exports.add_messages = function add_messages(messages, msg_list, opts) {
    if (!messages) {
        return;
    }

    opts = _.extend({messages_are_new: false, delay_render: false}, opts);

    _.each(messages, function (msg) {
        msg.content = msg.content.replace(humbug_images_re, "/user_uploads/unk/$1");
    });

    loading.destroy_indicator($('#page_loading_indicator'));
    $('#first_run_message').remove();

    msg_list.add_messages(messages, opts);

    if (msg_list === home_msg_list && opts.messages_are_new) {
        _.each(messages, function (message) {
            if (message.local_id === undefined) {
                compose.report_as_received(message);
            }
        });
    }
};

function maybe_add_narrowed_messages(messages, msg_list, messages_are_new) {
    var ids = [];
    _.each(messages, function (elem) {
        ids.push(elem.id);
    });

    channel.post({
        url:      '/json/messages_in_narrow',
        idempotent: true,
        data:     {msg_ids: JSON.stringify(ids),
                   narrow:  JSON.stringify(narrow.public_operators())},
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
            exports.add_messages(new_messages, msg_list, {messages_are_new: messages_are_new});
            unread.process_visible();
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

exports.update_messages = function update_messages(events) {
    var msgs_to_rerender = [];
    var topic_edited = false;
    var changed_narrow = false;

    _.each(events, function (event) {
        var msg = stored_messages[event.message_id];
        if (msg === undefined) {
            return;
        }
        msgs_to_rerender.push(msg);

        msg.alerted = event.flags.indexOf("has_alert_word") !== -1;
        msg.mentioned = event.flags.indexOf("mentioned") !== -1 ||
                        event.flags.indexOf("wildcard_mentioned") !== -1;

        condense.un_cache_message_content_height(msg.id);

        if (event.rendered_content !== undefined) {
            msg.content = event.rendered_content;
        }

        var row = current_msg_list.get_row(event.message_id);
        if (row.length > 0) {
            message_edit.end(row);
        }

        if (event.subject !== undefined) {
            // A topic edit may affect multiple messages, listed in
            // event.message_ids. event.message_id is still the first message
            // where the user initiated the edit.
            topic_edited = true;

            var going_forward_change = _.indexOf(['change_later', 'change_all'], event.propagate_mode) >= 0;

            var stream_name = stream_data.get_sub_by_id(event.stream_id).name;
            var compose_stream_name = compose.stream_name();

            if (going_forward_change && stream_name && compose_stream_name) {
                if (stream_name.toLowerCase() === compose_stream_name.toLowerCase()) {
                    if (event.orig_subject === compose.subject()) {
                        compose.subject(event.subject);
                    }
                }
            }

            if (going_forward_change) {
                var current_id = current_msg_list.selected_id();
                var selection_changed_topic = _.indexOf(event.message_ids, current_id) >= 0;

                if (selection_changed_topic) {
                    var current_filter = narrow.filter();
                    if (current_filter && stream_name) {
                        if (current_filter.has_topic(stream_name, event.orig_subject)) {
                            var new_filter = current_filter.filter_with_new_topic(event.subject);
                            var operators = new_filter.operators();
                            var opts = {
                                trigger: 'topic change',
                                then_select_id: current_id
                            };
                            narrow.activate(operators, opts);
                            changed_narrow = true;
                        }
                    }
                }
            }

            _.each(event.message_ids, function (id) {
                var msg = message_store.get(id);
                if (msg === undefined) {
                    return;
                }

                // Remove the recent subjects entry for the old subject;
                // must be called before we update msg.subject
                exports.process_message_for_recent_subjects(msg, true);
                // Update the unread counts; again, this must be called
                // before we update msg.subject
                unread.update_unread_subjects(msg, event);

                msg.subject = event.subject;
                msg.subject_links = event.subject_links;
                set_topic_edit_properties(msg);
                // Add the recent subjects entry for the new subject; must
                // be called after we update msg.subject
                exports.process_message_for_recent_subjects(msg);
            });
        }

        msg.last_edit_timestamp = event.edit_timestamp;
        delete msg.last_edit_timestr;

        notifications.received_messages([msg]);
        alert_words.process_message(msg);
    });

    // If a topic was edited, we re-render the whole view to get any propagated edits
    // to be updated
    if (topic_edited) {
        if (!changed_narrow) {
            home_msg_list.rerender();
            if (current_msg_list === message_list.narrowed) {
                message_list.narrowed.rerender();
            }
        }
    } else {
        home_msg_list.view.rerender_messages(msgs_to_rerender);
        if (current_msg_list === message_list.narrowed) {
            message_list.narrowed.view.rerender_messages(msgs_to_rerender);
        }
    }
    unread.update_unread_counts();
    stream_list.update_streams_sidebar();
    stream_list.update_private_messages();
};

exports.insert_new_messages = function insert_new_messages(messages) {
    messages = _.map(messages, add_message_metadata);

    // You must add add messages to home_msg_list BEFORE
    // calling unread.process_loaded_messages.
    exports.add_messages(messages, home_msg_list, {messages_are_new: true});
    exports.add_messages(messages, message_list.all, {messages_are_new: true});

    if (narrow.active()) {
        if (narrow.filter().can_apply_locally()) {
            exports.add_messages(messages, message_list.narrowed, {messages_are_new: true});
            notifications.possibly_notify_new_messages_outside_viewport(messages);
        } else {
            // if we cannot apply locally, we have to wait for this callback to happen to notify
            maybe_add_narrowed_messages(messages, message_list.narrowed, true);
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
        for (i = messages.length-1; i>=0; i--) {
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

    unread.process_visible();
    notifications.received_messages(messages);
    stream_list.update_streams_sidebar();
    stream_list.update_private_messages();
};

function process_result(messages, opts) {
    $('#get_old_messages_error').hide();

    if ((messages.length === 0) && (current_msg_list === message_list.narrowed) &&
        message_list.narrowed.empty()) {
        // Even after trying to load more messages, we have no
        // messages to display in this narrow.
        narrow.show_empty_narrow_message();
    }

    messages = _.map(messages, add_message_metadata);

    // If we're loading more messages into the home view, save them to
    // the message_list.all as well, as the home_msg_list is reconstructed
    // from message_list.all.
    if (opts.msg_list === home_msg_list) {
        process_loaded_for_unread(messages);
        exports.add_messages(messages, message_list.all, {messages_are_new: false});
    }

    if (messages.length !== 0 && !opts.cont_will_add_messages) {
        exports.add_messages(messages, opts.msg_list, {messages_are_new: false});
    }

    stream_list.update_streams_sidebar();
    stream_list.update_private_messages();

    if (opts.cont !== undefined) {
        opts.cont(messages);
    }
}

function get_old_messages_success(data, opts) {
    if (tutorial.is_running()) {
        // Don't actually process the messages until the tutorial is
        // finished, but do disable the loading indicator so it isn't
        // distracting in the background
        loading.destroy_indicator($('#page_loading_indicator'));
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
            exports.load_old_messages(opts);
        }, 0);
        return;
    }

    process_result(data.messages, opts);
    resize.resize_bottom_whitespace();
}

exports.load_old_messages = function load_old_messages(opts) {
    opts = _.extend({cont_will_add_messages: false}, opts);

    var data = {anchor: opts.anchor,
                num_before: opts.num_before,
                num_after: opts.num_after};

    if (opts.msg_list.narrowed && narrow.active()) {
        var operators = narrow.public_operators();
        if (page_params.narrow !== undefined) {
            operators = operators.concat(page_params.narrow);
        }
        data.narrow = JSON.stringify(operators);
    }
    if (opts.msg_list === home_msg_list && page_params.narrow_stream !== undefined) {
        data.narrow = JSON.stringify(page_params.narrow);
    }
    if (opts.use_first_unread_anchor) {
        data.use_first_unread_anchor = true;
    }

    channel.get({
        url:      '/json/messages',
        data:     data,
        idempotent: true,
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
                exports.load_old_messages(opts);
            }, 5000);
        }
    });
};

exports.reset_load_more_status = function reset_load_more_status() {
    load_more_enabled = true;
    ui.have_scrolled_away_from_top = true;
    ui.hide_loading_more_messages_indicator();
};

exports.load_more_messages = function load_more_messages(msg_list) {
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
    exports.load_old_messages({
        anchor: oldest_message_id.toFixed(),
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
};

exports.clear = function clear() {
    this.stored_messages = {};
};

util.execute_early(function () {
    // get the initial message list
    function load_more(messages) {

        // If we received the initially selected message, select it on the client side,
        // but not if the user has already selected another one during load.
        //
        // We fall back to the closest selected id, as the user may have removed
        // a stream from the home before already
        if (home_msg_list.selected_id() === -1 && !home_msg_list.empty()) {
            home_msg_list.select_id(page_params.initial_pointer,
                                    {then_scroll: true, use_closest: true,
                                     target_scroll_offset: page_params.initial_offset});
        }

        // catch the user up
        if (messages.length !== 0) {
            var latest_id = messages[messages.length-1].id;
            if (latest_id < page_params.max_message_id) {
                exports.load_old_messages({
                    anchor: latest_id.toFixed(),
                    num_before: 0,
                    num_after: 400,
                    msg_list: home_msg_list,
                    cont: load_more
                });
                return;
            }
        }

        server_events.home_view_loaded();

        // backfill more messages after the user is idle
        var backfill_batch_size = 1000;
        $(document).idle({'idle': 1000*10,
                          'onIdle': function () {
                              var first_id = message_list.all.first().id;
                              exports.load_old_messages({
                                  anchor: first_id,
                                  num_before: backfill_batch_size,
                                  num_after: 0,
                                  msg_list: home_msg_list
                              });
                          }});
    }

    if (page_params.have_initial_messages) {
        exports.load_old_messages({
            anchor: page_params.initial_pointer,
            num_before: 200,
            num_after: 200,
            msg_list: home_msg_list,
            cont: load_more
        });
    } else {
        server_events.home_view_loaded();
    }

    $(document).on('message_id_changed', function (event) {
        var old_id = event.old_id, new_id = event.new_id;
        if (pointer.furthest_read === old_id) {
            pointer.furthest_read = new_id;
        }
        if (stored_messages[old_id]) {
            stored_messages[new_id] = stored_messages[old_id];
            delete stored_messages[old_id];
        }

        // This handler cannot be in the MessageList constructor, which is the logical place
        // If it's there, the event handler creates a closure with a reference to the message
        // list itself. When narrowing, the old narrow message list is discarded and a new one
        // created, but due to the closure, the old list is not garbage collected. This also leads
        // to the old list receiving the change id events, and throwing errors as it does not
        // have the messages that you would expect in its internal data structures.
        _.each([message_list.all, home_msg_list, message_list.narrowed], function (msg_list) {
            if (msg_list !== undefined) {
                msg_list.change_message_id(old_id, new_id);

                if (msg_list.view !== undefined) {
                    msg_list.view.change_message_id(old_id, new_id);
                }
            }
        });
    });
});

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = message_store;
}
