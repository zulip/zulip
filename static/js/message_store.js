var message_store = (function () {

var exports = {};
var stored_messages = {};

exports.recent_private_messages = [];

exports.get = function get(message_id) {
    return stored_messages[message_id];
};

exports.get_pm_emails = function (message) {
    var recipient;
    var i;
    var other_recipients = _.filter(message.display_recipient,
                                  function (element) {
                                      return !people.is_current_user(element.email);
                                  });
    if (other_recipients.length === 0) {
        // private message with oneself
        return message.display_recipient[0].email;
    }

    recipient = other_recipients[0].email;

    for (i = 1; i < other_recipients.length; i += 1) {
        var email = other_recipients[i].email;
        recipient += ', ' + email;
    }
    return recipient;
};

exports.get_pm_full_names = function (message) {
    function name(recip) {
        if (recip.id) {
            var person = people.get_person_from_user_id(recip.id);
            if (person) {
                return person.full_name;
            }
        }
        return recip.full_name;
    }

    var other_recipients = _.filter(message.display_recipient,
                                  function (element) {
                                      return !people.is_current_user(element.email);
                                  });

    if (other_recipients.length === 0) {
        // private message with oneself
        return name(message.display_recipient[0]);
    }

    var names = _.map(other_recipients, name).sort();

    return names.join(', ');
};

exports.process_message_for_recent_private_messages = function (message) {
    var current_timestamp = 0;

    var user_ids = people.pm_with_user_ids(message);
    if (!user_ids) {
        return;
    }

    var user_ids_string = user_ids.join(',');

    if (!user_ids_string) {
        blueslip.warn('Unknown reply_to in message: ' + user_ids_string);
        return;
    }

    // If this conversation is already tracked, we'll replace with new timestamp,
    // so remove it from the current list.
    exports.recent_private_messages = _.filter(exports.recent_private_messages,
                                               function (recent_pm) {
        return recent_pm.user_ids_string !== user_ids_string;
    });

    var new_conversation = {user_ids_string: user_ids_string,
                            timestamp: Math.max(message.timestamp, current_timestamp)};

    exports.recent_private_messages.push(new_conversation);
    exports.recent_private_messages.sort(function (a, b) {
        return b.timestamp - a.timestamp;
    });
};

exports.set_topic_edit_properties = function (message) {
    message.always_visible_topic_edit = false;
    message.on_hover_topic_edit = false;
    if (!page_params.realm_allow_message_editing) {
        return;
    }

    // Messages with no topics should always have an edit icon visible
    // to encourage updating them. Admins can also edit any topic.
    if (message.subject === compose.empty_topic_placeholder()) {
        message.always_visible_topic_edit = true;
    } else if (page_params.is_admin) {
        message.on_hover_topic_edit = true;
    }
};

exports.add_message_metadata = function (message) {
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

    message.sent_by_me = people.is_current_user(message.sender_email);

    message.flags = message.flags || [];
    message.historical = (message.flags !== undefined &&
                          message.flags.indexOf('historical') !== -1);
    message.starred = message.flags.indexOf("starred") !== -1;
    message.mentioned = message.flags.indexOf("mentioned") !== -1 ||
                        message.flags.indexOf("wildcard_mentioned") !== -1;
    message.mentioned_me_directly = message.flags.indexOf("mentioned") !== -1;
    message.collapsed = message.flags.indexOf("collapsed") !== -1;
    message.alerted = message.flags.indexOf("has_alert_word") !== -1;
    message.is_me_message = message.flags.indexOf("is_me_message") !== -1;

    people.extract_people_from_message(message);

    var sender = people.get_person_from_user_id(message.sender_id);
    if (sender) {
        message.sender_full_name = sender.full_name;
        message.sender_email = sender.email;
    }

    switch (message.type) {
    case 'stream':
        message.is_stream = true;
        message.stream = message.display_recipient;
        composebox_typeahead.add_topic(message.stream, message.subject);
        message.reply_to = message.sender_email;

        stream_data.process_message_for_recent_topics(message);
        exports.set_topic_edit_properties(message);
        break;

    case 'private':
        message.is_private = true;
        message.reply_to = util.normalize_recipients(
                exports.get_pm_emails(message));
        message.display_reply_to = exports.get_pm_full_names(message);
        message.pm_with_url = people.pm_with_url(message);
        message.to_user_ids = people.emails_strings_to_user_ids_string(
                message.reply_to);

        exports.process_message_for_recent_private_messages(message);
        break;
    }

    alert_words.process_message(message);
    if (!message.reactions) {
        message.reactions = [];
    }
    stored_messages[message.id] = message;
    return message;
};

exports.clear = function clear() {
    this.stored_messages = {};
};

util.execute_early(function () {
    $(document).on('message_id_changed', function (event) {
        var old_id = event.old_id;
        var new_id = event.new_id;
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
