"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const pm_conversations = mock_esm("../src/pm_conversations", {
    recent: {},
});
const stream_list_sort = mock_esm("../src/stream_list_sort");
const unread = mock_esm("../src/unread");

const tg = zrequire("topic_generator");

run_test("streams", ({override}) => {
    function assert_next_stream(curr_stream_id, expected) {
        const actual = tg.get_next_stream(curr_stream_id);
        assert.equal(actual, expected);
    }

    override(stream_list_sort, "get_stream_ids", () => [1, 2, 3, 4]);

    assert_next_stream(undefined, 1);

    assert_next_stream(1, 2);
    assert_next_stream(4, 1);

    function assert_prev_stream(curr_stream_id, expected) {
        const actual = tg.get_prev_stream(curr_stream_id);
        assert.equal(actual, expected);
    }

    assert_prev_stream(undefined, 4);
    assert_prev_stream(4, 3);
    assert_prev_stream(1, 4);
});

run_test("topics", () => {
    const {next_topic} = tg;

    function make_next_topic(
        sorted_channels_info,
        topics_by_stream,
        unread_topic_names,
        topics_kept_unread_by_user = new Set(),
    ) {
        function get_topics(stream_id) {
            return topics_by_stream.get(stream_id) ?? [];
        }

        function has_unread_messages(_stream_id, topic) {
            if (topics_kept_unread_by_user.has(topic)) {
                topics_kept_unread_by_user.delete(topic);
                return false;
            }
            return unread_topic_names.has(topic);
        }

        return function (curr_stream_id, curr_topic) {
            return next_topic(
                sorted_channels_info,
                get_topics,
                has_unread_messages,
                curr_stream_id,
                curr_topic,
            );
        };
    }

    // Case 1: basic navigation within a single uncollapsed channel
    {
        const sorted_channels_info = [{channel_id: 1, is_collapsed: false}];
        const topics_by_stream = new Map([[1, ["t1", "t2", "t3"]]]);
        const unread_topic_names = new Set(["t1", "t2", "t3"]);

        const next = make_next_topic(sorted_channels_info, topics_by_stream, unread_topic_names);

        assert.deepEqual(next(1, "t1"), {stream_id: 1, topic: "t2"});
        assert.deepEqual(next(1, "t2"), {stream_id: 1, topic: "t3"});

        // Wrap-around behavior: go back to first unread
        assert.deepEqual(next(1, "t3"), {stream_id: 1, topic: "t1"});

        assert.deepEqual(next(1, undefined), {stream_id: 1, topic: "t1"});

        // Now mark everything as read → true undefined case
        unread_topic_names.clear();
        assert.equal(next(1, "t3"), undefined);
    }

    // Case 2: multiple uncollapsed channels, wrapping across channels
    {
        const sorted_channels_info = [
            {channel_id: 1, is_collapsed: false},
            {channel_id: 2, is_collapsed: false},
        ];
        const topics_by_stream = new Map([
            [1, ["a1", "a2"]],
            [2, ["b1"]],
        ]);
        const unread_topic_names = new Set(["a1", "a2", "b1"]);
        const topics_kept_unread_by_user = new Set();

        const next = make_next_topic(
            sorted_channels_info,
            topics_by_stream,
            unread_topic_names,
            topics_kept_unread_by_user,
        );

        // User starts with 2nd topic but doesn't mark it as read.
        topics_kept_unread_by_user.add("a2");
        // `next` navigates to a1 since it is still unread.
        assert.deepEqual(next(1, "a2"), {stream_id: 1, topic: "a1"});
        // User marks a1 as read.
        unread_topic_names.delete("a1");
        // `a2` is unread but we skip it since user wants to keep it unread.
        assert.deepEqual(next(1, "a1"), {stream_id: 2, topic: "b1"});
        // Wrap around to read any topics left.
        assert.deepEqual(next(2, "b1"), {stream_id: 1, topic: "a2"});

        assert.deepEqual(next(undefined, undefined), {stream_id: 1, topic: "a2"});
    }

    // Case 3: collapsed channels
    {
        const sorted_channels_info = [
            {channel_id: 1, is_collapsed: false},
            {channel_id: 2, is_collapsed: true},
            {channel_id: 3, is_collapsed: false},
        ];
        const topics_by_stream = new Map([
            [1, ["c1"]],
            [2, ["c2"]],
            [3, ["c3"]],
        ]);

        const unread_topic_names = new Set(["c1", "c2", "c3"]);
        const next = make_next_topic(sorted_channels_info, topics_by_stream, unread_topic_names);

        assert.deepEqual(next(1, "c1"), {stream_id: 3, topic: "c3"});

        unread_topic_names.delete("c1");
        unread_topic_names.delete("c3");

        assert.deepEqual(next(1, "c1"), {stream_id: 2, topic: "c2"});
    }
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
