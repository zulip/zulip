"use strict";

function gen_random_int() {
    return Math.floor(Math.random() * 1000 + 1);
}

const stream_id = gen_random_int();
const recipient_id = gen_random_int() + stream_id;

let prev_sender_id = 100;
let prev_msg_id = 10000;
let prev_timestamp = 10000000;

function create_next_sender_id() {
    prev_sender_id += 1;
    return prev_sender_id;
}

function create_next_msg_id() {
    prev_msg_id += 1;
    return prev_msg_id;
}

function create_next_timestamp() {
    // a random time interval of 50ms b/w two messages.
    prev_timestamp += 50;
    return prev_timestamp;
}

function create_stream_id() {
    return stream_id;
}

function create_recipient_id() {
    return recipient_id;
}

function create_user(sender_id = create_next_sender_id()) {
    const user = {
        email: `user${sender_id}@example.org`,
        id: sender_id,
        full_name: `user_${sender_id}`,
        is_mirror_dummy: false,
    };
    return user;
}

function create_pm_display_recip(sender_id) {
    const recipient = create_user(sender_id);

    return recipient;
}

function create_reaction(details) {
    const {type, sender_id = gen_random_int()} = details;

    let reaction;

    switch (type) {
        case "unicode_emoji": {
            reaction = {
                emoji_name: "+1",
                emoji_code: "1f44d",
                reaction_type: "unicode_emoji",
                user: create_user(sender_id),
                user_id: sender_id,
            };

            break;
        }
        case "realm_emoji": {
            reaction = {
                emoji_name: "thank_you",
                emoji_code: "133",
                reaction_type: "realm_emoji",
                user: create_user(sender_id),
                user_id: sender_id,
            };
            break;
        }

        case "zulip_extra_emoji": {
            reaction = {
                emoji_name: "zulip",
                emoji_code: "zulip",
                reaction_type: "zulip_extra_emoji",
                user: create_user(sender_id),
                user_id: sender_id,
            };
            break;
        }

        default:
            reaction = {};
    }

    return reaction;
}

function create_submessage(details) {
    const {type, content, message_id, sender_id, id} = details;

    const submessage = {
        msg_type: type,
        content: content ?? "<p>(submessage content)</p>",
        message_id: message_id ?? prev_msg_id,
        sender_id: sender_id ?? create_next_sender_id(),
        id: id ?? create_next_msg_id(),
    };

    return submessage;
}

function create_topic_link(text) {
    return {
        text,
        url: `https://${text}expanded_url@example`,
    };
}

function msg_base_props(base_props) {
    return {
        edit_history: base_props.edit_history,
        last_edit_timestamp: base_props.last_edit_timestamp,
        reactions: base_props.reactions ?? [],
        submessages: base_props.submessages ?? [],
        is_me_message: base_props.is_me_message ?? false,
        topic_links: base_props.topic_links ?? [],
        flags: base_props.flags ?? [],
    };
}

function msg_sender_props(sender) {
    // this will return object containing fields related to sender.

    const {
        sender_id = create_next_sender_id(),
        sender_email,
        sender_full_name,
        sender_realm_str,
        avatar_url,
        client,
    } = sender;

    return {
        client: client ?? "website",
        avatar_url: avatar_url ?? "https://avatar_provider/${sender_id}?version=1",
        sender_id,
        sender_email: sender_email ?? `user${sender_id}@example.org`,
        sender_full_name: sender_full_name ?? `user_${sender_id}`,
        sender_realm_str: sender_realm_str ?? "example",
    };
}

let topic_count = 1;
function msg_stream_props(stream_details) {
    // this will return object with fields exclusive to a "stream" message.
    const {stream_id, subject, display_recipient, recipient_id} = stream_details;
    topic_count += 1;
    return {
        stream_id,
        subject: subject ?? `topic:${topic_count}`,
        display_recipient: display_recipient ?? `channel:${stream_id}`,
        recipient_id: recipient_id ?? create_recipient_id(),
    };
}

function msg_pm_props(pm_details) {
    // this will return object with fields exclusive to a "private/dm" message

    const {display_recipient, recipient_id, sender_id} = pm_details;

    return {
        subject: "",
        display_recipient: display_recipient ?? [
            create_pm_display_recip(sender_id),
            create_pm_display_recip(create_next_sender_id()),
        ],
        recipient_id: recipient_id ?? create_recipient_id(),
    };
}

function make_private_server_msg(opts = {}) {
    // create private messages
    const sender_id = opts.sender_id ?? create_next_sender_id();
    const message_id = opts.id ?? create_next_msg_id();

    const base_props = {
        edit_history: opts.edit_history,
        last_edit_timestamp: opts.last_edit_timestamp,
        submessages: opts.submessages,
        reactions: opts.reactions,
        is_me_message: opts.is_me_message,
        topic_links: opts.topic_links,
        flags: opts.flags,
    };

    const sender = {
        sender_id,
        avatar_url: opts.avatar_url,
        client: opts.client,
        sender_full_name: opts.sender_full_name,
        sender_email: opts.sender_email,
        sender_realm_str: opts.sender_realm_str,
    };

    const pm_details = {
        display_recipient: opts.display_recipient,
        sender_id,
        recipient_id: opts.recipient_id,
    };

    return {
        ...msg_base_props(base_props),
        ...msg_sender_props(sender),
        ...msg_pm_props(pm_details),
        id: message_id,
        content: opts.content ?? "<p>(message content)</p>",
        content_type: opts.content_type ?? "text/html",
        timestamp: opts.timestamp ?? create_next_timestamp(),
        type: "private",
        local_id: opts.local_id,
    };
}

function make_stream_server_msg(opts = {}) {
    const sender_id = opts.sender_id ?? create_next_sender_id();
    const message_id = opts.id ?? create_next_msg_id();
    const stream_id = opts.stream_id ?? create_stream_id();

    const base_props = {
        edit_history: opts.edit_history,
        last_edit_timestamp: opts.last_edit_timestamp,
        submessages: opts.submessages,
        reactions: opts.reactions,
        is_me_message: opts.is_me_message,
        topic_links: opts.topic_links,
        flags: opts.flags,
    };

    const sender = {
        sender_id,
        avatar_url: opts.avatar_url,
        client: opts.client,
        sender_full_name: opts.sender_full_name,
        sender_email: opts.sender_email,
        sender_realm_str: opts.sender_realm_str,
    };

    const stream_details = {
        stream_id,
        subject: opts.subject,
        display_recipient: opts.display_recipient,
        recipient_id: opts.recipient_id,
    };

    return {
        ...msg_base_props(base_props),
        ...msg_sender_props(sender),
        ...msg_stream_props(stream_details),
        id: message_id,
        content: opts.content ?? "<p>(message content)</p>",
        content_type: opts.content_type ?? "text/html",
        timestamp: opts.timestamp ?? create_next_timestamp(),
        type: "stream",
        local_id: opts.local_id,
    };
}

exports.make_private_server_msg = make_private_server_msg;
exports.make_stream_server_msg = make_stream_server_msg;
exports.create_pm_display_recip = create_pm_display_recip;
exports.create_reaction = create_reaction;
exports.create_submessage = create_submessage;
exports.create_topic_link = create_topic_link;
