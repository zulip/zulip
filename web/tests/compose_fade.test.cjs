"use strict";

const assert = require("node:assert/strict");

const {make_realm} = require("./lib/example_realm.cjs");
const {make_stream} = require("./lib/example_stream.cjs");
const {make_user} = require("./lib/example_user.cjs");
const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const stream_data = zrequire("stream_data");
stream_data.set_channel_has_locally_available_topic(() => false);
const peer_data = zrequire("peer_data");
const people = zrequire("people");
const compose_fade = zrequire("compose_fade");
const compose_fade_helper = zrequire("compose_fade_helper");
const compose_state = zrequire("compose_state");
const {set_realm} = zrequire("state_data");

const realm = make_realm();
set_realm(realm);

const me = make_user({
    email: "me@example.com",
    user_id: 30,
    full_name: "Me Myself",
});

const alice = make_user({
    email: "alice@example.com",
    user_id: 31,
    full_name: "Alice",
});

const bob = make_user({
    email: "bob@example.com",
    user_id: 32,
    full_name: "Bob",
});

people.add_active_user(me);
people.initialize_current_user(me.user_id);

people.add_active_user(alice);
people.add_active_user(bob);

run_test("set_focused_recipient", () => {
    const sub = make_stream({
        stream_id: 101,
        name: "social",
        subscribed: true,
    });

    stream_data.clear_subscriptions();
    stream_data.add_sub_for_tests(sub);
    compose_state.set_stream_id(sub.stream_id);
    peer_data.set_subscribers(sub.stream_id, [me.user_id, alice.user_id]);
    $("input#stream_message_recipient_topic").val("lunch");
    compose_fade.set_focused_recipient("stream");

    const good_msg = {
        type: "stream",
        stream_id: 101,
        topic: "lunch",
    };
    const bad_msg = {
        type: "stream",
        stream_id: 999,
        topic: "lunch",
    };
    assert.ok(!compose_fade_helper.should_fade_message(good_msg));
    assert.ok(compose_fade_helper.should_fade_message(bad_msg));
});

run_test("want_normal_display", ({override, override_rewire}) => {
    const stream_id = 110;
    const sub = make_stream({
        stream_id,
        name: "display testing",
        subscribed: true,
    });

    stream_data.clear_subscriptions();

    // No focused recipient.
    compose_fade_helper.set_focused_recipient(undefined);
    assert.ok(compose_fade_helper.want_normal_display());

    // Focused recipient is a sub that doesn't exist.
    compose_fade_helper.set_focused_recipient({
        type: "stream",
        stream_id,
        topic: "",
    });
    assert.ok(compose_fade_helper.want_normal_display());

    // Focused recipient is a valid stream with no topic set
    // when topics are mandatory
    override(realm, "realm_topics_policy", "disable_empty_topic");
    stream_data.add_sub_for_tests(sub);
    assert.ok(compose_fade_helper.want_normal_display());

    // Focused recipient is a valid stream with no topic set
    // when topics are not mandatory.
    override(realm, "realm_topics_policy", "allow_empty_topic");
    override_rewire(stream_data, "can_create_new_topics_in_stream", () => true);
    assert.ok(!compose_fade_helper.want_normal_display());

    // When empty topics are allowed but user is still focused on
    // the topic input, show normal display since user is still
    // configuring topic.
    $("input#stream_message_recipient_topic").trigger("focus");
    assert.ok(compose_fade_helper.want_normal_display());
    $("input#stream_message_recipient_topic").trigger("blur");

    // When empty topics are allowed by policy but the user cannot
    // create new topics and no empty topic exists, show normal
    // display since the compose target is incomplete.
    override_rewire(stream_data, "can_create_new_topics_in_stream", () => false);
    assert.ok(compose_fade_helper.want_normal_display());

    // If we're focused to a topic, then we do want to fade.
    compose_fade_helper.set_focused_recipient({
        type: "stream",
        stream_id,
        topic: "lunch",
    });
    assert.ok(!compose_fade_helper.want_normal_display());

    // Private message with no recipient.
    compose_fade_helper.set_focused_recipient({
        type: "private",
        reply_to: "",
    });
    assert.ok(compose_fade_helper.want_normal_display());

    // Private message with a recipient.
    compose_fade_helper.set_focused_recipient({
        type: "private",
        reply_to: "hello@zulip.com",
    });
    assert.ok(!compose_fade_helper.want_normal_display());
});
