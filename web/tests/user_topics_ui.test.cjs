"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const user_topics = zrequire("user_topics");
const user_topics_ui = zrequire("user_topics_ui");
const stream_data = zrequire("stream_data");
const sub_store = zrequire("sub_store");

const design = {
    stream_id: 101,
    name: "design",
    subscribed: false,
    is_muted: false,
};

stream_data.add_sub(design);

function test(label, f) {
    run_test(label, (helpers) => {
        user_topics.set_user_topics([]);
        return f(helpers);
    });
}

function update_visibility_policy(visibility_policy) {
    user_topics.update_user_topics(design.stream_id, design.name, "java", visibility_policy);
}

test("toggle_topic_visibility_policy", ({override_rewire}) => {
    // Mute a topic
    assert.ok(!user_topics.is_topic_muted(design.stream_id, "java"));
    update_visibility_policy(user_topics.all_visibility_policies.MUTED);
    assert.ok(user_topics.is_topic_muted(design.stream_id, "java"));

    // Unsubscribe the channel
    design.subscribed = false;

    const message = {
        type: "stream",
        stream_id: design.stream_id,
        topic: "java",
    };

    // Verify that we can't toggle visibility policy in unsubscribed channel.
    user_topics_ui.toggle_topic_visibility_policy(message);
    assert.ok(user_topics.is_topic_muted(design.stream_id, "java"));

    override_rewire(
        user_topics,
        "set_user_topic_visibility_policy",
        (stream_id, topic_name, visibility_policy) => {
            const stream_name = sub_store.maybe_get_stream_name(stream_id);
            user_topics.update_user_topics(stream_id, stream_name, topic_name, visibility_policy);
        },
    );

    design.subscribed = true;

    // For NOT muted channel
    user_topics_ui.toggle_topic_visibility_policy(message);
    assert.ok(
        user_topics.get_topic_visibility_policy(design.stream_id, "java") ===
            user_topics.all_visibility_policies.INHERIT,
    );

    user_topics_ui.toggle_topic_visibility_policy(message);
    assert.ok(user_topics.is_topic_muted(design.stream_id, "java"));

    update_visibility_policy(user_topics.all_visibility_policies.UNMUTED);
    user_topics_ui.toggle_topic_visibility_policy(message);
    assert.ok(user_topics.is_topic_muted(design.stream_id, "java"));

    update_visibility_policy(user_topics.all_visibility_policies.FOLLOWED);
    user_topics_ui.toggle_topic_visibility_policy(message);
    assert.ok(user_topics.is_topic_muted(design.stream_id, "java"));

    // For muted channel
    design.is_muted = true;

    update_visibility_policy(user_topics.all_visibility_policies.INHERIT);
    user_topics_ui.toggle_topic_visibility_policy(message);
    assert.ok(user_topics.is_topic_unmuted(design.stream_id, "java"));

    update_visibility_policy(user_topics.all_visibility_policies.MUTED);
    user_topics_ui.toggle_topic_visibility_policy(message);
    assert.ok(user_topics.is_topic_unmuted(design.stream_id, "java"));

    user_topics_ui.toggle_topic_visibility_policy(message);
    assert.ok(
        user_topics.get_topic_visibility_policy(design.stream_id, "java") ===
            user_topics.all_visibility_policies.INHERIT,
    );

    update_visibility_policy(user_topics.all_visibility_policies.FOLLOWED);
    user_topics_ui.toggle_topic_visibility_policy(message);
    assert.ok(
        user_topics.get_topic_visibility_policy(design.stream_id, "java") ===
            user_topics.all_visibility_policies.INHERIT,
    );
});
