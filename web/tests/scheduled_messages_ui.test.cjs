"use strict";

const {strict: assert} = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const compose_actions = mock_esm("../src/compose_actions");
const compose_banner = mock_esm("../src/compose_banner");
mock_esm("../src/message_view");

const compose_split_messages = zrequire("compose_split_messages");
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
    let split_enabled_when_compose_started;
    override(compose_actions, "start", (opts) => {
        assert.equal(opts.content, "part1\n\n\npart2");
        split_enabled_when_compose_started = compose_split_messages.is_split_messages_enabled();
    });
    let banner_updates = 0;
    override(compose_banner, "update_split_messages_info_banner", () => {
        banner_updates += 1;
    });

    scheduled_messages_ui.open_scheduled_message_in_compose(scheduled_stream_message(true));
    assert.ok(split_enabled_when_compose_started);
    assert.equal(banner_updates, 1);

    scheduled_messages_ui.open_scheduled_message_in_compose(scheduled_stream_message(false));
    assert.ok(!split_enabled_when_compose_started);
    assert.equal(banner_updates, 2);
});
