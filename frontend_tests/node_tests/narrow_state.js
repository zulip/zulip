"use strict";

const people = zrequire("people");
zrequire("Filter", "js/filter");
zrequire("stream_data");
zrequire("narrow_state");

set_global("page_params", {});

function set_filter(operators) {
    operators = operators.map((op) => ({
        operator: op[0],
        operand: op[1],
    }));
    narrow_state.set_current_filter(new Filter(operators));
}

run_test("stream", () => {
    assert.equal(narrow_state.public_operators(), undefined);
    assert(!narrow_state.active());

    const test_stream = {name: "Test", stream_id: 15};
    stream_data.add_sub(test_stream);

    assert(!narrow_state.is_for_stream_id(test_stream.stream_id));

    set_filter([
        ["stream", "Test"],
        ["topic", "Bar"],
        ["search", "yo"],
    ]);
    assert(narrow_state.active());

    assert.equal(narrow_state.stream(), "Test");
    assert.equal(narrow_state.stream_id(), test_stream.stream_id);
    assert.equal(narrow_state.topic(), "Bar");
    assert(narrow_state.is_for_stream_id(test_stream.stream_id));

    const expected_operators = [
        {negated: false, operator: "stream", operand: "Test"},
        {negated: false, operator: "topic", operand: "Bar"},
        {negated: false, operator: "search", operand: "yo"},
    ];

    const public_operators = narrow_state.public_operators();
    assert.deepEqual(public_operators, expected_operators);
    assert.equal(narrow_state.search_string(), "stream:Test topic:Bar yo");
});

run_test("narrowed", () => {
    narrow_state.reset_current_filter(); // not narrowed, basically
    assert(!narrow_state.narrowed_to_pms());
    assert(!narrow_state.narrowed_by_reply());
    assert(!narrow_state.narrowed_by_pm_reply());
    assert(!narrow_state.narrowed_by_topic_reply());
    assert(!narrow_state.narrowed_to_search());
    assert(!narrow_state.narrowed_to_topic());
    assert(!narrow_state.narrowed_by_stream_reply());
    assert.equal(narrow_state.stream_id(), undefined);
    assert(!narrow_state.narrowed_to_starred());

    set_filter([["stream", "Foo"]]);
    assert(!narrow_state.narrowed_to_pms());
    assert(!narrow_state.narrowed_by_reply());
    assert(!narrow_state.narrowed_by_pm_reply());
    assert(!narrow_state.narrowed_by_topic_reply());
    assert(!narrow_state.narrowed_to_search());
    assert(!narrow_state.narrowed_to_topic());
    assert(narrow_state.narrowed_by_stream_reply());
    assert(!narrow_state.narrowed_to_starred());

    set_filter([["pm-with", "steve@zulip.com"]]);
    assert(narrow_state.narrowed_to_pms());
    assert(narrow_state.narrowed_by_reply());
    assert(narrow_state.narrowed_by_pm_reply());
    assert(!narrow_state.narrowed_by_topic_reply());
    assert(!narrow_state.narrowed_to_search());
    assert(!narrow_state.narrowed_to_topic());
    assert(!narrow_state.narrowed_by_stream_reply());
    assert(!narrow_state.narrowed_to_starred());

    set_filter([
        ["stream", "Foo"],
        ["topic", "bar"],
    ]);
    assert(!narrow_state.narrowed_to_pms());
    assert(narrow_state.narrowed_by_reply());
    assert(!narrow_state.narrowed_by_pm_reply());
    assert(narrow_state.narrowed_by_topic_reply());
    assert(!narrow_state.narrowed_to_search());
    assert(narrow_state.narrowed_to_topic());
    assert(!narrow_state.narrowed_by_stream_reply());
    assert(!narrow_state.narrowed_to_starred());

    set_filter([["search", "grail"]]);
    assert(!narrow_state.narrowed_to_pms());
    assert(!narrow_state.narrowed_by_reply());
    assert(!narrow_state.narrowed_by_pm_reply());
    assert(!narrow_state.narrowed_by_topic_reply());
    assert(narrow_state.narrowed_to_search());
    assert(!narrow_state.narrowed_to_topic());
    assert(!narrow_state.narrowed_by_stream_reply());
    assert(!narrow_state.narrowed_to_starred());

    set_filter([["is", "starred"]]);
    assert(!narrow_state.narrowed_to_pms());
    assert(!narrow_state.narrowed_by_reply());
    assert(!narrow_state.narrowed_by_pm_reply());
    assert(!narrow_state.narrowed_by_topic_reply());
    assert(!narrow_state.narrowed_to_search());
    assert(!narrow_state.narrowed_to_topic());
    assert(!narrow_state.narrowed_by_stream_reply());
    assert(narrow_state.narrowed_to_starred());
});

run_test("operators", () => {
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

run_test("muting_enabled", () => {
    set_filter([["stream", "devel"]]);
    assert(narrow_state.muting_enabled());

    narrow_state.reset_current_filter(); // not narrowed, basically
    assert(narrow_state.muting_enabled());

    set_filter([
        ["stream", "devel"],
        ["topic", "mac"],
    ]);
    assert(!narrow_state.muting_enabled());

    set_filter([["search", "whatever"]]);
    assert(!narrow_state.muting_enabled());

    set_filter([["is", "private"]]);
    assert(!narrow_state.muting_enabled());

    set_filter([["is", "starred"]]);
    assert(!narrow_state.muting_enabled());
});

run_test("set_compose_defaults", () => {
    set_filter([
        ["stream", "Foo"],
        ["topic", "Bar"],
    ]);

    const stream_and_subject = narrow_state.set_compose_defaults();
    assert.equal(stream_and_subject.stream, "Foo");
    assert.equal(stream_and_subject.topic, "Bar");

    set_filter([["pm-with", "foo@bar.com"]]);
    let pm_test = narrow_state.set_compose_defaults();
    assert.equal(pm_test.private_message_recipient, undefined);

    const john = {
        email: "john@doe.com",
        user_id: 57,
        full_name: "John Doe",
    };
    people.add_active_user(john);
    people.add_active_user(john);

    set_filter([["pm-with", "john@doe.com"]]);
    pm_test = narrow_state.set_compose_defaults();
    assert.equal(pm_test.private_message_recipient, "john@doe.com");

    set_filter([
        ["topic", "duplicate"],
        ["topic", "duplicate"],
    ]);
    assert.deepEqual(narrow_state.set_compose_defaults(), {});

    stream_data.add_sub({name: "ROME", stream_id: 99});
    set_filter([["stream", "rome"]]);

    const stream_test = narrow_state.set_compose_defaults();
    assert.equal(stream_test.stream, "ROME");
});

run_test("update_email", () => {
    const steve = {
        email: "steve@foo.com",
        user_id: 43,
        full_name: "Steve",
    };

    people.add_active_user(steve);
    set_filter([
        ["pm-with", "steve@foo.com"],
        ["sender", "steve@foo.com"],
        ["stream", "steve@foo.com"], // try to be tricky
    ]);
    narrow_state.update_email(steve.user_id, "showell@foo.com");
    const filter = narrow_state.filter();
    assert.deepEqual(filter.operands("pm-with"), ["showell@foo.com"]);
    assert.deepEqual(filter.operands("sender"), ["showell@foo.com"]);
    assert.deepEqual(filter.operands("stream"), ["steve@foo.com"]);
});

run_test("topic", () => {
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
        ["pm-with", "test@foo.com"],
    ]);
    assert.equal(narrow_state.topic(), undefined);

    narrow_state.set_current_filter(undefined);
    assert.equal(narrow_state.topic(), undefined);
});

run_test("stream", () => {
    set_filter([]);
    assert.equal(narrow_state.stream(), undefined);
    assert.equal(narrow_state.stream_id(), undefined);

    set_filter([
        ["stream", "Foo"],
        ["topic", "Bar"],
    ]);
    assert.equal(narrow_state.stream(), "Foo");
    assert.equal(narrow_state.stream_sub(), undefined);
    assert.equal(narrow_state.stream_id(), undefined);

    const sub = {name: "Foo", stream_id: 55};
    stream_data.add_sub(sub);
    assert.equal(narrow_state.stream_id(), 55);
    assert.deepEqual(narrow_state.stream_sub(), sub);

    set_filter([
        ["sender", "someone"],
        ["topic", "random"],
    ]);
    assert.equal(narrow_state.stream(), undefined);
});

run_test("pm_string", () => {
    // This function will return undefined unless we're clearly
    // narrowed to a specific PM (including huddles) with real
    // users.
    narrow_state.set_current_filter(undefined);
    assert.equal(narrow_state.pm_string(), undefined);

    set_filter([
        ["stream", "Foo"],
        ["topic", "Bar"],
    ]);
    assert.equal(narrow_state.pm_string(), undefined);

    set_filter([["pm-with", ""]]);
    assert.equal(narrow_state.pm_string(), undefined);

    set_filter([["pm-with", "bogus@foo.com"]]);
    assert.equal(narrow_state.pm_string(), undefined);

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

    set_filter([["pm-with", "bob@foo.com,alice@foo.com"]]);
    assert.equal(narrow_state.pm_string(), "444,555");
});
