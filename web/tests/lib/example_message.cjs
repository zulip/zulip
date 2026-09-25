"use strict";

const {zrequire} = require("./namespace.cjs");

// Generate message IDs that are random but strictly increasing.
// This ensures tests get unique IDs automatically and preserves
// ordering between messages when needed.
let last_issued_message_id = 100000;

const get_message_id = () => {
    last_issued_message_id += 1 + Math.floor(Math.random() * 10);
    return last_issued_message_id;
};

const base_message = (opts = {}) => {
    const people = zrequire("people");

    const sender_id = opts.sender_id;
    const sender = people.get_by_user_id(sender_id);

    return {
        id: opts.id ?? get_message_id(),
        sender_id,
        sender_email: sender.email,
        sender_full_name: sender.full_name,
        content: opts.content ?? "<p>Test message</p>",
        content_type: "text/html",
        timestamp: opts.timestamp ?? Date.now(),
        reactions: [],
        submessages: [],
        flags: [],
    };
};

exports.make_channel_message = (opts = {}) => {
    const stream_data = zrequire("stream_data");

    const stream_id = opts.stream_id;
    const sub = stream_data.get_sub_by_id(stream_id);

    return {
        ...base_message(opts),
        type: "stream",
        stream_id,
        display_recipient: sub.name,
        subject: opts.subject ?? "test-topic",
    };
};

exports.make_direct_message = (opts = {}) => ({
    ...base_message(opts),
    type: "private",
    display_recipient: opts.display_recipient ?? [],
});
