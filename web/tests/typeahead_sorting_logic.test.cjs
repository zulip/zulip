"use strict";

/**
 * Tests for typeahead sorting logic.
 *
 * This test file specifically validates the typeahead sorting behavior,
 * particularly the NEW rule: Users with shorter names are preferred over those
 * with longer names as a final tiebreaker.
 *
 * KEY BEHAVIOR CHANGE:
 * The shorter name rule is ONLY applied when a user has started typing (query is
 * non-empty). This prevents alphabetical name changes when the user hasn't typed
 * anything yet, improving predictability of the typeahead dropdown.
 *
 * SORTING HIERARCHY (in order of precedence):
 *
 * For Stream Context (viewing messages in a channel):
 *   1. Subscribers > Non-subscribers
 *   2. Recency in current topic/stream
 *   3. PM conversation partners
 *
 * For PM Context (viewing direct messages):
 *   1. PM conversation partners > Non-partners
 *   2. Message count (higher first)
 *   3. Shorter name (ONLY if user has typed something)
 *
 * TESTS INCLUDED:
 * - compare_users_for_streams: Validates stream-specific sorting
 * - compare_users_for_pms: Validates PM sorting with conditional name length
 * - compare_user_with_wildcard: Validates broadcast mentions (@all, @everyone)
 * - compare_people_for_relevance: Validates overall sorting strategy
 * - Integration tests: Verify correct ordering with mixed user groups
 */

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
        people.clear_recipient_counts_for_testing();
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
    assert.equal(result < 0, true, "subscriber should come before non-subscriber");
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
    assert.equal(result < 0, true, "more recent user should come first");
});

test("compare_users_for_streams: same recency, PM partner comes first", () => {
    const stream_id = stream1.stream_id;
    const topic = "test topic";

    peer_data.add_subscriber(stream_id, user1.user_id);
    peer_data.add_subscriber(stream_id, user2.user_id);

    // Make user1 a PM partner
    pm_conversations.set_partner(user1.user_id);

    const result = th.compare_users_for_streams(user1, user2, stream_id, topic);
    assert.equal(result < 0, true, "PM partner should come first");
});

test("compare_users_for_streams: non-subscriber without recency, then PM partner", () => {
    const stream_id = stream1.stream_id;
    const topic = "test topic";

    // Neither is a subscriber
    pm_conversations.set_partner(user2.user_id);

    const result = th.compare_users_for_streams(user1, user2, stream_id, topic);
    assert.equal(result > 0, true, "user2 with PM partnership should come first");
});

// ============================================================================
// Tests for compare_users_for_pms
// ============================================================================
// compare_users_for_pms is used when sorting PM recipients (no stream context).
// Sort order: PM partners > message count > shorter name (only when query is not empty)

test("compare_users_for_pms: PM partners ranked before non-partners", () => {
    pm_conversations.set_partner(user1.user_id);

    const result = th.compare_users_for_pms(user1, user2);
    assert.equal(result < 0, true, "PM partner should come before non-partner");
});

test("compare_users_for_pms: both partners, higher count comes first", () => {
    pm_conversations.set_partner(user1.user_id);
    pm_conversations.set_partner(user2.user_id);

    people.set_recipient_count_for_testing(user1.user_id, 10);
    people.set_recipient_count_for_testing(user2.user_id, 5);

    const result = th.compare_users_for_pms(user1, user2);
    assert.equal(result < 0, true, "higher message count should come first");
});

test("compare_users_for_pms: same count and partner status, shorter name comes first", () => {
    // This test verifies the NEW behavior: when users have the same partner
    // status and message count, shorter names are preferred.
    // This rule ONLY applies when the user has started typing (query is non-empty).
    pm_conversations.set_partner(short_name_user.user_id);
    pm_conversations.set_partner(long_name_user.user_id);

    people.set_recipient_count_for_testing(short_name_user.user_id, 5);
    people.set_recipient_count_for_testing(long_name_user.user_id, 5);

    const result = th.compare_users_for_pms(short_name_user, long_name_user, "a");
    assert.equal(result < 0, true, "shorter name should come first");
});

test("compare_users_for_pms: same count and partner status, name length sorting only when query is non-empty", () => {
    // This test verifies that name length comparison is ONLY applied when the
    // user has started typing (query is non-empty). Without a query, users with
    // equal PM partner status and message count will be treated as a tie (result=0).
    pm_conversations.set_partner(short_name_user.user_id);
    pm_conversations.set_partner(long_name_user.user_id);

    people.set_recipient_count_for_testing(short_name_user.user_id, 5);
    people.set_recipient_count_for_testing(long_name_user.user_id, 5);

    // With empty query, result should be 0 (tie)
    const result_empty = th.compare_users_for_pms(short_name_user, long_name_user, "");
    assert.equal(result_empty, 0, "name length should not be considered with empty query");

    // With non-empty query, shorter name should come first
    const result_with_query = th.compare_users_for_pms(short_name_user, long_name_user, "a");
    assert.equal(
        result_with_query < 0,
        true,
        "shorter name should come first when query is not empty",
    );
});

test("compare_users_for_pms: not partners but with different counts", () => {
    // Neither is a partner
    people.set_recipient_count_for_testing(user1.user_id, 10);
    people.set_recipient_count_for_testing(user2.user_id, 5);

    const result = th.compare_users_for_pms(user1, user2);
    assert.equal(result < 0, true, "higher count should come first");
});

// ============================================================================
// Tests for compare_user_with_wildcard (PM context)
// ============================================================================

test("compare_user_with_wildcard (PM): PM partner gets preference", () => {
    pm_conversations.set_partner(user1.user_id);

    const result = th.compare_user_with_wildcard(user1);
    assert.equal(result < 0, true, "PM partner should have priority over wildcard");
});

test("compare_user_with_wildcard (PM): non-partner has less preference", () => {
    // user2 is not a PM partner
    const result = th.compare_user_with_wildcard(user2);
    assert.equal(result > 0, true, "non-partner should have less priority than wildcard");
});

// ============================================================================
// Tests for compare_user_with_wildcard (Stream context)
// ============================================================================

test("compare_user_with_wildcard (Stream): subscriber gets preference", () => {
    const stream_id = stream1.stream_id;
    const topic = "test topic";

    peer_data.add_subscriber(stream_id, user1.user_id);

    const result = th.compare_user_with_wildcard(user1, stream_id, topic);
    assert.equal(result < 0, true, "subscriber should have priority over wildcard");
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
    assert.equal(result < 0, true, "topic participant should have priority over wildcard");
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
    assert.equal(result < 0, true, "stream participant should have priority over wildcard");
});

test("compare_user_with_wildcard (Stream): PM partner but nothing else", () => {
    const stream_id = stream1.stream_id;
    const topic = "test topic";

    pm_conversations.set_partner(user1.user_id);

    const result = th.compare_user_with_wildcard(user1, stream_id, topic);
    assert.equal(
        result < 0,
        true,
        "PM partner should have priority over wildcard in stream context",
    );
});

test("compare_user_with_wildcard (Stream): no relevance should have less priority", () => {
    const stream_id = stream1.stream_id;
    const topic = "test topic";

    const result = th.compare_user_with_wildcard(user2, stream_id, topic);
    assert.equal(
        result > 0,
        true,
        "user with no relevance should have less priority than wildcard",
    );
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
    assert.equal(result, 0, "equal criteria should produce a tie");
});

test("compare_people_for_relevance (Stream): user vs wildcard (subscriber wins)", () => {
    const stream_id = stream1.stream_id;
    const topic = "test topic";

    peer_data.add_subscriber(stream_id, user1.user_id);

    const person_user = {type: "user", user: user1};
    const person_wildcard = {type: "broadcast", user: {special_item_text: "@all", user_id: 0}};

    const result = th.compare_people_for_relevance(person_user, person_wildcard, stream_id, topic);
    assert.equal(result < 0, true, "subscriber should come before wildcard");
});

test("compare_people_for_relevance (Stream): wildcard vs user (non-subscriber)", () => {
    const stream_id = stream1.stream_id;
    const topic = "test topic";

    const person_wildcard = {type: "broadcast", user: {special_item_text: "@all", user_id: 0}};
    const person_user = {type: "user", user: user1};

    const result = th.compare_people_for_relevance(person_wildcard, person_user, stream_id, topic);
    assert.equal(result < 0, true, "wildcard should come before non-subscriber");
});

// ============================================================================
// Tests for compare_people_for_relevance (PM context)
// ============================================================================

test("compare_people_for_relevance (PM): two users both PM partners", () => {
    pm_conversations.set_partner(user1.user_id);
    pm_conversations.set_partner(user2.user_id);

    people.set_recipient_count_for_testing(user1.user_id, 10);
    people.set_recipient_count_for_testing(user2.user_id, 5);

    const person_a = {type: "user", user: user1};
    const person_b = {type: "user", user: user2};

    const result = th.compare_people_for_relevance(person_a, person_b);
    assert.equal(result < 0, true, "user with higher count should come first in PM context");
});

test("compare_people_for_relevance (PM): user vs wildcard (partner wins)", () => {
    pm_conversations.set_partner(user1.user_id);

    const person_user = {type: "user", user: user1};
    const person_wildcard = {type: "broadcast", user: {special_item_text: "@all", user_id: 0}};

    const result = th.compare_people_for_relevance(person_user, person_wildcard);
    assert.equal(result < 0, true, "PM partner should come before wildcard in PM context");
});

test("compare_people_for_relevance (PM): wildcard vs user (non-partner)", () => {
    const person_wildcard = {type: "broadcast", user: {special_item_text: "@all", user_id: 0}};
    const person_user = {type: "user", user: user1};

    const result = th.compare_people_for_relevance(person_wildcard, person_user);
    assert.equal(result < 0, true, "wildcard should come before non-partner in PM context");
});

test("compare_people_for_relevance (PM): two wildcards", () => {
    const person_wildcard_a = {
        type: "broadcast",
        user: {special_item_text: "@all", user_id: 0, idx: 1},
    };
    const person_wildcard_b = {
        type: "broadcast",
        user: {special_item_text: "@everyone", user_id: 0, idx: 2},
    };

    const result = th.compare_people_for_relevance(person_wildcard_a, person_wildcard_b);
    assert.equal(result < 0, true, "wildcards should be compared by idx");
});

// ============================================================================
// Integration tests - Sorting multiple people
// ============================================================================

test("sort people for stream relevance - mixed users", () => {
    const stream_id = stream1.stream_id;
    const topic = "test topic";

    peer_data.add_subscriber(stream_id, user1.user_id);
    pm_conversations.set_partner(user2.user_id);

    const people_list = [
        {type: "user", user: user2},
        {type: "user", user: user1},
    ];

    people_list.sort((a, b) => th.compare_people_for_relevance(a, b, stream_id, topic));

    assert.equal(people_list[0].user.user_id, user1.user_id, "subscriber should come first");
    assert.equal(people_list[1].user.user_id, user2.user_id, "PM partner should come second");
});

test("sort people for PM relevance - mixed users", () => {
    pm_conversations.set_partner(user1.user_id);
    people.set_recipient_count_for_testing(user1.user_id, 5);
    people.set_recipient_count_for_testing(user2.user_id, 10);

    const people_list = [
        {type: "user", user: user2},
        {type: "user", user: user1},
    ];

    people_list.sort((a, b) => th.compare_people_for_relevance(a, b));

    assert.equal(people_list[0].user.user_id, user1.user_id, "PM partner should come first");
    assert.equal(people_list[1].user.user_id, user2.user_id, "non-partner should come second");
});

test("sort users by name length - same other criteria", () => {
    pm_conversations.set_partner(short_name_user.user_id);
    pm_conversations.set_partner(long_name_user.user_id);
    people.set_recipient_count_for_testing(short_name_user.user_id, 5);
    people.set_recipient_count_for_testing(long_name_user.user_id, 5);

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

test("stream sorting priority: subscriber > topic participant > stream participant > PM partner", () => {
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

    // user4: not subscriber, no stream participation, PM partner
    pm_conversations.set_partner(user4.user_id);

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
    assert.equal(people_list[3].user.user_id, user4.user_id, "PM partner should be fourth");
});
