"use strict";

const { strict: assert } = require("assert");

const { mock_esm, zrequire } = require("./lib/namespace.cjs");
const { run_test, noop } = require("./lib/test.cjs");

// Track update calls
let update_announce_stream_option_calls = 0;

// Mock dependencies
mock_esm("../src/stream_ui_updates.ts", {
    update_announce_stream_option() {
        update_announce_stream_option_calls += 1;
    },
});

mock_esm("../src/settings_org.ts", {
    sync_realm_settings: noop,
});

mock_esm("../src/loading", {
    destroy_indicator: noop,
});

mock_esm("../src/reload_state", {
    is_in_progress() {
        return false;
    },
});

mock_esm("../src/sent_messages", {
    report_event_received() { },
    messages: new Map(),
});

const { realm } = zrequire("state_data");

const server_events = zrequire("server_events");

// Mark initial fetch as complete before running tests
server_events.finished_initial_fetch();

run_test("announcement_channel_batching_multiple_updates", () => {
    update_announce_stream_option_calls = 0;

    const events = [
        {
            id: 1,
            type: "realm",
            op: "update",
            property: "new_stream_announcements_stream_id",
            value: 42,
        },
        {
            id: 2,
            type: "realm",
            op: "update",
            property: "signup_announcements_stream_id",
            value: 43,
        },
        {
            id: 3,
            type: "realm",
            op: "update",
            property: "zulip_update_announcements_stream_id",
            value: 44,
        },
    ];

    server_events._get_events_success(events);

    assert.equal(
        update_announce_stream_option_calls,
        1,
        "update_announce_stream_option should be called once for batched updates",
    );
});

run_test("announcement_channel_single_update", () => {
    update_announce_stream_option_calls = 0;

    const events = [
        {
            id: 1,
            type: "realm",
            op: "update",
            property: "new_stream_announcements_stream_id",
            value: 42,
        },
    ];

    server_events._get_events_success(events);

    assert.equal(
        update_announce_stream_option_calls,
        1,
        "update_announce_stream_option should be called once for single update",
    );
});

run_test("non_announcement_channel_updates_not_batched", () => {
    update_announce_stream_option_calls = 0;

    const events = [
        {
            id: 1,
            type: "realm",
            op: "update",
            property: "name",
            value: "New Realm Name",
        },
    ];

    server_events._get_events_success(events);

    assert.equal(
        update_announce_stream_option_calls,
        0,
        "update_announce_stream_option should not be called for non-announcement updates",
    );
});
