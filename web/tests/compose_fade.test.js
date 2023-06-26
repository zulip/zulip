"use strict";

const {strict: assert} = require("assert");

const {mock_jquery, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");

mock_jquery((selector) => {
    switch (selector) {
        case "#stream_message_recipient_topic":
            return {
                val() {
                    return "lunch";
                },
            };
        /* istanbul ignore next */
        default:
            throw new Error(`Unknown selector ${selector}`);
    }
});

const stream_data = zrequire("stream_data");
const peer_data = zrequire("peer_data");
const people = zrequire("people");
const compose_fade = zrequire("compose_fade");
const compose_recipient = zrequire("compose_recipient");
const compose_fade_helper = zrequire("compose_fade_helper");
const compose_state = zrequire("compose_state");

const me = {
    email: "me@example.com",
    user_id: 30,
    full_name: "Me Myself",
};

const alice = {
    email: "alice@example.com",
    user_id: 31,
    full_name: "Alice",
};

const bob = {
    email: "bob@example.com",
    user_id: 32,
    full_name: "Bob",
};

people.add_active_user(me);
people.initialize_current_user(me.user_id);

people.add_active_user(alice);
people.add_active_user(bob);

run_test("set_focused_recipient", ({override_rewire}) => {
    override_rewire(compose_recipient, "selected_stream_name", "social");
    override_rewire(compose_recipient, "is_direct_message_selected", false);

    override_rewire(compose_recipient, "on_compose_select_recipient_update", () => {});
    const sub = {
        stream_id: 101,
        name: "social",
        subscribed: true,
    };

    compose_fade.set_focused_recipient("stream");

    // If a stream is unknown, then we turn off the compose-fade
    // feature, since a mix won't happen if the message can't be
    // delivered.
    stream_data.clear_subscriptions();
    assert.equal(compose_fade_helper.would_receive_message(bob.user_id), true);

    stream_data.add_sub(sub);
    compose_state.set_stream_id(sub.stream_id);
    peer_data.set_subscribers(sub.stream_id, [me.user_id, alice.user_id]);
    compose_fade.set_focused_recipient("stream");

    assert.equal(compose_fade_helper.would_receive_message(me.user_id), true);
    assert.equal(compose_fade_helper.would_receive_message(alice.user_id), true);
    assert.equal(compose_fade_helper.would_receive_message(bob.user_id), false);

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
