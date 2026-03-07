"use strict";

const assert = require("node:assert/strict");

const {make_realm} = require("./lib/example_realm.cjs");
const {make_user} = require("./lib/example_user.cjs");
const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");

let banner_update_called = false;
mock_esm("../src/topic_resolution_compose", {
    update_banner_if_needed() {
        banner_update_called = true;
    },
});

mock_esm("../src/navbar_alerts", {
    toggle_organization_profile_incomplete_banner: noop,
});

// settings_org mock removed (unused in this test path)
// ...
// sent_messages, loading, popup_banners, stream_events, message_events mocks removed
set_global("addEventListener", noop);

const server_events_dispatch = zrequire("server_events_dispatch");
const state_data = zrequire("state_data");

run_test("topic_resolution_message_requirement_update", () => {
    // Initialize realm data with valid default values
    const realm = make_realm({
        realm_topic_resolution_message_requirement: "not_requested",
    });
    state_data.set_realm(realm);

    const user = make_user({
        is_admin: true,
    });
    state_data.set_current_user(user);

    banner_update_called = false;

    const event = {
        type: "realm",
        op: "update",
        property: "topic_resolution_message_requirement",
        value: "required",
    };

    server_events_dispatch.dispatch_normal_event(event);

    assert.ok(banner_update_called);
    // Verify the value was updated in state_data (which is what realm object refers to)
    // server_events_dispatch updates `realm` which is exported from state_data
    assert.equal(state_data.realm.realm_topic_resolution_message_requirement, "required");
});
