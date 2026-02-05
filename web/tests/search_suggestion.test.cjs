"use strict";

const assert = require("node:assert/strict");

const {make_realm} = require("./lib/example_realm.cjs");
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
const realm = make_realm();
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

    // Add users to `valid_user_ids`.
    const source = "server_events";
    people.init();
    people.add_active_user(bob, source);
    people.add_active_user(me, source);
    people.add_active_user(ted, source);
    people.add_active_user(alice, source);
    people.add_active_user(jeff, source);

    people.initialize_current_user(me.user_id);

    stream_topic_history.reset();
    direct_message_group_data.clear_for_testing();
    stream_data.clear_subscriptions();
}

function get_suggestions(query, pill_query = "") {
    return search.get_suggestions(
        Filter.parse(pill_query).map((suggestion) => Filter.convert_suggestion_to_term(suggestion)),
        Filter.parse(query),
    );
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
    assert.deepEqual(suggestions, expected);
});

test("basic_get_suggestions_for_spectator", () => {
    page_params.is_spectator = true;
    const web_public_id = new_stream_id();
    const sub = {name: "Web public", stream_id: web_public_id, is_web_public: true};
    stream_data.add_sub_for_tests(sub);

    let query = "";
    let suggestions = get_suggestions(query);
    assert.deepEqual(suggestions, [
        "channels:",
        "channel:",
        "is:resolved",
        "-is:resolved",
        "has:link",
        "has:image",
        "has:attachment",
        "has:reaction",
    ]);

    stream_data.delete_sub(sub.stream_id);
    query = "channels:";
    suggestions = get_suggestions(query);
    assert.deepEqual(suggestions, []);
    page_params.is_spectator = false;
});

test("get_suggestions deduplication", () => {
    let query = "has:attachment";
    let suggestions = get_suggestions(query, query);
    let expected = ["has:attachment"];
    assert.deepEqual(suggestions, expected);

    query = "has:attachment has:attachment";
    suggestions = get_suggestions(query);
    expected = ["has:attachment"];
    assert.deepEqual(suggestions, expected);
});

test("get_is_suggestions_for_spectator", () => {
    page_params.is_spectator = true;

    const query = "is:";
    const suggestions = get_suggestions(query);
    // The list of suggestions should only contain "is:resolved" for a spectator
    assert.deepEqual(suggestions, ["is:resolved"]);
    page_params.is_spectator = false;
});

test("dm_suggestions", ({override}) => {
    let query = "is:dm";
    let suggestions = get_suggestions(query);
    let expected = [
        "is:dm",
        `dm:${alice.user_id}`,
        `dm:${bob.user_id}`,
        `dm:${jeff.user_id}`,
        `dm:${me.user_id}`,
        `dm:${ted.user_id}`,
    ];
    assert.deepEqual(suggestions, expected);

    query = "is:dm al";
    suggestions = get_suggestions(query);
    expected = [
        "is:dm al",
        "is:dm is:alerted",
        `is:dm dm:${alice.user_id}`,
        `is:dm sender:${alice.user_id}`,
        `is:dm dm-including:${alice.user_id}`,
    ];
    assert.deepEqual(suggestions, expected);

    // "is:private" was renamed to "is:dm", so
    // we suggest "is:dm" to anyone with "is:private"
    // in their muscle memory.
    query = "is:pr";
    suggestions = get_suggestions(query);
    expected = ["is:dm"];
    assert.deepEqual(suggestions, expected);

    query = "is:private";
    suggestions = get_suggestions(query);
    // Same search suggestions as for "is:dm"
    expected = [
        "is:dm",
        `dm:${alice.user_id}`,
        `dm:${bob.user_id}`,
        `dm:${jeff.user_id}`,
        `dm:${me.user_id}`,
        `dm:${ted.user_id}`,
    ];
    assert.deepEqual(suggestions, expected);

    query = "dm:t";
    suggestions = get_suggestions(query);
    expected = [`dm:${ted.user_id}`];
    assert.deepEqual(suggestions, expected);

    query = "-dm:t";
    suggestions = get_suggestions(query);
    expected = [`is:dm -dm:${ted.user_id}`];
    assert.deepEqual(suggestions, expected);

    query = `dm:${ted.user_id}`;
    suggestions = get_suggestions(query);
    expected = [`dm:${ted.user_id}`];
    assert.deepEqual(suggestions, expected);

    query = "sender:ted";
    suggestions = get_suggestions(query);
    expected = [`sender:${ted.user_id}`];
    assert.deepEqual(suggestions, expected);

    query = "sender:te";
    suggestions = get_suggestions(query);
    expected = [`sender:${ted.user_id}`];
    assert.deepEqual(suggestions, expected);

    query = "-sender:te";
    suggestions = get_suggestions(query);
    expected = [`-sender:${ted.user_id}`];
    assert.deepEqual(suggestions, expected);

    query = `sender:${ted.user_id}`;
    suggestions = get_suggestions(query);
    expected = [`sender:${ted.user_id}`];
    assert.deepEqual(suggestions, expected);

    query = "is:unread from:ted";
    suggestions = get_suggestions(query);
    expected = [`is:unread sender:${ted.user_id}`];
    assert.deepEqual(suggestions, expected);

    // Users can enter bizarre queries, and if they do, we want to
    // be conservative with suggestions.
    query = "is:dm near:3";
    suggestions = get_suggestions(query);
    expected = ["is:dm near:3"];
    assert.deepEqual(suggestions, expected);

    query = `dm:${ted.user_id} near:3`;
    suggestions = get_suggestions(query);
    expected = [`dm:${ted.user_id} near:3`];
    assert.deepEqual(suggestions, expected);

    // Make sure suggestions still work if preceding tokens
    query = `is:alerted sender:${ted.user_id}`;
    suggestions = get_suggestions(query);
    expected = [`is:alerted sender:${ted.user_id}`];
    assert.deepEqual(suggestions, expected);

    query = "is:starred has:link is:dm al";
    suggestions = get_suggestions(query);
    expected = [
        "is:starred has:link is:dm al",
        "is:starred has:link is:dm is:alerted",
        `is:starred has:link is:dm dm:${alice.user_id}`,
        `is:starred has:link is:dm sender:${alice.user_id}`,
        `is:starred has:link is:dm dm-including:${alice.user_id}`,
    ];
    assert.deepEqual(suggestions, expected);

    query = `from:${ted.user_id}`;
    suggestions = get_suggestions(query);
    expected = [`sender:${ted.user_id}`];
    assert.deepEqual(suggestions, expected);

    // "pm-with" operator returns search result
    // and "dm" operator as a suggestions
    override(narrow_state, "stream_id", () => undefined);
    query = "pm-with";
    suggestions = get_suggestions(query);
    expected = ["pm-with", "dm:"];
    assert.deepEqual(suggestions, expected);

    query = "pm-with:t";
    suggestions = get_suggestions(query);
    expected = [`dm:${ted.user_id}`];
    assert.deepEqual(suggestions, expected);
});

test("group_suggestions", () => {
    // If there's an existing completed user pill right before
    // the input string, we suggest a user group as one of the
    // suggestions.
    let pill_query = `dm:${bob.user_id}`;
    let query = "alice";
    let suggestions = get_suggestions(query, pill_query);
    let expected = [
        `dm:${bob.user_id} alice`,
        `dm:${bob.user_id},${alice.user_id}`,
        `dm:${bob.user_id} sender:${alice.user_id}`,
        `dm:${bob.user_id} dm-including:${alice.user_id}`,
    ];
    assert.deepEqual(suggestions, expected);

    // Do not suggest "myself@zulip.com" (the name of the current user) for dms
    pill_query = `dm:${ted.user_id}`;
    query = "my";
    suggestions = get_suggestions(query, pill_query);
    expected = [
        `dm:${ted.user_id} my`,
        `dm:${ted.user_id} sender:${me.user_id}`,
        `dm:${ted.user_id} dm-including:${me.user_id}`,
    ];
    assert.deepEqual(suggestions, expected);

    // "is:dm" should be properly prepended to each suggestion
    // if the "dm" operator is negated.

    query = "-dm:bob@zulip.co";
    suggestions = get_suggestions(query);
    expected = [`is:dm -dm:${bob.user_id}`];
    assert.deepEqual(suggestions, expected);

    // If user types "pm-with" operator, show suggestions for
    // group direct messages with the "dm" operator.
    pill_query = `pm-with:${bob.user_id}`;
    query = "alice";
    suggestions = get_suggestions(query, pill_query);
    expected = [
        `dm:${bob.user_id} alice`,
        `dm:${bob.user_id},${alice.user_id}`,
        `dm:${bob.user_id} sender:${alice.user_id}`,
        `dm:${bob.user_id} dm-including:${alice.user_id}`,
    ];
    assert.deepEqual(suggestions, expected);

    // Test multiple terms
    pill_query = `is:starred has:link dm:${bob.user_id}`;
    query = "Smit";
    suggestions = get_suggestions(query, pill_query);
    expected = [
        `is:starred has:link dm:${bob.user_id} Smit`,
        `is:starred has:link dm:${bob.user_id},${ted.user_id}`,
        `is:starred has:link dm:${bob.user_id} sender:${ted.user_id}`,
        `is:starred has:link dm:${bob.user_id} dm-including:${ted.user_id}`,
    ];
    assert.deepEqual(suggestions, expected);

    // Doesn't show dms because it's invalid in combination
    // with a channel. (Random channel id.)
    stream_data.add_sub_for_tests({stream_id: 66, name: "misc", subscribed: true});
    query = `channel:66 has:link dm:${bob.user_id},Smit`;
    suggestions = get_suggestions(query);
    expected = [];
    assert.deepEqual(suggestions, expected);

    // Invalid emails don't give suggestions
    query = "dm:invalid@zulip.com,Smit";
    suggestions = get_suggestions(query);
    expected = [];
    assert.deepEqual(suggestions, expected);
});

test("empty_query_suggestions", () => {
    const query = "";

    const devel_id = new_stream_id();
    const office_id = new_stream_id();
    stream_data.add_sub_for_tests({
        stream_id: devel_id,
        name: "devel",
        subscribed: true,
        is_web_public: true,
    });
    stream_data.add_sub_for_tests({stream_id: office_id, name: "office", subscribed: true});

    const suggestions = get_suggestions(query);

    const expected = [
        "channels:",
        "channel:",
        "is:dm",
        "is:starred",
        "is:mentioned",
        "is:followed",
        "is:alerted",
        "is:unread",
        "is:muted",
        "is:resolved",
        "-is:resolved",
        `sender:${me.user_id}`,
        `channel:${devel_id}`,
        `channel:${office_id}`,
        "has:link",
        "has:image",
        "has:attachment",
        "has:reaction",
    ];

    assert.deepEqual(suggestions, expected);
});

test("has_suggestions", ({override}) => {
    // Checks that category wise suggestions are displayed instead of a single
    // default suggestion when suggesting `has` operator.
    let query = "h";
    stream_data.add_sub_for_tests({stream_id: 44, name: "devel", subscribed: true});
    stream_data.add_sub_for_tests({stream_id: 77, name: "office", subscribed: true});
    override(narrow_state, "stream_id", noop);

    let suggestions = get_suggestions(query);
    let expected = ["h", "has:link", "has:image", "has:attachment", "has:reaction"];
    assert.deepEqual(suggestions, expected);

    query = "-h";
    suggestions = get_suggestions(query);
    expected = ["-h", "-has:link", "-has:image", "-has:attachment", "-has:reaction"];
    assert.deepEqual(suggestions, expected);

    // operand suggestions follow.

    query = "has:";
    suggestions = get_suggestions(query);
    expected = ["has:link", "has:image", "has:attachment", "has:reaction"];
    assert.deepEqual(suggestions, expected);

    query = "has:im";
    suggestions = get_suggestions(query);
    expected = ["has:image"];
    assert.deepEqual(suggestions, expected);

    query = "-has:im";
    suggestions = get_suggestions(query);
    expected = ["-has:image"];
    assert.deepEqual(suggestions, expected);

    query = "att";
    suggestions = get_suggestions(query);
    expected = ["att", "has:attachment"];
    assert.deepEqual(suggestions, expected);

    stream_data.add_sub_for_tests({stream_id: 66, name: "misc", subscribed: true});
    query = "channel:66 is:alerted has:lin";
    suggestions = get_suggestions(query);
    expected = ["channel:66 is:alerted has:link"];
    assert.deepEqual(suggestions, expected);
});

test("check_is_suggestions", ({override}) => {
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
        `dm:${alice.user_id}`,
        `sender:${alice.user_id}`,
        `dm-including:${alice.user_id}`,
        "has:image",
    ];
    assert.deepEqual(suggestions, expected);

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
    assert.deepEqual(suggestions, expected);

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
    assert.deepEqual(suggestions, expected);

    query = "is:st";
    suggestions = get_suggestions(query);
    expected = ["is:starred"];
    assert.deepEqual(suggestions, expected);

    query = "-is:st";
    suggestions = get_suggestions(query);
    expected = ["-is:starred"];
    assert.deepEqual(suggestions, expected);

    // Still returns suggestions for "streams:public",
    // but shows html description used for "channels:public"
    query = "st";
    suggestions = get_suggestions(query);
    expected = ["st", "channels:", "channel:", "is:starred"];
    assert.deepEqual(suggestions, expected);

    stream_data.add_sub_for_tests({stream_id: 66, name: "misc", subscribed: true});
    query = "channel:66 has:link is:sta";
    suggestions = get_suggestions(query);
    expected = ["channel:66 has:link is:starred"];
    assert.deepEqual(suggestions, expected);
});

test("sent_by_me_suggestions", ({override}) => {
    override(narrow_state, "stream_id", noop);

    let query = "";
    let suggestions = get_suggestions(query);
    assert.ok(suggestions.includes(`sender:${me.user_id}`));

    query = "sender";
    suggestions = get_suggestions(query);
    let expected = ["sender", "sender:", `sender:${me.user_id}`];
    assert.deepEqual(suggestions, expected);

    query = "-sender";
    suggestions = get_suggestions(query);
    expected = ["-sender", "-sender:", `-sender:${me.user_id}`];
    assert.deepEqual(suggestions, expected);

    query = "from";
    suggestions = get_suggestions(query);
    expected = ["from", "sender:", `sender:${me.user_id}`];
    assert.deepEqual(suggestions, expected);

    query = "-from";
    suggestions = get_suggestions(query);
    expected = ["-from", "-sender:", `-sender:${me.user_id}`];
    assert.deepEqual(suggestions, expected);

    query = `sender:${bob.user_id}`;
    suggestions = get_suggestions(query);
    expected = [`sender:${bob.user_id}`];
    assert.deepEqual(suggestions, expected);

    query = `from:${bob.user_id}`;
    suggestions = get_suggestions(query);
    expected = [`sender:${bob.user_id}`];
    assert.deepEqual(suggestions, expected);

    query = "sent";
    suggestions = get_suggestions(query);
    expected = ["sent", `sender:${me.user_id}`];
    assert.deepEqual(suggestions, expected);

    query = "-sent";
    suggestions = get_suggestions(query);
    expected = ["-sent", `-sender:${me.user_id}`];
    assert.deepEqual(suggestions, expected);

    const denmark_id = new_stream_id();
    const sub = {name: "Denmark", stream_id: denmark_id};
    stream_data.add_sub_for_tests(sub);
    query = `channel:${denmark_id} topic:Denmark1 sent`;
    suggestions = get_suggestions(query);
    expected = [
        `channel:${denmark_id} topic:Denmark1 sent`,
        `channel:${denmark_id} topic:Denmark1 sender:${me.user_id}`,
    ];
    assert.deepEqual(suggestions, expected);

    query = "is:starred sender:m";
    suggestions = get_suggestions(query);
    expected = [`is:starred sender:${me.user_id}`];
    assert.deepEqual(suggestions, expected);
});

test("topic_suggestions", ({override, override_rewire}) => {
    let suggestions;
    let expected;

    override(stream_topic_history_util, "get_server_history", noop);
    const office_id = new_stream_id();
    stream_data.add_sub_for_tests({stream_id: office_id, name: "office", subscribed: true});
    override(narrow_state, "stream_id", () => office_id);

    const devel_id = new_stream_id();
    stream_data.add_sub_for_tests({stream_id: devel_id, name: "devel", subscribed: true});
    stream_data.add_sub_for_tests({stream_id: office_id, name: "office", subscribed: true});

    suggestions = get_suggestions("te");
    expected = ["te", `dm:${ted.user_id}`, `sender:${ted.user_id}`, `dm-including:${ted.user_id}`];
    assert.deepEqual(suggestions, expected);

    stream_topic_history.add_message({
        stream_id: devel_id,
        topic_name: "REXX",
    });

    for (const topic_name of ["team", "ignore", "✔ ice cream", "✔ team work", "test"]) {
        stream_topic_history.add_message({
            stream_id: office_id,
            topic_name,
        });
    }

    suggestions = get_suggestions("te");
    expected = [
        "te",
        `dm:${ted.user_id}`,
        `sender:${ted.user_id}`,
        `dm-including:${ted.user_id}`,
        `channel:${office_id} topic:team`,
        `channel:${office_id} topic:✔+team+work`,
        `channel:${office_id} topic:test`,
    ];
    assert.deepEqual(suggestions, expected);

    suggestions = get_suggestions(`topic:staplers channel:${office_id}`);
    expected = [`topic:staplers channel:${office_id}`];
    assert.deepEqual(suggestions, expected);

    suggestions = get_suggestions(`channel:${devel_id} topic:`);
    expected = [`channel:${devel_id} topic:`, `channel:${devel_id} topic:REXX`];
    assert.deepEqual(suggestions, expected);

    suggestions = get_suggestions(`channel:${devel_id} -topic:`);
    expected = [`channel:${devel_id} -topic:`, `channel:${devel_id} -topic:REXX`];
    assert.deepEqual(suggestions, expected);

    suggestions = get_suggestions("-topic:te");
    expected = [
        "-topic:te",
        `channel:${office_id} -topic:team`,
        `channel:${office_id} -topic:✔+team+work`,
        `channel:${office_id} -topic:test`,
    ];
    assert.deepEqual(suggestions, expected);

    suggestions = get_suggestions("topic:", `-channel:${office_id}`);
    expected = [
        `-channel:${office_id} topic:`,
        `-channel:${office_id} channel:${devel_id} topic:REXX`,
    ];
    assert.deepEqual(suggestions, expected);

    suggestions = get_suggestions("topic:", `-channel:${office_id} -channel:${devel_id}`);
    expected = [`-channel:${office_id} -channel:${devel_id} topic:`];
    assert.deepEqual(suggestions, expected);

    suggestions = get_suggestions(`is:alerted channel:${devel_id} is:starred topic:`);
    expected = [
        `is:alerted channel:${devel_id} is:starred topic:`,
        `is:alerted channel:${devel_id} is:starred topic:REXX`,
    ];
    assert.deepEqual(suggestions, expected);

    suggestions = get_suggestions(`is:dm channel:${devel_id} topic:`);
    expected = [`is:dm channel:${devel_id} topic:`];
    assert.deepEqual(suggestions, expected);

    suggestions = get_suggestions(`topic:REXX channel:${devel_id} topic:`);
    expected = [`topic:REXX channel:${devel_id} topic:`];
    assert.deepEqual(suggestions, expected);

    suggestions = get_suggestions("topic:");
    expected = [
        "topic:",
        "channel:5 topic:✔+ice+cream",
        "channel:5 topic:ignore",
        `channel:5 topic:team`,
        "channel:5 topic:✔+team+work",
        `channel:5 topic:test`,
        "channel:6 topic:REXX",
    ];
    assert.deepEqual(suggestions, expected);
    override(narrow_state, "stream_id", () => "");

    for (const topic_name of ["a", "b", "c", "trap", "talks", "tower"]) {
        stream_topic_history.add_message({
            stream_id: devel_id,
            topic_name,
        });
    }

    override_rewire(stream_data, "set_max_channel_width_css_variable", noop);
    stream_data.subscribe_myself(stream_data.get_sub("devel"));
    stream_data.subscribe_myself(stream_data.get_sub("office"));
    suggestions = get_suggestions("topic:");
    expected = [
        "topic:",
        "channel:6 topic:a",
        "channel:6 topic:b",
        "channel:6 topic:c",
        "channel:5 topic:✔+ice+cream",
        "channel:5 topic:ignore",
        "channel:6 topic:REXX",
        "channel:5 topic:team",
        "channel:5 topic:✔+team+work",
        "channel:5 topic:test",
        "channel:6 topic:trap",
    ];
    assert.deepEqual(suggestions, expected);

    suggestions = get_suggestions("topic:t");
    expected = [
        "topic:t",
        "channel:5 topic:team",
        "channel:5 topic:✔+team+work",
        "channel:5 topic:test",
        "channel:6 topic:trap",
        "channel:6 topic:talks",
        "channel:6 topic:tower",
    ];
    assert.deepEqual(suggestions, expected);

    // Prioritize topics from currently narrowed channel
    override(narrow_state, "stream_id", () => devel_id);
    suggestions = get_suggestions("topic:t");
    expected = [
        "topic:t",
        "channel:6 topic:trap",
        "channel:6 topic:talks",
        "channel:6 topic:tower",
        "channel:5 topic:team",
        "channel:5 topic:✔+team+work",
        "channel:5 topic:test",
    ];
    assert.deepEqual(suggestions, expected);

    override(narrow_state, "stream_id", () => office_id);
    suggestions = get_suggestions("topic:t");
    expected = [
        "topic:t",
        "channel:5 topic:team",
        "channel:5 topic:✔+team+work",
        "channel:5 topic:test",
        "channel:6 topic:trap",
        "channel:6 topic:talks",
        "channel:6 topic:tower",
    ];
    assert.deepEqual(suggestions, expected);
});

test("topic_suggestions (limits)", () => {
    let candidate_topic_entries = [];

    function wrap(topics) {
        return topics.map((t) => ({channel_id: "1", topic: t}));
    }

    function assert_result(guess, expected_topic_strings) {
        assert.deepEqual(
            search.get_topic_suggestions_from_candidates({
                candidate_topic_entries,
                guess,
            }),
            wrap(expected_topic_strings),
        );
    }

    assert_result("", []);
    assert_result("zzz", []);

    candidate_topic_entries = wrap(["a", "b", "c"]);
    assert_result("", ["a", "b", "c"]);
    assert_result("b", ["b"]);
    assert_result("z", []);

    candidate_topic_entries = wrap([
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
    ]);

    // We max out at 10 topics, so as not to overwhelm the user.
    assert_result("", ["a1", "a2", "b1", "b2", "a3", "a4", "a5", "c1", "a6", "a7"]);
    assert_result("a", ["a1", "a2", "a3", "a4", "a5", "a6", "a7", "a8", "a9", "a10"]);
    assert_result("b", ["b1", "b2"]);
    assert_result("z", []);
});

test("whitespace_glitch", ({override}) => {
    const office_stream_id = new_stream_id();

    const query = "channel:office "; // note trailing space

    override(stream_topic_history_util, "get_server_history", noop);
    stream_data.add_sub_for_tests({stream_id: office_stream_id, name: "office", subscribed: true});

    const suggestions = get_suggestions(query);

    const expected = [`channel:${office_stream_id}`];

    assert.deepEqual(suggestions, expected);
});

test("channel_completion", ({override}) => {
    const office_stream_id = new_stream_id();
    stream_data.add_sub_for_tests({stream_id: office_stream_id, name: "office", subscribed: true});
    const dev_help_stream_id = new_stream_id();
    stream_data.add_sub_for_tests({
        stream_id: dev_help_stream_id,
        name: "dev help",
        subscribed: true,
    });

    override(narrow_state, "stream_id", noop);

    let query = "channel:of";
    let suggestions = get_suggestions(query);
    let expected = [`channel:${office_stream_id}`];
    assert.deepEqual(suggestions, expected);

    query = "-channel:of";
    suggestions = get_suggestions(query);
    expected = [`-channel:${office_stream_id}`];
    assert.deepEqual(suggestions, expected);

    query = "hel";
    suggestions = get_suggestions(query);
    expected = ["hel", `channel:${dev_help_stream_id}`];
    assert.deepEqual(suggestions, expected);
});

test("people_suggestions", ({override}) => {
    let query = "te";

    override(narrow_state, "stream_id", noop);

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
    people.add_active_user(ted, "server_events");
    people.add_active_user(bob, "server_events");
    people.add_active_user(alice, "server_events");

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
        `dm:${bob.user_id}`, // bob térry
        `dm:${ted.user_id}`,
        `sender:${bob.user_id}`,
        `sender:${ted.user_id}`,
        `dm-including:${bob.user_id}`,
        `dm-including:${ted.user_id}`,
    ];

    assert.deepEqual(suggestions, expected);

    const accessible_user = {
        user_id: 299,
        full_name: "Test unknown user",
        email: "user299@zulipdev.com",
    };
    people.add_active_user(accessible_user, "server_events");
    suggestions = get_suggestions(query);

    expected = [
        "te",
        `dm:${bob.user_id}`,
        `dm:${ted.user_id}`,
        `dm:${inaccessible_user.user_id}`,
        `sender:${bob.user_id}`,
        `sender:${ted.user_id}`,
        `sender:${inaccessible_user.user_id}`,
        `dm-including:${bob.user_id}`,
        `dm-including:${ted.user_id}`,
        `dm-including:${inaccessible_user.user_id}`,
    ];
    assert.deepEqual(suggestions, expected);

    suggestions = get_suggestions("Ted "); // note space

    expected = ["Ted", `dm:${ted.user_id}`, `sender:${ted.user_id}`, `dm-including:${ted.user_id}`];

    assert.deepEqual(suggestions, expected);

    query = "sender:ted sm";
    expected = [`sender:${ted.user_id}`];
    suggestions = get_suggestions(query);
    assert.deepEqual(suggestions, expected);

    query = "sender:ted@zulip.com new";
    expected = ["new"];
    suggestions = get_suggestions(query);
    assert.deepEqual(suggestions, expected);

    query = "sender:ted@tulip.com new";
    expected = []; // Invalid email
    suggestions = get_suggestions(query);
    assert.deepEqual(suggestions, expected);
});

test("operator_suggestions", ({override}) => {
    override(stream_topic_history_util, "get_server_history", noop);
    override(narrow_state, "stream_id", () => undefined);

    // Completed operator should return nothing
    let query = "channel:";
    let suggestions = get_suggestions(query);
    let expected = [];
    assert.deepEqual(suggestions, expected);

    query = "ch";
    suggestions = get_suggestions(query);
    expected = ["ch", "channels:", "channel:"];
    assert.deepEqual(suggestions, expected);

    query = "-s";
    suggestions = get_suggestions(query);
    expected = ["-s", "-sender:", "-channels:", "-channel:", `-sender:${me.user_id}`];
    assert.deepEqual(suggestions, expected);

    stream_data.add_sub_for_tests({stream_id: 66, name: "misc", subscribed: true});
    query = "channel:66 is:alerted -f";
    suggestions = get_suggestions(query);
    expected = [
        "channel:66 is:alerted -f",
        "channel:66 is:alerted -sender:",
        `channel:66 is:alerted -sender:${me.user_id}`,
    ];
    assert.deepEqual(suggestions, expected);
});

test("queries_with_spaces", () => {
    const office_id = new_stream_id();
    stream_data.add_sub_for_tests({stream_id: office_id, name: "office", subscribed: true});
    const dev_help_id = new_stream_id();
    stream_data.add_sub_for_tests({stream_id: dev_help_id, name: "dev help", subscribed: true});

    // test allowing spaces with quotes surrounding operand
    let query = 'channel:"dev he"';
    let suggestions = get_suggestions(query);
    let expected = [`channel:${dev_help_id}`];
    assert.deepEqual(suggestions, expected);

    // test mismatched quote
    query = 'channel:"dev h';
    suggestions = get_suggestions(query);
    expected = [`channel:${dev_help_id}`];
    assert.deepEqual(suggestions, expected);
});
