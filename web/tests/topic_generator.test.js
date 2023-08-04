"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");

const pm_conversations = mock_esm("../src/pm_conversations", {
    recent: {},
});
const stream_data = mock_esm("../src/stream_data");
const stream_list_sort = mock_esm("../src/stream_list_sort");
const stream_topic_history = mock_esm("../src/stream_topic_history");
const unread = mock_esm("../src/unread");
const user_topics = mock_esm("../src/user_topics");

const tg = zrequire("topic_generator");

run_test("streams", ({override}) => {
    function assert_next_stream(curr_stream, expected) {
        const actual = tg.get_next_stream(curr_stream);
        assert.equal(actual, expected);
    }

    override(stream_list_sort, "get_streams", () => ["announce", "muted", "devel", "test here"]);

    assert_next_stream(undefined, "announce");
    assert_next_stream("NOT THERE", "announce");

    assert_next_stream("announce", "muted");
    assert_next_stream("test here", "announce");

    function assert_prev_stream(curr_stream, expected) {
        const actual = tg.get_prev_stream(curr_stream);
        assert.equal(actual, expected);
    }

    assert_prev_stream(undefined, "test here");
    assert_prev_stream("test here", "devel");
    assert_prev_stream("announce", "test here");
});

run_test("topics", ({override}) => {
    const streams = ["stream1", "stream2", "stream3", "stream4"];
    const topics = new Map([
        ["stream1", ["read", "read", "1a", "1b", "read", "1c"]],
        ["stream2", []],
        ["stream3", ["3a", "read", "read", "3b", "read"]],
        ["stream4", ["4a"]],
    ]);

    function has_unread_messages(_stream, topic) {
        return topic !== "read";
    }

    function get_topics(stream) {
        return topics.get(stream);
    }

    function next_topic(curr_stream, curr_topic) {
        return tg.next_topic(streams, get_topics, has_unread_messages, curr_stream, curr_topic);
    }

    assert.deepEqual(next_topic("stream1", "1a"), {stream: "stream1", topic: "1b"});
    assert.deepEqual(next_topic("stream1", undefined), {stream: "stream1", topic: "1a"});
    assert.deepEqual(next_topic("stream2", "bogus"), {stream: "stream3", topic: "3a"});
    assert.deepEqual(next_topic("stream3", "3b"), {stream: "stream3", topic: "3a"});
    assert.deepEqual(next_topic("stream4", "4a"), {stream: "stream1", topic: "1a"});
    assert.deepEqual(next_topic(undefined, undefined), {stream: "stream1", topic: "1a"});

    assert.deepEqual(
        tg.next_topic(streams, get_topics, () => false, "stream1", "1a"),
        undefined,
    );

    // Now test the deeper function that is wired up to
    // real functions stream_data/stream_list_sort/unread.

    override(stream_list_sort, "get_streams", () => ["announce", "muted", "devel", "test here"]);

    const muted_stream_id = 400;
    const devel_stream_id = 401;

    const stream_id_dct = {
        muted: muted_stream_id,
        devel: devel_stream_id,
    };

    override(stream_topic_history, "get_recent_topic_names", (stream_id) => {
        switch (stream_id) {
            case muted_stream_id:
                return ["ms-topic1", "ms-topic2"];
            case devel_stream_id:
                return ["muted", "python"];
        }

        return [];
    });

    override(stream_data, "get_stream_id", (stream_name) => stream_id_dct[stream_name]);

    override(stream_data, "is_stream_muted_by_name", (stream_name) => stream_name === "muted");

    override(unread, "topic_has_any_unread", (stream_id) =>
        [devel_stream_id, muted_stream_id].includes(stream_id),
    );

    override(user_topics, "is_topic_muted", (_stream_name, topic) => topic === "muted");

    let next_item = tg.get_next_topic("announce", "whatever");
    assert.deepEqual(next_item, {
        stream: "devel",
        topic: "python",
    });

    next_item = tg.get_next_topic("muted", undefined);
    assert.deepEqual(next_item, {
        stream: "muted",
        topic: "ms-topic1",
    });
});

run_test("get_next_unread_pm_string", ({override}) => {
    override(pm_conversations.recent, "get_strings", () => ["1", "read", "2,3", "4", "unk"]);

    override(unread, "num_unread_for_user_ids_string", (user_ids_string) => {
        if (user_ids_string === "unk") {
            return undefined;
        }

        if (user_ids_string === "read") {
            return 0;
        }

        return 5; // random non-zero value
    });

    assert.equal(tg.get_next_unread_pm_string(), "1");
    assert.equal(tg.get_next_unread_pm_string("4"), "1");
    assert.equal(tg.get_next_unread_pm_string("unk"), "1");
    assert.equal(tg.get_next_unread_pm_string("4"), "1");
    assert.equal(tg.get_next_unread_pm_string("1"), "2,3");
    assert.equal(tg.get_next_unread_pm_string("read"), "2,3");
    assert.equal(tg.get_next_unread_pm_string("2,3"), "4");

    override(unread, "num_unread_for_user_ids_string", () => 0);

    assert.equal(tg.get_next_unread_pm_string("2,3"), undefined);
});
