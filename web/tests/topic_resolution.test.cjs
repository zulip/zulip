"use strict";

const assert = require("node:assert/strict");

const {make_realm} = require("./lib/example_realm.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const stream_data = mock_esm("../src/stream_data", {
    can_post_messages_in_stream() {},
    can_resolve_topics() {},
});

const resolved_topic = mock_esm("../src/resolved_topic", {
    is_resolved() {},
});

const topic_resolution = zrequire("topic_resolution");
const {set_realm} = zrequire("state_data");

const realm = make_realm({
    realm_topic_resolution_message_requirement: "not_requested",
});
set_realm(realm);

const active_sub = {
    is_archived: false,
};

run_test("can_toggle_topic_resolution returns false for missing or archived sub", () => {
    assert.equal(topic_resolution.can_toggle_topic_resolution(undefined, "topic"), false);
    assert.equal(topic_resolution.can_toggle_topic_resolution({is_archived: true}, "topic"), false);
});

run_test(
    "can_toggle_topic_resolution for resolved topic follows resolve permission",
    ({override}) => {
        override(realm, "realm_topic_resolution_message_requirement", "required");
        override(resolved_topic, "is_resolved", () => true);
        override(stream_data, "can_resolve_topics", () => true);
        assert.equal(topic_resolution.can_toggle_topic_resolution(active_sub, "topic"), true);

        override(stream_data, "can_resolve_topics", () => false);
        assert.equal(topic_resolution.can_toggle_topic_resolution(active_sub, "topic"), false);
    },
);

run_test(
    "can_toggle_topic_resolution blocks unresolved topic in required mode without post permission",
    ({override}) => {
        override(realm, "realm_topic_resolution_message_requirement", "required");
        override(resolved_topic, "is_resolved", () => false);
        override(stream_data, "can_resolve_topics", () => true);
        override(stream_data, "can_post_messages_in_stream", () => false);
        assert.equal(topic_resolution.can_toggle_topic_resolution(active_sub, "topic"), false);
    },
);

run_test(
    "can_toggle_topic_resolution in required mode with post permission follows resolve permission",
    ({override}) => {
        override(realm, "realm_topic_resolution_message_requirement", "required");
        override(resolved_topic, "is_resolved", () => false);
        override(stream_data, "can_post_messages_in_stream", () => true);
        override(stream_data, "can_resolve_topics", () => true);
        assert.equal(topic_resolution.can_toggle_topic_resolution(active_sub, "topic"), true);

        override(stream_data, "can_resolve_topics", () => false);
        assert.equal(topic_resolution.can_toggle_topic_resolution(active_sub, "topic"), false);
    },
);

run_test(
    "can_toggle_topic_resolution in optional/not_requested follows resolve permission",
    ({override}) => {
        override(resolved_topic, "is_resolved", () => false);

        override(realm, "realm_topic_resolution_message_requirement", "optional");
        override(stream_data, "can_resolve_topics", () => true);
        assert.equal(topic_resolution.can_toggle_topic_resolution(active_sub, "topic"), true);

        override(realm, "realm_topic_resolution_message_requirement", "not_requested");
        override(stream_data, "can_resolve_topics", () => false);
        assert.equal(topic_resolution.can_toggle_topic_resolution(active_sub, "topic"), false);
    },
);
