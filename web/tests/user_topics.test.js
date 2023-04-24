"use strict";

const {strict: assert} = require("assert");

const {all_visibility_policies} = require("../src/user_topics");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const blueslip = require("./lib/zblueslip");
const {page_params} = require("./lib/zpage_params");

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
    user_topics.update_user_topics(devel.stream_id, "java", all_visibility_policies.MUTED);
    assert.ok(user_topics.is_topic_muted(devel.stream_id, "java"));

    // test idempotency
    user_topics.update_user_topics(devel.stream_id, "java", all_visibility_policies.MUTED);
    assert.ok(user_topics.is_topic_muted(devel.stream_id, "java"));

    user_topics.update_user_topics(devel.stream_id, "java", all_visibility_policies.INHERIT);
    assert.ok(!user_topics.is_topic_muted(devel.stream_id, "java"));

    // test idempotency
    user_topics.update_user_topics(devel.stream_id, "java", all_visibility_policies.INHERIT);
    assert.ok(!user_topics.is_topic_muted(devel.stream_id, "java"));

    // test unknown stream is harmless too
    user_topics.update_user_topics(unknown.stream_id, "java", all_visibility_policies.INHERIT);
    assert.ok(!user_topics.is_topic_muted(unknown.stream_id, "java"));
});

test("add_and_remove_unmutes", () => {
    assert.ok(!user_topics.is_topic_unmuted(devel.stream_id, "java"));
    user_topics.update_user_topics(devel.stream_id, "java", all_visibility_policies.UNMUTED);
    assert.ok(user_topics.is_topic_unmuted(devel.stream_id, "java"));

    // test idempotency
    user_topics.update_user_topics(devel.stream_id, "java", all_visibility_policies.UNMUTED);
    assert.ok(user_topics.is_topic_unmuted(devel.stream_id, "java"));

    user_topics.update_user_topics(devel.stream_id, "java", all_visibility_policies.INHERIT);
    assert.ok(!user_topics.is_topic_unmuted(devel.stream_id, "java"));

    // test idempotency
    user_topics.update_user_topics(devel.stream_id, "java", all_visibility_policies.INHERIT);
    assert.ok(!user_topics.is_topic_unmuted(devel.stream_id, "java"));

    // test unknown stream is harmless too
    user_topics.update_user_topics(unknown.stream_id, "java", all_visibility_policies.INHERIT);
    assert.ok(!user_topics.is_topic_unmuted(unknown.stream_id, "java"));
});

test("get_mutes", () => {
    assert.deepEqual(
        user_topics.get_user_topics_for_visibility_policy(
            user_topics.all_visibility_policies.MUTED,
        ),
        [],
    );
    user_topics.update_user_topics(
        office.stream_id,
        "gossip",
        all_visibility_policies.MUTED,
        1577836800,
    );
    user_topics.update_user_topics(
        devel.stream_id,
        "java",
        all_visibility_policies.MUTED,
        1577836700,
    );
    const all_muted_topics = user_topics
        .get_user_topics_for_visibility_policy(user_topics.all_visibility_policies.MUTED)
        .sort((a, b) => a.date_updated - b.date_updated);

    assert.deepEqual(all_muted_topics, [
        {
            date_updated: 1577836700000,
            date_updated_str: "Dec 31, 2019",
            stream: devel.name,
            stream_id: devel.stream_id,
            topic: "java",
            visibility_policy: all_visibility_policies.MUTED,
        },
        {
            date_updated: 1577836800000,
            date_updated_str: "Jan 1, 2020",
            stream: office.name,
            stream_id: office.stream_id,
            topic: "gossip",
            visibility_policy: all_visibility_policies.MUTED,
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
            visibility_policy: all_visibility_policies.MUTED,
        },
        {
            stream_id: design.stream_id,
            topic_name: "typography",
            last_updated: "1577836800",
            visibility_policy: all_visibility_policies.MUTED,
        },
        {
            stream_id: 999, // BOGUS STREAM ID
            topic_name: "random",
            last_updated: "1577836800",
            visibility_policy: all_visibility_policies.MUTED,
        },
    ];

    user_topics.initialize();

    assert.deepEqual(
        user_topics
            .get_user_topics_for_visibility_policy(user_topics.all_visibility_policies.MUTED)
            .sort(),
        [
            {
                date_updated: 1577836800000,
                date_updated_str: "Jan 1, 2020",
                stream: social.name,
                stream_id: social.stream_id,
                topic: "breakfast",
                visibility_policy: all_visibility_policies.MUTED,
            },
            {
                date_updated: 1577836800000,
                date_updated_str: "Jan 1, 2020",
                stream: design.name,
                stream_id: design.stream_id,
                topic: "typography",
                visibility_policy: all_visibility_policies.MUTED,
            },
        ],
    );

    user_topics.set_user_topic({
        stream_id: design.stream_id,
        topic_name: "typography",
        last_updated: "1577836800",
        visibility_policy: all_visibility_policies.INHERIT,
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
            visibility_policy: all_visibility_policies.MUTED,
        },
    ]);
    assert.ok(user_topics.is_topic_muted(social.stream_id, "breakfast"));
    assert.ok(user_topics.is_topic_muted(social.stream_id, "breakFAST"));
});
