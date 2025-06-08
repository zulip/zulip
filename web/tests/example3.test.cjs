"use strict";

const assert = require("node:assert/strict");

const {make_stream} = require("./lib/example_stream.cjs");
const {make_message_list} = require("./lib/message_list.cjs");
const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

// In the Zulip app you can narrow your message stream by topic, by
// sender, by direct message recipient, by search keywords, etc.
// We will discuss narrows more broadly, but first let's test out a
// core piece of code that makes things work.

const {Filter} = zrequire("../src/filter");
const {set_realm} = zrequire("state_data");
const stream_data = zrequire("stream_data");

set_realm({});

const denmark_stream = make_stream({
    color: "blue",
    name: "Denmark",
    stream_id: 101,
    subscribed: false,
});

run_test("filter", () => {
    stream_data.clear_subscriptions();
    stream_data.add_sub(denmark_stream);

    const filter_terms = [
        {operator: "stream", operand: denmark_stream.stream_id.toString()},
        {operator: "topic", operand: "copenhagen"},
    ];

    const filter = new Filter(filter_terms);

    const predicate = filter.predicate();

    // We don't need full-fledged messages to test the gist of
    // our filter.  If there are details that are distracting from
    // your test, you should not feel guilty about removing them.
    assert.equal(predicate({type: "personal"}), false);

    assert.equal(
        predicate({
            type: "stream",
            stream_id: denmark_stream.stream_id,
            topic: "does not match filter",
        }),
        false,
    );

    assert.equal(
        predicate({
            type: "stream",
            stream_id: denmark_stream.stream_id,
            topic: "copenhagen",
        }),
        true,
    );
});

// We have a "narrow" abstraction that sits roughly on top of the
// "filter" abstraction.  If you are in a narrow, we track the
// state with the narrow_state module.

const narrow_state = zrequire("narrow_state");
const message_lists = zrequire("message_lists");

run_test("narrow_state", () => {
    stream_data.clear_subscriptions();
    stream_data.add_sub(denmark_stream);
    message_lists.set_current(undefined);

    // As we often do, first make assertions about the starting
    // state:

    assert.equal(narrow_state.stream_name(), undefined);

    // Now set up a Filter object.
    const filter_terms = [
        {operator: "stream", operand: denmark_stream.stream_id.toString()},
        {operator: "topic", operand: "copenhagen"},
    ];

    // And here is where we actually change state.
    message_lists.set_current(make_message_list(filter_terms));
    assert.equal(narrow_state.stream_name(), "Denmark");
    assert.equal(narrow_state.topic(), "copenhagen");
});
