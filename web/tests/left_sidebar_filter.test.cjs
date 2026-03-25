"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const narrow_state = mock_esm("../src/narrow_state", {
    filter: () => ({}),
    stream_id: () => undefined,
});
const stream_data = mock_esm("../src/stream_data", {
    is_subscribed: () => false,
});

const blueslip = zrequire("blueslip");
const left_sidebar_filter = zrequire("left_sidebar_filter");

run_test("get_raw_topics_state", ({override}) => {
    left_sidebar_filter.rewire_left_sidebar_filter_pill_widget(null);
    assert.equal(left_sidebar_filter.get_raw_topics_state(), "");

    const pill_items = [{syntax: "is:resolved"}];
    left_sidebar_filter.rewire_left_sidebar_filter_pill_widget({
        items() {
            return pill_items;
        },
    });
    assert.equal(left_sidebar_filter.get_raw_topics_state(), "is:resolved");

    let warning_message;
    override(blueslip, "warn", (message) => {
        warning_message = message;
    });
    pill_items.push({syntax: "is:followed"});
    assert.equal(left_sidebar_filter.get_raw_topics_state(), "is:resolved");
    assert.equal(warning_message, "Multiple pills found in left sidebar filter input.");
});

run_test("topic_state_filter_applies_and_get_effective_topics_state_for_search", ({override}) => {
    left_sidebar_filter.rewire_left_sidebar_filter_pill_widget(null);
    assert.equal(left_sidebar_filter.topic_state_filter_applies(), false);
    assert.equal(left_sidebar_filter.get_effective_topics_state_for_search(), "");

    left_sidebar_filter.rewire_left_sidebar_filter_pill_widget({
        items: () => [{syntax: "is:followed"}],
    });
    override(narrow_state, "stream_id", () => 5);
    assert.equal(left_sidebar_filter.topic_state_filter_applies(), false);
    assert.equal(left_sidebar_filter.get_effective_topics_state_for_search(), "");

    override(stream_data, "is_subscribed", () => true);
    assert.equal(left_sidebar_filter.topic_state_filter_applies(), true);
    assert.equal(left_sidebar_filter.get_effective_topics_state_for_search(), "is:followed");
});
