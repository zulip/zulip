"use strict";

const {strict: assert} = require("assert");

const _ = require("lodash");

const {mock_esm, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

const muted_topics = mock_esm("../../static/js/muted_topics", {
    is_topic_muted() {
        return false;
    },
});
const narrow_state = mock_esm("../../static/js/narrow_state", {
    topic() {},
});

const topic_list = mock_esm("../../static/js/topic_list", {
    get_topic_search_term() {},
});

const stream_data = zrequire("stream_data");
const stream_topic_history = zrequire("stream_topic_history");
const topic_list_data = zrequire("topic_list_data");
const unread = zrequire("unread");

const general = {
    stream_id: 556,
    name: "general",
};

stream_data.add_sub(general);

function get_list_info(zoomed) {
    const stream_id = general.stream_id;
    return topic_list_data.get_list_info(stream_id, zoomed);
}

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
        more_topics_unreads: 0,
        num_possible_topics: 0,
    });

    function add_topic_message(topic_name, message_id) {
        stream_topic_history.add_message({
            stream_id: general.stream_id,
            topic_name,
            message_id,
        });
    }
    for (const i of _.range(7)) {
        let topic_name;
        // All odd topics are resolved.
        if (i % 2) {
            topic_name = "✔ topic ";
        } else {
            topic_name = "topic ";
        }
        add_topic_message(topic_name + i, 1000 + i);
    }

    override(narrow_state, "topic", () => "topic 6");

    list_info = get_list_info();
    assert.equal(list_info.items.length, 5);
    assert.equal(list_info.more_topics_unreads, 0);
    assert.equal(list_info.num_possible_topics, 7);

    assert.deepEqual(list_info.items[0], {
        is_active_topic: true,
        is_muted: false,
        is_zero: true,
        topic_display_name: "topic 6",
        topic_name: "topic 6",
        topic_resolved_prefix: "",
        unread: 0,
        url: "#narrow/stream/556-general/topic/topic.206",
    });

    assert.deepEqual(list_info.items[1], {
        is_active_topic: false,
        is_muted: false,
        is_zero: true,
        topic_display_name: "topic 5",
        topic_name: "✔ topic 5",
        topic_resolved_prefix: "✔ ",
        unread: 0,
        url: "#narrow/stream/556-general/topic/.E2.9C.94.20topic.205",
    });
    // If we zoom in, our results based on topic filter.
    // If topic search input is empty, we show all 7 topics.

    const zoomed = true;
    override(topic_list, "get_topic_search_term", () => "");
    list_info = get_list_info(zoomed);
    assert.equal(list_info.items.length, 7);
    assert.equal(list_info.more_topics_unreads, 0);
    assert.equal(list_info.num_possible_topics, 7);

    add_topic_message("After Brooklyn", 1008);
    add_topic_message("Catering", 1009);
    // when topic search is open then we list topics based on search term.
    override(topic_list, "get_topic_search_term", () => "b,c");
    list_info = get_list_info(zoomed);
    assert.equal(list_info.items.length, 2);
    assert.equal(list_info.more_topics_unreads, 0);
    assert.equal(list_info.num_possible_topics, 2);
});

test("get_list_info unreads", ({override}) => {
    let list_info;

    let message_id = 0;
    for (let i = 14; i >= 0; i -= 1) {
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

    /*
        We have 15 topics, but we only show up
        to 8 topics, depending on how many have
        unread counts.  We only show a max of 5
        fully-read topics.

        So first we'll get 7 topics, where 2 are
        unread.
    */
    add_unreads("topic 8", 8);
    add_unreads("topic 9", 9);

    list_info = get_list_info();
    assert.equal(list_info.items.length, 7);
    assert.equal(list_info.more_topics_unreads, 0);
    assert.equal(list_info.num_possible_topics, 15);

    assert.deepEqual(
        list_info.items.map((li) => li.topic_name),
        ["topic 0", "topic 1", "topic 2", "topic 3", "topic 4", "topic 8", "topic 9"],
    );

    add_unreads("topic 6", 6);
    add_unreads("topic 7", 7);

    list_info = get_list_info();
    assert.equal(list_info.items.length, 8);
    assert.equal(list_info.more_topics_unreads, 9);
    assert.equal(list_info.num_possible_topics, 15);

    assert.deepEqual(
        list_info.items.map((li) => li.topic_name),
        ["topic 0", "topic 1", "topic 2", "topic 3", "topic 4", "topic 6", "topic 7", "topic 8"],
    );

    add_unreads("topic 4", 4);
    add_unreads("topic 5", 5);
    add_unreads("topic 13", 13);

    override(muted_topics, "is_topic_muted", (stream_id, topic_name) => {
        assert.equal(stream_id, general.stream_id);
        return topic_name === "topic 4";
    });

    list_info = get_list_info();
    assert.equal(list_info.items.length, 8);
    assert.equal(list_info.more_topics_unreads, 9 + 13);
    assert.equal(list_info.num_possible_topics, 15);

    assert.deepEqual(
        list_info.items.map((li) => li.topic_name),
        ["topic 0", "topic 1", "topic 2", "topic 3", "topic 5", "topic 6", "topic 7", "topic 8"],
    );
});
