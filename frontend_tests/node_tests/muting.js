"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const blueslip = require("../zjsunit/zblueslip");
const {page_params} = require("../zjsunit/zpage_params");

const muted_topics = zrequire("muted_topics");
const muted_users = zrequire("muted_users");
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
        muted_topics.set_muted_topics([]);
        muted_users.set_muted_users([]);
        f({override});
    });
}

test("edge_cases", () => {
    // private messages
    assert.ok(!muted_topics.is_topic_muted(undefined, undefined));

    // invalid user
    assert.ok(!muted_users.is_user_muted(undefined));
});

test("add_and_remove_mutes", () => {
    assert.ok(!muted_topics.is_topic_muted(devel.stream_id, "java"));
    muted_topics.add_muted_topic(devel.stream_id, "java");
    assert.ok(muted_topics.is_topic_muted(devel.stream_id, "java"));

    // test idempotentcy
    muted_topics.add_muted_topic(devel.stream_id, "java");
    assert.ok(muted_topics.is_topic_muted(devel.stream_id, "java"));

    muted_topics.remove_muted_topic(devel.stream_id, "java");
    assert.ok(!muted_topics.is_topic_muted(devel.stream_id, "java"));

    // test idempotentcy
    muted_topics.remove_muted_topic(devel.stream_id, "java");
    assert.ok(!muted_topics.is_topic_muted(devel.stream_id, "java"));

    // test unknown stream is harmless too
    muted_topics.remove_muted_topic(unknown.stream_id, "java");
    assert.ok(!muted_topics.is_topic_muted(unknown.stream_id, "java"));

    assert.ok(!muted_users.is_user_muted(1));
    muted_users.add_muted_user(1);
    assert.ok(muted_users.is_user_muted(1));

    // test idempotentcy
    muted_users.add_muted_user(1);
    assert.ok(muted_users.is_user_muted(1));

    muted_users.remove_muted_user(1);
    assert.ok(!muted_users.is_user_muted(1));

    // test idempotentcy
    muted_users.remove_muted_user(1);
    assert.ok(!muted_users.is_user_muted(1));
});

test("get_unmuted_users", () => {
    const hamlet = {
        user_id: 1,
        full_name: "King Hamlet",
    };
    const cordelia = {
        user_id: 2,
        full_name: "Cordelia, Lear's Daughter",
    };
    const othello = {
        user_id: 3,
        full_name: "Othello, Moor of Venice",
    };

    muted_users.add_muted_user(hamlet.user_id);
    muted_users.add_muted_user(cordelia.user_id);

    assert.deepEqual(
        muted_users.filter_muted_user_ids([hamlet.user_id, cordelia.user_id, othello.user_id]),
        [othello.user_id],
    );
    assert.deepEqual(muted_users.filter_muted_users([hamlet, cordelia, othello]), [othello]);
});

test("get_mutes", () => {
    assert.deepEqual(muted_topics.get_muted_topics(), []);
    muted_topics.add_muted_topic(office.stream_id, "gossip", 1577836800);
    muted_topics.add_muted_topic(devel.stream_id, "java", 1577836700);
    const all_muted_topics = muted_topics
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

    assert.deepEqual(muted_users.get_muted_users(), []);
    muted_users.add_muted_user(6, 1577836800);
    muted_users.add_muted_user(4, 1577836800);
    const all_muted_users = muted_users
        .get_muted_users()
        .sort((a, b) => a.date_muted - b.date_muted);

    assert.deepEqual(all_muted_users, [
        {
            date_muted: 1577836800000,
            date_muted_str: "Jan\u00A001,\u00A02020",
            id: 6,
        },
        {
            date_muted: 1577836800000,
            date_muted_str: "Jan\u00A001,\u00A02020",
            id: 4,
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
    page_params.muted_users = [
        {id: 3, timestamp: 1577836800},
        {id: 2, timestamp: 1577836800},
    ];
    muted_topics.initialize();
    muted_users.initialize();

    assert.deepEqual(muted_topics.get_muted_topics().sort(), [
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

    assert.deepEqual(muted_users.get_muted_users().sort(), [
        {
            date_muted: 1577836800000,
            date_muted_str: "Jan\u00A001,\u00A02020",
            id: 3,
        },
        {
            date_muted: 1577836800000,
            date_muted_str: "Jan\u00A001,\u00A02020",
            id: 2,
        },
    ]);
});

test("case_insensitivity", () => {
    muted_topics.set_muted_topics([]);
    assert.ok(!muted_topics.is_topic_muted(social.stream_id, "breakfast"));
    muted_topics.set_muted_topics([["SOCial", "breakfast"]]);
    assert.ok(muted_topics.is_topic_muted(social.stream_id, "breakfast"));
    assert.ok(muted_topics.is_topic_muted(social.stream_id, "breakFAST"));
});
