"use strict";

let last_issued_message_id = 100000;

const get_message_id = () => {
    last_issued_message_id += 1 + Math.floor(Math.random() * 10);
    return last_issued_message_id;
};

exports.make_stream_message = (opts = {}) => {
    const message_id = opts.id ?? get_message_id();

    const default_message = {
        id: message_id,
        type: "stream",
        sender_id: opts.sender_id ?? 1,
        sender_email: opts.sender_email ?? "user@example.com",
        sender_full_name: opts.sender_full_name ?? "Test User",
        content: opts.content ?? "<p>Test message</p>",
        content_type: "text/html",
        timestamp: opts.timestamp ?? Date.now(),
        stream_id: opts.stream_id ?? 1,
        display_recipient: opts.display_recipient ?? "general",
        subject: opts.subject ?? "test-topic",
        reactions: [],
        submessages: [],
        flags: [],
    };

    return {...default_message, ...opts};
};

exports.make_private_message = (opts = {}) => {
    const message_id = opts.id ?? get_message_id();

    const default_message = {
        id: message_id,
        type: "private",
        sender_id: opts.sender_id ?? 1,
        sender_email: opts.sender_email ?? "user@example.com",
        sender_full_name: opts.sender_full_name ?? "Test User",
        content: opts.content ?? "<p>Test message</p>",
        content_type: "text/html",
        timestamp: opts.timestamp ?? Date.now(),
        display_recipient: opts.display_recipient ?? [],
        reactions: [],
        submessages: [],
        flags: [],
    };

    return {...default_message, ...opts};
};
