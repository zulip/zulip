"use strict";

const assert = require("node:assert/strict");

const {make_message_list} = require("./lib/message_list.cjs");
const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {page_params} = require("./lib/zpage_params.cjs");

const people = zrequire("people");
const {Filter} = zrequire("../src/filter");
const stream_data = zrequire("stream_data");
const narrow_state = zrequire("narrow_state");
const message_lists = zrequire("message_lists");
const inbox_util = zrequire("inbox_util");

function set_filter(raw_terms) {
    const terms = raw_terms.map((op) => ({
        operator: op[0],
        operand: op[1],
    }));
    const msg_list = make_message_list(terms);
    message_lists.set_current(msg_list);

    return msg_list.data.filter;
}

function test(label, f) {
    run_test(label, ({override}) => {
        message_lists.set_current(undefined);
        stream_data.clear_subscriptions();
        f({override});
    });
}

test("stream", () => {
    assert.equal(narrow_state.public_search_terms(), undefined);
    assert.ok(!narrow_state.filter());
    assert.equal(narrow_state.stream_id(), undefined);

    // hash_util.decode_operand returns an empty string when
    // stream_data.slug_to_stream_id returns undefined, e.g., the
    // stream name in the URL no longer exists or is inaccessible.
    set_filter([["channel", ""]]);
    assert.ok(narrow_state.filter());
    assert.equal(narrow_state.stream_name(), undefined);
    assert.equal(narrow_state.stream_id(), undefined);
    assert.equal(narrow_state.stream_sub(), undefined);

    const test_stream_id = 15;
    assert.ok(!narrow_state.narrowed_to_stream_id(test_stream_id));

    // Stream doesn't exist or is inaccessible. The narrow
    // does parse the channel operand as a valid number.
    set_filter([["stream", test_stream_id.toString()]]);
    assert.ok(narrow_state.filter());
    // These do not check for stream subscription data.
    assert.equal(narrow_state.stream_id(), test_stream_id);
    assert.ok(narrow_state.narrowed_to_stream_id(test_stream_id));
    // These do check for stream subscription data.
    assert.equal(narrow_state.stream_name(), undefined);
    assert.equal(narrow_state.stream_id(undefined, true), undefined);
    assert.equal(narrow_state.stream_sub(), undefined);

    // Stream exists and user has access to the stream.
    const test_stream = {name: "Test", stream_id: test_stream_id};
    stream_data.add_sub(test_stream);
    set_filter([
        ["stream", test_stream_id.toString()],
        ["topic", "Bar"],
        ["search", "yo"],
    ]);
    assert.ok(narrow_state.filter());

    assert.equal(narrow_state.stream_name(), "Test");
    assert.equal(narrow_state.stream_id(), test_stream_id);
    assert.equal(narrow_state.stream_sub().stream_id, test_stream.stream_id);
    assert.equal(narrow_state.topic(), "Bar");
    assert.ok(narrow_state.narrowed_to_stream_id(test_stream_id));

    const expected_terms = [
        {negated: false, operator: "channel", operand: test_stream_id.toString()},
        {negated: false, operator: "topic", operand: "Bar"},
        {negated: false, operator: "search", operand: "yo"},
    ];

    const public_terms = narrow_state.public_search_terms();
    assert.deepEqual(public_terms, expected_terms);
});

const foo_stream_id = 72;
const foo_stream = {name: "Foo", stream_id: foo_stream_id};
test("narrowed", () => {
    assert.ok(!narrow_state.narrowed_to_pms());
    assert.ok(!narrow_state.narrowed_by_reply());
    assert.ok(!narrow_state.narrowed_by_pm_reply());
    assert.ok(!narrow_state.narrowed_by_topic_reply());
    assert.ok(!narrow_state.narrowed_by_stream_reply());
    assert.equal(narrow_state.stream_sub(), undefined);

    stream_data.add_sub(foo_stream);

    set_filter([["stream", "Foo"]]);
    assert.ok(!narrow_state.narrowed_to_pms());
    assert.ok(!narrow_state.narrowed_by_reply());
    assert.ok(!narrow_state.narrowed_by_pm_reply());
    assert.ok(!narrow_state.narrowed_by_topic_reply());
    assert.ok(narrow_state.narrowed_by_stream_reply());
    assert.ok(!narrow_state.is_search_view());

    set_filter([["dm", "steve@zulip.com"]]);
    assert.ok(narrow_state.narrowed_to_pms());
    assert.ok(narrow_state.narrowed_by_reply());
    assert.ok(narrow_state.narrowed_by_pm_reply());
    assert.ok(!narrow_state.narrowed_by_topic_reply());
    assert.ok(!narrow_state.narrowed_by_stream_reply());
    assert.ok(!narrow_state.is_search_view());

    set_filter([
        ["stream", foo_stream_id.toString()],
        ["topic", "bar"],
    ]);
    assert.ok(!narrow_state.narrowed_to_pms());
    assert.ok(narrow_state.narrowed_by_reply());
    assert.ok(!narrow_state.narrowed_by_pm_reply());
    assert.ok(narrow_state.narrowed_by_topic_reply());
    assert.ok(!narrow_state.narrowed_by_stream_reply());
    assert.ok(!narrow_state.is_search_view());

    set_filter([["search", "grail"]]);
    assert.ok(!narrow_state.narrowed_to_pms());
    assert.ok(!narrow_state.narrowed_by_reply());
    assert.ok(!narrow_state.narrowed_by_pm_reply());
    assert.ok(!narrow_state.narrowed_by_topic_reply());
    assert.ok(!narrow_state.narrowed_by_stream_reply());
    assert.ok(narrow_state.is_search_view());

    set_filter([["is", "starred"]]);
    assert.ok(!narrow_state.narrowed_to_pms());
    assert.ok(!narrow_state.narrowed_by_reply());
    assert.ok(!narrow_state.narrowed_by_pm_reply());
    assert.ok(!narrow_state.narrowed_by_topic_reply());
    assert.ok(!narrow_state.narrowed_by_stream_reply());
    assert.ok(narrow_state.is_search_view());
});

test("terms", () => {
    set_filter([
        ["stream", foo_stream_id.toString()],
        ["topic", "Bar"],
        ["search", "Yo"],
    ]);
    let result = narrow_state.search_terms();
    assert.equal(result.length, 3);
    assert.equal(result[0].operator, "channel");
    assert.equal(result[0].operand, foo_stream_id.toString());

    assert.equal(result[1].operator, "topic");
    assert.equal(result[1].operand, "Bar");

    assert.equal(result[2].operator, "search");
    assert.equal(result[2].operand, "Yo");

    message_lists.set_current(undefined);
    result = narrow_state.search_terms();
    assert.equal(result.length, 0);

    page_params.narrow = [{operator: "stream", operand: foo_stream_id.toString()}];
    result = narrow_state.search_terms();
    assert.equal(result.length, 1);
    assert.equal(result[0].operator, "channel");
    assert.equal(result[0].operand, foo_stream_id.toString());

    // `with` terms are excluded from search terms.
    page_params.narrow = [
        {operator: "stream", operand: foo_stream_id.toString()},
        {operator: "topic", operand: "Bar"},
        {operator: "with", operand: "12"},
    ];
    result = narrow_state.search_terms();
    assert.equal(result.length, 2);
    assert.equal(result[0].operator, "channel");
    assert.equal(result[1].operator, "topic");
});

test("excludes_muted_topics", () => {
    let filter = set_filter([["stream", "devel"]]);
    assert.ok(filter.excludes_muted_topics());

    // Combined feed view.
    filter = set_filter([["in", "home"]]);
    assert.ok(filter.excludes_muted_topics());

    filter = set_filter([
        ["stream", "devel"],
        ["topic", "mac"],
    ]);
    assert.ok(!filter.excludes_muted_topics());

    filter = set_filter([["search", "whatever"]]);
    assert.ok(!filter.excludes_muted_topics());

    filter = set_filter([["is", "private"]]);
    assert.ok(!filter.excludes_muted_topics());

    filter = set_filter([["is", "starred"]]);
    assert.ok(!filter.excludes_muted_topics());
});

test("set_compose_defaults", () => {
    set_filter([
        ["stream", foo_stream_id.toString()],
        ["topic", "Bar"],
    ]);

    // First try with a stream that doesn't exist.
    let stream_and_topic = narrow_state.set_compose_defaults();
    assert.equal(stream_and_topic.stream_id, undefined);
    assert.equal(stream_and_topic.topic, "Bar");

    stream_data.add_sub(foo_stream);
    stream_and_topic = narrow_state.set_compose_defaults();
    assert.equal(stream_and_topic.stream_id, foo_stream_id);
    assert.equal(stream_and_topic.topic, "Bar");

    set_filter([["dm", "foo@bar.com"]]);
    let dm_test = narrow_state.set_compose_defaults();
    assert.equal(dm_test.private_message_recipient, undefined);

    const john = {
        email: "john@doe.com",
        user_id: 57,
        full_name: "John Doe",
    };
    people.add_active_user(john);
    people.add_active_user(john);

    set_filter([["dm", "john@doe.com"]]);
    dm_test = narrow_state.set_compose_defaults();
    assert.deepEqual(dm_test.private_message_recipient_ids, [john.user_id]);

    // Even though we renamed "pm-with" to "dm",
    // compose defaults are set correctly.
    set_filter([["pm-with", "john@doe.com"]]);
    dm_test = narrow_state.set_compose_defaults();
    assert.deepEqual(dm_test.private_message_recipient_ids, [john.user_id]);

    set_filter([
        ["topic", "duplicate"],
        ["topic", "duplicate"],
    ]);
    assert.deepEqual(narrow_state.set_compose_defaults(), {});

    const rome_id = 99;
    stream_data.add_sub({name: "ROME", stream_id: rome_id});
    set_filter([["stream", rome_id.toString()]]);

    const stream_test = narrow_state.set_compose_defaults();
    assert.equal(stream_test.stream_id, rome_id);
});

test("update_email", () => {
    const steve = {
        email: "steve@foo.com",
        user_id: 43,
        full_name: "Steve",
    };

    people.add_active_user(steve);
    set_filter([
        ["dm", "steve@foo.com"],
        ["sender", "steve@foo.com"],
        ["stream", "steve@foo.com"], // try to be tricky
    ]);
    narrow_state.update_email(steve.user_id, "showell@foo.com");
    const filter = narrow_state.filter();
    assert.deepEqual(filter.operands("dm"), ["showell@foo.com"]);
    assert.deepEqual(filter.operands("sender"), ["showell@foo.com"]);
    assert.deepEqual(filter.operands("channel"), ["steve@foo.com"]);
});

test("topic", () => {
    set_filter([
        ["stream", foo_stream.stream_id.toString()],
        ["topic", "Bar"],
    ]);
    assert.equal(narrow_state.topic(), "Bar");

    set_filter([
        ["stream", "release"],
        ["topic", "@#$$^test"],
    ]);
    assert.equal(narrow_state.topic(), "@#$$^test");

    set_filter([]);
    assert.equal(narrow_state.topic(), undefined);

    set_filter([
        ["sender", "test@foo.com"],
        ["dm", "test@foo.com"],
    ]);
    assert.equal(narrow_state.topic(), undefined);

    message_lists.set_current(undefined);
    assert.equal(narrow_state.topic(), undefined);
});

test("stream_sub", () => {
    set_filter([]);
    assert.equal(narrow_state.stream_name(), undefined);
    assert.equal(narrow_state.stream_sub(), undefined);

    set_filter([
        ["stream", "55"],
        ["topic", "Bar"],
    ]);
    assert.equal(narrow_state.stream_name(), undefined);
    assert.equal(narrow_state.stream_sub(), undefined);

    const sub = {name: "Foo", stream_id: 55};
    stream_data.add_sub(sub);
    assert.equal(narrow_state.stream_name(), "Foo");
    assert.deepEqual(narrow_state.stream_sub(), sub);

    set_filter([
        ["sender", "someone"],
        ["topic", "random"],
    ]);
    assert.equal(narrow_state.stream_name(), undefined);
});

test("pm_ids_string", () => {
    // This function will return undefined unless we're clearly
    // narrowed to a specific direct message (including group
    // direct messages) with real users.
    message_lists.set_current(undefined);
    assert.equal(narrow_state.pm_ids_string(), undefined);
    assert.deepStrictEqual(narrow_state.pm_ids_set(), new Set());

    set_filter([
        ["stream", foo_stream.stream_id.toString()],
        ["topic", "Bar"],
    ]);
    assert.equal(narrow_state.pm_ids_string(), undefined);
    assert.deepStrictEqual(narrow_state.pm_ids_set(), new Set());

    set_filter([["dm", ""]]);
    assert.equal(narrow_state.pm_ids_string(), undefined);
    assert.deepStrictEqual(narrow_state.pm_ids_set(), new Set());

    set_filter([["dm", "bogus@foo.com"]]);
    assert.equal(narrow_state.pm_ids_string(), undefined);
    assert.deepStrictEqual(narrow_state.pm_ids_set(), new Set());

    const alice = {
        email: "alice@foo.com",
        user_id: 444,
        full_name: "Alice",
    };

    const bob = {
        email: "bob@foo.com",
        user_id: 555,
        full_name: "Bob",
    };

    people.add_active_user(alice);
    people.add_active_user(bob);

    set_filter([["dm", "bob@foo.com,alice@foo.com"]]);
    assert.equal(narrow_state.pm_ids_string(), "444,555");
    assert.deepStrictEqual(narrow_state.pm_ids_set(), new Set([444, 555]));
});

test("inbox_view_visible", () => {
    const filter = new Filter([
        {
            operator: "channel",
            operand: 10,
        },
    ]);
    inbox_util.set_filter(filter);
    inbox_util.set_visible(true);
    assert.ok(narrow_state.filter() === filter);
});
