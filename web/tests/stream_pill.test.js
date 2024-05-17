"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");

const peer_data = zrequire("peer_data");
const stream_data = zrequire("stream_data");
const stream_pill = zrequire("stream_pill");

const denmark = {
    stream_id: 101,
    name: "Denmark",
    subscribed: true,
};
const sweden = {
    stream_id: 102,
    name: "Sweden",
    subscribed: false,
};

peer_data.set_subscribers(denmark.stream_id, [1, 2, 3, 77]);
peer_data.set_subscribers(sweden.stream_id, [1, 2, 3, 4, 5]);

const denmark_pill = {
    stream_name: denmark.name,
    stream_id: denmark.stream_id,
    type: "stream",
    display_value: "#Denmark: 3 users",
};
const sweden_pill = {
    stream_name: sweden.name,
    stream_id: sweden.stream_id,
    type: "stream",
    display_value: "#Sweden: 5 users",
};

const subs = [denmark, sweden];
for (const sub of subs) {
    stream_data.add_sub(sub);
}

run_test("create_item", () => {
    function test_create_item(stream_name, current_items, expected_item) {
        const item = stream_pill.create_item_from_stream_name(stream_name, current_items);
        assert.deepEqual(item, expected_item);
    }

    test_create_item("sweden", [], undefined);
    test_create_item("#sweden", [sweden_pill], undefined);
    test_create_item("  #sweden", [], sweden_pill);
    test_create_item("#test", [], undefined);
});

run_test("get_stream_id", () => {
    assert.equal(stream_pill.get_stream_name_from_item(denmark_pill), denmark.name);
});

run_test("get_user_ids", () => {
    const items = [denmark_pill, sweden_pill];
    const widget = {items: () => items};

    const user_ids = stream_pill.get_user_ids(widget);
    assert.deepEqual(user_ids, [1, 2, 3, 4, 5, 77]);
});

run_test("get_stream_ids", () => {
    const items = [denmark_pill, sweden_pill];
    const widget = {items: () => items};

    const stream_ids = stream_pill.get_stream_ids(widget);
    assert.deepEqual(stream_ids, [101, 102]);
});
