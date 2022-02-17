"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("../zjsunit/namespace");
const {make_stub} = require("../zjsunit/stub");
const {run_test} = require("../zjsunit/test");
const blueslip = require("../zjsunit/zblueslip");
const {page_params} = require("../zjsunit/zpage_params");

const events = require("./lib/events");

const event_fixtures = events.fixtures;
const test_user = events.test_user;

const compose_fade = mock_esm("../../static/js/compose_fade");
const message_lists = mock_esm("../../static/js/message_lists");
const narrow_state = mock_esm("../../static/js/narrow_state");
const overlays = mock_esm("../../static/js/overlays");
const settings_org = mock_esm("../../static/js/settings_org");
const settings_streams = mock_esm("../../static/js/settings_streams");
const stream_events = mock_esm("../../static/js/stream_events");
const stream_list = mock_esm("../../static/js/stream_list");
const stream_settings_ui = mock_esm("../../static/js/stream_settings_ui");
message_lists.current = {};

const peer_data = zrequire("peer_data");
const people = zrequire("people");
const stream_data = zrequire("stream_data");
const server_events_dispatch = zrequire("server_events_dispatch");

const noop = () => {};

people.add_active_user(test_user);

const me = {
    email: "me@zulip.com",
    full_name: "Me Myself",
    user_id: 101,
};
people.add_active_user(me);
people.initialize_current_user(me.user_id);

const dispatch = server_events_dispatch.dispatch_normal_event;

function test(label, f) {
    run_test(label, ({override, override_rewire}) => {
        stream_data.clear_subscriptions();
        f({override, override_rewire});
    });
}

test("add", ({override}) => {
    const event = event_fixtures.subscription__add;

    const sub = event.subscriptions[0];
    const stream_id = sub.stream_id;

    stream_data.add_sub({
        stream_id,
        name: sub.name,
    });

    const subscription_stub = make_stub();
    override(stream_events, "mark_subscribed", subscription_stub.f);
    dispatch(event);
    assert.equal(subscription_stub.num_calls, 1);
    const args = subscription_stub.get_args("sub", "subscribers");
    assert.deepEqual(args.sub.stream_id, stream_id);
    assert.deepEqual(args.subscribers, event.subscriptions[0].subscribers);
});

test("peer add/remove", ({override}) => {
    let event = event_fixtures.subscription__peer_add;

    stream_data.add_sub({
        name: "devel",
        stream_id: event.stream_ids[0],
    });

    const subs_stub = make_stub();
    override(stream_settings_ui, "update_subscribers_ui", subs_stub.f);

    const compose_fade_stub = make_stub();
    override(compose_fade, "update_faded_users", compose_fade_stub.f);

    dispatch(event);
    assert.equal(compose_fade_stub.num_calls, 1);
    assert.equal(subs_stub.num_calls, 1);

    assert.ok(peer_data.is_user_subscribed(event.stream_ids[0], event.user_ids[0]));

    event = event_fixtures.subscription__peer_remove;
    dispatch(event);
    assert.equal(compose_fade_stub.num_calls, 2);
    assert.equal(subs_stub.num_calls, 2);

    assert.ok(!peer_data.is_user_subscribed(event.stream_ids[0], event.user_ids[0]));
});

test("remove", ({override}) => {
    const event = event_fixtures.subscription__remove;
    const event_sub = event.subscriptions[0];
    const stream_id = event_sub.stream_id;

    const sub = {
        stream_id,
        name: event_sub.name,
    };

    stream_data.add_sub(sub);

    const stub = make_stub();
    override(stream_events, "mark_unsubscribed", stub.f);
    dispatch(event);
    assert.equal(stub.num_calls, 1);
    const args = stub.get_args("sub");
    assert.deepEqual(args.sub, sub);
});

test("update", ({override}) => {
    const event = event_fixtures.subscription__update;

    const stub = make_stub();
    override(stream_events, "update_property", stub.f);
    dispatch(event);
    assert.equal(stub.num_calls, 1);
    const args = stub.get_args("stream_id", "property", "value");
    assert.deepEqual(args.stream_id, event.stream_id);
    assert.deepEqual(args.property, event.property);
    assert.deepEqual(args.value, event.value);
});

test("add error handling", () => {
    // test blueslip errors/warns
    const event = event_fixtures.subscription__add;

    blueslip.expect("error", "Subscribing to unknown stream with ID 101");
    dispatch(event);
    blueslip.reset();
});

test("peer event error handling (bad stream_ids/user_ids)", ({override}) => {
    override(compose_fade, "update_faded_users", () => {});

    const add_event = {
        type: "subscription",
        op: "peer_add",
        stream_ids: [8888, 9999],
        user_ids: [3333, 4444],
    };

    blueslip.expect("warn", "We have untracked stream_ids: 8888,9999");
    blueslip.expect("warn", "We have untracked user_ids: 3333,4444");
    dispatch(add_event);
    blueslip.reset();

    const remove_event = {
        type: "subscription",
        op: "peer_remove",
        stream_ids: [8888, 9999],
        user_ids: [3333, 4444],
    };

    blueslip.expect("warn", "We have untracked stream_ids: 8888,9999");
    blueslip.expect("warn", "We have untracked user_ids: 3333,4444");
    dispatch(remove_event);
});

test("stream update", ({override}) => {
    const event = event_fixtures.stream__update;

    const stub = make_stub();
    override(stream_events, "update_property", stub.f);
    override(settings_streams, "update_default_streams_table", noop);
    dispatch(event);
    assert.equal(stub.num_calls, 1);
    const args = stub.get_args("stream_id", "property", "value");
    assert.equal(args.stream_id, event.stream_id);
    assert.equal(args.property, event.property);
    assert.equal(args.value, event.value);
});

test("stream create", ({override, override_rewire}) => {
    const event = event_fixtures.stream__create;

    const stub = make_stub();
    override_rewire(stream_data, "create_streams", stub.f);
    override(stream_settings_ui, "add_sub_to_table", noop);
    override(overlays, "streams_open", () => true);
    dispatch(event);
    assert.equal(stub.num_calls, 1);
    const args = stub.get_args("streams");
    assert.deepEqual(
        args.streams.map((stream) => stream.stream_id),
        [101, 102],
    );
});

test("stream delete (normal)", ({override, override_rewire}) => {
    const event = event_fixtures.stream__delete;

    for (const stream of event.streams) {
        stream_data.add_sub(stream);
    }

    stream_data.subscribe_myself(event.streams[0]);

    override_rewire(stream_data, "delete_sub", noop);
    override(settings_streams, "update_default_streams_table", noop);

    narrow_state.is_for_stream_id = () => true;

    let bookend_updates = 0;
    override(message_lists.current, "update_trailing_bookend", () => {
        bookend_updates += 1;
    });

    const removed_stream_ids = [];

    override(stream_settings_ui, "remove_stream", (stream_id) => {
        removed_stream_ids.push(stream_id);
    });

    let removed_sidebar_rows = 0;
    override(stream_list, "remove_sidebar_row", () => {
        removed_sidebar_rows += 1;
    });

    dispatch(event);

    assert.deepEqual(removed_stream_ids, [event.streams[0].stream_id, event.streams[1].stream_id]);

    // We should possibly be able to make a single call to
    // update_trailing_bookend, but we currently do it for each stream.
    assert.equal(bookend_updates, 2);

    assert.equal(removed_sidebar_rows, 1);
});

test("stream delete (special streams)", ({override}) => {
    const event = event_fixtures.stream__delete;

    for (const stream of event.streams) {
        stream_data.add_sub(stream);
    }

    // sanity check data
    assert.equal(event.streams.length, 2);
    page_params.realm_notifications_stream_id = event.streams[0].stream_id;
    page_params.realm_signup_notifications_stream_id = event.streams[1].stream_id;

    override(stream_settings_ui, "remove_stream", noop);
    override(settings_org, "sync_realm_settings", noop);
    override(settings_streams, "update_default_streams_table", noop);
    override(message_lists.current, "update_trailing_bookend", noop);
    override(stream_list, "remove_sidebar_row", noop);

    dispatch(event);

    assert.equal(page_params.realm_notifications_stream_id, -1);
    assert.equal(page_params.realm_signup_notifications_stream_id, -1);
});
