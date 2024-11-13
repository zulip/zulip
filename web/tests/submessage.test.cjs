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
    let msg = {};

    assert.equal(submessage.get_message_events(msg), undefined);

    msg = {
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

run_test("check sender", ({override}) => {
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

    override(message_store, "get", (arg) => {
        assert.equal(arg, message_id);
        return message;
    });

    blueslip.expect("warn", "User 2 tried to hijack message 101");

    submessage.process_submessages({
        message_id,
    });
});

run_test("handle_event", () => {
    const message = {
        id: 42,
    };

    const event = {
        id: 11,
        msg_type: "widget",
        sender_id: 99,
        message_id: message.id,
        content: '"some_data"',
    };

    let args;
    widgetize.handle_event = (opts) => {
        args = opts;
    };

    message_store.get = (msg_id) => {
        assert.equal(msg_id, message.id);
        return message;
    };

    submessage.handle_event(event);

    assert.deepEqual(args, {
        sender_id: 99,
        message_id: 42,
        data: "some_data",
    });

    assert.deepEqual(message.submessages[0], event);
});
