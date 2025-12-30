"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const channel = mock_esm("../src/channel");
mock_esm("../src/message_util", {
    get_count_of_messages_in_topic_sent_after_current_message: () => 5,
    get_loaded_messages_in_topic: () => [1, 2, 3, 4, 5, 6, 7],
});

const stream_popover = zrequire("stream_popover");

run_test("update_move_messages_count_text", ({override}) => {
    const $count_element = $.create("count-element");
    const stream_id = 10;
    const topic_name = "test topic";
    const message_id = 100;

    // Test change_one
    stream_popover.update_move_messages_count_text(
        $count_element,
        "change_one",
        stream_id,
        topic_name,
        message_id,
    );
    assert.equal($count_element.text(), "1 message will be moved.");

    // Test change_all (Calculating state)
    let get_called = false;
    let get_args;
    override(channel, "get", (args) => {
        get_called = true;
        get_args = args;
    });

    stream_popover.update_move_messages_count_text(
        $count_element,
        "change_all",
        stream_id,
        topic_name,
        message_id,
    );
    assert.ok(get_called);
    assert.equal($count_element.text(), "Calculating…");
    assert.equal(get_args.url, "/json/messages/count");
    assert.equal(JSON.parse(get_args.data.narrow)[0].operand, stream_id);
    assert.equal(JSON.parse(get_args.data.narrow)[1].operand, topic_name);

    // Test success callback
    get_args.success({count: 10});
    assert.equal($count_element.text(), "10 messages will be moved.");

    // Test error callback (fallback)
    stream_popover.update_move_messages_count_text(
        $count_element,
        "change_all",
        stream_id,
        topic_name,
        message_id,
    );
    get_args.error();
    assert.equal($count_element.text(), "At least 7 messages will be moved.");

    // Test change_later
    stream_popover.update_move_messages_count_text(
        $count_element,
        "change_later",
        stream_id,
        topic_name,
        message_id,
    );
    assert.equal(get_args.data.anchor, message_id);
    assert.equal(get_args.data.include_anchor, true);
    get_args.error();
    assert.equal($count_element.text(), "At least 5 messages will be moved.");
});
