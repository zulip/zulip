"use strict";

const {strict: assert} = require("assert");

const {set_global, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");

const muted_users = zrequire("muted_users");
const typing_data = zrequire("typing_data");

function test(label, f) {
    run_test(label, ({override}) => {
        typing_data.clear_for_testing();
        muted_users.set_muted_users([]);
        f({override});
    });
}

test("basics", () => {
    // The typing_data needs to be robust with lists of
    // user ids being in arbitrary sorting order. So all
    // the apparent randomness in these tests has a purpose.

    const stream_id = 1;
    const topic = "typing notifications";
    const topic_typing_key = typing_data.get_topic_key(stream_id, topic);

    typing_data.add_typist(typing_data.get_direct_message_conversation_key([5, 10, 15]), 15);
    assert.deepEqual(typing_data.get_group_typists([15, 10, 5]), [15]);

    typing_data.add_typist(topic_typing_key, 12);
    assert.deepEqual(typing_data.get_topic_typists(stream_id, topic), [12]);

    // test that you can add twice
    typing_data.add_typist(typing_data.get_direct_message_conversation_key([5, 10, 15]), 15);

    // add another id to our first group
    typing_data.add_typist(typing_data.get_direct_message_conversation_key([5, 10, 15]), 10);
    assert.deepEqual(typing_data.get_group_typists([10, 15, 5]), [10, 15]);

    typing_data.add_typist(topic_typing_key, 12);

    // add another typist to our stream/topic
    typing_data.add_typist(topic_typing_key, 13);
    assert.deepEqual(typing_data.get_topic_typists(stream_id, topic), [12, 13]);

    // start adding to a new group
    typing_data.add_typist(typing_data.get_direct_message_conversation_key([7, 15]), 7);
    typing_data.add_typist(typing_data.get_direct_message_conversation_key([7, 15]), 15);

    // test get_all_direct_message_typists
    assert.deepEqual(typing_data.get_all_direct_message_typists(), [7, 10, 15]);

    // test basic removal
    assert.ok(
        typing_data.remove_typist(typing_data.get_direct_message_conversation_key([15, 7]), 7),
    );
    assert.deepEqual(typing_data.get_group_typists([7, 15]), [15]);
    assert.ok(typing_data.remove_typist(topic_typing_key, 12));
    assert.deepEqual(typing_data.get_topic_typists(stream_id, topic), [13]);

    // test removing an id that is not there
    assert.ok(
        !typing_data.remove_typist(typing_data.get_direct_message_conversation_key([15, 7]), 7),
    );
    assert.deepEqual(typing_data.get_group_typists([7, 15]), [15]);
    assert.deepEqual(typing_data.get_all_direct_message_typists(), [10, 15]);

    // remove user from one group, but "15" will still be among
    // "all typists"
    assert.ok(
        typing_data.remove_typist(typing_data.get_direct_message_conversation_key([15, 7]), 15),
    );
    assert.deepEqual(typing_data.get_all_direct_message_typists(), [10, 15]);

    // now remove from the other group
    assert.ok(
        typing_data.remove_typist(typing_data.get_direct_message_conversation_key([5, 15, 10]), 15),
    );
    assert.deepEqual(typing_data.get_all_direct_message_typists(), [10]);

    // test duplicate ids in a groups
    typing_data.add_typist(typing_data.get_direct_message_conversation_key([20, 40, 20]), 20);
    assert.deepEqual(typing_data.get_group_typists([20, 40]), [20]);

    // test clearing out typing data
    typing_data.clear_typing_data();
    assert.deepEqual(typing_data.get_group_typists(), []);
    assert.deepEqual(typing_data.get_all_direct_message_typists(), []);
    assert.deepEqual(typing_data.get_topic_typists(stream_id, topic), []);
});

test("muted_typists_excluded", () => {
    const stream_id = 1;
    const topic = "typing notifications";
    const topic_typing_key = typing_data.get_topic_key(stream_id, topic);

    typing_data.add_typist(typing_data.get_direct_message_conversation_key([5, 10, 15]), 5);
    typing_data.add_typist(typing_data.get_direct_message_conversation_key([5, 10, 15]), 10);
    typing_data.add_typist(topic_typing_key, 7);
    typing_data.add_typist(topic_typing_key, 12);

    // Nobody is muted.
    assert.deepEqual(typing_data.get_group_typists([5, 10, 15]), [5, 10]);
    assert.deepEqual(typing_data.get_all_direct_message_typists(), [5, 10]);
    assert.deepEqual(typing_data.get_topic_typists(stream_id, topic), [7, 12]);

    // Mute a user, and test that the get_* functions exclude that user.
    muted_users.add_muted_user(10);
    muted_users.add_muted_user(7);
    assert.deepEqual(typing_data.get_group_typists([5, 10, 15]), [5]);
    assert.deepEqual(typing_data.get_all_direct_message_typists(), [5]);
    assert.deepEqual(typing_data.get_topic_typists(stream_id, topic), [12]);
});

test("timers", () => {
    const events = {};

    const stub_timer_id = "timer_id_stub";
    const stub_group = [5, 10, 15];
    const stub_delay = 99;
    const stub_f = "function";
    const stub_stream_id = 1;
    const stub_topic = "typing notifications";
    const topic_typing_key = typing_data.get_topic_key(stub_stream_id, stub_topic);

    function set_timeout(f, delay) {
        assert.equal(delay, stub_delay);
        events.f = f;
        events.timer_set = true;
        return stub_timer_id;
    }

    function clear_timeout(timer) {
        assert.equal(timer, stub_timer_id);
        events.timer_cleared = true;
    }

    function reset_events() {
        events.f = undefined;
        events.timer_cleared = false;
        events.timer_set = false;
    }

    function kickstart() {
        reset_events();
        typing_data.kickstart_inbound_timer(
            typing_data.get_direct_message_conversation_key(stub_group),
            stub_delay,
            stub_f,
        );
    }

    function clear() {
        reset_events();
        typing_data.clear_inbound_timer(
            typing_data.get_direct_message_conversation_key(stub_group),
        );
    }

    function streams_kickstart() {
        reset_events();
        typing_data.kickstart_inbound_timer(topic_typing_key, stub_delay, stub_f);
    }

    function streams_clear() {
        reset_events();
        typing_data.clear_inbound_timer(topic_typing_key);
    }

    set_global("setTimeout", set_timeout);
    set_global("clearTimeout", clear_timeout);

    // first time, we set
    kickstart();
    assert.deepEqual(events, {
        f: stub_f,
        timer_cleared: false,
        timer_set: true,
    });

    // second time we clear and set
    kickstart();
    assert.deepEqual(events, {
        f: stub_f,
        timer_cleared: true,
        timer_set: true,
    });

    // clearing out typing data
    kickstart();
    typing_data.clear_typing_data();
    assert.deepEqual(events, {
        f: stub_f,
        timer_cleared: true,
        timer_set: true,
    });

    kickstart();
    // first time clearing, we clear
    clear();
    assert.deepEqual(events, {
        f: undefined,
        timer_cleared: true,
        timer_set: false,
    });

    // second time clearing, we noop
    clear();
    assert.deepEqual(events, {
        f: undefined,
        timer_cleared: false,
        timer_set: false,
    });

    // first time, we set
    streams_kickstart();
    assert.deepEqual(events, {
        f: stub_f,
        timer_cleared: false,
        timer_set: true,
    });

    // second time we clear and set
    streams_kickstart();
    assert.deepEqual(events, {
        f: stub_f,
        timer_cleared: true,
        timer_set: true,
    });

    // first time clearing, we clear
    streams_clear();
    assert.deepEqual(events, {
        f: undefined,
        timer_cleared: true,
        timer_set: false,
    });

    // second time clearing, we noop
    streams_clear();
    assert.deepEqual(events, {
        f: undefined,
        timer_cleared: false,
        timer_set: false,
    });
});
