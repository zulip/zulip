"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const {page_params} = require("./lib/zpage_params.cjs");

const narrow_state = mock_esm("../src/narrow_state");
const stream_topic_history_util = mock_esm("../src/stream_topic_history_util");

const direct_message_group_data = zrequire("direct_message_group_data");

const {Filter} = zrequire("filter");
const stream_data = zrequire("stream_data");
const stream_topic_history = zrequire("stream_topic_history");
const people = zrequire("people");
const search = zrequire("search_suggestion");
const {set_current_user, set_realm} = zrequire("state_data");

const current_user = {};
set_current_user(current_user);
const realm = {};
set_realm(realm);

const me = {
    email: "myself@zulip.com",
    full_name: "Me Myself",
    user_id: 41,
};

const bob = {
    email: "bob@zulip.com",
    full_name: "Bob Roberts",
    user_id: 42,
};

const ted = {
    email: "ted@zulip.com",
    delivery_email: "ted@zulip.com",
    user_id: 101,
    full_name: "Ted Smith",
};

const alice = {
    email: "alice@zulip.com",
    user_id: 102,
    full_name: "Alice Ignore",
};

const jeff = {
    email: "jeff@zulip.com",
    user_id: 103,
    full_name: "Jeff Zoolipson",
};

const example_avatar_url = "http://example.com/example.png";

let _stream_id = 0;
function new_stream_id() {
    _stream_id += 1;
    return _stream_id;
}

function init({override}) {
    override(current_user, "is_admin", true);

    people.init();
    people.add_active_user(bob);
    people.add_active_user(me);
    people.add_active_user(ted);
    people.add_active_user(alice);
    people.add_active_user(jeff);

    people.initialize_current_user(me.user_id);

    stream_topic_history.reset();
    direct_message_group_data.clear_for_testing();
    stream_data.clear_subscriptions();
}

function get_suggestions(query, pill_query = "") {
    return search.get_suggestions(Filter.parse(pill_query), Filter.parse(query));
}

function test(label, f) {
    run_test(label, (helpers) => {
        init(helpers);
        f(helpers);
    });
}

test("basic_get_suggestions", ({override}) => {
    const query = "fred";

    override(narrow_state, "stream_id", noop);

    const suggestions = get_suggestions(query);

    const expected = ["fred"];
    assert.deepEqual(suggestions.strings, expected);
});

test("basic_get_suggestions_for_spectator", () => {
    page_params.is_spectator = true;

    const query = "";
    const suggestions = get_suggestions(query);
    assert.deepEqual(suggestions.strings, [
        "is:resolved",
        "-is:resolved",
        "has:link",
        "has:image",
        "has:attachment",
        "has:reaction",
    ]);
    page_params.is_spectator = false;
});

test("get_suggestions deduplication", () => {
    let query = "has:attachment";
    let suggestions = get_suggestions(query, query);
    let expected = ["has:attachment"];
    assert.deepEqual(suggestions.strings, expected);

    query = "has:attachment has:attachment";
    suggestions = get_suggestions(query);
    expected = ["has:attachment"];
    assert.deepEqual(suggestions.strings, expected);
});

test("get_is_suggestions_for_spectator", () => {
    page_params.is_spectator = true;

    const query = "is:";
    const suggestions = get_suggestions(query);
    // The list of suggestions should only contain "is:resolved" for a spectator
    assert.deepEqual(suggestions.strings, ["is:resolved"]);
    page_params.is_spectator = false;
});

test("subset_suggestions", ({mock_template}) => {
    mock_template("search_description.hbs", true, (_data, html) => html);

    const denmark_id = new_stream_id();
    const sub = {name: "Denmark", stream_id: denmark_id};
    stream_data.add_sub(sub);
    const query = `channel:${denmark_id} topic:Hamlet shakespeare`;

    const suggestions = get_suggestions(query);

    const expected = [
        `channel:${denmark_id} topic:Hamlet shakespeare`,
        `channel:${denmark_id} topic:Hamlet`,
        `channel:${denmark_id}`,
    ];

    assert.deepEqual(suggestions.strings, expected);
});

test("dm_suggestions", ({override, mock_template}) => {
    mock_template("search_description.hbs", true, (_data, html) => html);

    let query = "is:dm";
    let suggestions = get_suggestions(query);
    let expected = [
        "is:dm",
        "dm:alice@zulip.com",
        "dm:bob@zulip.com",
        "dm:jeff@zulip.com",
        "dm:myself@zulip.com",
        "dm:ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = "is:dm al";
    suggestions = get_suggestions(query);
    expected = [
        "is:dm al",
        "is:dm is:alerted",
        "is:dm dm:alice@zulip.com",
        "is:dm sender:alice@zulip.com",
        "is:dm dm-including:alice@zulip.com",
        "is:dm",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // "is:private" was renamed to "is:dm", so
    // we suggest "is:dm" to anyone with "is:private"
    // in their muscle memory.
    query = "is:pr";
    suggestions = get_suggestions(query);
    expected = ["is:dm"];
    assert.deepEqual(suggestions.strings, expected);

    query = "is:private";
    suggestions = get_suggestions(query);
    // Same search suggestions as for "is:dm"
    expected = [
        "is:dm",
        "dm:alice@zulip.com",
        "dm:bob@zulip.com",
        "dm:jeff@zulip.com",
        "dm:myself@zulip.com",
        "dm:ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = "dm:t";
    suggestions = get_suggestions(query);
    expected = ["dm:ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "-dm:t";
    suggestions = get_suggestions(query);
    expected = ["is:dm -dm:ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "dm:ted@zulip.com";
    suggestions = get_suggestions(query);
    expected = ["dm:ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "sender:ted";
    suggestions = get_suggestions(query);
    expected = ["sender:ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "sender:te";
    suggestions = get_suggestions(query);
    expected = ["sender:ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "-sender:te";
    suggestions = get_suggestions(query);
    expected = ["-sender:ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "sender:ted@zulip.com";
    suggestions = get_suggestions(query);
    expected = ["sender:ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "is:unread from:ted";
    suggestions = get_suggestions(query);
    expected = ["is:unread sender:ted@zulip.com", "is:unread"];
    assert.deepEqual(suggestions.strings, expected);

    // Users can enter bizarre queries, and if they do, we want to
    // be conservative with suggestions.
    query = "is:dm near:3";
    suggestions = get_suggestions(query);
    expected = ["is:dm near:3", "is:dm"];
    assert.deepEqual(suggestions.strings, expected);

    query = "dm:ted@zulip.com near:3";
    suggestions = get_suggestions(query);
    expected = ["dm:ted@zulip.com near:3", "dm:ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    // Make sure suggestions still work if preceding tokens
    query = "is:alerted sender:ted@zulip.com";
    suggestions = get_suggestions(query);
    expected = ["is:alerted sender:ted@zulip.com", "is:alerted"];
    assert.deepEqual(suggestions.strings, expected);

    query = "is:starred has:link is:dm al";
    suggestions = get_suggestions(query);
    expected = [
        "is:starred has:link is:dm al",
        "is:starred has:link is:dm is:alerted",
        "is:starred has:link is:dm dm:alice@zulip.com",
        "is:starred has:link is:dm sender:alice@zulip.com",
        "is:starred has:link is:dm dm-including:alice@zulip.com",
        "is:starred has:link is:dm",
        "is:starred has:link",
        "is:starred",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = "from:ted@zulip.com";
    suggestions = get_suggestions(query);
    expected = ["sender:ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    // "pm-with" operator returns search result
    // and "dm" operator as a suggestions
    override(narrow_state, "stream_id", () => undefined);
    query = "pm-with";
    suggestions = get_suggestions(query);
    expected = ["pm-with", "dm:"];
    assert.deepEqual(suggestions.strings, expected);

    query = "pm-with:t";
    suggestions = get_suggestions(query);
    expected = ["dm:ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);
});

test("group_suggestions", ({mock_template}) => {
    mock_template("search_description.hbs", true, (_data, html) => html);

    // If there's an existing completed user pill right before
    // the input string, we suggest a user group as one of the
    // suggestions.
    let pill_query = "dm:bob@zulip.com";
    let query = "alice";
    let suggestions = get_suggestions(query, pill_query);
    let expected = [
        "dm:bob@zulip.com alice",
        "dm:bob@zulip.com,alice@zulip.com",
        "dm:bob@zulip.com sender:alice@zulip.com",
        "dm:bob@zulip.com dm-including:alice@zulip.com",
        "dm:bob@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // Do not suggest "myself@zulip.com" (the name of the current user) for dms
    pill_query = "dm:ted@zulip.com";
    query = "my";
    suggestions = get_suggestions(query, pill_query);
    expected = [
        "dm:ted@zulip.com my",
        "dm:ted@zulip.com sender:myself@zulip.com",
        "dm:ted@zulip.com dm-including:myself@zulip.com",
        "dm:ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // "is:dm" should be properly prepended to each suggestion
    // if the "dm" operator is negated.

    query = "-dm:bob@zulip.co";
    suggestions = get_suggestions(query);
    expected = ["is:dm -dm:bob@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    // If user types "pm-with" operator, show suggestions for
    // group direct messages with the "dm" operator.
    pill_query = "pm-with:bob@zulip.com";
    query = "alice";
    suggestions = get_suggestions(query, pill_query);
    expected = [
        "dm:bob@zulip.com alice",
        "dm:bob@zulip.com,alice@zulip.com",
        "dm:bob@zulip.com sender:alice@zulip.com",
        "dm:bob@zulip.com dm-including:alice@zulip.com",
        "dm:bob@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // Test multiple terms
    pill_query = "is:starred has:link dm:bob@zulip.com";
    query = "Smit";
    suggestions = get_suggestions(query, pill_query);
    expected = [
        "is:starred has:link dm:bob@zulip.com Smit",
        "is:starred has:link dm:bob@zulip.com,ted@zulip.com",
        "is:starred has:link dm:bob@zulip.com sender:ted@zulip.com",
        "is:starred has:link dm:bob@zulip.com dm-including:ted@zulip.com",
        "is:starred has:link dm:bob@zulip.com",
        "is:starred has:link",
        "is:starred",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // Doesn't show dms because it's invalid in combination
    // with a channel. (Random channel id.)
    query = "channel:66 has:link dm:bob@zulip.com,Smit";
    suggestions = get_suggestions(query);
    expected = ["channel:66 has:link", "channel:66"];
    assert.deepEqual(suggestions.strings, expected);

    // Invalid emails don't give suggestions
    query = "has:link dm:invalid@zulip.com,Smit";
    suggestions = get_suggestions(query);
    expected = ["has:link"];
    assert.deepEqual(suggestions.strings, expected);
});

test("empty_query_suggestions", () => {
    const query = "";

    const devel_id = new_stream_id();
    const office_id = new_stream_id();
    stream_data.add_sub({stream_id: devel_id, name: "devel", subscribed: true});
    stream_data.add_sub({stream_id: office_id, name: "office", subscribed: true});

    const suggestions = get_suggestions(query);

    const expected = [
        "channels:public",
        "is:dm",
        "is:starred",
        "is:mentioned",
        "is:followed",
        "is:alerted",
        "is:unread",
        "is:muted",
        "is:resolved",
        "-is:resolved",
        "sender:myself@zulip.com",
        `channel:${devel_id}`,
        `channel:${office_id}`,
        "has:link",
        "has:image",
        "has:attachment",
        "has:reaction",
    ];

    assert.deepEqual(suggestions.strings, expected);

    function describe(q) {
        return suggestions.lookup_table.get(q).description_html;
    }
    assert.equal(describe("is:dm"), "Direct messages");
    assert.equal(describe("is:starred"), "Starred messages");
    assert.equal(describe("is:mentioned"), "Messages that mention you");
    assert.equal(describe("is:alerted"), "Alerted messages");
    assert.equal(describe("is:unread"), "Unread messages");
    assert.equal(describe("is:resolved"), "Resolved topics");
    assert.equal(describe("is:followed"), "Followed topics");
    assert.equal(describe("sender:myself@zulip.com"), "Sent by me");
    assert.equal(describe("has:link"), "Messages with links");
    assert.equal(describe("has:image"), "Messages with images");
    assert.equal(describe("has:attachment"), "Messages with attachments");
});

test("has_suggestions", ({override, mock_template}) => {
    mock_template("search_description.hbs", true, (_data, html) => html);

    // Checks that category wise suggestions are displayed instead of a single
    // default suggestion when suggesting `has` operator.
    let query = "h";
    stream_data.add_sub({stream_id: 44, name: "devel", subscribed: true});
    stream_data.add_sub({stream_id: 77, name: "office", subscribed: true});
    override(narrow_state, "stream_id", noop);

    let suggestions = get_suggestions(query);
    let expected = ["h", "has:link", "has:image", "has:attachment", "has:reaction"];
    assert.deepEqual(suggestions.strings, expected);

    function describe(q) {
        return suggestions.lookup_table.get(q).description_html;
    }

    assert.equal(describe("has:link"), "Messages with links");
    assert.equal(describe("has:image"), "Messages with images");
    assert.equal(describe("has:attachment"), "Messages with attachments");

    query = "-h";
    suggestions = get_suggestions(query);
    expected = ["-h", "-has:link", "-has:image", "-has:attachment", "-has:reaction"];
    assert.deepEqual(suggestions.strings, expected);
    assert.equal(describe("-has:link"), "Exclude messages with links");
    assert.equal(describe("-has:image"), "Exclude messages with images");
    assert.equal(describe("-has:attachment"), "Exclude messages with attachments");

    // operand suggestions follow.

    query = "has:";
    suggestions = get_suggestions(query);
    expected = ["has:link", "has:image", "has:attachment", "has:reaction"];
    assert.deepEqual(suggestions.strings, expected);

    query = "has:im";
    suggestions = get_suggestions(query);
    expected = ["has:image"];
    assert.deepEqual(suggestions.strings, expected);

    query = "-has:im";
    suggestions = get_suggestions(query);
    expected = ["-has:image"];
    assert.deepEqual(suggestions.strings, expected);

    query = "att";
    suggestions = get_suggestions(query);
    expected = ["att", "has:attachment"];
    assert.deepEqual(suggestions.strings, expected);

    // 66 is misc channel id.
    query = "channel:66 is:alerted has:lin";
    suggestions = get_suggestions(query);
    expected = ["channel:66 is:alerted has:link", "channel:66 is:alerted", "channel:66"];
    assert.deepEqual(suggestions.strings, expected);
});

test("check_is_suggestions", ({override, mock_template}) => {
    mock_template("search_description.hbs", true, (_data, html) => html);

    override(narrow_state, "stream_id", noop);

    let query = "i";
    let suggestions = get_suggestions(query);
    let expected = [
        "i",
        "is:dm",
        "is:starred",
        "is:mentioned",
        "is:followed",
        "is:alerted",
        "is:unread",
        "is:muted",
        "is:resolved",
        "dm:alice@zulip.com",
        "sender:alice@zulip.com",
        "dm-including:alice@zulip.com",
        "has:image",
    ];
    assert.deepEqual(suggestions.strings, expected);

    function describe(q) {
        return suggestions.lookup_table.get(q).description_html;
    }

    assert.equal(describe("is:dm"), "Direct messages");
    assert.equal(describe("is:starred"), "Starred messages");
    assert.equal(describe("is:mentioned"), "Messages that mention you");
    assert.equal(describe("is:alerted"), "Alerted messages");
    assert.equal(describe("is:unread"), "Unread messages");
    assert.equal(describe("is:resolved"), "Resolved topics");
    assert.equal(describe("is:followed"), "Followed topics");
    assert.equal(describe("is:muted"), "Muted messages");

    query = "-i";
    suggestions = get_suggestions(query);
    expected = [
        "-i",
        "-is:dm",
        "-is:starred",
        "-is:mentioned",
        "-is:followed",
        "-is:alerted",
        "-is:unread",
        "-is:muted",
        "-is:resolved",
    ];
    assert.deepEqual(suggestions.strings, expected);

    assert.equal(describe("-is:dm"), "Exclude direct messages");
    assert.equal(describe("-is:starred"), "Exclude starred messages");
    assert.equal(describe("-is:mentioned"), "Exclude messages that mention you");
    assert.equal(describe("-is:alerted"), "Exclude alerted messages");
    assert.equal(describe("-is:unread"), "Exclude unread messages");
    assert.equal(describe("-is:resolved"), "Unresolved topics");
    assert.equal(describe("-is:followed"), "Exclude followed topics");
    assert.equal(describe("-is:muted"), "Exclude muted messages");

    // operand suggestions follow.

    query = "is:";
    suggestions = get_suggestions(query);
    expected = [
        "is:dm",
        "is:starred",
        "is:mentioned",
        "is:followed",
        "is:alerted",
        "is:unread",
        "is:muted",
        "is:resolved",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = "is:st";
    suggestions = get_suggestions(query);
    expected = ["is:starred"];
    assert.deepEqual(suggestions.strings, expected);

    query = "-is:st";
    suggestions = get_suggestions(query);
    expected = ["-is:starred"];
    assert.deepEqual(suggestions.strings, expected);

    // Still returns suggestions for "streams:public",
    // but shows html description used for "channels:public"
    query = "st";
    suggestions = get_suggestions(query);
    expected = ["st", "streams:public", "is:starred", "channel:"];
    assert.deepEqual(suggestions.strings, expected);

    query = "channel:66 has:link is:sta";
    suggestions = get_suggestions(query);
    expected = ["channel:66 has:link is:starred", "channel:66 has:link", "channel:66"];
    assert.deepEqual(suggestions.strings, expected);
});

test("sent_by_me_suggestions", ({override, mock_template}) => {
    mock_template("search_description.hbs", true, (_data, html) => html);

    override(narrow_state, "stream_id", noop);

    let query = "";
    let suggestions = get_suggestions(query);
    assert.ok(suggestions.strings.includes("sender:myself@zulip.com"));
    assert.equal(
        suggestions.lookup_table.get("sender:myself@zulip.com").description_html,
        "Sent by me",
    );

    query = "sender";
    suggestions = get_suggestions(query);
    let expected = ["sender", "sender:myself@zulip.com", "sender:"];
    assert.deepEqual(suggestions.strings, expected);

    query = "-sender";
    suggestions = get_suggestions(query);
    expected = ["-sender", "-sender:myself@zulip.com", "-sender:"];
    assert.deepEqual(suggestions.strings, expected);

    query = "from";
    suggestions = get_suggestions(query);
    expected = ["from", "sender:myself@zulip.com", "sender:"];
    assert.deepEqual(suggestions.strings, expected);

    query = "-from";
    suggestions = get_suggestions(query);
    expected = ["-from", "-sender:myself@zulip.com", "-sender:"];
    assert.deepEqual(suggestions.strings, expected);

    query = "sender:bob@zulip.com";
    suggestions = get_suggestions(query);
    expected = ["sender:bob@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "from:bob@zulip.com";
    suggestions = get_suggestions(query);
    expected = ["sender:bob@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "sent";
    suggestions = get_suggestions(query);
    expected = ["sent", "sender:myself@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "-sent";
    suggestions = get_suggestions(query);
    expected = ["-sent", "-sender:myself@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    const denmark_id = new_stream_id();
    const sub = {name: "Denmark", stream_id: denmark_id};
    stream_data.add_sub(sub);
    query = `channel:${denmark_id} topic:Denmark1 sent`;
    suggestions = get_suggestions(query);
    expected = [
        `channel:${denmark_id} topic:Denmark1 sent`,
        `channel:${denmark_id} topic:Denmark1 sender:myself@zulip.com`,
        `channel:${denmark_id} topic:Denmark1`,
        `channel:${denmark_id}`,
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = "is:starred sender:m";
    suggestions = get_suggestions(query);
    expected = ["is:starred sender:myself@zulip.com", "is:starred"];
    assert.deepEqual(suggestions.strings, expected);
});

test("topic_suggestions", ({override, mock_template}) => {
    mock_template("search_description.hbs", true, (_data, html) => html);
    let suggestions;
    let expected;

    override(stream_topic_history_util, "get_server_history", noop);
    const office_id = new_stream_id();
    stream_data.add_sub({stream_id: office_id, name: "office", subscribed: true});
    override(narrow_state, "stream_id", () => office_id);

    const devel_id = new_stream_id();
    stream_data.add_sub({stream_id: devel_id, name: "devel", subscribed: true});
    stream_data.add_sub({stream_id: office_id, name: "office", subscribed: true});

    suggestions = get_suggestions("te");
    expected = ["te", "dm:ted@zulip.com", "sender:ted@zulip.com", "dm-including:ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    stream_topic_history.add_message({
        stream_id: devel_id,
        topic_name: "REXX",
    });

    for (const topic_name of ["team", "ignore", "test"]) {
        stream_topic_history.add_message({
            stream_id: office_id,
            topic_name,
        });
    }

    suggestions = get_suggestions("te");
    expected = [
        "te",
        "dm:ted@zulip.com",
        "sender:ted@zulip.com",
        "dm-including:ted@zulip.com",
        `channel:${office_id} topic:team`,
        `channel:${office_id} topic:test`,
    ];
    assert.deepEqual(suggestions.strings, expected);

    function describe(q) {
        return suggestions.lookup_table.get(q).description_html;
    }
    assert.equal(describe("te"), "Search for te");
    assert.equal(describe(`channel:${office_id} topic:team`), "Messages in #office > team");

    suggestions = get_suggestions(`topic:staplers channel:${office_id}`);
    expected = [`topic:staplers channel:${office_id}`, "topic:staplers"];
    assert.deepEqual(suggestions.strings, expected);

    suggestions = get_suggestions(`channel:${devel_id} topic:`);
    expected = [
        `channel:${devel_id} topic:`,
        `channel:${devel_id} topic:REXX`,
        `channel:${devel_id}`,
    ];
    assert.deepEqual(suggestions.strings, expected);

    suggestions = get_suggestions(`channel:${devel_id} -topic:`);
    expected = [
        `channel:${devel_id} -topic:`,
        `channel:${devel_id} -topic:REXX`,
        `channel:${devel_id}`,
    ];
    assert.deepEqual(suggestions.strings, expected);

    suggestions = get_suggestions("-topic:te");
    expected = [
        "-topic:te",
        `channel:${office_id} -topic:team`,
        `channel:${office_id} -topic:test`,
    ];
    assert.deepEqual(suggestions.strings, expected);

    suggestions = get_suggestions(`is:alerted channel:${devel_id} is:starred topic:`);
    expected = [
        `is:alerted channel:${devel_id} is:starred topic:`,
        `is:alerted channel:${devel_id} is:starred topic:REXX`,
        `is:alerted channel:${devel_id} is:starred`,
        `is:alerted channel:${devel_id}`,
        "is:alerted",
    ];
    assert.deepEqual(suggestions.strings, expected);

    suggestions = get_suggestions(`is:dm channel:${devel_id} topic:`);
    expected = [`is:dm channel:${devel_id} topic:`, `is:dm channel:${devel_id}`, `is:dm`];
    assert.deepEqual(suggestions.strings, expected);

    suggestions = get_suggestions(`topic:REXX channel:${devel_id} topic:`);
    expected = [
        `topic:REXX channel:${devel_id} topic:`,
        `topic:REXX channel:${devel_id}`,
        "topic:REXX",
    ];
    assert.deepEqual(suggestions.strings, expected);
});

test("topic_suggestions (limits)", () => {
    let candidate_topics = [];

    function assert_result(guess, expected_topics) {
        assert.deepEqual(
            search.get_topic_suggestions_from_candidates({candidate_topics, guess}),
            expected_topics,
        );
    }

    assert_result("", []);
    assert_result("zzz", []);

    candidate_topics = ["a", "b", "c"];
    assert_result("", ["a", "b", "c"]);
    assert_result("b", ["b"]);
    assert_result("z", []);

    candidate_topics = [
        "a1",
        "a2",
        "b1",
        "b2",
        "a3",
        "a4",
        "a5",
        "c1",
        "a6",
        "a7",
        "a8",
        "c2",
        "a9",
        "a10",
        "a11",
        "a12",
    ];
    // We max out at 10 topics, so as not to overwhelm the user.
    assert_result("", ["a1", "a2", "b1", "b2", "a3", "a4", "a5", "c1", "a6", "a7"]);
    assert_result("a", ["a1", "a2", "a3", "a4", "a5", "a6", "a7", "a8", "a9", "a10"]);
    assert_result("b", ["b1", "b2"]);
    assert_result("z", []);
});

test("whitespace_glitch", ({override, mock_template}) => {
    mock_template("search_description.hbs", true, (_data, html) => html);
    const office_stream_id = new_stream_id();

    const query = "channel:office "; // note trailing space

    override(stream_topic_history_util, "get_server_history", noop);
    stream_data.add_sub({stream_id: office_stream_id, name: "office", subscribed: true});

    const suggestions = get_suggestions(query);

    const expected = [`channel:${office_stream_id}`];

    assert.deepEqual(suggestions.strings, expected);
});

test("xss_channel_name", () => {
    const stream_id = new_stream_id();
    stream_data.add_sub({stream_id, name: "<em> Italics </em>", subscribed: true});

    const query = "channel:ita";
    const suggestions = get_suggestions(query);
    assert.deepEqual(
        suggestions.lookup_table.get(`channel:${stream_id}`).description_html,
        "Messages in #&lt;em&gt; Italics &lt;/em&gt;",
    );
});

test("channel_completion", ({override}) => {
    const office_stream_id = new_stream_id();
    stream_data.add_sub({stream_id: office_stream_id, name: "office", subscribed: true});
    const dev_help_stream_id = new_stream_id();
    stream_data.add_sub({stream_id: dev_help_stream_id, name: "dev help", subscribed: true});

    override(narrow_state, "stream_id", noop);

    let query = "channel:of";
    let suggestions = get_suggestions(query);
    let expected = [`channel:${office_stream_id}`];
    assert.deepEqual(suggestions.strings, expected);

    query = "-channel:of";
    suggestions = get_suggestions(query);
    expected = [`-channel:${office_stream_id}`];
    assert.deepEqual(suggestions.strings, expected);

    query = "hel";
    suggestions = get_suggestions(query);
    expected = ["hel", `channel:${dev_help_stream_id}`];
    assert.deepEqual(suggestions.strings, expected);
});

test("people_suggestions", ({override, mock_template}) => {
    mock_template("search_description.hbs", true, (_data, html) => html);

    let query = "te";

    override(narrow_state, "stream_id", noop);

    const ted = {
        email: "ted@zulip.com",
        user_id: 201,
        full_name: "Ted Smith",
    };

    const bob = {
        email: "bob@zulip.com",
        user_id: 202,
        full_name: "Bob Térry",
        avatar_url: example_avatar_url,
        is_guest: false,
    };

    const alice = {
        email: "alice@zulip.com",
        user_id: 203,
        full_name: "Alice Ignore",
    };
    people.add_active_user(ted);
    people.add_active_user(bob);
    people.add_active_user(alice);

    // Add an inaccessible user to verify that it is not included in
    // suggestions.
    const inaccessible_user = {
        user_id: 299,
        // All inaccessible users are named as "Unknown user", but we name
        // it differently here so that the name matches the search query.
        full_name: "Test unknown user",
        email: "user299@zulipdev.com",
        is_inaccessible_user: true,
    };
    people._add_user(inaccessible_user);

    let suggestions = get_suggestions(query);

    let expected = [
        "te",
        "dm:bob@zulip.com", // bob térry
        "dm:ted@zulip.com",
        "sender:bob@zulip.com",
        "sender:ted@zulip.com",
        "dm-including:bob@zulip.com",
        "dm-including:ted@zulip.com",
    ];

    assert.deepEqual(suggestions.strings, expected);

    const accessible_user = {
        user_id: 299,
        full_name: "Test unknown user",
        email: "user299@zulipdev.com",
    };
    people.add_active_user(accessible_user);
    suggestions = get_suggestions(query);

    expected = [
        "te",
        "dm:bob@zulip.com",
        "dm:ted@zulip.com",
        "dm:user299@zulipdev.com",
        "sender:bob@zulip.com",
        "sender:ted@zulip.com",
        "sender:user299@zulipdev.com",
        "dm-including:bob@zulip.com",
        "dm-including:ted@zulip.com",
        "dm-including:user299@zulipdev.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    function test_describe(q, description_html_start) {
        assert.ok(
            suggestions.lookup_table.get(q).description_html.startsWith(description_html_start),
        );
    }
    test_describe("dm:ted@zulip.com", "Direct messages with");
    test_describe("sender:ted@zulip.com", "Sent by");
    test_describe("dm-including:ted@zulip.com", "Direct messages including");

    let expectedString = "Ted Smith";

    function test_full_name(q, full_name_html) {
        return suggestions.lookup_table.get(q).description_html.includes(full_name_html);
    }
    test_full_name("sender:ted@zulip.com", expectedString);
    test_full_name("dm:ted@zulip.com", expectedString);
    test_full_name("dm-including:ted@zulip.com", expectedString);

    expectedString = example_avatar_url;

    function test_avatar_url(q, avatar_url) {
        return suggestions.lookup_table.get(q).description_html.includes(avatar_url);
    }
    test_avatar_url("dm:bob@zulip.com", expectedString);
    test_avatar_url("sender:bob@zulip.com", expectedString);
    test_avatar_url("dm-including:bob@zulip.com", expectedString);

    suggestions = get_suggestions("Ted "); // note space

    expected = ["Ted", "dm:ted@zulip.com", "sender:ted@zulip.com", "dm-including:ted@zulip.com"];

    assert.deepEqual(suggestions.strings, expected);

    query = "sender:ted sm";
    expected = ["sender:ted@zulip.com"];
    suggestions = get_suggestions(query);
    assert.deepEqual(suggestions.strings, expected);

    query = "sender:ted@zulip.com new";
    expected = ["sender:ted@zulip.com new", "sender:ted@zulip.com"];
    suggestions = get_suggestions(query);
    assert.deepEqual(suggestions.strings, expected);

    query = "sender:ted@tulip.com new";
    expected = []; // Invalid email
    suggestions = get_suggestions(query);
    assert.deepEqual(suggestions.strings, expected);
});

test("operator_suggestions", ({override, mock_template}) => {
    mock_template("search_description.hbs", true, (_data, html) => html);

    override(narrow_state, "stream_id", () => undefined);

    // Completed operator should return nothing
    let query = "channel:";
    let suggestions = get_suggestions(query);
    let expected = [];
    assert.deepEqual(suggestions.strings, expected);

    query = "ch";
    suggestions = get_suggestions(query);
    expected = ["ch", "channels:public", "channel:"];
    assert.deepEqual(suggestions.strings, expected);

    query = "-s";
    suggestions = get_suggestions(query);
    expected = ["-s", "-sender:myself@zulip.com", "-sender:", "-channel:"];
    assert.deepEqual(suggestions.strings, expected);

    // 66 is a misc channel id.
    query = "channel:66 is:alerted -f";
    suggestions = get_suggestions(query);
    expected = [
        "channel:66 is:alerted -f",
        "channel:66 is:alerted -sender:myself@zulip.com",
        "channel:66 is:alerted -sender:",
        "channel:66 is:alerted",
        "channel:66",
    ];
    assert.deepEqual(suggestions.strings, expected);
});

test("queries_with_spaces", () => {
    const office_id = new_stream_id();
    stream_data.add_sub({stream_id: office_id, name: "office", subscribed: true});
    const dev_help_id = new_stream_id();
    stream_data.add_sub({stream_id: dev_help_id, name: "dev help", subscribed: true});

    // test allowing spaces with quotes surrounding operand
    let query = 'channel:"dev he"';
    let suggestions = get_suggestions(query);
    let expected = [`channel:${dev_help_id}`];
    assert.deepEqual(suggestions.strings, expected);

    // test mismatched quote
    query = 'channel:"dev h';
    suggestions = get_suggestions(query);
    expected = [`channel:${dev_help_id}`];
    assert.deepEqual(suggestions.strings, expected);
});
