"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const topic_link_util = zrequire("topic_link_util");
const stream_data = zrequire("stream_data");

const sweden_stream = {
    name: "Sweden",
    description: "Cold, mountains and home decor.",
    stream_id: 1,
    subscribed: true,
    type: "stream",
};

const denmark_stream = {
    name: "Denmark",
    description: "Vikings and boats, in a serene and cold weather.",
    stream_id: 2,
    subscribed: true,
    type: "stream",
};

const dollar_stream = {
    name: "$$MONEY$$",
    description: "Money money money",
    stream_id: 6,
    subscribed: true,
    type: "stream",
};

stream_data.add_sub(sweden_stream);
stream_data.add_sub(denmark_stream);
stream_data.add_sub(dollar_stream);

run_test("stream_topic_link_syntax_test", () => {
    assert.equal(
        topic_link_util.get_stream_topic_link_syntax("#**Sweden>", "topic"),
        "#**Sweden>topic**",
    );
    assert.equal(
        topic_link_util.get_stream_topic_link_syntax("#**Sweden>to", "topic"),
        "#**Sweden>topic**",
    );
    assert.equal(
        topic_link_util.get_stream_topic_link_syntax("#**Sweden>t", "test `test` test"),
        "[#Sweden > test &#96;test&#96; test](#narrow/channel/1-Sweden/topic/test.20.60test.60.20test)",
    );
    assert.equal(
        topic_link_util.get_stream_topic_link_syntax("#**Denmark>t", "test `test` test`s"),
        "[#Denmark > test &#96;test&#96; test&#96;s](#narrow/channel/2-Denmark/topic/test.20.60test.60.20test.60s)",
    );
    assert.equal(
        topic_link_util.get_stream_topic_link_syntax("#**Sweden>typeah", "error due to *"),
        "[#Sweden > error due to &#42;](#narrow/channel/1-Sweden/topic/error.20due.20to.20*)",
    );
    assert.equal(
        topic_link_util.get_stream_topic_link_syntax("#**Sweden>t", "*asterisk"),
        "[#Sweden > &#42;asterisk](#narrow/channel/1-Sweden/topic/*asterisk)",
    );
    assert.equal(
        topic_link_util.get_stream_topic_link_syntax("#**Sweden>gibberish", "greaterthan>"),
        "[#Sweden > greaterthan&gt;](#narrow/channel/1-Sweden/topic/greaterthan.3E)",
    );
    assert.equal(
        topic_link_util.get_stream_topic_link_syntax("#**$$MONEY$$>t", "dollar"),
        "[#&#36;&#36;MONEY&#36;&#36; > dollar](#narrow/channel/6-.24.24MONEY.24.24/topic/dollar)",
    );
    assert.equal(
        topic_link_util.get_stream_topic_link_syntax("#**Sweden>t", "swe$$dish"),
        "[#Sweden > swe&#36;&#36;dish](#narrow/channel/1-Sweden/topic/swe.24.24dish)",
    );
    assert.equal(
        topic_link_util.get_fallback_markdown_link("Sweden"),
        "[#Sweden](#narrow/channel/1-Sweden)",
    );

    assert.equal(
        topic_link_util.get_fallback_markdown_link("$$MONEY$$"),
        "[#&#36;&#36;MONEY&#36;&#36;](#narrow/channel/6-.24.24MONEY.24.24)",
    );

    assert.equal(
        topic_link_util.get_stream_topic_link_syntax("#**Sweden>&ab", "&ab"),
        "[#Sweden > &amp;ab](#narrow/channel/1-Sweden/topic/.26ab)",
    );

    // Only for full coverage of the module.
    assert.equal(topic_link_util.escape_invalid_stream_topic_characters("Sweden"), "Sweden");
});
