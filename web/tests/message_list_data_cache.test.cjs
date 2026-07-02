"use strict";

const assert = require("node:assert/strict");

const {make_realm} = require("./lib/example_realm.cjs");
const {make_stream} = require("./lib/example_stream.cjs");
const {make_user} = require("./lib/example_user.cjs");
const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const muted_users = zrequire("muted_users");
const people = zrequire("people");
const stream_data = zrequire("stream_data");
const state_data = zrequire("state_data");
const {initialize_user_settings} = zrequire("user_settings");

state_data.set_realm(make_realm());
const me = make_user({email: "me@example.com", user_id: 1, full_name: "Me"});
const alice = make_user({email: "alice@example.com", user_id: 2, full_name: "Alice"});
const bob = make_user({email: "bob@example.com", user_id: 3, full_name: "Bob"});
people.add_active_user(me, "server_events");
people.add_active_user(alice, "server_events");
people.add_active_user(bob, "server_events");
people.initialize_current_user(me.user_id);
state_data.set_current_user(me);
muted_users.set_muted_users([]);
initialize_user_settings({user_settings: {}});

const foo_stream = make_stream({name: "Foo", stream_id: 100});
stream_data.add_sub_for_tests(foo_stream);

const {Filter} = zrequire("filter");
const {MessageListData} = zrequire("../src/message_list_data");
const message_list_data_cache = zrequire("../src/message_list_data_cache");
const recent_view_messages_data = zrequire("../src/recent_view_messages_data");

const recent = recent_view_messages_data.recent_view_messages_data;

function make_data(filter_terms, message_ids = []) {
    const data = new MessageListData({
        excludes_muted_topics: false,
        excludes_muted_users: false,
        filter: new Filter(filter_terms),
    });
    if (message_ids.length > 0) {
        const messages = message_ids.map((id) => ({
            id,
            type: "stream",
            stream_id: foo_stream.stream_id,
            topic: "bar",
            sender_id: me.user_id,
            unread: false,
        }));
        data.add_messages(messages, true);
    }
    return data;
}

function reset_cache() {
    message_list_data_cache.clear();
    recent.clear();
}

function test(label, f) {
    run_test(label, () => {
        reset_cache();
        f();
    });
}

const channel_topic_terms = [
    {operator: "channel", operand: foo_stream.stream_id.toString()},
    {operator: "topic", operand: "bar"},
];
const channel_topic_near_terms = (msg_id) => [
    ...channel_topic_terms,
    {operator: "near", operand: msg_id.toString()},
];
const channel_topic_with_terms = (msg_id) => [
    ...channel_topic_terms,
    {operator: "with", operand: msg_id.toString()},
];
const dm_terms = [{operator: "dm", operand: [alice.user_id]}];
const dm_near_terms = (msg_id) => [...dm_terms, {operator: "near", operand: msg_id.toString()}];
const dm_with_terms = (msg_id) => [...dm_terms, {operator: "with", operand: msg_id.toString()}];

test("cache miss returns only recent_view_messages_data", () => {
    const supersets = message_list_data_cache.get_superset_datasets(
        new Filter(channel_topic_terms),
    );
    assert.deepEqual(supersets, [recent]);
});

test("exact match returned alongside fallback", () => {
    const exact = make_data(channel_topic_terms);
    message_list_data_cache.add(exact);
    const supersets = message_list_data_cache.get_superset_datasets(
        new Filter(channel_topic_terms),
    );
    assert.deepEqual(supersets, [exact, recent]);
});

test("conversation cache used to populate `near` view", () => {
    // We have a cached `channel:foo topic:bar` view that contains message 42;
    // target `channel:foo topic:bar near:42` should reuse it.
    const conversation = make_data(channel_topic_terms, [40, 42, 44]);
    message_list_data_cache.add(conversation);

    const supersets = message_list_data_cache.get_superset_datasets(
        new Filter(channel_topic_near_terms(42)),
    );
    assert.deepEqual(supersets, [conversation, recent]);
});

test("conversation cache used to populate `with` view", () => {
    const conversation = make_data(channel_topic_terms, [40, 42, 44]);
    message_list_data_cache.add(conversation);

    const supersets = message_list_data_cache.get_superset_datasets(
        new Filter(channel_topic_with_terms(42)),
    );
    assert.deepEqual(supersets, [conversation, recent]);
});

test("conversation cache skipped when it lacks the anchor message", () => {
    const conversation = make_data(channel_topic_terms, [10, 11, 12]);
    message_list_data_cache.add(conversation);

    const supersets = message_list_data_cache.get_superset_datasets(
        new Filter(channel_topic_near_terms(42)),
    );
    assert.deepEqual(supersets, [recent]);
});

test("two near views differing only in anchor share cached data", () => {
    // Cached `near:42` view; target `near:99` should still consume it
    // when the cached dataset already includes message 99.
    const cached_near = make_data(channel_topic_near_terms(42), [40, 42, 99]);
    message_list_data_cache.add(cached_near);

    const supersets = message_list_data_cache.get_superset_datasets(
        new Filter(channel_topic_near_terms(99)),
    );
    assert.deepEqual(supersets, [cached_near, recent]);
});

test("exact match for `near` view is not duplicated by helper", () => {
    const cached_near = make_data(channel_topic_near_terms(42), [40, 42, 44]);
    message_list_data_cache.add(cached_near);

    const supersets = message_list_data_cache.get_superset_datasets(
        new Filter(channel_topic_near_terms(42)),
    );
    // cached_near matches both the exact-match check and the helper's
    // criteria; make sure it only appears once.
    assert.deepEqual(supersets, [cached_near, recent]);
});

test("DM `near` view uses cached DM conversation", () => {
    const dm_cached = make_data(dm_terms);
    dm_cached.add_messages(
        [
            {
                id: 7,
                type: "private",
                sender_id: alice.user_id,
                display_recipient: [{id: me.user_id}, {id: alice.user_id}],
                unread: false,
            },
        ],
        true,
    );
    message_list_data_cache.add(dm_cached);

    const supersets = message_list_data_cache.get_superset_datasets(new Filter(dm_near_terms(7)));
    assert.deepEqual(supersets, [dm_cached, recent]);
});

test("non-conversation cached views (e.g. is:starred) are not used as supersets", () => {
    const starred = make_data([{operator: "is", operand: "starred"}]);
    starred.add_messages(
        [
            {
                id: 42,
                type: "stream",
                stream_id: foo_stream.stream_id,
                topic: "bar",
                sender_id: me.user_id,
                starred: true,
                unread: false,
            },
        ],
        true,
    );
    message_list_data_cache.add(starred);

    const supersets = message_list_data_cache.get_superset_datasets(
        new Filter(channel_topic_near_terms(42)),
    );
    // The starred view contains the message but isn't a conversation view,
    // so muting semantics may differ — we must not use it as a superset.
    assert.deepEqual(supersets, [recent]);
});

test("non-near/with target ignores the helper entirely", () => {
    const cached_near = make_data(channel_topic_near_terms(42), [40, 42, 44]);
    message_list_data_cache.add(cached_near);

    // Target lacks both near and with; even though a cached conversation
    // view exists with overlapping messages, the helper is a no-op.
    const supersets = message_list_data_cache.get_superset_datasets(
        new Filter(channel_topic_terms),
    );
    assert.deepEqual(supersets, [recent]);
});

test("recent_view_messages_data containing message is not double-listed", () => {
    recent.add_messages(
        [
            {
                id: 42,
                type: "stream",
                stream_id: foo_stream.stream_id,
                topic: "bar",
                sender_id: me.user_id,
                unread: false,
            },
        ],
        true,
    );

    const supersets = message_list_data_cache.get_superset_datasets(
        new Filter(channel_topic_near_terms(42)),
    );
    // `recent` is empty-filter, so it's not a conversation view; the helper
    // shouldn't include it. The fallback at the end adds it exactly once.
    assert.deepEqual(supersets, [recent]);
});

test("multiple conversation caches are all considered", () => {
    const conversation = make_data(channel_topic_terms, [40, 42, 44]);
    const cached_near = make_data(channel_topic_near_terms(60), [58, 60, 62]);
    message_list_data_cache.add(conversation);
    message_list_data_cache.add(cached_near);
    // Add a second message to `conversation` so it also contains 62.
    conversation.add_messages(
        [
            {
                id: 62,
                type: "stream",
                stream_id: foo_stream.stream_id,
                topic: "bar",
                sender_id: me.user_id,
                unread: false,
            },
        ],
        true,
    );

    const supersets = message_list_data_cache.get_superset_datasets(
        new Filter(channel_topic_near_terms(62)),
    );
    // Both cached conversation datasets contain message 62, so both should
    // be candidates. recent_view_messages_data is always last.
    assert.equal(supersets.length, 3);
    assert.ok(supersets.includes(conversation));
    assert.ok(supersets.includes(cached_near));
    assert.equal(supersets.at(-1), recent);
});

test("conversation-view muting flags keep candidate reuse safe", () => {
    // `get_supersets_containing_anchor_msg` trusts that a conversation-view
    // candidate has not silently dropped a message the target needs. That
    // relies on the muting flags below; pin them so a future filter.ts
    // change forces this reasoning to be re-examined.
    const cases = [
        {terms: channel_topic_terms, excludes_muted_users: true},
        {terms: channel_topic_near_terms(42), excludes_muted_users: true},
        {terms: channel_topic_with_terms(42), excludes_muted_users: true},
        {terms: dm_terms, excludes_muted_users: false},
        {terms: dm_near_terms(7), excludes_muted_users: false},
        {terms: dm_with_terms(7), excludes_muted_users: false},
    ];
    for (const {terms, excludes_muted_users} of cases) {
        const filter = new Filter(terms);
        assert.ok(filter.is_conversation_view());
        // Muted-topic filtering is disabled for every conversation view, so
        // a candidate cannot have dropped a message on that basis.
        assert.equal(filter.excludes_muted_topics(), false);
        // Muted-user filtering may apply, but only ever identically across
        // views of the same shape (and channel and DM messages never share a
        // dataset), so a candidate drops only what the target would too.
        assert.equal(filter.excludes_muted_users(), excludes_muted_users);
    }
});
