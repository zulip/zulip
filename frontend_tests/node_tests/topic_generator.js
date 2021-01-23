"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

const pm_conversations = zrequire("pm_conversations");
pm_conversations.recent = {};

zrequire("muting");
zrequire("unread");
zrequire("stream_data");
zrequire("stream_topic_history");
zrequire("stream_sort");
const tg = zrequire("topic_generator");

run_test("streams", () => {
    function assert_next_stream(curr_stream, expected) {
        const actual = tg.get_next_stream(curr_stream);
        assert.equal(actual, expected);
    }

    stream_sort.get_streams = function () {
        return ["announce", "muted", "devel", "test here"];
    };

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

run_test("topics", () => {
    const streams = [1, 2, 3, 4];
    const topics = new Map([
        [1, ["read", "read", "1a", "1b", "read", "1c"]],
        [2, []],
        [3, ["3a", "read", "read", "3b", "read"]],
        [4, ["4a"]],
    ]);

    function has_unread_messages(stream, topic) {
        return topic !== "read";
    }

    function get_topics(stream) {
        return topics.get(stream);
    }

    function next_topic(curr_stream, curr_topic) {
        return tg.next_topic(streams, get_topics, has_unread_messages, curr_stream, curr_topic);
    }

    assert.deepEqual(next_topic(1, "1a"), {stream: 1, topic: "1b"});
    assert.deepEqual(next_topic(1, undefined), {stream: 1, topic: "1a"});
    assert.deepEqual(next_topic(2, "bogus"), {stream: 3, topic: "3a"});
    assert.deepEqual(next_topic(3, "3b"), {stream: 3, topic: "3a"});
    assert.deepEqual(next_topic(4, "4a"), {stream: 1, topic: "1a"});
    assert.deepEqual(next_topic(undefined, undefined), {stream: 1, topic: "1a"});

    assert.deepEqual(
        tg.next_topic(streams, get_topics, () => false, 1, "1a"),
        undefined,
    );

    // Now test the deeper function that is wired up to
    // real functions stream_data/stream_sort/unread.

    stream_sort.get_streams = function () {
        return ["announce", "muted", "devel", "test here"];
    };

    const muted_stream_id = 400;
    const devel_stream_id = 401;

    const stream_id_dct = {
        muted: muted_stream_id,
        devel: devel_stream_id,
    };

    stream_topic_history.get_recent_topic_names = function (stream_id) {
        switch (stream_id) {
            case muted_stream_id:
                return ["ms-topic1", "ms-topic2"];
            case devel_stream_id:
                return ["muted", "python"];
        }

        return [];
    };

    stream_data.get_stream_id = function (stream_name) {
        return stream_id_dct[stream_name];
    };

    stream_data.is_stream_muted_by_name = function (stream_name) {
        return stream_name === "muted";
    };

    unread.topic_has_any_unread = function (stream_id) {
        return [devel_stream_id, muted_stream_id].includes(stream_id);
    };

    muting.is_topic_muted = function (stream_name, topic) {
        return topic === "muted";
    };

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

run_test("get_next_unread_pm_string", () => {
    pm_conversations.recent.get_strings = function () {
        return ["1", "read", "2,3", "4", "unk"];
    };

    unread.num_unread_for_person = function (user_ids_string) {
        if (user_ids_string === "unk") {
            return undefined;
        }

        if (user_ids_string === "read") {
            return 0;
        }

        return 5; // random non-zero value
    };

    assert.equal(tg.get_next_unread_pm_string(), "1");
    assert.equal(tg.get_next_unread_pm_string("4"), "1");
    assert.equal(tg.get_next_unread_pm_string("unk"), "1");
    assert.equal(tg.get_next_unread_pm_string("4"), "1");
    assert.equal(tg.get_next_unread_pm_string("1"), "2,3");
    assert.equal(tg.get_next_unread_pm_string("read"), "2,3");
    assert.equal(tg.get_next_unread_pm_string("2,3"), "4");

    unread.num_unread_for_person = () => 0;

    assert.equal(tg.get_next_unread_pm_string("2,3"), undefined);
});
