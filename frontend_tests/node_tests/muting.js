"use strict";

const {strict: assert} = require("assert");

const {set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

const page_params = set_global("page_params", {});

const muting = zrequire("muting");
const stream_data = zrequire("stream_data");

const design = {
    stream_id: 100,
    name: "design",
};

const devel = {
    stream_id: 101,
    name: "devel",
};

const office = {
    stream_id: 102,
    name: "office",
};

const social = {
    stream_id: 103,
    name: "social",
};

const unknown = {
    stream_id: 999,
    name: "whatever",
};

stream_data.add_sub(design);
stream_data.add_sub(devel);
stream_data.add_sub(office);
stream_data.add_sub(social);

function test(label, f) {
    run_test(label, (override) => {
        muting.set_muted_topics([]);
        f(override);
    });
}

test("edge_cases", () => {
    // private messages
    assert(!muting.is_topic_muted(undefined, undefined));
});

test("basics", () => {
    assert(!muting.is_topic_muted(devel.stream_id, "java"));
    muting.add_muted_topic(devel.stream_id, "java");
    assert(muting.is_topic_muted(devel.stream_id, "java"));

    // test idempotentcy
    muting.add_muted_topic(devel.stream_id, "java");
    assert(muting.is_topic_muted(devel.stream_id, "java"));

    muting.remove_muted_topic(devel.stream_id, "java");
    assert(!muting.is_topic_muted(devel.stream_id, "java"));

    // test idempotentcy
    muting.remove_muted_topic(devel.stream_id, "java");
    assert(!muting.is_topic_muted(devel.stream_id, "java"));

    // test unknown stream is harmless too
    muting.remove_muted_topic(unknown.stream_id, "java");
    assert(!muting.is_topic_muted(unknown.stream_id, "java"));
});

test("basics", () => {
    assert.deepEqual(muting.get_muted_topics(), []);
    muting.add_muted_topic(office.stream_id, "gossip", 1577836800);
    muting.add_muted_topic(devel.stream_id, "java", 1577836700);
    const muted_topics = muting.get_muted_topics().sort((a, b) => a.date_muted - b.date_muted);

    assert.deepEqual(muted_topics, [
        {
            date_muted: 1577836700000,
            date_muted_str: "Dec\u00A031,\u00A02019",
            stream: devel.name,
            stream_id: devel.stream_id,
            topic: "java",
        },
        {
            date_muted: 1577836800000,
            date_muted_str: "Jan\u00A001,\u00A02020",
            stream: office.name,
            stream_id: office.stream_id,
            topic: "gossip",
        },
    ]);
});

test("unknown streams", () => {
    blueslip.expect("warn", "Unknown stream in set_muted_topics: BOGUS STREAM");

    page_params.muted_topics = [
        ["social", "breakfast", 1577836800],
        ["design", "typography", 1577836800],
        ["BOGUS STREAM", "whatever", 1577836800],
    ];
    muting.initialize();

    assert.deepEqual(muting.get_muted_topics().sort(), [
        {
            date_muted: 1577836800000,
            date_muted_str: "Jan\u00A001,\u00A02020",
            stream: social.name,
            stream_id: social.stream_id,
            topic: "breakfast",
        },
        {
            date_muted: 1577836800000,
            date_muted_str: "Jan\u00A001,\u00A02020",
            stream: design.name,
            stream_id: design.stream_id,
            topic: "typography",
        },
    ]);
});

test("case_insensitivity", () => {
    muting.set_muted_topics([]);
    assert(!muting.is_topic_muted(social.stream_id, "breakfast"));
    muting.set_muted_topics([["SOCial", "breakfast"]]);
    assert(muting.is_topic_muted(social.stream_id, "breakfast"));
    assert(muting.is_topic_muted(social.stream_id, "breakFAST"));
});
