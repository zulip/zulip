"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");

const channel = mock_esm("../src/channel");

const message_util = zrequire("message_util");

let reported_ids = [];
function record_last_message_id(id) {
    reported_ids.push(id);
}

function test(label, f) {
    run_test(label, (helpers) => {
        reported_ids = [];
        f(helpers);
    });
}

test("get_last_message_id_in_narrow builds the request from the narrow", () => {
    let requested_opts;
    channel.get = (opts) => {
        requested_opts = opts;
    };

    const narrow = [
        {operator: "channel", operand: 5},
        {operator: "topic", operand: "topic"},
    ];
    message_util.get_last_message_id_in_narrow(narrow, noop, {allow_empty_topic_name: true});

    assert.equal(requested_opts.url, "/json/messages");
    assert.deepEqual(requested_opts.data, {
        narrow: JSON.stringify(narrow),
        anchor: "newest",
        num_before: 1,
        num_after: 0,
        allow_empty_topic_name: true,
    });
});

test("get_last_message_id_in_narrow reports the last message id on success", () => {
    channel.get = (opts) => {
        opts.success({messages: [{id: 987}]});
    };

    message_util.get_last_message_id_in_narrow(
        [{operator: "dm", operand: [4]}],
        record_last_message_id,
    );

    assert.deepEqual(reported_ids, [987]);
});

test("get_last_message_id_in_narrow ignores an empty result", () => {
    channel.get = (opts) => {
        opts.success({messages: []});
    };

    message_util.get_last_message_id_in_narrow(
        [{operator: "dm", operand: [4]}],
        record_last_message_id,
    );

    assert.deepEqual(reported_ids, []);
});

test("get_last_message_id_in_narrow ignores errors", () => {
    channel.get = (opts) => {
        opts.error();
    };

    // Should not throw or report a message id.
    message_util.get_last_message_id_in_narrow(
        [{operator: "dm", operand: [4]}],
        record_last_message_id,
    );

    assert.deepEqual(reported_ids, []);
});
