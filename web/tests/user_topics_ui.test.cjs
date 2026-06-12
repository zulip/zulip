"use strict";

const assert = require("node:assert/strict");

const {make_stream} = require("./lib/example_stream.cjs");
const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const overlays = mock_esm("../src/overlays", {settings_open: () => false});
const settings_user_topics = mock_esm("../src/settings_user_topics", {loaded: false});
mock_esm("../src/stream_list", {update_streams_sidebar: noop});
mock_esm("../src/unread_ui", {update_unread_counts: noop});
mock_esm("../src/recent_view_ui", {update_topic_visibility_policy: noop});
mock_esm("../src/message_lists", {
    current: undefined,
    all_rendered_message_lists: () => [],
});
mock_esm("../src/popover_menus", {
    is_topic_menu_popover_displayed: () => false,
    is_visibility_policy_popover_displayed: () => false,
});
mock_esm("../src/inbox_util", {is_visible: () => false});
mock_esm("../src/narrow_state", {narrowed_by_topic_reply: () => false});

const user_topics = zrequire("user_topics");
const user_topics_ui = zrequire("user_topics_ui");
const stream_data = zrequire("stream_data");
const sub_store = zrequire("sub_store");

const design = make_stream({
    stream_id: 101,
    name: "design",
    subscribed: false,
    is_muted: false,
});

stream_data.add_sub_for_tests(design);

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

test("handle_topic_updates_with_quoted_topic_name", ({override}) => {
    // The Settings > Topics row lookup builds a jQuery selector from
    // the topic name; characters special in CSS strings, like a
    // double quote, must be escaped rather than corrupting the
    // selector.
    const topic_name = 'topic with "quotes"';

    override(overlays, "settings_open", () => true);
    override(settings_user_topics, "loaded", true);
    set_global("setTimeout", (f) => f());

    const $row = $(
        `tr[data-stream-id="${design.stream_id}"][data-topic="${CSS.escape(topic_name)}"]`,
    );
    const $status = $.create("topic-visibility-select-stub");
    $row.set_find_results("select.settings_user_topic_visibility_policy", $status);

    user_topics_ui.handle_topic_updates({
        stream_id: design.stream_id,
        topic_name,
        visibility_policy: user_topics.all_visibility_policies.MUTED,
        last_updated: 1681662420,
    });

    // The handler found the row via the escaped selector and updated
    // its visibility-policy dropdown.
    assert.equal($status.val(), user_topics.all_visibility_policies.MUTED);
});
