"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");

const stream_topic_history_util = mock_esm("../src/stream_topic_history_util");
mock_esm("../src/people.ts", {
    maybe_get_user_by_id: noop,
});

const all_messages_data = zrequire("all_messages_data");
const {set_realm} = zrequire("state_data");
const stream_data = zrequire("stream_data");
const stream_topic_history = zrequire("stream_topic_history");
const topic_list = zrequire("topic_list");

set_realm({});

function test(label, f) {
    run_test(label, (helpers) => {
        f(helpers);
    });
}

test("is_full_topic_history_available", ({override}) => {
    const stream_id = 21;
    const general = {
        name: "general",
        stream_id,
        first_message_id: null,
    };
    const messages = [
        {id: 1, stream_id},
        {id: 2, stream_id},
        {id: 3, stream_id},
    ];
    const sub = stream_data.create_sub_from_server_data(general);

    // Currently, all_messages_data is empty.
    assert.equal(topic_list.is_full_topic_history_available(stream_id), false);

    all_messages_data.all_messages_data.clear();
    all_messages_data.all_messages_data.add_messages(messages, true);

    let has_found_newest = false;

    override(
        all_messages_data.all_messages_data.fetch_status,
        "has_found_newest",
        () => has_found_newest,
    );

    assert.equal(topic_list.is_full_topic_history_available(stream_id), false);
    has_found_newest = true;
    // sub.first_message_id === null
    assert.equal(topic_list.is_full_topic_history_available(stream_id), true);

    // Note that we'll return `true` here due to
    // fetched_stream_ids having the stream_id now.
    assert.equal(topic_list.is_full_topic_history_available(stream_id), true);

    // Clear the data, otherwise `is_full_topic_history_available`
    // will always return true due to stream_id in fetched_stream_ids.
    stream_topic_history.reset();

    sub.first_message_id = 0;
    assert.equal(topic_list.is_full_topic_history_available(stream_id), false);

    sub.first_message_id = 2;
    let full_topic_history_fetched_and_widget_updated = false;
    stream_topic_history_util.get_server_history = (stream_id) => {
        assert.equal(stream_id, general.stream_id);
        full_topic_history_fetched_and_widget_updated = true;
    };
    assert.equal(topic_list.is_full_topic_history_available(stream_id), true);
    assert.equal(full_topic_history_fetched_and_widget_updated, true);
});
