"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const {page_params} = require("./lib/zpage_params");

// In the Zulip app you can narrow your message stream by topic, by
// sender, by direct message recipient, by search keywords, etc.
// We will discuss narrows more broadly, but first let's test out a
// core piece of code that makes things work.

const {Filter} = zrequire("../src/filter");
const stream_data = zrequire("stream_data");

// This is the first time we have to deal with page_params.
// page_params has a lot of important data shared by various
// modules. Most of the data is irrelevant to our tests.
// Use this to explicitly say we are not a special Zephyr
// realm, since we want to test the "normal" codepath.
page_params.realm_is_zephyr_mirror_realm = false;

const denmark_stream = {
    color: "blue",
    name: "Denmark",
    stream_id: 101,
    subscribed: false,
};

run_test("filter", () => {
    stream_data.clear_subscriptions();
    stream_data.add_sub(denmark_stream);

    const filter_terms = [
        {operator: "stream", operand: "Denmark"},
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

run_test("narrow_state", () => {
    stream_data.clear_subscriptions();
    stream_data.add_sub(denmark_stream);
    narrow_state.reset_current_filter();

    // As we often do, first make assertions about the starting
    // state:

    assert.equal(narrow_state.stream_name(), undefined);

    // Now set up a Filter object.
    const filter_terms = [
        {operator: "stream", operand: "Denmark"},
        {operator: "topic", operand: "copenhagen"},
    ];

    const filter = new Filter(filter_terms);

    // And here is where we actually change state.
    narrow_state.set_current_filter(filter);

    assert.equal(narrow_state.stream_name(), "Denmark");
    assert.equal(narrow_state.topic(), "copenhagen");
});
