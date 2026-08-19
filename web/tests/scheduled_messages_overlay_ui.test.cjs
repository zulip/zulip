"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const scheduled_messages = zrequire("scheduled_messages");
const scheduled_messages_overlay_ui = zrequire("scheduled_messages_overlay_ui");

function make_scheduled_message(id, split_group_id, timestamp) {
    return {
        scheduled_message_id: id,
        type: "stream",
        to: 1,
        topic: "topic",
        content: `m${id}`,
        rendered_content: `<p>m${id}</p>`,
        scheduled_delivery_timestamp: timestamp,
        failed: false,
        split_group_id,
    };
}

run_test("overlay collapses a split message's parts into one item", () => {
    const by_id = new Map();
    for (const id of [1, 2, 3]) {
        by_id.set(id, make_scheduled_message(id, "group-a", 1000));
    }
    by_id.set(4, make_scheduled_message(4, null, 2000));
    scheduled_messages.set_scheduled_messages_by_id_for_testing(by_id);

    assert.deepEqual(scheduled_messages_overlay_ui.keyboard_handling_context.get_items_ids(), [
        "1",
        "4",
    ]);
});
