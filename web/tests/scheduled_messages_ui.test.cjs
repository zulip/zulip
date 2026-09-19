"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");

const channel = mock_esm("../src/channel");
const compose_actions = mock_esm("../src/compose_actions", {
    register_compose_cancel_hook: noop,
    register_compose_box_clear_hook: noop,
});
const compose_banner = mock_esm("../src/compose_banner", {
    WARNING: "warning",
    CLASSNAMES: {unscheduled_message: "unscheduled_message"},
    update_split_messages_info_banner: noop,
    show_warning_message: noop,
});
mock_esm("../src/timerender", {get_full_datetime: () => "10:30 AM"});

const compose_split_messages = zrequire("compose_split_messages");
const scheduled_messages = zrequire("scheduled_messages");
const scheduled_messages_ui = zrequire("scheduled_messages_ui");

const DELIVERY_TIMESTAMP = 1_700_000_000;

function make_scheduled_parts(contents) {
    const scheduled_messages_by_id = new Map();
    for (const [index, content] of contents.entries()) {
        const scheduled_message_id = index + 1;
        scheduled_messages_by_id.set(scheduled_message_id, {
            scheduled_message_id,
            type: "stream",
            to: 101,
            topic: "split topic",
            content,
            scheduled_delivery_timestamp: DELIVERY_TIMESTAMP,
        });
    }
    scheduled_messages.set_scheduled_messages_by_id_for_testing(scheduled_messages_by_id);
    return scheduled_messages_by_id.keys().toArray();
}

run_test("undo_split_scheduled_messages", ({override}) => {
    const ids = make_scheduled_parts(["part1", "part2", "part3"]);

    const deleted_urls = [];
    override(channel, "del", (opts) => {
        deleted_urls.push(opts.url);
        opts.success();
    });
    let compose_args;
    override(compose_actions, "start", (args) => {
        compose_args = args;
    });
    let unscheduled_banner_shown = false;
    override(compose_banner, "show_warning_message", () => {
        unscheduled_banner_shown = true;
    });
    compose_split_messages.set_split_messages_enabled(false);

    scheduled_messages_ui.undo_split_scheduled_messages(ids);

    assert.deepEqual(deleted_urls, [
        "/json/scheduled_messages/1",
        "/json/scheduled_messages/2",
        "/json/scheduled_messages/3",
    ]);
    assert.equal(compose_args.message_type, "stream");
    assert.equal(compose_args.topic, "split topic");
    assert.equal(compose_args.content, "part1\n\n\npart2\n\n\npart3");
    assert.ok(compose_split_messages.is_split_messages_enabled());
    assert.equal(compose_split_messages.count_message_content_split_parts(compose_args.content), 3);
    assert.ok(unscheduled_banner_shown);

    compose_split_messages.set_split_messages_enabled(false);
});

run_test("undo_split_scheduled_messages_partial_failure", ({override}) => {
    const ids = make_scheduled_parts(["part1", "part2", "part3"]);

    const deleted_urls = [];
    override(channel, "del", (opts) => {
        deleted_urls.push(opts.url);
        if (deleted_urls.length === 2) {
            opts.error();
        } else {
            opts.success();
        }
    });
    let compose_args;
    override(compose_actions, "start", (args) => {
        compose_args = args;
    });
    let still_scheduled_count;
    override(compose_banner, "show_partial_undo_failure", (count) => {
        still_scheduled_count = count;
    });
    compose_split_messages.set_split_messages_enabled(false);

    scheduled_messages_ui.undo_split_scheduled_messages(ids);

    assert.deepEqual(deleted_urls, ["/json/scheduled_messages/1", "/json/scheduled_messages/2"]);
    assert.equal(compose_args.content, "part1");
    assert.equal(still_scheduled_count, 2);

    compose_split_messages.set_split_messages_enabled(false);
});

run_test("undo_split_scheduled_messages_with_a_part_already_gone", ({override}) => {
    const ids = make_scheduled_parts(["part1", "part2", "part3"]);
    scheduled_messages.remove_scheduled_message(ids[1]);

    let still_scheduled_count;
    override(compose_banner, "show_partial_undo_failure", (count) => {
        still_scheduled_count = count;
    });
    compose_split_messages.set_split_messages_enabled(false);

    scheduled_messages_ui.undo_split_scheduled_messages(ids);

    assert.equal(still_scheduled_count, 3);
    assert.ok(!compose_split_messages.is_split_messages_enabled());
});

run_test("undo_split_scheduled_messages_first_delete_fails", ({override}) => {
    const ids = make_scheduled_parts(["part1", "part2"]);

    override(channel, "del", (opts) => {
        opts.error();
    });
    let still_scheduled_count;
    override(compose_banner, "show_partial_undo_failure", (count) => {
        still_scheduled_count = count;
    });
    compose_split_messages.set_split_messages_enabled(false);

    scheduled_messages_ui.undo_split_scheduled_messages(ids);

    assert.ok(!compose_split_messages.is_split_messages_enabled());
    assert.equal(still_scheduled_count, 2);
});
