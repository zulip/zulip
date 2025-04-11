"use strict";

const assert = require("node:assert/strict");

const _ = require("lodash");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

mock_esm("../src/message_store", {
    get() {
        return {
            stream_id: 556,
            topic: "general",
        };
    },
});
const user_topics = mock_esm("../src/user_topics", {
    is_topic_muted() {
        return false;
    },
    is_topic_followed() {
        return false;
    },
    is_topic_unmuted_or_followed() {
        return false;
    },
});
const narrow_state = mock_esm("../src/narrow_state", {
    topic() {},
    stream_id() {},
});

const {set_realm} = zrequire("state_data");
const stream_data = zrequire("stream_data");
const stream_topic_history = zrequire("stream_topic_history");
const topic_list_data = zrequire("topic_list_data");
const unread = zrequire("unread");

const REALM_EMPTY_TOPIC_DISPLAY_NAME = "test general chat";

set_realm({realm_empty_topic_display_name: REALM_EMPTY_TOPIC_DISPLAY_NAME});

const general = {
    stream_id: 556,
    name: "general",
};

stream_data.add_sub(general);

function get_list_info(zoom, search) {
    const stream_id = general.stream_id;
    const zoomed = zoom === undefined ? false : zoom;
    const search_term = search === undefined ? "" : search;
    return topic_list_data.get_list_info(stream_id, zoomed, (topics) =>
        topic_list_data.filter_topics_by_search_term(topics, search_term),
    );
}

test("filter_topics_by_search_term with resolved topics_state", () => {
    const topic_names = ["topic 1", "✔ resolved topic", "topic 2"];
    const search_term = "";

    // Filter for resolved topics.
    let topics_state = "is: resolved";

    let result = topic_list_data.filter_topics_by_search_term(
        topic_names,
        search_term,
        topics_state,
    );

    assert.deepEqual(result, ["✔ resolved topic"]);

    // Filter for unresolved topics.
    topics_state = "-is: resolved";
    result = topic_list_data.filter_topics_by_search_term(topic_names, search_term, topics_state);

    assert.deepEqual(result, ["topic 1", "topic 2"]);
});

function test(label, f) {
    run_test(label, (helpers) => {
        stream_topic_history.reset();
        f(helpers);
    });
}

test("get_list_info w/real stream_topic_history", ({override}) => {
    let list_info;
    const empty_list_info = get_list_info();

    assert.deepEqual(empty_list_info, {
        items: [],
        more_topics_have_unread_mention_messages: false,
        more_topics_unreads: 0,
        more_topics_unread_count_muted: false,
        num_possible_topics: 0,
    });

    function add_topic_message(topic_name, message_id) {
        stream_topic_history.add_message({
            stream_id: general.stream_id,
            topic_name,
            message_id,
        });
    }
    for (const i of _.range(10)) {
        let topic_name;
        // All odd topics are resolved.
        if (i % 2) {
            topic_name = "✔ topic ";
        } else {
            topic_name = "topic ";
        }
        add_topic_message(topic_name + i, 1000 + i);
    }

    override(narrow_state, "topic", () => "topic 11");
    override(narrow_state, "stream_id", () => 556);

    list_info = get_list_info();
    assert.equal(list_info.items.length, 8);
    assert.equal(list_info.more_topics_unreads, 0);
    assert.equal(list_info.more_topics_have_unread_mention_messages, false);
    assert.equal(list_info.num_possible_topics, 11);

    // The topic link is not a permalink since the topic has no
    // messages sent yet.
    assert.deepEqual(list_info.items[0], {
        topic_name: "topic 11",
        topic_resolved_prefix: "",
        topic_display_name: "topic 11",
        is_empty_string_topic: false,
        unread: 0,
        is_zero: true,
        stream_id: 556,
        is_muted: false,
        is_followed: false,
        is_unmuted_or_followed: false,
        is_active_topic: true,
        url: "#narrow/channel/556-general/topic/topic.2011",
        contains_unread_mention: false,
    });

    override(narrow_state, "topic", () => "topic 6");

    list_info = get_list_info();
    assert.equal(list_info.items.length, 8);
    assert.equal(list_info.more_topics_unreads, 0);
    assert.equal(list_info.more_topics_have_unread_mention_messages, false);
    assert.equal(list_info.num_possible_topics, 10);

    assert.deepEqual(list_info.items[0], {
        contains_unread_mention: false,
        is_active_topic: false,
        is_muted: false,
        is_followed: false,
        is_unmuted_or_followed: false,
        is_zero: true,
        stream_id: 556,
        topic_display_name: "topic 9",
        topic_name: "✔ topic 9",
        topic_resolved_prefix: "✔ ",
        is_empty_string_topic: false,
        unread: 0,
        url: `#narrow/channel/556-general/topic/.E2.9C.94.20topic.209/with/${1000 + 9}`,
    });

    assert.deepEqual(list_info.items[1], {
        contains_unread_mention: false,
        is_active_topic: false,
        is_muted: false,
        is_followed: false,
        is_unmuted_or_followed: false,
        is_zero: true,
        stream_id: 556,
        topic_display_name: "topic 8",
        topic_name: "topic 8",
        topic_resolved_prefix: "",
        is_empty_string_topic: false,
        unread: 0,
        url: `#narrow/channel/556-general/topic/topic.208/with/${1000 + 8}`,
    });

    // Empty string as topic name.
    add_topic_message("", 2025);

    list_info = get_list_info();
    assert.equal(list_info.items.length, 8);
    assert.equal(list_info.more_topics_unreads, 0);
    assert.equal(list_info.more_topics_have_unread_mention_messages, false);
    assert.equal(list_info.num_possible_topics, 11);

    assert.deepEqual(list_info.items[0], {
        contains_unread_mention: false,
        is_active_topic: false,
        is_muted: false,
        is_followed: false,
        is_unmuted_or_followed: false,
        is_zero: true,
        stream_id: 556,
        topic_display_name: REALM_EMPTY_TOPIC_DISPLAY_NAME,
        topic_name: "",
        topic_resolved_prefix: "",
        is_empty_string_topic: true,
        unread: 0,
        url: "#narrow/channel/556-general/topic//with/2025",
    });

    // If we zoom in, our results are based on topic filter.
    // If topic search input is empty, we show all 10 topics.
    const zoomed = true;
    list_info = get_list_info(zoomed);
    assert.equal(list_info.items.length, 11);
    assert.equal(list_info.more_topics_unreads, 0);
    assert.equal(list_info.more_topics_have_unread_mention_messages, false);
    assert.equal(list_info.num_possible_topics, 11);

    add_topic_message("After Brooklyn", 1008);
    add_topic_message("Delhi", 1009);

    // When topic search input is not empty, we show topics
    // based on the search term.
    let search_term = "b,d";
    list_info = get_list_info(zoomed, search_term);
    assert.equal(list_info.items.length, 2);
    assert.equal(list_info.more_topics_unreads, 0);
    assert.equal(list_info.more_topics_have_unread_mention_messages, false);
    assert.equal(list_info.num_possible_topics, 2);

    // Verify empty string topic shows up for "general" search term.
    search_term = "general";
    list_info = get_list_info(zoomed, search_term);
    assert.equal(list_info.items.length, 1);
    assert.equal(list_info.items[0].topic_name, "");
    assert.equal(list_info.items[0].topic_display_name, REALM_EMPTY_TOPIC_DISPLAY_NAME);
});

test("get_list_info unreads", ({override}) => {
    let list_info;

    let message_id = 0;
    for (let i = 15; i >= 0; i -= 1) {
        stream_topic_history.add_message({
            stream_id: general.stream_id,
            message_id: (message_id += 1),
            topic_name: `topic ${i}`,
        });
    }

    function add_unreads(topic, count) {
        unread.process_loaded_messages(
            Array.from({length: count}, () => ({
                id: (message_id += 1),
                stream_id: general.stream_id,
                topic,
                type: "stream",
                unread: true,
            })),
        );
    }

    function add_unreads_with_mention(topic, count) {
        unread.process_loaded_messages(
            Array.from({length: count}, () => ({
                id: (message_id += 1),
                stream_id: general.stream_id,
                topic,
                type: "stream",
                unread: true,
                mentioned: true,
                mentioned_me_directly: true,
            })),
        );
    }

    /*
        We have 16 topics, but we only show up
        to 12 topics, depending on how many have
        unread counts.  We only show a max of 8
        fully-read topics.

        So first we'll get 10 topics, where 2 are
        unread.
    */
    add_unreads("topic 14", 1);
    add_unreads("topic 13", 1);

    /*
        We added 1 unread message in 'topic 14',
        but now we would add a unread message
        with `mention` for user, to test
        `more_topics_have_unread_mention_messages`.
    */
    add_unreads_with_mention("topic 14", 1);

    list_info = get_list_info();
    assert.equal(list_info.items.length, 10);
    assert.equal(list_info.more_topics_unreads, 0);
    assert.equal(list_info.more_topics_have_unread_mention_messages, false);
    assert.equal(list_info.num_possible_topics, 16);

    assert.deepEqual(
        list_info.items.map((li) => li.topic_name),
        [
            "topic 0",
            "topic 1",
            "topic 2",
            "topic 3",
            "topic 4",
            "topic 5",
            "topic 6",
            "topic 7",
            "topic 13",
            "topic 14",
        ],
    );

    add_unreads("topic 12", 1);
    add_unreads("topic 11", 1);
    add_unreads("topic 10", 1);

    list_info = get_list_info();
    assert.equal(list_info.items.length, 12);
    assert.equal(list_info.more_topics_unreads, 2);
    assert.equal(list_info.more_topics_have_unread_mention_messages, true);
    assert.equal(list_info.num_possible_topics, 16);

    assert.deepEqual(
        list_info.items.map((li) => li.topic_name),
        [
            "topic 0",
            "topic 1",
            "topic 2",
            "topic 3",
            "topic 4",
            "topic 5",
            "topic 6",
            "topic 7",
            "topic 10",
            "topic 11",
            "topic 12",
            "topic 13",
        ],
    );

    add_unreads("topic 9", 1);
    add_unreads("topic 8", 1);

    add_unreads("topic 4", 1);
    override(user_topics, "is_topic_muted", (stream_id, topic_name) => {
        assert.equal(stream_id, general.stream_id);
        return topic_name === "topic 4";
    });

    // muting the stream and unmuting the topic 5
    // this should make topic 5 at top in items array
    general.is_muted = true;
    add_unreads("topic 5", 1);
    override(user_topics, "is_topic_unmuted_or_followed", (stream_id, topic_name) => {
        assert.equal(stream_id, general.stream_id);
        return topic_name === "topic 5";
    });

    list_info = get_list_info();
    assert.equal(list_info.items.length, 12);
    assert.equal(list_info.more_topics_unreads, 3);
    assert.equal(list_info.more_topics_have_unread_mention_messages, true);
    assert.equal(list_info.num_possible_topics, 16);
    assert.equal(list_info.more_topics_unread_count_muted, false);

    assert.deepEqual(
        list_info.items.map((li) => li.topic_name),
        [
            "topic 5",
            "topic 0",
            "topic 1",
            "topic 2",
            "topic 3",
            "topic 6",
            "topic 7",
            "topic 8",
            "topic 9",
            "topic 10",
            "topic 11",
            "topic 12",
        ],
    );

    // Now test with topics 4/8/9, all the ones with unreads, being muted.
    override(user_topics, "is_topic_muted", (stream_id, topic_name) => {
        assert.equal(stream_id, general.stream_id);
        return ["topic 4", "topic 8", "topic 9"].includes(topic_name);
    });
    list_info = get_list_info();
    assert.equal(list_info.items.length, 12);
    assert.equal(list_info.more_topics_unreads, 3);
    // Topic 14 now makes it above the "show all topics" fold.
    assert.equal(list_info.more_topics_have_unread_mention_messages, false);
    assert.equal(list_info.num_possible_topics, 16);
    assert.equal(list_info.more_topics_unread_count_muted, true);
    assert.deepEqual(
        list_info.items.map((li) => li.topic_name),
        [
            "topic 5",
            "topic 0",
            "topic 1",
            "topic 2",
            "topic 3",
            "topic 6",
            "topic 7",
            "topic 10",
            "topic 11",
            "topic 12",
            "topic 13",
            "topic 14",
        ],
    );

    add_unreads_with_mention("topic 8", 1);
    list_info = get_list_info();
    assert.equal(list_info.items.length, 12);
    assert.equal(list_info.more_topics_unreads, 4);
    // Topic 8's new mention gets counted here.
    assert.equal(list_info.more_topics_have_unread_mention_messages, true);
    assert.equal(list_info.num_possible_topics, 16);
    assert.equal(list_info.more_topics_unread_count_muted, true);
    assert.deepEqual(
        list_info.items.map((li) => li.topic_name),
        [
            "topic 5",
            "topic 0",
            "topic 1",
            "topic 2",
            "topic 3",
            "topic 6",
            "topic 7",
            "topic 10",
            "topic 11",
            "topic 12",
            "topic 13",
            "topic 14",
        ],
    );

    // Adding an additional older unmuted topic with unreads should
    // result in just the unmuted unreads being counted.
    add_unreads("topic 15", 15);
    list_info = get_list_info();
    assert.equal(list_info.items.length, 12);
    assert.equal(list_info.more_topics_unreads, 15);
    assert.equal(list_info.more_topics_have_unread_mention_messages, true);
    assert.equal(list_info.num_possible_topics, 16);
    assert.equal(list_info.more_topics_unread_count_muted, false);
    assert.deepEqual(
        list_info.items.map((li) => li.topic_name),
        [
            "topic 5",
            "topic 0",
            "topic 1",
            "topic 2",
            "topic 3",
            "topic 6",
            "topic 7",
            "topic 10",
            "topic 11",
            "topic 12",
            "topic 13",
            "topic 14",
        ],
    );
});

test("get_list_info with specific topics and searches", () => {
    let list_info;

    function add_topic_message(topic_name, message_id) {
        stream_topic_history.add_message({
            stream_id: general.stream_id,
            topic_name,
            message_id,
        });
    }

    add_topic_message("BF-2924 zulip", 1001);
    add_topic_message("tech_support/escalation", 1002);

    list_info = get_list_info(true, "2924");
    assert.equal(list_info.items.length, 1);
    assert.equal(list_info.items[0].topic_name, "BF-2924 zulip");

    list_info = get_list_info(true, "support/escalation");
    assert.equal(list_info.items.length, 1);
    assert.equal(list_info.items[0].topic_name, "tech_support/escalation");

    list_info = get_list_info(true, "support");
    assert.equal(list_info.items.length, 1);
    assert.equal(list_info.items[0].topic_name, "tech_support/escalation");

    list_info = get_list_info(true, "zulip");
    assert.equal(list_info.items.length, 1);
    assert.equal(list_info.items[0].topic_name, "BF-2924 zulip");

    list_info = get_list_info(true, "SUPPORT");
    assert.equal(list_info.items.length, 1);
    assert.equal(list_info.items[0].topic_name, "tech_support/escalation");

    list_info = get_list_info(true, "nonexistent");
    assert.equal(list_info.items.length, 0);
});
