"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

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

run_test("topics", ({override}) => {
    const streams = [1, 2, 3, 4];
    const topics = new Map([
        [1, ["read", "read", "1a", "1b", "read", "1c"]],
        [2, []],
        [3, ["3a", "read", "read", "3b", "read"]],
        [4, ["4a"]],
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

    assert.deepEqual(next_topic(1, "1a"), {stream_id: 1, topic: "1b"});
    assert.deepEqual(next_topic(1, undefined), {stream_id: 1, topic: "1a"});
    assert.deepEqual(next_topic(2, "bogus"), {stream_id: 3, topic: "3a"});
    assert.deepEqual(next_topic(3, "3b"), {stream_id: 3, topic: "3a"});
    assert.deepEqual(next_topic(4, "4a"), {stream_id: 1, topic: "1a"});
    assert.deepEqual(next_topic(undefined, undefined), {stream_id: 1, topic: "1a"});

    assert.deepEqual(
        tg.next_topic(streams, get_topics, () => false, 1, "1a"),
        undefined,
    );

    // Now test the deeper function that is wired up to
    // real functions stream_data/stream_list_sort/unread.

    const muted_stream_id = 400;
    const devel_stream_id = 401;
    const announce_stream_id = 402;
    const test_here_stream_id = 403;
    override(stream_list_sort, "get_stream_ids", () => [
        announce_stream_id,
        muted_stream_id,
        devel_stream_id,
        test_here_stream_id,
    ]);

    override(stream_topic_history, "get_recent_topic_names", (stream_id) => {
        switch (stream_id) {
            case muted_stream_id:
                return ["ms-topic1", "ms-topic2", "unmuted", "followed-muted"];
            case devel_stream_id:
                return ["muted", "python", "followed-devel"];
        }

        return [];
    });

    override(stream_data, "is_muted", (stream_id) => stream_id === muted_stream_id);

    let topic_has_unreads = new Set([
        "unmuted",
        "followed-muted",
        "muted",
        "python",
        "followed-devel",
    ]);
    function mark_topic_as_read(topic) {
        topic_has_unreads.delete(topic);
    }
    override(unread, "topic_has_any_unread", (_stream_id, topic) => topic_has_unreads.has(topic));

    override(user_topics, "is_topic_muted", (_stream_name, topic) => topic === "muted");

    override(
        user_topics,
        "is_topic_unmuted_or_followed",
        (_stream_name, topic) =>
            topic === "unmuted" || topic === "followed-muted" || topic === "followed-devel",
    );

    override(
        user_topics,
        "is_topic_followed",
        (_stream_name, topic) => topic === "followed-muted" || topic === "followed-devel",
    );

    let next_item = tg.get_next_topic(announce_stream_id, "whatever");
    assert.deepEqual(next_item, {
        stream_id: muted_stream_id,
        topic: "unmuted",
    });
    mark_topic_as_read("unmuted");

    next_item = tg.get_next_topic(muted_stream_id, "unmuted");
    assert.deepEqual(next_item, {
        stream_id: muted_stream_id,
        topic: "followed-muted",
    });
    mark_topic_as_read("followed-muted");

    next_item = tg.get_next_topic(muted_stream_id, "followed-muted");
    assert.deepEqual(next_item, {
        stream_id: devel_stream_id,
        topic: "python",
    });
    mark_topic_as_read("python");

    next_item = tg.get_next_topic(devel_stream_id, "python");
    assert.deepEqual(next_item, {
        stream_id: devel_stream_id,
        topic: "followed-devel",
    });
    mark_topic_as_read("followed-devel");

    // Mark topics as unread again
    topic_has_unreads = new Set(["unmuted", "followed-muted", "muted", "python", "followed-devel"]);
    // Shift + N takes the user to next unread followed topic,
    // even if the stream is muted.
    next_item = tg.get_next_topic(announce_stream_id, "whatever", true);
    assert.deepEqual(next_item, {
        stream_id: muted_stream_id,
        topic: "followed-muted",
    });

    next_item = tg.get_next_topic(muted_stream_id, "whatever", true);
    assert.deepEqual(next_item, {
        stream_id: muted_stream_id,
        topic: "followed-muted",
    });

    next_item = tg.get_next_topic(muted_stream_id, undefined);
    assert.deepEqual(next_item, {
        stream_id: muted_stream_id,
        topic: "unmuted",
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
