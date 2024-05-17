"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("./lib/namespace");
const {run_test, noop} = require("./lib/test");
const {current_user, page_params, realm} = require("./lib/zpage_params");

const narrow_state = mock_esm("../src/narrow_state");
const stream_topic_history_util = mock_esm("../src/stream_topic_history_util");

const huddle_data = zrequire("huddle_data");

const stream_data = zrequire("stream_data");
const stream_topic_history = zrequire("stream_topic_history");
const people = zrequire("people");
const search = zrequire("search_suggestion");

search.__Rewire__("max_num_of_search_results", 15);

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

function init() {
    current_user.is_admin = true;

    people.init();
    people.add_active_user(bob);
    people.add_active_user(me);
    people.add_active_user(ted);
    people.add_active_user(alice);
    people.add_active_user(jeff);

    people.initialize_current_user(me.user_id);

    stream_topic_history.reset();
    huddle_data.clear_for_testing();
    stream_data.clear_subscriptions();
}

function get_suggestions(query) {
    return search.get_suggestions(query);
}

function test(label, f) {
    run_test(label, (helpers) => {
        init();
        f(helpers);
    });
}

test("basic_get_suggestions", ({override}) => {
    const query = "fred";

    override(narrow_state, "stream_name", () => "office");

    const suggestions = get_suggestions(query);

    const expected = ["fred"];
    assert.deepEqual(suggestions.strings, expected);
});

test("basic_get_suggestions_for_spectator", () => {
    page_params.is_spectator = true;

    const query = "";
    const suggestions = get_suggestions(query);
    assert.deepEqual(suggestions.strings, ["has:link", "has:image", "has:attachment"]);
    page_params.is_spectator = false;
});

test("subset_suggestions", ({mock_template}) => {
    mock_template("search_description.hbs", true, (_data, html) => html);

    const query = "channel:Denmark topic:Hamlet shakespeare";

    const suggestions = get_suggestions(query);

    const expected = [
        "channel:Denmark topic:Hamlet shakespeare",
        "channel:Denmark topic:Hamlet",
        "channel:Denmark",
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
        "is:dm sender:alice@zulip.com",
        "is:dm dm:alice@zulip.com",
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
    expected = ["is:dm"];
    assert.deepEqual(suggestions.strings, expected);

    query = "dm:t";
    suggestions = get_suggestions(query);
    expected = ["dm:t", "dm:ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "-dm:t";
    suggestions = get_suggestions(query);
    expected = ["-dm:t", "is:dm -dm:ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "dm:ted@zulip.com";
    suggestions = get_suggestions(query);
    expected = ["dm:ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "sender:ted";
    suggestions = get_suggestions(query);
    expected = ["sender:ted", "sender:ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "sender:te";
    suggestions = get_suggestions(query);
    expected = ["sender:te", "sender:ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "-sender:te";
    suggestions = get_suggestions(query);
    expected = ["-sender:te", "-sender:ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "sender:ted@zulip.com";
    suggestions = get_suggestions(query);
    expected = ["sender:ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "is:unread from:ted";
    suggestions = get_suggestions(query);
    expected = ["is:unread sender:ted", "is:unread sender:ted@zulip.com", "is:unread"];
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
        "is:starred has:link is:dm sender:alice@zulip.com",
        "is:starred has:link is:dm dm:alice@zulip.com",
        "is:starred has:link is:dm dm-including:alice@zulip.com",
        "is:starred has:link is:dm",
        "is:starred has:link",
        "is:starred",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // Make sure it handles past context correctly
    query = "stream:Denmark dm:";
    suggestions = get_suggestions(query);
    expected = ["channel:Denmark dm:", "channel:Denmark"];
    assert.deepEqual(suggestions.strings, expected);

    query = "from:ted@zulip.com from:";
    suggestions = get_suggestions(query);
    expected = ["sender:ted@zulip.com sender:", "sender:ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    // "pm-with" operator returns search result
    // and "dm" operator as a suggestions
    override(narrow_state, "stream_name", () => undefined);
    query = "pm-with";
    suggestions = get_suggestions(query);
    expected = ["pm-with", "dm:"];
    assert.deepEqual(suggestions.strings, expected);

    query = "pm-with:t";
    suggestions = get_suggestions(query);
    expected = ["dm:t", "dm:ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);
});

test("group_suggestions", ({mock_template}) => {
    mock_template("search_description.hbs", true, (_data, html) => html);

    // Entering a comma in a "dm:" query should immediately
    // generate suggestions for the next person.
    let query = "dm:bob@zulip.com,";
    let suggestions = get_suggestions(query);
    let expected = [
        "dm:bob@zulip.com,",
        "dm:bob@zulip.com,alice@zulip.com",
        "dm:bob@zulip.com,jeff@zulip.com",
        "dm:bob@zulip.com,ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // Only the last part of a comma-separated "dm" query
    // should be used to generate suggestions.
    query = "dm:bob@zulip.com,t";
    suggestions = get_suggestions(query);
    expected = ["dm:bob@zulip.com,t", "dm:bob@zulip.com,ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    // Smit should also generate ted@zulip.com (Ted Smith) as a suggestion.
    query = "dm:bob@zulip.com,Smit";
    suggestions = get_suggestions(query);
    expected = ["dm:bob@zulip.com,Smit", "dm:bob@zulip.com,ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    // Do not suggest "myself@zulip.com" (the name of the current user)
    query = "dm:ted@zulip.com,my";
    suggestions = get_suggestions(query);
    expected = ["dm:ted@zulip.com,my"];
    assert.deepEqual(suggestions.strings, expected);

    // No superfluous suggestions should be generated.
    query = "dm:bob@zulip.com,red";
    suggestions = get_suggestions(query);
    expected = ["dm:bob@zulip.com,red"];
    assert.deepEqual(suggestions.strings, expected);

    // "is:dm" should be properly prepended to each suggestion
    // if the "dm" operator is negated.

    query = "-dm:bob@zulip.com,";
    suggestions = get_suggestions(query);
    expected = [
        "-dm:bob@zulip.com,",
        "is:dm -dm:bob@zulip.com,alice@zulip.com",
        "is:dm -dm:bob@zulip.com,jeff@zulip.com",
        "is:dm -dm:bob@zulip.com,ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = "-dm:bob@zulip.com,t";
    suggestions = get_suggestions(query);
    expected = ["-dm:bob@zulip.com,t", "is:dm -dm:bob@zulip.com,ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "-dm:bob@zulip.com,Smit";
    suggestions = get_suggestions(query);
    expected = ["-dm:bob@zulip.com,Smit", "is:dm -dm:bob@zulip.com,ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "-dm:bob@zulip.com,red";
    suggestions = get_suggestions(query);
    expected = ["-dm:bob@zulip.com,red"];
    assert.deepEqual(suggestions.strings, expected);

    // If user types "pm-with" operator, an email and a comma,
    // show suggestions for group direct messages with the "dm"
    // operator.
    query = "pm-with:bob@zulip.com,";
    suggestions = get_suggestions(query);
    expected = [
        "dm:bob@zulip.com,",
        "dm:bob@zulip.com,alice@zulip.com",
        "dm:bob@zulip.com,jeff@zulip.com",
        "dm:bob@zulip.com,ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // Test multiple terms
    query = "is:starred has:link dm:bob@zulip.com,Smit";
    suggestions = get_suggestions(query);
    expected = [
        "is:starred has:link dm:bob@zulip.com,Smit",
        "is:starred has:link dm:bob@zulip.com,ted@zulip.com",
        "is:starred has:link",
        "is:starred",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = "channel:Denmark has:link dm:bob@zulip.com,Smit";
    suggestions = get_suggestions(query);
    expected = [
        "channel:Denmark has:link dm:bob@zulip.com,Smit",
        "channel:Denmark has:link",
        "channel:Denmark",
    ];
    assert.deepEqual(suggestions.strings, expected);

    function message(user_ids, timestamp) {
        return {
            type: "private",
            display_recipient: user_ids.map((id) => ({
                id,
            })),
            timestamp,
        };
    }

    huddle_data.process_loaded_messages([
        message([bob.user_id, ted.user_id], 99),
        message([bob.user_id, ted.user_id, jeff.user_id], 98),
    ]);

    // Simulate a past group direct message which should now
    // prioritize ted over alice
    query = "dm:bob@zulip.com,";
    suggestions = get_suggestions(query);
    expected = [
        "dm:bob@zulip.com,",
        "dm:bob@zulip.com,ted@zulip.com",
        "dm:bob@zulip.com,alice@zulip.com",
        "dm:bob@zulip.com,jeff@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // bob, ted, and jeff are already an existing group direct message,
    // so prioritize this one
    query = "dm:bob@zulip.com,ted@zulip.com,";
    suggestions = get_suggestions(query);
    expected = [
        "dm:bob@zulip.com,ted@zulip.com,",
        "dm:bob@zulip.com,ted@zulip.com,jeff@zulip.com",
        "dm:bob@zulip.com,ted@zulip.com,alice@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // bob, ted, and jeff are already an existing group direct message,
    // but if we start with just jeff, then don't prioritize ted over
    // alice because it doesn't complete the full group direct message.
    query = "dm:jeff@zulip.com,";
    suggestions = get_suggestions(query);
    expected = [
        "dm:jeff@zulip.com,",
        "dm:jeff@zulip.com,alice@zulip.com",
        "dm:jeff@zulip.com,bob@zulip.com",
        "dm:jeff@zulip.com,ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = "dm:jeff@zulip.com,ted@zulip.com hi";
    suggestions = get_suggestions(query);
    expected = ["dm:jeff@zulip.com,ted@zulip.com hi", "dm:jeff@zulip.com,ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);
});

test("empty_query_suggestions", () => {
    const query = "";

    stream_data.add_sub({stream_id: 44, name: "devel", subscribed: true});
    stream_data.add_sub({stream_id: 77, name: "office", subscribed: true});

    const suggestions = get_suggestions(query);

    const expected = [
        "channels:public",
        "is:dm",
        "is:starred",
        "is:mentioned",
        "is:alerted",
        "is:unread",
        "is:resolved",
        "sender:myself@zulip.com",
        "channel:devel",
        "channel:office",
        "has:link",
        "has:image",
        "has:attachment",
    ];

    assert.deepEqual(suggestions.strings, expected);

    function describe(q) {
        return suggestions.lookup_table.get(q).description_html;
    }
    assert.equal(describe("is:dm"), "Direct messages");
    assert.equal(describe("is:starred"), "Starred messages");
    assert.equal(describe("is:mentioned"), "@-mentions");
    assert.equal(describe("is:alerted"), "Alerted messages");
    assert.equal(describe("is:unread"), "Unread messages");
    assert.equal(describe("is:resolved"), "Topics marked as resolved");
    assert.equal(describe("sender:myself@zulip.com"), "Sent by me");
    assert.equal(describe("has:link"), "Messages that contain links");
    assert.equal(describe("has:image"), "Messages that contain images");
    assert.equal(describe("has:attachment"), "Messages that contain attachments");
});

test("has_suggestions", ({override, mock_template}) => {
    mock_template("search_description.hbs", true, (_data, html) => html);

    // Checks that category wise suggestions are displayed instead of a single
    // default suggestion when suggesting `has` operator.
    let query = "h";
    stream_data.add_sub({stream_id: 44, name: "devel", subscribed: true});
    stream_data.add_sub({stream_id: 77, name: "office", subscribed: true});
    override(narrow_state, "stream_name", noop);

    let suggestions = get_suggestions(query);
    let expected = ["h", "has:link", "has:image", "has:attachment"];
    assert.deepEqual(suggestions.strings, expected);

    function describe(q) {
        return suggestions.lookup_table.get(q).description_html;
    }

    assert.equal(describe("has:link"), "Messages that contain links");
    assert.equal(describe("has:image"), "Messages that contain images");
    assert.equal(describe("has:attachment"), "Messages that contain attachments");

    query = "-h";
    suggestions = get_suggestions(query);
    expected = ["-h", "-has:link", "-has:image", "-has:attachment"];
    assert.deepEqual(suggestions.strings, expected);
    assert.equal(describe("-has:link"), "Exclude messages that contain links");
    assert.equal(describe("-has:image"), "Exclude messages that contain images");
    assert.equal(describe("-has:attachment"), "Exclude messages that contain attachments");

    // operand suggestions follow.

    query = "has:";
    suggestions = get_suggestions(query);
    expected = ["has:link", "has:image", "has:attachment"];
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

    query = "channel:Denmark is:alerted has:lin";
    suggestions = get_suggestions(query);
    expected = [
        "channel:Denmark is:alerted has:link",
        "channel:Denmark is:alerted",
        "channel:Denmark",
    ];
    assert.deepEqual(suggestions.strings, expected);
});

test("check_is_suggestions", ({override, mock_template}) => {
    mock_template("search_description.hbs", true, (_data, html) => html);

    stream_data.add_sub({stream_id: 44, name: "devel", subscribed: true});
    stream_data.add_sub({stream_id: 77, name: "office", subscribed: true});
    override(narrow_state, "stream_name", noop);

    let query = "i";
    let suggestions = get_suggestions(query);
    let expected = [
        "i",
        "is:dm",
        "is:starred",
        "is:mentioned",
        "is:alerted",
        "is:unread",
        "is:resolved",
        "sender:alice@zulip.com",
        "dm:alice@zulip.com",
        "dm-including:alice@zulip.com",
        "has:image",
    ];
    assert.deepEqual(suggestions.strings, expected);

    function describe(q) {
        return suggestions.lookup_table.get(q).description_html;
    }

    assert.equal(describe("is:dm"), "Direct messages");
    assert.equal(describe("is:starred"), "Starred messages");
    assert.equal(describe("is:mentioned"), "@-mentions");
    assert.equal(describe("is:alerted"), "Alerted messages");
    assert.equal(describe("is:unread"), "Unread messages");
    assert.equal(describe("is:resolved"), "Topics marked as resolved");

    query = "-i";
    suggestions = get_suggestions(query);
    expected = [
        "-i",
        "-is:dm",
        "-is:starred",
        "-is:mentioned",
        "-is:alerted",
        "-is:unread",
        "-is:resolved",
    ];
    assert.deepEqual(suggestions.strings, expected);

    assert.equal(describe("-is:dm"), "Exclude direct messages");
    assert.equal(describe("-is:starred"), "Exclude starred messages");
    assert.equal(describe("-is:mentioned"), "Exclude @-mentions");
    assert.equal(describe("-is:alerted"), "Exclude alerted messages");
    assert.equal(describe("-is:unread"), "Exclude unread messages");
    assert.equal(describe("-is:resolved"), "Exclude topics marked as resolved");

    // operand suggestions follow.

    query = "is:";
    suggestions = get_suggestions(query);
    expected = ["is:dm", "is:starred", "is:mentioned", "is:alerted", "is:unread", "is:resolved"];
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

    query = "channel:Denmark has:link is:sta";
    suggestions = get_suggestions(query);
    expected = [
        "channel:Denmark has:link is:starred",
        "channel:Denmark has:link",
        "channel:Denmark",
    ];
    assert.deepEqual(suggestions.strings, expected);
});

test("sent_by_me_suggestions", ({override, mock_template}) => {
    mock_template("search_description.hbs", true, (_data, html) => html);

    override(narrow_state, "stream_name", noop);

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

    query = "channel:Denmark topic:Denmark1 sent";
    suggestions = get_suggestions(query);
    expected = [
        "channel:Denmark topic:Denmark1 sent",
        "channel:Denmark topic:Denmark1 sender:myself@zulip.com",
        "channel:Denmark topic:Denmark1",
        "channel:Denmark",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = "is:starred sender:m";
    suggestions = get_suggestions(query);
    expected = ["is:starred sender:m", "is:starred sender:myself@zulip.com", "is:starred"];
    assert.deepEqual(suggestions.strings, expected);

    query = "sender:alice@zulip.com sender:";
    suggestions = get_suggestions(query);
    expected = ["sender:alice@zulip.com sender:", "sender:alice@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);
});

test("topic_suggestions", ({override, mock_template}) => {
    mock_template("search_description.hbs", true, (_data, html) => html);
    let suggestions;
    let expected;

    override(stream_topic_history_util, "get_server_history", noop);
    stream_data.add_sub({stream_id: 77, name: "office", subscribed: true});
    override(narrow_state, "stream_name", () => "office");

    const devel_id = 44;
    const office_id = 77;
    stream_data.add_sub({stream_id: devel_id, name: "devel", subscribed: true});
    stream_data.add_sub({stream_id: office_id, name: "office", subscribed: true});

    suggestions = get_suggestions("te");
    expected = ["te", "sender:ted@zulip.com", "dm:ted@zulip.com", "dm-including:ted@zulip.com"];
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
        "sender:ted@zulip.com",
        "dm:ted@zulip.com",
        "dm-including:ted@zulip.com",
        "channel:office topic:team",
        "channel:office topic:test",
    ];
    assert.deepEqual(suggestions.strings, expected);

    function describe(q) {
        return suggestions.lookup_table.get(q).description_html;
    }
    assert.equal(describe("te"), "Search for <strong>te</strong>");
    assert.equal(describe("channel:office topic:team"), "Channel office > team");

    suggestions = get_suggestions("topic:staplers channel:office");
    expected = ["topic:staplers channel:office", "topic:staplers"];
    assert.deepEqual(suggestions.strings, expected);

    suggestions = get_suggestions("channel:devel topic:");
    expected = ["channel:devel topic:", "channel:devel topic:REXX", "channel:devel"];
    assert.deepEqual(suggestions.strings, expected);

    suggestions = get_suggestions("channel:devel -topic:");
    expected = ["channel:devel -topic:", "channel:devel -topic:REXX", "channel:devel"];
    assert.deepEqual(suggestions.strings, expected);

    suggestions = get_suggestions("-topic:te");
    expected = ["-topic:te", "channel:office -topic:team", "channel:office -topic:test"];
    assert.deepEqual(suggestions.strings, expected);

    suggestions = get_suggestions("is:alerted channel:devel is:starred topic:");
    expected = [
        "is:alerted channel:devel is:starred topic:",
        "is:alerted channel:devel is:starred topic:REXX",
        "is:alerted channel:devel is:starred",
        "is:alerted channel:devel",
        "is:alerted",
    ];
    assert.deepEqual(suggestions.strings, expected);

    suggestions = get_suggestions("is:dm channel:devel topic:");
    expected = ["is:dm channel:devel topic:", "is:dm channel:devel", "is:dm"];
    assert.deepEqual(suggestions.strings, expected);

    suggestions = get_suggestions("topic:REXX channel:devel topic:");
    expected = ["topic:REXX channel:devel topic:", "topic:REXX channel:devel", "topic:REXX"];
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

    const query = "channel:office "; // note trailing space

    override(stream_topic_history_util, "get_server_history", noop);
    stream_data.add_sub({stream_id: 77, name: "office", subscribed: true});

    const suggestions = get_suggestions(query);

    const expected = ["channel:office"];

    assert.deepEqual(suggestions.strings, expected);
});

test("channel_completion", ({override, mock_template}) => {
    mock_template("search_description.hbs", true, (_data, html) => html);

    stream_data.add_sub({stream_id: 77, name: "office", subscribed: true});
    stream_data.add_sub({stream_id: 88, name: "dev help", subscribed: true});

    override(narrow_state, "stream_name", noop);

    let query = "channel:of";
    let suggestions = get_suggestions(query);
    let expected = ["channel:of", "channel:office"];
    assert.deepEqual(suggestions.strings, expected);

    query = "-channel:of";
    suggestions = get_suggestions(query);
    expected = ["-channel:of", "-channel:office"];
    assert.deepEqual(suggestions.strings, expected);

    query = "hel";
    suggestions = get_suggestions(query);
    expected = ["hel", "channel:dev+help"];
    assert.deepEqual(suggestions.strings, expected);
});

test("people_suggestions", ({override, mock_template}) => {
    mock_template("search_description.hbs", true, (_data, html) => html);

    let query = "te";

    override(narrow_state, "stream_name", noop);

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
        "sender:bob@zulip.com",
        "sender:ted@zulip.com",
        "dm:bob@zulip.com", // bob térry
        "dm:ted@zulip.com",
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
        "sender:bob@zulip.com",
        "sender:ted@zulip.com",
        "sender:user299@zulipdev.com",
        "dm:bob@zulip.com",
        "dm:ted@zulip.com",
        "dm:user299@zulipdev.com",
        "dm-including:bob@zulip.com",
        "dm-including:ted@zulip.com",
        "dm-including:user299@zulipdev.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    function is_person(q) {
        return suggestions.lookup_table.get(q).is_person;
    }
    assert.equal(is_person("dm:ted@zulip.com"), true);
    assert.equal(is_person("sender:ted@zulip.com"), true);
    assert.equal(is_person("dm-including:ted@zulip.com"), true);

    function has_image(q) {
        return suggestions.lookup_table.get(q).user_pill_context.has_image;
    }
    assert.equal(has_image("dm:bob@zulip.com"), true);
    assert.equal(has_image("sender:bob@zulip.com"), true);
    assert.equal(has_image("dm-including:bob@zulip.com"), true);

    function describe(q) {
        return suggestions.lookup_table.get(q).description_html;
    }
    assert.equal(describe("dm:ted@zulip.com"), "Direct messages with");
    assert.equal(describe("sender:ted@zulip.com"), "Sent by");
    assert.equal(describe("dm-including:ted@zulip.com"), "Direct messages including");

    let expectedString = "<strong>Te</strong>d Smith";

    function get_full_name(q) {
        return suggestions.lookup_table.get(q).user_pill_context.display_value.string;
    }
    assert.equal(get_full_name("sender:ted@zulip.com"), expectedString);
    assert.equal(get_full_name("dm:ted@zulip.com"), expectedString);
    assert.equal(get_full_name("dm-including:ted@zulip.com"), expectedString);

    expectedString = example_avatar_url + "?s=50";

    function get_avatar_url(q) {
        return suggestions.lookup_table.get(q).user_pill_context.img_src;
    }
    assert.equal(get_avatar_url("dm:bob@zulip.com"), expectedString);
    assert.equal(get_avatar_url("sender:bob@zulip.com"), expectedString);
    assert.equal(get_avatar_url("dm-including:bob@zulip.com"), expectedString);

    function get_should_add_guest_user_indicator(q) {
        return suggestions.lookup_table.get(q).user_pill_context.should_add_guest_user_indicator;
    }

    realm.realm_enable_guest_user_indicator = true;
    suggestions = get_suggestions(query);

    assert.equal(get_should_add_guest_user_indicator("dm:bob@zulip.com"), false);
    assert.equal(get_should_add_guest_user_indicator("sender:bob@zulip.com"), false);
    assert.equal(get_should_add_guest_user_indicator("dm-including:bob@zulip.com"), false);

    bob.is_guest = true;
    suggestions = get_suggestions(query);

    assert.equal(get_should_add_guest_user_indicator("dm:bob@zulip.com"), true);
    assert.equal(get_should_add_guest_user_indicator("sender:bob@zulip.com"), true);
    assert.equal(get_should_add_guest_user_indicator("dm-including:bob@zulip.com"), true);

    realm.realm_enable_guest_user_indicator = false;
    suggestions = get_suggestions(query);

    assert.equal(get_should_add_guest_user_indicator("dm:bob@zulip.com"), false);
    assert.equal(get_should_add_guest_user_indicator("sender:bob@zulip.com"), false);
    assert.equal(get_should_add_guest_user_indicator("dm-including:bob@zulip.com"), false);

    suggestions = get_suggestions("Ted "); // note space

    expected = ["Ted", "sender:ted@zulip.com", "dm:ted@zulip.com", "dm-including:ted@zulip.com"];

    assert.deepEqual(suggestions.strings, expected);

    query = "sender:ted sm";
    expected = ["sender:ted+sm", "sender:ted@zulip.com"];
    suggestions = get_suggestions(query);
    assert.deepEqual(suggestions.strings, expected);

    query = "sender:ted@zulip.com new";
    expected = ["sender:ted@zulip.com new", "sender:ted@zulip.com"];
    suggestions = get_suggestions(query);
    assert.deepEqual(suggestions.strings, expected);

    query = "sender:ted@tulip.com new";
    expected = ["sender:ted@tulip.com+new"];
    suggestions = get_suggestions(query);
    assert.deepEqual(suggestions.strings, expected);
});

test("operator_suggestions", ({override, mock_template}) => {
    mock_template("search_description.hbs", true, (_data, html) => html);

    override(narrow_state, "stream_name", () => undefined);

    // Completed operator should return nothing
    let query = "channel:";
    let suggestions = get_suggestions(query);
    let expected = ["channel:"];
    assert.deepEqual(suggestions.strings, expected);

    query = "ch";
    suggestions = get_suggestions(query);
    expected = ["ch", "channels:public", "channel:"];
    assert.deepEqual(suggestions.strings, expected);

    query = "-s";
    suggestions = get_suggestions(query);
    expected = ["-s", "-sender:myself@zulip.com", "-sender:", "-channel:"];
    assert.deepEqual(suggestions.strings, expected);

    query = "channel:Denmark is:alerted -f";
    suggestions = get_suggestions(query);
    expected = [
        "channel:Denmark is:alerted -f",
        "channel:Denmark is:alerted -sender:myself@zulip.com",
        "channel:Denmark is:alerted -sender:",
        "channel:Denmark is:alerted",
        "channel:Denmark",
    ];
    assert.deepEqual(suggestions.strings, expected);
});

test("queries_with_spaces", ({mock_template}) => {
    mock_template("search_description.hbs", true, (_data, html) => html);

    stream_data.add_sub({stream_id: 77, name: "office", subscribed: true});
    stream_data.add_sub({stream_id: 88, name: "dev help", subscribed: true});

    // test allowing spaces with quotes surrounding operand
    let query = 'channel:"dev he"';
    let suggestions = get_suggestions(query);
    let expected = ["channel:dev+he", "channel:dev+help"];
    assert.deepEqual(suggestions.strings, expected);

    // test mismatched quote
    query = 'channel:"dev h';
    suggestions = get_suggestions(query);
    expected = ["channel:dev+h", "channel:dev+help"];
    assert.deepEqual(suggestions.strings, expected);

    // test extra space after operator still works
    query = "channel: offi";
    suggestions = get_suggestions(query);
    expected = ["channel:offi", "channel:office"];
    assert.deepEqual(suggestions.strings, expected);
});
