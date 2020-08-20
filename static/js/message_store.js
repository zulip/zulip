"use strict";

const people = require("./people");
const pm_conversations = require("./pm_conversations");
const util = require("./util");

const stored_messages = new Map();

/*
    We keep a set of user_ids for all people
    who have sent stream messages or who have
    been on PMs sent by the user.

    We will use this in search to prevent really
    large result sets for realms that have lots
    of users who haven't sent messages recently.

    We'll likely eventually want to replace this with
    accessing some combination of data from recent_senders
    and pm_conversations for better accuracy.
*/
const message_user_ids = new Set();

exports.user_ids = function () {
    return Array.from(message_user_ids);
};

exports.get = function get(message_id) {
    if (message_id === undefined || message_id === null) {
        blueslip.error("message_store.get got bad value: " + message_id);
        return;
    }

    if (typeof message_id !== "number") {
        blueslip.error("message_store got non-number: " + message_id);

        // Try to soldier on, assuming the caller treats message
        // ids as strings.
        message_id = parseFloat(message_id);
    }

    return stored_messages.get(message_id);
};

exports.each = function (f) {
    stored_messages.forEach(f);
};

exports.get_pm_emails = function (message) {
    function email(user_id) {
        const person = people.get_by_user_id(user_id);
        if (!person) {
            blueslip.error("Unknown user id " + user_id);
            return "?";
        }
        return person.email;
    }

    const user_ids = people.pm_with_user_ids(message);
    const emails = user_ids.map(email).sort();

    return emails.join(", ");
};

exports.get_pm_full_names = function (message) {
    function name(user_id) {
        const person = people.get_by_user_id(user_id);
        if (!person) {
            blueslip.error("Unknown user id " + user_id);
            return "?";
        }
        return person.full_name;
    }

    const user_ids = people.pm_with_user_ids(message);
    const names = user_ids.map(name).sort();

    return names.join(", ");
};

exports.process_message_for_recent_private_messages = function (message) {
    const user_ids = people.pm_with_user_ids(message);
    if (!user_ids) {
        return;
    }

    for (const user_id of user_ids) {
        pm_conversations.set_partner(user_id);
    }

    pm_conversations.recent.insert(user_ids, message.id);
};

exports.set_message_booleans = function (message) {
    const flags = message.flags || [];

    function convert_flag(flag_name) {
        return flags.includes(flag_name);
    }

    message.unread = !convert_flag("read");
    message.historical = convert_flag("historical");
    message.starred = convert_flag("starred");
    message.mentioned = convert_flag("mentioned") || convert_flag("wildcard_mentioned");
    message.mentioned_me_directly = convert_flag("mentioned");
    message.collapsed = convert_flag("collapsed");
    message.alerted = convert_flag("has_alert_word");

    // Once we have set boolean flags here, the `flags` attribute is
    // just a distraction, so we delete it.  (All the downstream code
    // uses booleans.)
    delete message.flags;
};

exports.init_booleans = function (message) {
    // This initializes booleans for the local-echo path where
    // we don't have flags from the server yet.  (We want to
    // explicitly set flags to false to be consistent with other
    // codepaths.)
    message.unread = false;
    message.historical = false;
    message.starred = false;
    message.mentioned = false;
    message.mentioned_me_directly = false;
    message.collapsed = false;
    message.alerted = false;
};

exports.update_booleans = function (message, flags) {
    // When we get server flags for local echo or message edits,
    // we are vulnerable to race conditions, so only update flags
    // that are driven by message content.
    function convert_flag(flag_name) {
        return flags.includes(flag_name);
    }

    message.mentioned = convert_flag("mentioned") || convert_flag("wildcard_mentioned");
    message.mentioned_me_directly = convert_flag("mentioned");
    message.alerted = convert_flag("has_alert_word");
};

exports.add_message_metadata = function (message) {
    const cached_msg = stored_messages.get(message.id);
    if (cached_msg !== undefined) {
        // Copy the match topic and content over if they exist on
        // the new message
        if (util.get_match_topic(message) !== undefined) {
            util.set_match_data(cached_msg, message);
        }
        return cached_msg;
    }

    message.sent_by_me = people.is_current_user(message.sender_email);

    people.extract_people_from_message(message);
    people.maybe_incr_recipient_count(message);

    const sender = people.get_by_user_id(message.sender_id);
    if (sender) {
        message.sender_full_name = sender.full_name;
        message.sender_email = sender.email;
    }

    // Convert topic even for PMs, as legacy code
    // wants the empty field.
    util.convert_message_topic(message);

    switch (message.type) {
        case "stream":
            message.is_stream = true;
            message.stream = message.display_recipient;
            message.reply_to = message.sender_email;

            stream_topic_history.add_message({
                stream_id: message.stream_id,
                topic_name: message.topic,
                message_id: message.id,
            });

            recent_senders.process_message_for_senders(message);
            message_user_ids.add(message.sender_id);
            break;

        case "private":
            message.is_private = true;
            message.reply_to = util.normalize_recipients(exports.get_pm_emails(message));
            message.display_reply_to = exports.get_pm_full_names(message);
            message.pm_with_url = people.pm_with_url(message);
            message.to_user_ids = people.pm_reply_user_string(message);

            exports.process_message_for_recent_private_messages(message);

            if (people.is_my_user_id(message.sender_id)) {
                for (const recip of message.display_recipient) {
                    message_user_ids.add(recip.id);
                }
            }
            break;
    }

    alert_words.process_message(message);
    if (!message.reactions) {
        message.reactions = [];
    }
    stored_messages.set(message.id, message);
    return message;
};

exports.update_property = function (property, value, info) {
    switch (property) {
        case "sender_full_name":
        case "small_avatar_url":
            exports.each((msg) => {
                if (msg.sender_id && msg.sender_id === info.user_id) {
                    msg[property] = value;
                }
            });
            break;
        case "stream_name":
            exports.each((msg) => {
                if (msg.stream_id && msg.stream_id === info.stream_id) {
                    msg.display_recipient = value;
                    msg.stream = value;
                }
            });
            break;
    }
};

exports.reify_message_id = function (opts) {
    const old_id = opts.old_id;
    const new_id = opts.new_id;
    if (stored_messages.has(old_id)) {
        stored_messages.set(new_id, stored_messages.get(old_id));
        stored_messages.delete(old_id);
    }

    for (const msg_list of [message_list.all, home_msg_list, message_list.narrowed]) {
        if (msg_list !== undefined) {
            msg_list.change_message_id(old_id, new_id);

            if (msg_list.view !== undefined) {
                msg_list.view.change_message_id(old_id, new_id);
            }
        }
    }
};

window.message_store = exports;
