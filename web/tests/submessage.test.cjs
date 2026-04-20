"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");

const channel = mock_esm("../src/channel");
const message_store = mock_esm("../src/message_store");
const widgetize = mock_esm("../src/widgetize");

const submessage = zrequire("submessage");

run_test("get_message_events", () => {
    let msg = {
        submessages: [],
    };
    assert.equal(submessage.get_message_events(msg), undefined);

    const submessages = [
        {id: 222, sender_id: 99, content: '{"type":"new_option","idx":1,"option":"bar"}'},
        {
            id: 9,
            sender_id: 33,
            content: '{"widget_type": "poll", "extra_data": {"question": "foo", "options": []}}',
        },
    ];

    msg = {
        locally_echoed: true,
        submessages,
    };
    assert.equal(submessage.get_message_events(msg), undefined);

    msg = {
        submessages,
    };
    assert.deepEqual(submessage.get_message_events(msg), [
        {
            sender_id: 33,
            data: {
                widget_type: "poll",
                extra_data: {
                    question: "foo",
                    options: [],
                },
            },
        },
        {
            sender_id: 99,
            data: {
                type: "new_option",
                idx: 1,
                option: "bar",
            },
        },
    ]);
});

run_test("make_server_callback", () => {
    const message_id = 444;
    const callback = submessage.make_server_callback(message_id);
    let was_posted;

    channel.post = (opts) => {
        was_posted = true;
        assert.deepEqual(opts, {
            url: "/json/submessage",
            data: {
                message_id,
                msg_type: "whatever",
                content: '{"foo":32}',
            },
        });
    };

    callback({
        msg_type: "whatever",
        data: {foo: 32},
    });

    assert.ok(was_posted);
});

run_test("check sender", () => {
    const message_id = 101;

    const message = {
        id: message_id,
        sender_id: 1,
        submessages: [
            {
                sender_id: 2,
                content:
                    '{"widget_type": "poll", "extra_data": {"question": "foo", "options": []}}',
            },
        ],
    };

    blueslip.expect("warn", "User 2 tried to hijack message 101");

    submessage.process_submessages(message);
});

run_test("handle_event", () => {
    const message = {
        id: 42,
        submessages: [],
    };

    const event = {
        id: 11,
        msg_type: "widget",
        sender_id: 99,
        message_id: message.id,
        content: '"some_data"',
    };

    let args;
    let post_to_server;
    widgetize.handle_event = (opts) => {
        args = opts;
        post_to_server = opts.post_to_server;
    };

    message_store.get = (msg_id) => {
        assert.equal(msg_id, message.id);
        return message;
    };

    submessage.handle_event(event);

    assert.ok(post_to_server);
    assert.deepEqual(args, {
        sender_id: 99,
        message: {
            id: message.id,
            submessages: [event],
        },
        post_to_server,
        data: "some_data",
    });

    assert.deepEqual(message.submessages[0], event);
});

run_test("is_poll_message", () => {
    // Empty submessages
    assert.equal(submessage.is_poll_message({submessages: []}), false);

    // Poll message
    assert.equal(
        submessage.is_poll_message({submessages: [{content: '{"widget_type": "poll"}'}]}),
        true,
    );

    // Non-poll widget
    assert.equal(
        submessage.is_poll_message({submessages: [{content: '{"widget_type": "todo"}'}]}),
        false,
    );

    // Invalid JSON
    assert.equal(submessage.is_poll_message({submessages: [{content: "INVALID"}]}), false);
});

run_test("is_widget_edited", () => {
    // Poll with no edits (only creation submessage)
    let message = {
        submessages: [{content: '{"widget_type": "poll"}'}],
    };
    assert.equal(submessage.is_widget_edited(message), false);
    assert.equal(message.has_widget_edits, false);

    // Poll with new_option edit
    message = {
        submessages: [{content: '{"widget_type": "poll"}'}, {content: '{"type": "new_option"}'}],
    };
    assert.equal(submessage.is_widget_edited(message), true);
    assert.equal(message.has_widget_edits, true);

    // Poll with question edit
    message = {
        submessages: [{content: '{"widget_type": "poll"}'}, {content: '{"type": "question"}'}],
    };
    assert.equal(submessage.is_widget_edited(message), true);
    assert.equal(message.has_widget_edits, true);

    // Poll with only votes (not an edit)
    message = {
        submessages: [{content: '{"widget_type": "poll"}'}, {content: '{"type": "vote"}'}],
    };
    assert.equal(submessage.is_widget_edited(message), false);
    assert.equal(message.has_widget_edits, false);

    // Caching: once set, returns cached value without re-parsing
    message.has_widget_edits = true;
    assert.equal(submessage.is_widget_edited(message), true);

    // Empty submessages
    message = {submessages: []};
    assert.equal(submessage.is_widget_edited(message), false);

    // Non-poll widget is not considered edited
    message = {
        submessages: [{content: '{"widget_type": "todo"}'}, {content: '{"type": "new_task"}'}],
    };
    assert.equal(submessage.is_widget_edited(message), false);

    // Malformed JSON in subsequent submessages is skipped
    message = {
        submessages: [{content: '{"widget_type": "poll"}'}, {content: "INVALID JSON"}],
    };
    assert.equal(submessage.is_widget_edited(message), false);
});
