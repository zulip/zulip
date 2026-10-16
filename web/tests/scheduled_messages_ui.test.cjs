"use strict";

const {strict: assert} = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const compose_actions = mock_esm("../src/compose_actions");
mock_esm("../src/compose_banner");
mock_esm("../src/message_view");

const scheduled_messages_ui = zrequire("scheduled_messages_ui");

function scheduled_stream_message(split_message_on_send) {
    return {
        scheduled_message_id: 1,
        type: "stream",
        to: 5,
        topic: "lunch",
        content: "part1\n\n\npart2",
        rendered_content: "<p>part1</p><p>part2</p>",
        scheduled_delivery_timestamp: 1681662420,
        failed: false,
        split_message_on_send,
    };
}

run_test("open_scheduled_message_in_compose", ({override}) => {
    let start_opts;
    override(compose_actions, "start", (opts) => {
        start_opts = opts;
    });

    scheduled_messages_ui.open_scheduled_message_in_compose(scheduled_stream_message(true));
    assert.equal(start_opts.content, "part1\n\n\npart2");
    assert.equal(start_opts.split_messages_enabled, true);

    scheduled_messages_ui.open_scheduled_message_in_compose(scheduled_stream_message(false));
    assert.equal(start_opts.split_messages_enabled, false);
});
