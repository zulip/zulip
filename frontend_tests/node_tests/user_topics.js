"use strict";

const {strict: assert} = require("assert");

const {visibility_policy} = require("../../static/js/user_topics");
const {zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const blueslip = require("../zjsunit/zblueslip");
const {page_params} = require("../zjsunit/zpage_params");

const user_topics = zrequire("user_topics");
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
    run_test(label, ({override}) => {
        user_topics.set_user_topics([]);
        f({override});
    });
}

test("edge_cases", () => {
    // private messages
    assert.ok(!user_topics.is_topic_muted(undefined, undefined));
});

test("add_and_remove_mutes", () => {
    assert.ok(!user_topics.is_topic_muted(devel.stream_id, "java"));
    user_topics.add_muted_topic(devel.stream_id, "java");
    assert.ok(user_topics.is_topic_muted(devel.stream_id, "java"));

    // test idempotency
    user_topics.add_muted_topic(devel.stream_id, "java");
    assert.ok(user_topics.is_topic_muted(devel.stream_id, "java"));

    user_topics.remove_muted_topic(devel.stream_id, "java");
    assert.ok(!user_topics.is_topic_muted(devel.stream_id, "java"));

    // test idempotency
    user_topics.remove_muted_topic(devel.stream_id, "java");
    assert.ok(!user_topics.is_topic_muted(devel.stream_id, "java"));

    // test unknown stream is harmless too
    user_topics.remove_muted_topic(unknown.stream_id, "java");
    assert.ok(!user_topics.is_topic_muted(unknown.stream_id, "java"));
});

test("get_mutes", () => {
    assert.deepEqual(user_topics.get_muted_topics(), []);
    user_topics.add_muted_topic(office.stream_id, "gossip", 1577836800);
    user_topics.add_muted_topic(devel.stream_id, "java", 1577836700);
    const all_muted_topics = user_topics
        .get_muted_topics()
        .sort((a, b) => a.date_muted - b.date_muted);

    assert.deepEqual(all_muted_topics, [
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

test("set_user_topics", () => {
    blueslip.expect("warn", "Unknown stream ID in set_user_topic: 999");

    user_topics.set_user_topics([]);
    assert.ok(!user_topics.is_topic_muted(social.stream_id, "breakfast"));
    assert.ok(!user_topics.is_topic_muted(design.stream_id, "typography"));

    page_params.user_topics = [
        {
            stream_id: social.stream_id,
            topic_name: "breakfast",
            last_updated: "1577836800",
            visibility_policy: visibility_policy.MUTED,
        },
        {
            stream_id: design.stream_id,
            topic_name: "typography",
            last_updated: "1577836800",
            visibility_policy: visibility_policy.MUTED,
        },
        {
            stream_id: 999, // BOGUS STREAM ID
            topic_name: "random",
            last_updated: "1577836800",
            visibility_policy: visibility_policy.MUTED,
        },
    ];

    user_topics.initialize();

    assert.deepEqual(user_topics.get_muted_topics().sort(), [
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

    user_topics.set_user_topic({
        stream_id: design.stream_id,
        topic_name: "typography",
        last_updated: "1577836800",
        visibility_policy: visibility_policy.VISIBILITY_POLICY_INHERIT,
    });
    assert.ok(!user_topics.is_topic_muted(design.stream_id, "typography"));
});

test("case_insensitivity", () => {
    user_topics.set_user_topics([]);
    assert.ok(!user_topics.is_topic_muted(social.stream_id, "breakfast"));
    user_topics.set_user_topics([
        {
            stream_id: social.stream_id,
            topic_name: "breakfast",
            last_updated: "1577836800",
            visibility_policy: visibility_policy.MUTED,
        },
    ]);
    assert.ok(user_topics.is_topic_muted(social.stream_id, "breakfast"));
    assert.ok(user_topics.is_topic_muted(social.stream_id, "breakFAST"));
});
