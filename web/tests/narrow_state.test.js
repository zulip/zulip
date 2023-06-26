"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");

const people = zrequire("people");
const {Filter} = zrequire("../src/filter");
const stream_data = zrequire("stream_data");
const narrow_state = zrequire("narrow_state");

function set_filter(operators) {
    operators = operators.map((op) => ({
        operator: op[0],
        operand: op[1],
    }));
    narrow_state.set_current_filter(new Filter(operators));
}

function test(label, f) {
    run_test(label, ({override}) => {
        narrow_state.reset_current_filter();
        stream_data.clear_subscriptions();
        f({override});
    });
}

test("stream", () => {
    assert.equal(narrow_state.public_operators(), undefined);
    assert.ok(!narrow_state.active());

    const test_stream = {name: "Test", stream_id: 15};
    stream_data.add_sub(test_stream);

    assert.ok(!narrow_state.is_for_stream_id(test_stream.stream_id));

    set_filter([
        ["stream", "Test"],
        ["topic", "Bar"],
        ["search", "yo"],
    ]);
    assert.ok(narrow_state.active());

    assert.equal(narrow_state.stream_name(), "Test");
    assert.equal(narrow_state.stream_sub().stream_id, test_stream.stream_id);
    assert.equal(narrow_state.topic(), "Bar");
    assert.ok(narrow_state.is_for_stream_id(test_stream.stream_id));

    const expected_operators = [
        {negated: false, operator: "stream", operand: "Test"},
        {negated: false, operator: "topic", operand: "Bar"},
        {negated: false, operator: "search", operand: "yo"},
    ];

    const public_operators = narrow_state.public_operators();
    assert.deepEqual(public_operators, expected_operators);
    assert.equal(narrow_state.search_string(), "stream:Test topic:Bar yo");
});

test("narrowed", () => {
    assert.ok(!narrow_state.narrowed_to_pms());
    assert.ok(!narrow_state.narrowed_by_reply());
    assert.ok(!narrow_state.narrowed_by_pm_reply());
    assert.ok(!narrow_state.narrowed_by_topic_reply());
    assert.ok(!narrow_state.narrowed_to_search());
    assert.ok(!narrow_state.narrowed_to_topic());
    assert.ok(!narrow_state.narrowed_by_stream_reply());
    assert.equal(narrow_state.stream_sub(), undefined);
    assert.ok(!narrow_state.narrowed_to_starred());

    set_filter([["stream", "Foo"]]);
    assert.ok(!narrow_state.narrowed_to_pms());
    assert.ok(!narrow_state.narrowed_by_reply());
    assert.ok(!narrow_state.narrowed_by_pm_reply());
    assert.ok(!narrow_state.narrowed_by_topic_reply());
    assert.ok(!narrow_state.narrowed_to_search());
    assert.ok(!narrow_state.narrowed_to_topic());
    assert.ok(narrow_state.narrowed_by_stream_reply());
    assert.ok(!narrow_state.narrowed_to_starred());

    set_filter([["dm", "steve@zulip.com"]]);
    assert.ok(narrow_state.narrowed_to_pms());
    assert.ok(narrow_state.narrowed_by_reply());
    assert.ok(narrow_state.narrowed_by_pm_reply());
    assert.ok(!narrow_state.narrowed_by_topic_reply());
    assert.ok(!narrow_state.narrowed_to_search());
    assert.ok(!narrow_state.narrowed_to_topic());
    assert.ok(!narrow_state.narrowed_by_stream_reply());
    assert.ok(!narrow_state.narrowed_to_starred());

    set_filter([
        ["stream", "Foo"],
        ["topic", "bar"],
    ]);
    assert.ok(!narrow_state.narrowed_to_pms());
    assert.ok(narrow_state.narrowed_by_reply());
    assert.ok(!narrow_state.narrowed_by_pm_reply());
    assert.ok(narrow_state.narrowed_by_topic_reply());
    assert.ok(!narrow_state.narrowed_to_search());
    assert.ok(narrow_state.narrowed_to_topic());
    assert.ok(!narrow_state.narrowed_by_stream_reply());
    assert.ok(!narrow_state.narrowed_to_starred());

    set_filter([["search", "grail"]]);
    assert.ok(!narrow_state.narrowed_to_pms());
    assert.ok(!narrow_state.narrowed_by_reply());
    assert.ok(!narrow_state.narrowed_by_pm_reply());
    assert.ok(!narrow_state.narrowed_by_topic_reply());
    assert.ok(narrow_state.narrowed_to_search());
    assert.ok(!narrow_state.narrowed_to_topic());
    assert.ok(!narrow_state.narrowed_by_stream_reply());
    assert.ok(!narrow_state.narrowed_to_starred());

    set_filter([["is", "starred"]]);
    assert.ok(!narrow_state.narrowed_to_pms());
    assert.ok(!narrow_state.narrowed_by_reply());
    assert.ok(!narrow_state.narrowed_by_pm_reply());
    assert.ok(!narrow_state.narrowed_by_topic_reply());
    assert.ok(!narrow_state.narrowed_to_search());
    assert.ok(!narrow_state.narrowed_to_topic());
    assert.ok(!narrow_state.narrowed_by_stream_reply());
    assert.ok(narrow_state.narrowed_to_starred());
});

test("operators", () => {
    set_filter([
        ["stream", "Foo"],
        ["topic", "Bar"],
        ["search", "Yo"],
    ]);
    let result = narrow_state.operators();
    assert.equal(result.length, 3);
    assert.equal(result[0].operator, "stream");
    assert.equal(result[0].operand, "Foo");

    assert.equal(result[1].operator, "topic");
    assert.equal(result[1].operand, "Bar");

    assert.equal(result[2].operator, "search");
    assert.equal(result[2].operand, "yo");

    narrow_state.reset_current_filter();
    result = narrow_state.operators();
    assert.equal(result.length, 0);
});

test("excludes_muted_topics", () => {
    set_filter([["stream", "devel"]]);
    assert.ok(narrow_state.excludes_muted_topics());

    narrow_state.reset_current_filter(); // not narrowed, basically
    assert.ok(narrow_state.excludes_muted_topics());

    set_filter([
        ["stream", "devel"],
        ["topic", "mac"],
    ]);
    assert.ok(!narrow_state.excludes_muted_topics());

    set_filter([["search", "whatever"]]);
    assert.ok(!narrow_state.excludes_muted_topics());

    set_filter([["is", "private"]]);
    assert.ok(!narrow_state.excludes_muted_topics());

    set_filter([["is", "starred"]]);
    assert.ok(!narrow_state.excludes_muted_topics());
});

test("set_compose_defaults", () => {
    set_filter([
        ["stream", "Foo"],
        ["topic", "Bar"],
    ]);

    // First try with a stream that doesn't exist.
    let stream_and_topic = narrow_state.set_compose_defaults();
    assert.equal(stream_and_topic.stream_id, undefined);
    assert.equal(stream_and_topic.topic, "Bar");

    const test_stream = {name: "Foo", stream_id: 72};
    stream_data.add_sub(test_stream);
    stream_and_topic = narrow_state.set_compose_defaults();
    assert.equal(stream_and_topic.stream_id, 72);
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
    assert.equal(dm_test.private_message_recipient, "john@doe.com");

    // Even though we renamed "pm-with" to "dm",
    // compose defaults are set correctly.
    set_filter([["pm-with", "john@doe.com"]]);
    dm_test = narrow_state.set_compose_defaults();
    assert.equal(dm_test.private_message_recipient, "john@doe.com");

    set_filter([
        ["topic", "duplicate"],
        ["topic", "duplicate"],
    ]);
    assert.deepEqual(narrow_state.set_compose_defaults(), {});

    stream_data.add_sub({name: "ROME", stream_id: 99});
    set_filter([["stream", "rome"]]);

    const stream_test = narrow_state.set_compose_defaults();
    assert.equal(stream_test.stream_id, 99);
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
    assert.deepEqual(filter.operands("stream"), ["steve@foo.com"]);
});

test("topic", () => {
    set_filter([
        ["stream", "Foo"],
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

    narrow_state.set_current_filter(undefined);
    assert.equal(narrow_state.topic(), undefined);
});

test("stream_sub", () => {
    set_filter([]);
    assert.equal(narrow_state.stream_name(), undefined);
    assert.equal(narrow_state.stream_sub(), undefined);

    set_filter([
        ["stream", "Foo"],
        ["topic", "Bar"],
    ]);
    assert.equal(narrow_state.stream_name(), "Foo");
    assert.equal(narrow_state.stream_sub(), undefined);

    const sub = {name: "Foo", stream_id: 55};
    stream_data.add_sub(sub);
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
    narrow_state.set_current_filter(undefined);
    assert.equal(narrow_state.pm_ids_string(), undefined);

    set_filter([
        ["stream", "Foo"],
        ["topic", "Bar"],
    ]);
    assert.equal(narrow_state.pm_ids_string(), undefined);

    set_filter([["dm", ""]]);
    assert.equal(narrow_state.pm_ids_string(), undefined);

    set_filter([["dm", "bogus@foo.com"]]);
    assert.equal(narrow_state.pm_ids_string(), undefined);

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
});
