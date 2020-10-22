"use strict";

const events = require("./lib/events");

const event_fixtures = events.fixtures;
const test_user = events.test_user;

set_global("compose_fade", {});
set_global("stream_events", {});
set_global("subs", {});

const people = zrequire("people");
zrequire("stream_data");
zrequire("server_events_dispatch");

people.add_active_user(test_user);

const dispatch = server_events_dispatch.dispatch_normal_event;

function test(label, f) {
    stream_data.clear_subscriptions();

    run_test(label, (override) => {
        f(override);
    });
}

test("add", (override) => {
    const event = event_fixtures.subscription__add;

    const sub = event.subscriptions[0];
    const stream_id = sub.stream_id;

    stream_data.add_sub({
        stream_id,
        name: sub.name,
    });

    global.with_stub((subscription_stub) => {
        override("stream_events.mark_subscribed", subscription_stub.f);
        dispatch(event);
        const args = subscription_stub.get_args("sub", "subscribers");
        assert.deepEqual(args.sub.stream_id, stream_id);
        assert.deepEqual(args.subscribers, event.subscriptions[0].subscribers);
    });
});

test("peer add/remove", (override) => {
    let event = event_fixtures.subscription__peer_add;

    stream_data.add_sub({
        name: "devel",
        stream_id: event.stream_ids[0],
    });

    const subs_stub = global.make_stub();
    override("subs.update_subscribers_ui", subs_stub.f);

    const compose_fade_stub = global.make_stub();
    override("compose_fade.update_faded_users", compose_fade_stub.f);

    dispatch(event);
    assert.equal(compose_fade_stub.num_calls, 1);
    assert.equal(subs_stub.num_calls, 1);

    event = event_fixtures.subscription__peer_remove;
    dispatch(event);
    assert.equal(compose_fade_stub.num_calls, 2);
    assert.equal(subs_stub.num_calls, 2);
});

test("remove", (override) => {
    const event = event_fixtures.subscription__remove;
    const event_sub = event.subscriptions[0];
    const stream_id = event_sub.stream_id;

    const sub = {
        stream_id,
        name: event_sub.name,
    };

    stream_data.add_sub(sub);

    global.with_stub((stub) => {
        override("stream_events.mark_unsubscribed", stub.f);
        dispatch(event);
        const args = stub.get_args("sub");
        assert.deepEqual(args.sub, sub);
    });
});

test("update", (override) => {
    const event = event_fixtures.subscription__update;
    global.with_stub((stub) => {
        override("stream_events.update_property", stub.f);
        dispatch(event);
        const args = stub.get_args("stream_id", "property", "value");
        assert.deepEqual(args.stream_id, event.stream_id);
        assert.deepEqual(args.property, event.property);
        assert.deepEqual(args.value, event.value);
    });
});

test("add error handling", (override) => {
    // test blueslip errors/warns
    const event = event_fixtures.subscription__add;
    global.with_stub((stub) => {
        override("blueslip.error", stub.f);
        dispatch(event);
        assert.deepEqual(stub.get_args("param").param, "Subscribing to unknown stream with ID 101");
    });
});

test("peer event error handling (bad stream_ids)", (override) => {
    override("compose_fade.update_faded_users", () => {});

    const add_event = {
        type: "subscription",
        op: "peer_add",
        stream_ids: [99999],
    };

    blueslip.expect("warn", "Cannot find stream for peer_add: 99999");
    dispatch(add_event);
    blueslip.reset();

    const remove_event = {
        type: "subscription",
        op: "peer_remove",
        stream_ids: [99999],
    };

    blueslip.expect("warn", "Cannot find stream for peer_remove: 99999");
    dispatch(remove_event);
});

test("peer event error handling (add_subscriber)", (override) => {
    override("compose_fade.update_faded_users", () => {});
    override("subs.update_subscribers_ui", () => {});

    stream_data.add_sub({
        name: "devel",
        stream_id: 1,
    });

    override("stream_data.add_subscriber", () => false);

    const add_event = {
        type: "subscription",
        op: "peer_add",
        stream_ids: [1],
        user_ids: [99999], // id is irrelevant
    };

    blueslip.expect("warn", "Cannot process peer_add event");
    dispatch(add_event);
    blueslip.reset();

    override("stream_data.remove_subscriber", () => false);

    const remove_event = {
        type: "subscription",
        op: "peer_remove",
        stream_ids: [1],
        user_ids: [99999], // id is irrelevant
    };

    blueslip.expect("warn", "Cannot process peer_remove event.");
    dispatch(remove_event);
});
