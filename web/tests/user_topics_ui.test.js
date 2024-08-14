"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");

const user_topics = zrequire("user_topics");
const user_topics_ui = zrequire("user_topics_ui");
const stream_data = zrequire("stream_data");

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

test("toggle_topic_visibility_policy", () => {
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
});
