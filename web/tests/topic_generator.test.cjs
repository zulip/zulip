"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const narrow_state = mock_esm("../src/narrow_state");
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

const devel = 1;
const design = 2;
const muted_channel = 3;
const sorted_channels_info = [
    {channel_id: devel, is_collapsed: false},
    {channel_id: design, is_collapsed: true},
    {channel_id: muted_channel, is_collapsed: false},
];
const elsewhere = [undefined, undefined];

// Mocks what choosing the next topic reads, and returns setters for
// the unread topics per channel, the topic visibility policies, and
// the current narrow.
function mock_channels_and_topics(override) {
    // Not every test reads all of these.
    const mock = (module, name, f) => override(module, name, f, {unused: false});

    let unread_topics = new Map();
    let topic_policies = new Map();
    let curr_stream_id;
    let curr_topic;

    function topic_policy(stream_id, topic) {
        return topic_policies.get(`${stream_id}:${topic.toLowerCase()}`);
    }
    function is_unread(stream_id, topic) {
        return (unread_topics.get(stream_id) ?? []).includes(topic);
    }

    mock(stream_data, "is_muted", (stream_id) => stream_id === muted_channel);
    mock(
        user_topics,
        "is_topic_muted",
        (stream_id, topic) => topic_policy(stream_id, topic) === "muted",
    );
    mock(user_topics, "is_topic_unmuted_or_followed", (stream_id, topic) =>
        ["unmuted", "followed"].includes(topic_policy(stream_id, topic)),
    );
    mock(stream_topic_history, "get_recent_topic_names", (stream_id) => [
        "read topic",
        ...(unread_topics.get(stream_id) ?? []),
        "another read topic",
    ]);
    mock(unread, "get_msg_ids_for_topic", (stream_id, topic) =>
        is_unread(stream_id, topic) ? [`${stream_id}:${topic}`] : [],
    );
    mock(unread, "get_topics_with_unreads", (stream_id) => unread_topics.get(stream_id) ?? []);
    mock(narrow_state, "stream_id", () => curr_stream_id);
    mock(narrow_state, "topic", () => curr_topic);
    mock(narrow_state, "filter", () => ({
        sorted_term_types: () => (curr_topic === undefined ? ["channel"] : ["channel", "topic"]),
    }));
    mock(
        narrow_state,
        "narrowed_by_topic_reply",
        () => curr_stream_id !== undefined && curr_topic !== undefined,
    );

    return {
        set_unread_topics(topics) {
            unread_topics = new Map(topics);
        },
        set_topic_policies(policies) {
            topic_policies = new Map(policies);
        },
        set_narrow(narrow) {
            [curr_stream_id, curr_topic] = narrow;
        },
    };
}

run_test("get_next_topic and has_next_unread_topic", ({override}) => {
    const {set_unread_topics, set_topic_policies, set_narrow} = mock_channels_and_topics(override);

    function assert_next_topic(narrow, expected) {
        tg.reset_topics_kept_unread_by_user();
        set_narrow(narrow);
        const only_followed_topics = false;
        assert.deepEqual(
            tg.get_next_topic(...narrow, only_followed_topics, sorted_channels_info),
            expected,
        );
        assert.equal(
            tg.has_next_unread_topic(...narrow, sorted_channels_info),
            expected !== undefined,
        );
    }

    assert_next_topic(elsewhere, undefined);
    assert_next_topic([devel, "lunch"], undefined);

    // An unread topic is next from anywhere but that topic itself.
    set_unread_topics([[devel, ["lunch"]]]);
    assert_next_topic(elsewhere, {stream_id: devel, topic: "lunch"});
    assert_next_topic([devel, undefined], {stream_id: devel, topic: "lunch"});
    assert_next_topic([devel, "read topic"], {stream_id: devel, topic: "lunch"});
    assert_next_topic([design, "lunch"], {stream_id: devel, topic: "lunch"});
    assert_next_topic([devel, "lunch"], undefined);

    set_unread_topics([[devel, ["lunch", "dinner"]]]);
    assert_next_topic([devel, "lunch"], {stream_id: devel, topic: "dinner"});

    // The topic with an empty name is a topic like any other.
    set_unread_topics([[devel, [""]]]);
    assert_next_topic([devel, undefined], {stream_id: devel, topic: ""});
    assert_next_topic([devel, ""], undefined);

    // A channel in a collapsed folder counts.
    set_unread_topics([[design, ["logo"]]]);
    assert_next_topic(elsewhere, {stream_id: design, topic: "logo"});
    assert_next_topic([devel, "lunch"], {stream_id: design, topic: "logo"});

    // A muted topic does not.
    set_topic_policies([[`${design}:logo`, "muted"]]);
    assert_next_topic(elsewhere, undefined);
    assert_next_topic([design, undefined], undefined);

    // In a muted channel, only unmuted and followed topics count.
    set_topic_policies([]);
    set_unread_topics([[muted_channel, ["noise"]]]);
    assert_next_topic(elsewhere, undefined);
    assert_next_topic([muted_channel, undefined], undefined);

    set_topic_policies([[`${muted_channel}:noise`, "unmuted"]]);
    assert_next_topic(elsewhere, {stream_id: muted_channel, topic: "noise"});
    assert_next_topic([muted_channel, undefined], {stream_id: muted_channel, topic: "noise"});
    assert_next_topic([muted_channel, "noise"], undefined);

    set_topic_policies([[`${muted_channel}:noise`, "followed"]]);
    assert_next_topic(elsewhere, {stream_id: muted_channel, topic: "noise"});

    // Each channel is judged by its own muting, wherever the user is.
    set_topic_policies([]);
    assert_next_topic([devel, "read topic"], undefined);
    set_unread_topics([[devel, ["lunch"]]]);
    assert_next_topic([muted_channel, "read topic"], {stream_id: devel, topic: "lunch"});

    // A channel that is not in the left sidebar does not count.
    set_unread_topics([[99, ["lunch"]]]);
    assert_next_topic(elsewhere, undefined);
});

run_test("a topic left unread is skipped once by get_next_topic, but counts", ({override}) => {
    const {set_unread_topics, set_narrow} = mock_channels_and_topics(override);
    tg.reset_topics_kept_unread_by_user();
    const only_followed_topics = false;
    function get_next_topic(narrow) {
        set_narrow(narrow);
        return tg.get_next_topic(...narrow, only_followed_topics, sorted_channels_info);
    }

    set_unread_topics([[devel, ["lunch", "dinner"]]]);
    assert.deepEqual(get_next_topic([devel, "lunch"]), {stream_id: devel, topic: "dinner"});

    set_unread_topics([[devel, ["lunch"]]]);
    set_narrow([devel, "read topic"]);
    assert.ok(tg.has_next_unread_topic(devel, "read topic", sorted_channels_info));
    assert.equal(get_next_topic([devel, "read topic"]), undefined);
    assert.deepEqual(get_next_topic([devel, "read topic"]), {stream_id: devel, topic: "lunch"});
});

run_test("has_next_unread_topic ignores the case of the current topic", ({override}) => {
    const {set_unread_topics, set_narrow} = mock_channels_and_topics(override);

    set_unread_topics([[devel, ["lunch"]]]);
    set_narrow([devel, "LUNCH"]);
    assert.ok(!tg.has_next_unread_topic(devel, "LUNCH", sorted_channels_info));
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
