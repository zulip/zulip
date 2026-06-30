"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const people = zrequire("people");
const pm_conversations = zrequire("pm_conversations");
const recent_senders = zrequire("recent_senders");
const peer_data = zrequire("peer_data");
const stream_data = zrequire("stream_data");
const {set_current_user} = zrequire("state_data");
const th = zrequire("typeahead_helper");

const current_user = {is_guest: false, is_admin: false};
set_current_user(current_user);
people.initialize_current_user({user_id: 1, full_name: "Me"});

// Test users
const user1 = {
    user_id: 2,
    full_name: "Alice",
    email: "alice@example.com",
    is_bot: false,
};

const user2 = {
    user_id: 3,
    full_name: "Bob",
    email: "bob@example.com",
    is_bot: false,
};

const user3 = {
    user_id: 4,
    full_name: "Charlie",
    email: "charlie@example.com",
    is_bot: false,
};

const user4 = {
    user_id: 5,
    full_name: "David",
    email: "david@example.com",
    is_bot: false,
};

const user5 = {
    user_id: 6,
    full_name: "Eve",
    email: "eve@example.com",
    is_bot: false,
};

const bot_user = {
    user_id: 7,
    full_name: "Bot User",
    email: "bot@example.com",
    is_bot: true,
};

const short_name_user = {
    user_id: 8,
    full_name: "Al",
    email: "al@example.com",
    is_bot: false,
};

const long_name_user = {
    user_id: 9,
    full_name: "Alexander",
    email: "alexander@example.com",
    is_bot: false,
};

for (const user of [user1, user2, user3, user4, user5, bot_user, short_name_user, long_name_user]) {
    people.add_active_user(user);
}

// Test streams
const stream1 = {
    name: "Dev",
    stream_id: 101,
    color: "blue",
    subscriber_count: 0,
};

const stream2 = {
    name: "General",
    stream_id: 102,
    color: "green",
    subscriber_count: 0,
};

stream_data.create_streams([stream1, stream2]);
stream_data.add_sub_for_tests(stream1);
stream_data.add_sub_for_tests(stream2);

function test(label, f) {
    run_test(label, (helpers) => {
        pm_conversations.clear_for_testing();
        recent_senders.clear_for_testing();
        peer_data.clear_for_testing();
        peer_data.set_subscribers(stream1.stream_id, [], true);
        peer_data.set_subscribers(stream2.stream_id, [], true);
        f(helpers);
    });
}

// ============================================================================
// Tests for compare_users_for_streams
// ============================================================================

test("compare_users_for_streams: subscribers ranked before non-subscribers", () => {
    const stream_id = stream1.stream_id;
    const topic = "test topic";

    // Make user1 a subscriber
    peer_data.add_subscriber(stream_id, user1.user_id);

    const result = th.compare_users_for_streams(user1, user2, stream_id, topic);
    assert.ok(result < 0, "subscriber should come before non-subscriber");
});

test("compare_users_for_streams: both subscribers, recency decides", () => {
    const stream_id = stream1.stream_id;
    const topic = "test topic";

    peer_data.add_subscriber(stream_id, user1.user_id);
    peer_data.add_subscriber(stream_id, user2.user_id);

    recent_senders.process_stream_message({
        stream_id,
        topic,
        sender_id: user2.user_id,
        id: 100,
    });
    recent_senders.process_stream_message({
        stream_id,
        topic,
        sender_id: user1.user_id,
        id: 200,
    });

    const result = th.compare_users_for_streams(user1, user2, stream_id, topic);
    assert.ok(result < 0, "more recent user should come first");
});

test("compare_users_for_streams: same recency, recent DM contact comes first", () => {
    const stream_id = stream1.stream_id;
    const topic = "test topic";

    peer_data.add_subscriber(stream_id, user1.user_id);
    peer_data.add_subscriber(stream_id, user2.user_id);

    // Give user1 a recent direct message.
    pm_conversations.recent.insert([user1.user_id], 100);

    const result = th.compare_users_for_streams(user1, user2, stream_id, topic);
    assert.ok(result < 0, "recent DM contact should come first");
});

test("compare_users_for_streams: non-subscribers, recent DM contact comes first", () => {
    const stream_id = stream1.stream_id;
    const topic = "test topic";

    // Neither is a subscriber
    pm_conversations.recent.insert([user2.user_id], 100);

    const result = th.compare_users_for_streams(user1, user2, stream_id, topic);
    assert.ok(result > 0, "user2 with a recent direct message should come first");
});

// ============================================================================
// Tests for compare_users_for_dms
// ============================================================================
// compare_users_for_dms is used when sorting DM recipients (no stream context).
// Sort order: direct message recency > shorter name (if query) > alphabetical

test("compare_users_for_dms: users with DM history ranked before those without", () => {
    pm_conversations.recent.insert([user1.user_id], 100);

    const result = th.compare_users_for_dms(user1, user2);
    assert.ok(result < 0, "user with a direct message should come before one without");
});

test("compare_users_for_dms: both have DMs, more recent comes first", () => {
    pm_conversations.recent.insert([user2.user_id], 100);
    pm_conversations.recent.insert([user1.user_id], 200);

    const result = th.compare_users_for_dms(user1, user2);
    assert.ok(result < 0, "more recent direct message should come first");
});

test("compare_users_for_dms: a more recent group DM counts toward recency", () => {
    // A newer group DM that includes user1 outranks an older 1:1 with user2.
    pm_conversations.recent.insert([user2.user_id], 100);
    pm_conversations.recent.insert([user1.user_id, user3.user_id], 200);

    const result = th.compare_users_for_dms(user1, user2);
    assert.ok(result < 0, "member of a more recent group DM should come first");
});

test("compare_users_for_dms: same DM recency, shorter name comes first", () => {
    // When users tie on direct message recency, shorter names are preferred.
    // This rule ONLY applies when the user has started typing (query is non-empty).
    const result = th.compare_users_for_dms(short_name_user, long_name_user, "a");
    assert.ok(result < 0, "shorter name should come first");
});

test("compare_users_for_dms: name length sorting only when query is non-empty", () => {
    // Name length comparison is ONLY applied when the user has started typing
    // (query is non-empty). Without a query, users with equal direct message
    // recency fall through to alphabetical.

    // With empty query, name length is skipped; alphabetical applies
    const result_empty = th.compare_users_for_dms(short_name_user, long_name_user, "");
    assert.ok(result_empty < 0, "alphabetical sort applies with empty query");

    // With non-empty query, shorter name should come first
    const result_with_query = th.compare_users_for_dms(short_name_user, long_name_user, "a");
    assert.ok(result_with_query < 0, "shorter name should come first when query is not empty");
});

// ============================================================================
// Tests for compare_user_with_wildcard (DM context)
// ============================================================================

test("compare_user_with_wildcard (DM): recent DM contact gets preference", () => {
    pm_conversations.recent.insert([user1.user_id], 100);

    const result = th.compare_user_with_wildcard(user1);
    assert.ok(result < 0, "recent DM contact should have priority over wildcard");
});

test("compare_user_with_wildcard (DM): user without DM history has less preference", () => {
    // user2 has no direct message history.
    const result = th.compare_user_with_wildcard(user2);
    assert.ok(result > 0, "user with no DM history should have less priority than wildcard");
});

// ============================================================================
// Tests for compare_user_with_wildcard (Stream context)
// ============================================================================

test("compare_user_with_wildcard (Stream): subscriber gets preference", () => {
    const stream_id = stream1.stream_id;
    const topic = "test topic";

    peer_data.add_subscriber(stream_id, user1.user_id);

    const result = th.compare_user_with_wildcard(user1, stream_id, topic);
    assert.ok(result < 0, "subscriber should have priority over wildcard");
});

test("compare_user_with_wildcard (Stream): non-subscriber who posted in topic", () => {
    const stream_id = stream1.stream_id;
    const topic = "test topic";

    recent_senders.process_stream_message({
        stream_id,
        topic,
        sender_id: user1.user_id,
        id: 110,
    });

    const result = th.compare_user_with_wildcard(user1, stream_id, topic);
    assert.ok(result < 0, "topic participant should have priority over wildcard");
});

test("compare_user_with_wildcard (Stream): posted in stream but not topic", () => {
    const stream_id = stream1.stream_id;
    const topic = "test topic";

    recent_senders.process_stream_message({
        stream_id,
        topic: "other topic",
        sender_id: user1.user_id,
        id: 120,
    });

    const result = th.compare_user_with_wildcard(user1, stream_id, topic);
    assert.ok(result < 0, "stream participant should have priority over wildcard");
});

test("compare_user_with_wildcard (Stream): recent DM contact but nothing else", () => {
    const stream_id = stream1.stream_id;
    const topic = "test topic";

    pm_conversations.recent.insert([user1.user_id], 100);

    const result = th.compare_user_with_wildcard(user1, stream_id, topic);
    assert.ok(result < 0, "recent DM contact should have priority over wildcard in stream context");
});

test("compare_user_with_wildcard (Stream): no relevance should have less priority", () => {
    const stream_id = stream1.stream_id;
    const topic = "test topic";

    const result = th.compare_user_with_wildcard(user2, stream_id, topic);
    assert.ok(result > 0, "user with no relevance should have less priority than wildcard");
});

// ============================================================================
// Tests for compare_people_for_relevance (Stream context)
// ============================================================================

test("compare_people_for_relevance (Stream): two users both subscribers", () => {
    const stream_id = stream1.stream_id;
    const topic = "test topic";

    peer_data.add_subscriber(stream_id, user1.user_id);
    peer_data.add_subscriber(stream_id, user2.user_id);

    const person_a = {type: "user", user: user1};
    const person_b = {type: "user", user: user2};

    const result = th.compare_people_for_relevance(person_a, person_b, stream_id, topic);
    assert.ok(result < 0, "equal criteria, alphabetical tiebreaker: Alice < Bob");
});

test("compare_people_for_relevance (Stream): user vs wildcard (subscriber wins)", () => {
    const stream_id = stream1.stream_id;
    const topic = "test topic";

    peer_data.add_subscriber(stream_id, user1.user_id);

    const person_user = {type: "user", user: user1};
    const person_wildcard = {type: "broadcast", user: {special_item_text: "@all", user_id: 0}};

    const result = th.compare_people_for_relevance(person_user, person_wildcard, stream_id, topic);
    assert.ok(result < 0, "subscriber should come before wildcard");
});

test("compare_people_for_relevance (Stream): wildcard vs user (non-subscriber)", () => {
    const stream_id = stream1.stream_id;
    const topic = "test topic";

    const person_wildcard = {type: "broadcast", user: {special_item_text: "@all", user_id: 0}};
    const person_user = {type: "user", user: user1};

    const result = th.compare_people_for_relevance(person_wildcard, person_user, stream_id, topic);
    assert.ok(result < 0, "wildcard should come before non-subscriber");
});

// ============================================================================
// Tests for compare_people_for_relevance (DM context)
// ============================================================================

test("compare_people_for_relevance (DM): two users with DMs, more recent first", () => {
    pm_conversations.recent.insert([user2.user_id], 100);
    pm_conversations.recent.insert([user1.user_id], 200);

    const person_a = {type: "user", user: user1};
    const person_b = {type: "user", user: user2};

    const result = th.compare_people_for_relevance(person_a, person_b);
    assert.ok(result < 0, "user with the more recent direct message should come first");
});

test("compare_people_for_relevance (DM): user vs wildcard (recent DM wins)", () => {
    pm_conversations.recent.insert([user1.user_id], 100);

    const person_user = {type: "user", user: user1};
    const person_wildcard = {type: "broadcast", user: {special_item_text: "@all", user_id: 0}};

    const result = th.compare_people_for_relevance(person_user, person_wildcard);
    assert.ok(result < 0, "recent DM contact should come before wildcard in DM context");
});

test("compare_people_for_relevance (DM): wildcard vs user with no DM history", () => {
    const person_wildcard = {type: "broadcast", user: {special_item_text: "@all", user_id: 0}};
    const person_user = {type: "user", user: user1};

    const result = th.compare_people_for_relevance(person_wildcard, person_user);
    assert.ok(result < 0, "wildcard should come before a user with no DM history");
});

test("compare_people_for_relevance (DM): two wildcards", () => {
    const person_wildcard_a = {
        type: "broadcast",
        user: {special_item_text: "@all", user_id: 0, idx: 1},
    };
    const person_wildcard_b = {
        type: "broadcast",
        user: {special_item_text: "@everyone", user_id: 0, idx: 2},
    };

    const result = th.compare_people_for_relevance(person_wildcard_a, person_wildcard_b);
    assert.ok(result < 0, "wildcards should be compared by idx");
});

// ============================================================================
// Integration tests - Sorting multiple people
// ============================================================================

test("sort people for stream relevance - mixed users", () => {
    const stream_id = stream1.stream_id;
    const topic = "test topic";

    peer_data.add_subscriber(stream_id, user1.user_id);
    pm_conversations.recent.insert([user2.user_id], 100);

    const people_list = [
        {type: "user", user: user2},
        {type: "user", user: user1},
    ];

    people_list.sort((a, b) => th.compare_people_for_relevance(a, b, stream_id, topic));

    assert.equal(people_list[0].user.user_id, user1.user_id, "subscriber should come first");
    assert.equal(
        people_list[1].user.user_id,
        user2.user_id,
        "recent DM contact should come second",
    );
});

test("sort people for DM relevance - mixed users", () => {
    // user1 has a more recent direct message than user2.
    pm_conversations.recent.insert([user2.user_id], 100);
    pm_conversations.recent.insert([user1.user_id], 200);

    const people_list = [
        {type: "user", user: user2},
        {type: "user", user: user1},
    ];

    people_list.sort((a, b) => th.compare_people_for_relevance(a, b));

    assert.equal(
        people_list[0].user.user_id,
        user1.user_id,
        "more recent DM contact should come first",
    );
    assert.equal(
        people_list[1].user.user_id,
        user2.user_id,
        "less recent DM contact should come second",
    );
});

test("sort users by name length - same other criteria", () => {
    // Neither user has direct message history, so they tie on recency and the
    // non-empty query makes name length the deciding factor.
    const people_list = [
        {type: "user", user: long_name_user},
        {type: "user", user: short_name_user},
    ];

    people_list.sort((a, b) => th.compare_people_for_relevance(a, b, undefined, undefined, "a"));

    assert.equal(
        people_list[0].user.user_id,
        short_name_user.user_id,
        "shorter name should come first",
    );
    assert.equal(
        people_list[1].user.user_id,
        long_name_user.user_id,
        "longer name should come second",
    );
});

test("stream sorting priority: subscriber > topic participant > stream participant > DM contact", () => {
    const stream_id = stream1.stream_id;
    const topic = "test topic";

    // user1: subscriber
    peer_data.add_subscriber(stream_id, user1.user_id);

    // user2: not subscriber, but posted in topic
    recent_senders.process_stream_message({
        stream_id,
        topic,
        sender_id: user2.user_id,
        id: 300,
    });

    // user3: posted in stream but not topic
    recent_senders.process_stream_message({
        stream_id,
        topic: "other topic",
        sender_id: user3.user_id,
        id: 250,
    });

    // user4: not subscriber, no stream participation, but a recent DM contact
    pm_conversations.recent.insert([user4.user_id], 400);

    const people_list = [
        {type: "user", user: user3},
        {type: "user", user: user2},
        {type: "user", user: user4},
        {type: "user", user: user1},
    ];

    people_list.sort((a, b) => th.compare_people_for_relevance(a, b, stream_id, topic));

    assert.equal(people_list[0].user.user_id, user1.user_id, "subscriber should be first");
    assert.equal(people_list[1].user.user_id, user2.user_id, "topic participant should be second");
    assert.equal(people_list[2].user.user_id, user3.user_id, "stream participant should be third");
    assert.equal(people_list[3].user.user_id, user4.user_id, "recent DM contact should be fourth");
});
