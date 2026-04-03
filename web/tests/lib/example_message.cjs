"use strict";

// Generate message IDs that are random but strictly increasing.
// This ensures tests get unique IDs automatically and preserves
// ordering between messages when needed.
let last_issued_message_id = 100000;

const get_message_id = () => {
    last_issued_message_id += 1 + Math.floor(Math.random() * 10);
    return last_issued_message_id;
};

const base_message = (opts = {}) => {
    const message_id = opts.id ?? get_message_id();

    return {
        id: message_id,
        sender_id: opts.sender_id ?? 1,
        sender_email: opts.sender_email ?? "user@example.com",
        sender_full_name: opts.sender_full_name ?? "Test User",
        content: opts.content ?? "<p>Test message</p>",
        content_type: "text/html",
        timestamp: opts.timestamp ?? Date.now(),
        reactions: [],
        submessages: [],
        flags: [],
    };
};

exports.make_stream_message = (opts = {}) => ({
    ...base_message(opts),
    type: "stream",
    stream_id: opts.stream_id ?? 1,
    display_recipient: opts.display_recipient ?? "general",
    subject: opts.subject ?? "test-topic",
});

exports.make_private_message = (opts = {}) => ({
    ...base_message(opts),
    type: "private",
    display_recipient: opts.display_recipient ?? [],
});
