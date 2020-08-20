"use strict";

set_global("page_params", {
    search_pills_enabled: true,
});

set_global("message_store", {
    user_ids: () => [],
});

const settings_config = zrequire("settings_config");
page_params.realm_email_address_visibility =
    settings_config.email_address_visibility_values.admins_only.code;

const huddle_data = zrequire("huddle_data");

zrequire("typeahead_helper");
zrequire("Filter", "js/filter");
zrequire("narrow_state");
zrequire("stream_data");
zrequire("stream_topic_history");
const people = zrequire("people");
zrequire("unread");
zrequire("common");
const search = zrequire("search_suggestion");

search.max_num_of_search_results = 15;

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

const noop = () => {};

function init() {
    people.init();
    people.add_active_user(bob);
    people.add_active_user(me);
    people.add_active_user(ted);
    people.add_active_user(alice);
    people.add_active_user(jeff);

    people.initialize_current_user(me.user_id);
}
init();

page_params.is_admin = true;
set_global("narrow", {});

stream_topic_history.reset();

function get_suggestions(base_query, query) {
    return search.get_suggestions(base_query, query);
}

run_test("basic_get_suggestions", () => {
    const query = "fred";

    global.stream_data.subscribed_streams = function () {
        return [];
    };

    global.narrow_state.stream = function () {
        return "office";
    };

    const suggestions = get_suggestions("", query);

    const expected = ["fred"];
    assert.deepEqual(suggestions.strings, expected);
});

run_test("subset_suggestions", () => {
    const query = "shakespeare";
    const base_query = "stream:Denmark topic:Hamlet";

    global.stream_data.subscribed_streams = function () {
        return [];
    };

    global.narrow_state.stream = function () {
        return;
    };

    const suggestions = get_suggestions(base_query, query);

    const expected = ["shakespeare"];

    assert.deepEqual(suggestions.strings, expected);
});

run_test("private_suggestions", () => {
    global.stream_data.subscribed_streams = function () {
        return [];
    };

    global.narrow_state.stream = function () {
        return;
    };

    let query = "is:private";
    let suggestions = get_suggestions("", query);
    let expected = [
        "is:private",
        "pm-with:alice@zulip.com",
        "pm-with:bob@zulip.com",
        "pm-with:jeff@zulip.com",
        "pm-with:myself@zulip.com",
        "pm-with:ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = "al";
    let base_query = "is:private";
    suggestions = get_suggestions(base_query, query);
    expected = [
        "al",
        "is:alerted",
        "sender:alice@zulip.com",
        "pm-with:alice@zulip.com",
        "group-pm-with:alice@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = "pm-with:t";
    suggestions = get_suggestions("", query);
    expected = ["pm-with:t", "pm-with:ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "-pm-with:t";
    suggestions = get_suggestions("", query);
    expected = ["-pm-with:t", "is:private -pm-with:ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "pm-with:ted@zulip.com";
    suggestions = get_suggestions("", query);
    expected = ["pm-with:ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "sender:ted";
    suggestions = get_suggestions("", query);
    expected = ["sender:ted", "sender:ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "sender:te";
    suggestions = get_suggestions("", query);
    expected = ["sender:te", "sender:ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "-sender:te";
    suggestions = get_suggestions("", query);
    expected = ["-sender:te", "-sender:ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "sender:ted@zulip.com";
    suggestions = get_suggestions("", query);
    expected = ["sender:ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "from:ted";
    base_query = "is:unread";
    suggestions = get_suggestions(base_query, query);
    expected = ["from:ted", "from:ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    // Users can enter bizarre queries, and if they do, we want to
    // be conservative with suggestions.
    query = "near:3";
    base_query = "is:private";
    suggestions = get_suggestions(base_query, query);
    expected = ["near:3"];
    assert.deepEqual(suggestions.strings, expected);

    query = "near:3";
    base_query = "pm-with:ted@zulip.com";
    suggestions = get_suggestions(base_query, query);
    expected = ["near:3"];
    assert.deepEqual(suggestions.strings, expected);

    // Make sure suggestions still work if preceding tokens
    query = "sender:ted@zulip.com";
    base_query = "is:alerted";
    suggestions = get_suggestions(base_query, query);
    expected = ["sender:ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "al";
    base_query = "is:starred has:link is:private";
    suggestions = get_suggestions(base_query, query);
    expected = [
        "al",
        "is:alerted",
        "sender:alice@zulip.com",
        "pm-with:alice@zulip.com",
        "group-pm-with:alice@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // Make sure it handles past context correctly
    query = "pm-with:";
    base_query = "stream:Denmark";
    suggestions = get_suggestions(base_query, query);
    expected = ["pm-with:"];
    assert.deepEqual(suggestions.strings, expected);

    query = "sender:";
    base_query = "sender:ted@zulip.com";
    suggestions = get_suggestions(base_query, query);
    expected = ["sender:"];
    assert.deepEqual(suggestions.strings, expected);
});

run_test("group_suggestions", () => {
    global.stream_data.subscribed_streams = function () {
        return [];
    };

    global.narrow_state.stream = function () {
        return;
    };

    // Entering a comma in a pm-with query should immediately generate
    // suggestions for the next person.
    let query = "pm-with:bob@zulip.com,";
    let suggestions = get_suggestions("", query);
    let expected = [
        "pm-with:bob@zulip.com,",
        "pm-with:bob@zulip.com,alice@zulip.com",
        "pm-with:bob@zulip.com,jeff@zulip.com",
        "pm-with:bob@zulip.com,ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // Only the last part of a comma-separated pm-with query should be used to
    // generate suggestions.
    query = "pm-with:bob@zulip.com,t";
    suggestions = get_suggestions("", query);
    expected = ["pm-with:bob@zulip.com,t", "pm-with:bob@zulip.com,ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    // Smit should also generate ted@zulip.com (Ted Smith) as a suggestion.
    query = "pm-with:bob@zulip.com,Smit";
    suggestions = get_suggestions("", query);
    expected = ["pm-with:bob@zulip.com,Smit", "pm-with:bob@zulip.com,ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    // Do not suggest "myself@zulip.com" (the name of the current user)
    query = "pm-with:ted@zulip.com,mys";
    suggestions = get_suggestions("", query);
    expected = ["pm-with:ted@zulip.com,mys"];
    assert.deepEqual(suggestions.strings, expected);

    // No superfluous suggestions should be generated.
    query = "pm-with:bob@zulip.com,red";
    suggestions = get_suggestions("", query);
    expected = ["pm-with:bob@zulip.com,red"];
    assert.deepEqual(suggestions.strings, expected);

    // is:private should be properly prepended to each suggestion if the pm-with
    // operator is negated.

    query = "-pm-with:bob@zulip.com,";
    suggestions = get_suggestions("", query);
    expected = [
        "-pm-with:bob@zulip.com,",
        "is:private -pm-with:bob@zulip.com,alice@zulip.com",
        "is:private -pm-with:bob@zulip.com,jeff@zulip.com",
        "is:private -pm-with:bob@zulip.com,ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = "-pm-with:bob@zulip.com,t";
    suggestions = get_suggestions("", query);
    expected = ["-pm-with:bob@zulip.com,t", "is:private -pm-with:bob@zulip.com,ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "-pm-with:bob@zulip.com,Smit";
    suggestions = get_suggestions("", query);
    expected = ["-pm-with:bob@zulip.com,Smit", "is:private -pm-with:bob@zulip.com,ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "-pm-with:bob@zulip.com,red";
    suggestions = get_suggestions("", query);
    expected = ["-pm-with:bob@zulip.com,red"];
    assert.deepEqual(suggestions.strings, expected);

    // Test multiple operators
    query = "pm-with:bob@zulip.com,Smit";
    let base_query = "is:starred has:link";
    suggestions = get_suggestions(base_query, query);
    expected = ["pm-with:bob@zulip.com,Smit", "pm-with:bob@zulip.com,ted@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "pm-with:bob@zulip.com,Smit";
    base_query = "stream:Denmark has:link";
    suggestions = get_suggestions(base_query, query);
    expected = ["pm-with:bob@zulip.com,Smit"];
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

    // Simulate a past huddle which should now prioritize ted over alice
    query = "pm-with:bob@zulip.com,";
    suggestions = get_suggestions("", query);
    expected = [
        "pm-with:bob@zulip.com,",
        "pm-with:bob@zulip.com,ted@zulip.com",
        "pm-with:bob@zulip.com,alice@zulip.com",
        "pm-with:bob@zulip.com,jeff@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // bob,ted,jeff is already an existing huddle, so prioritize this one
    query = "pm-with:bob@zulip.com,ted@zulip.com,";
    suggestions = get_suggestions("", query);
    expected = [
        "pm-with:bob@zulip.com,ted@zulip.com,",
        "pm-with:bob@zulip.com,ted@zulip.com,jeff@zulip.com",
        "pm-with:bob@zulip.com,ted@zulip.com,alice@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // bob,ted,jeff is already an existing huddle, but if we start with just jeff,
    // then don't prioritize ted over alice because it doesn't complete the full huddle.
    query = "pm-with:jeff@zulip.com,";
    suggestions = get_suggestions("", query);
    expected = [
        "pm-with:jeff@zulip.com,",
        "pm-with:jeff@zulip.com,alice@zulip.com",
        "pm-with:jeff@zulip.com,bob@zulip.com",
        "pm-with:jeff@zulip.com,ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = "pm-with:jeff@zulip.com,ted@zulip.com hi";
    suggestions = get_suggestions("", query);
    expected = ["pm-with:jeff@zulip.com,ted@zulip.com hi"];
    assert.deepEqual(suggestions.strings, expected);
});

init();

run_test("empty_query_suggestions", () => {
    const query = "";

    global.stream_data.subscribed_streams = function () {
        return ["devel", "office"];
    };

    global.narrow_state.stream = function () {
        return;
    };

    const suggestions = get_suggestions("", query);

    const expected = [
        "",
        "streams:public",
        "is:private",
        "is:starred",
        "is:mentioned",
        "is:alerted",
        "is:unread",
        "sender:myself@zulip.com",
        "stream:devel",
        "stream:office",
        "has:link",
        "has:image",
        "has:attachment",
    ];

    assert.deepEqual(suggestions.strings, expected);

    function describe(q) {
        return suggestions.lookup_table.get(q).description;
    }
    assert.equal(describe("is:private"), "Private messages");
    assert.equal(describe("is:starred"), "Starred messages");
    assert.equal(describe("is:mentioned"), "@-mentions");
    assert.equal(describe("is:alerted"), "Alerted messages");
    assert.equal(describe("is:unread"), "Unread messages");
    assert.equal(describe("sender:myself@zulip.com"), "Sent by me");
    assert.equal(describe("has:link"), "Messages with one or more link");
    assert.equal(describe("has:image"), "Messages with one or more image");
    assert.equal(describe("has:attachment"), "Messages with one or more attachment");
});

run_test("has_suggestions", () => {
    // Checks that category wise suggestions are displayed instead of a single
    // default suggestion when suggesting `has` operator.
    let query = "h";
    global.stream_data.subscribed_streams = function () {
        return ["devel", "office"];
    };
    global.narrow_state.stream = function () {
        return;
    };

    let suggestions = get_suggestions("", query);
    let expected = ["h", "has:link", "has:image", "has:attachment"];
    assert.deepEqual(suggestions.strings, expected);

    function describe(q) {
        return suggestions.lookup_table.get(q).description;
    }

    assert.equal(describe("has:link"), "Messages with one or more link");
    assert.equal(describe("has:image"), "Messages with one or more image");
    assert.equal(describe("has:attachment"), "Messages with one or more attachment");

    query = "-h";
    suggestions = get_suggestions("", query);
    expected = ["-h", "-has:link", "-has:image", "-has:attachment"];
    assert.deepEqual(suggestions.strings, expected);
    assert.equal(describe("-has:link"), "Exclude messages with one or more link");
    assert.equal(describe("-has:image"), "Exclude messages with one or more image");
    assert.equal(describe("-has:attachment"), "Exclude messages with one or more attachment");

    // operand suggestions follow.

    query = "has:";
    suggestions = get_suggestions("", query);
    expected = ["has:link", "has:image", "has:attachment"];
    assert.deepEqual(suggestions.strings, expected);

    query = "has:im";
    suggestions = get_suggestions("", query);
    expected = ["has:image"];
    assert.deepEqual(suggestions.strings, expected);

    query = "-has:im";
    suggestions = get_suggestions("", query);
    expected = ["-has:image"];
    assert.deepEqual(suggestions.strings, expected);

    query = "att";
    suggestions = get_suggestions("", query);
    expected = ["att", "has:attachment"];
    assert.deepEqual(suggestions.strings, expected);

    query = "has:lin";
    const base_query = "stream:Denmark is:alerted";
    suggestions = get_suggestions(base_query, query);
    expected = ["has:link"];
    assert.deepEqual(suggestions.strings, expected);
});

run_test("check_is_suggestions", () => {
    let query = "i";
    global.stream_data.subscribed_streams = function () {
        return ["devel", "office"];
    };
    global.narrow_state.stream = function () {
        return;
    };

    let suggestions = get_suggestions("", query);
    let expected = [
        "i",
        "is:private",
        "is:starred",
        "is:mentioned",
        "is:alerted",
        "is:unread",
        "sender:alice@zulip.com",
        "pm-with:alice@zulip.com",
        "group-pm-with:alice@zulip.com",
        "has:image",
    ];
    assert.deepEqual(suggestions.strings, expected);

    function describe(q) {
        return suggestions.lookup_table.get(q).description;
    }

    assert.equal(describe("is:private"), "Private messages");
    assert.equal(describe("is:starred"), "Starred messages");
    assert.equal(describe("is:mentioned"), "@-mentions");
    assert.equal(describe("is:alerted"), "Alerted messages");
    assert.equal(describe("is:unread"), "Unread messages");

    query = "-i";
    suggestions = get_suggestions("", query);
    expected = ["-i", "-is:private", "-is:starred", "-is:mentioned", "-is:alerted", "-is:unread"];
    assert.deepEqual(suggestions.strings, expected);

    assert.equal(describe("-is:private"), "Exclude private messages");
    assert.equal(describe("-is:starred"), "Exclude starred messages");
    assert.equal(describe("-is:mentioned"), "Exclude @-mentions");
    assert.equal(describe("-is:alerted"), "Exclude alerted messages");
    assert.equal(describe("-is:unread"), "Exclude unread messages");

    query = "";
    suggestions = get_suggestions("", query);
    expected = [
        "",
        "streams:public",
        "is:private",
        "is:starred",
        "is:mentioned",
        "is:alerted",
        "is:unread",
        "sender:myself@zulip.com",
        "stream:devel",
        "stream:office",
        "has:link",
        "has:image",
        "has:attachment",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = "";
    let base_query = "is:private";
    suggestions = get_suggestions(base_query, query);
    expected = [
        "is:starred",
        "is:mentioned",
        "is:alerted",
        "is:unread",
        "sender:myself@zulip.com",
        "has:link",
        "has:image",
        "has:attachment",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // operand suggestions follow.

    query = "is:";
    suggestions = get_suggestions("", query);
    expected = ["is:private", "is:starred", "is:mentioned", "is:alerted", "is:unread"];
    assert.deepEqual(suggestions.strings, expected);

    query = "is:st";
    suggestions = get_suggestions("", query);
    expected = ["is:starred"];
    assert.deepEqual(suggestions.strings, expected);

    query = "-is:st";
    suggestions = get_suggestions("", query);
    expected = ["-is:starred"];
    assert.deepEqual(suggestions.strings, expected);

    query = "st";
    suggestions = get_suggestions("", query);
    expected = ["st", "streams:public", "is:starred", "stream:"];
    assert.deepEqual(suggestions.strings, expected);

    query = "is:sta";
    base_query = "stream:Denmark has:link";
    suggestions = get_suggestions(base_query, query);
    expected = ["is:starred"];
    assert.deepEqual(suggestions.strings, expected);
});

run_test("sent_by_me_suggestions", () => {
    global.stream_data.subscribed_streams = function () {
        return [];
    };

    global.narrow_state.stream = function () {
        return;
    };

    let query = "";
    let suggestions = get_suggestions("", query);
    assert(suggestions.strings.includes("sender:myself@zulip.com"));
    assert.equal(suggestions.lookup_table.get("sender:myself@zulip.com").description, "Sent by me");

    query = "sender";
    suggestions = get_suggestions("", query);
    let expected = ["sender", "sender:myself@zulip.com", "sender:"];
    assert.deepEqual(suggestions.strings, expected);

    query = "-sender";
    suggestions = get_suggestions("", query);
    expected = ["-sender", "-sender:myself@zulip.com", "-sender:"];
    assert.deepEqual(suggestions.strings, expected);

    query = "from";
    suggestions = get_suggestions("", query);
    expected = ["from", "from:myself@zulip.com", "from:"];
    assert.deepEqual(suggestions.strings, expected);

    query = "-from";
    suggestions = get_suggestions("", query);
    expected = ["-from", "-from:myself@zulip.com", "-from:"];
    assert.deepEqual(suggestions.strings, expected);

    query = "sender:bob@zulip.com";
    suggestions = get_suggestions("", query);
    expected = ["sender:bob@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "from:bob@zulip.com";
    suggestions = get_suggestions("", query);
    expected = ["from:bob@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "sent";
    suggestions = get_suggestions("", query);
    expected = ["sent", "sender:myself@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "-sent";
    suggestions = get_suggestions("", query);
    expected = ["-sent", "-sender:myself@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "sent";
    let base_query = "stream:Denmark topic:Denmark1";
    suggestions = get_suggestions(base_query, query);
    expected = ["sent", "sender:myself@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "sender:m";
    base_query = "is:starred";
    suggestions = get_suggestions(base_query, query);
    expected = ["sender:m", "sender:myself@zulip.com"];
    assert.deepEqual(suggestions.strings, expected);

    query = "sender:";
    base_query = "is:starred";
    suggestions = get_suggestions(base_query, query);
    expected = [
        "sender:",
        "sender:myself@zulip.com",
        "sender:alice@zulip.com",
        "sender:bob@zulip.com",
        "sender:jeff@zulip.com",
        "sender:ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);
});

run_test("topic_suggestions", () => {
    let suggestions;
    let expected;

    global.stream_data.subscribed_streams = function () {
        return ["office"];
    };

    global.narrow_state.stream = function () {
        return "office";
    };

    const devel_id = 44;
    const office_id = 77;

    global.stream_data.get_stream_id = function (stream_name) {
        switch (stream_name) {
            case "office":
                return office_id;
            case "devel":
                return devel_id;
        }
    };

    stream_topic_history.reset();
    suggestions = get_suggestions("", "te");
    expected = [
        "te",
        "sender:ted@zulip.com",
        "pm-with:ted@zulip.com",
        "group-pm-with:ted@zulip.com",
    ];
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

    suggestions = get_suggestions("", "te");
    expected = [
        "te",
        "sender:ted@zulip.com",
        "pm-with:ted@zulip.com",
        "group-pm-with:ted@zulip.com",
        "stream:office topic:team",
        "stream:office topic:test",
    ];
    assert.deepEqual(suggestions.strings, expected);

    function describe(q) {
        return suggestions.lookup_table.get(q).description;
    }
    assert.equal(describe("te"), "Search for te");
    assert.equal(describe("stream:office topic:team"), "Stream office &gt; team");

    suggestions = get_suggestions("topic:staplers", "stream:office");
    expected = ["stream:office"];
    assert.deepEqual(suggestions.strings, expected);

    suggestions = get_suggestions("stream:devel", "topic:");
    expected = ["topic:", "topic:REXX"];
    assert.deepEqual(suggestions.strings, expected);

    suggestions = get_suggestions("stream:devel", "-topic:");
    expected = ["-topic:", "-topic:REXX"];
    assert.deepEqual(suggestions.strings, expected);

    suggestions = get_suggestions("", "-topic:te");
    expected = ["-topic:te", "stream:office -topic:team", "stream:office -topic:test"];
    assert.deepEqual(suggestions.strings, expected);

    suggestions = get_suggestions("is:alerted stream:devel is:starred", "topic:");
    expected = ["topic:", "topic:REXX"];
    assert.deepEqual(suggestions.strings, expected);

    suggestions = get_suggestions("is:private stream:devel", "topic:");
    expected = ["topic:"];
    assert.deepEqual(suggestions.strings, expected);

    suggestions = get_suggestions("topic:REXX stream:devel", "topic:");
    expected = ["topic:"];
    assert.deepEqual(suggestions.strings, expected);
});

run_test("whitespace_glitch", () => {
    const query = "stream:office "; // note trailing space

    global.stream_data.subscribed_streams = function () {
        return ["office"];
    };

    global.narrow_state.stream = function () {
        return;
    };

    stream_topic_history.reset();

    const suggestions = get_suggestions("", query);

    const expected = ["stream:office"];

    assert.deepEqual(suggestions.strings, expected);
});

run_test("stream_completion", () => {
    global.stream_data.subscribed_streams = function () {
        return ["office", "dev help"];
    };

    global.narrow_state.stream = function () {
        return;
    };

    stream_topic_history.reset();

    let query = "stream:of";
    let suggestions = get_suggestions("", query);
    let expected = ["stream:of", "stream:office"];
    assert.deepEqual(suggestions.strings, expected);

    query = "-stream:of";
    suggestions = get_suggestions("", query);
    expected = ["-stream:of", "-stream:office"];
    assert.deepEqual(suggestions.strings, expected);

    query = "hel";
    suggestions = get_suggestions("", query);
    expected = ["hel", "stream:dev+help"];
    assert.deepEqual(suggestions.strings, expected);
});

function people_suggestion_setup() {
    global.stream_data.subscribed_streams = () => [];
    global.narrow_state.stream = noop;

    const ted = {
        email: "ted@zulip.com",
        user_id: 201,
        full_name: "Ted Smith",
    };
    people.add_active_user(ted);

    const bob = {
        email: "bob@zulip.com",
        user_id: 202,
        full_name: "Bob Térry",
    };

    people.add_active_user(bob);
    const alice = {
        email: "alice@zulip.com",
        user_id: 203,
        full_name: "Alice Ignore",
    };
    people.add_active_user(alice);

    stream_topic_history.reset();
}

run_test("people_suggestions", () => {
    people_suggestion_setup();
    let query = "te";
    let suggestions = get_suggestions("", query);
    let expected = [
        "te",
        "sender:bob@zulip.com",
        "sender:ted@zulip.com",
        "pm-with:bob@zulip.com", // bob térry
        "pm-with:ted@zulip.com",
        "group-pm-with:bob@zulip.com",
        "group-pm-with:ted@zulip.com",
    ];

    assert.deepEqual(suggestions.strings, expected);

    const describe = (q) => suggestions.lookup_table.get(q).description;

    assert.equal(
        describe("pm-with:ted@zulip.com"),
        "Private messages with <strong>Te</strong>d Smith &lt;<strong>te</strong>d@zulip.com&gt;",
    );
    assert.equal(
        describe("sender:ted@zulip.com"),
        "Sent by <strong>Te</strong>d Smith &lt;<strong>te</strong>d@zulip.com&gt;",
    );

    suggestions = get_suggestions("", "Ted "); // note space
    expected = [
        "Ted",
        "sender:ted@zulip.com",
        "pm-with:ted@zulip.com",
        "group-pm-with:ted@zulip.com",
    ];

    assert.deepEqual(suggestions.strings, expected);

    query = "sender:ted sm";
    let base_query = "";
    expected = ["sender:ted+sm", "sender:ted@zulip.com"];
    suggestions = get_suggestions(base_query, query);
    assert.deepEqual(suggestions.strings, expected);

    query = "new";
    base_query = "sender:ted@zulip.com";
    expected = ["new"];
    suggestions = get_suggestions(base_query, query);
    assert.deepEqual(suggestions.strings, expected);

    query = "sender:ted@tulip.com new";
    base_query = "";
    expected = ["sender:ted@tulip.com+new"];
    suggestions = get_suggestions(base_query, query);
    assert.deepEqual(suggestions.strings, expected);

    query = "new";
    base_query = "sender:ted@tulip.com";
    expected = ["new"];
    suggestions = get_suggestions(base_query, query);
    assert.deepEqual(suggestions.strings, expected);
});

run_test("people_suggestion (Admin only email visibility)", () => {
    /* Suggestions when realm_email_address_visibility is set to admin
    only */
    people_suggestion_setup();
    const query = "te";
    page_params.is_admin = false;
    const suggestions = get_suggestions("", query);
    const expected = [
        "te",
        "sender:bob@zulip.com",
        "sender:ted@zulip.com",
        "pm-with:bob@zulip.com", // bob térry
        "pm-with:ted@zulip.com",
        "group-pm-with:bob@zulip.com",
        "group-pm-with:ted@zulip.com",
    ];

    assert.deepEqual(suggestions.strings, expected);

    const describe = (q) => suggestions.lookup_table.get(q).description;

    assert.equal(
        describe("pm-with:ted@zulip.com"),
        "Private messages with <strong>Te</strong>d Smith",
    );
    assert.equal(describe("sender:ted@zulip.com"), "Sent by <strong>Te</strong>d Smith");
});

run_test("operator_suggestions", () => {
    // Completed operator should return nothing
    let query = "stream:";
    let suggestions = get_suggestions("", query);
    let expected = ["stream:"];
    assert.deepEqual(suggestions.strings, expected);

    query = "st";
    suggestions = get_suggestions("", query);
    expected = ["st", "streams:public", "is:starred", "stream:"];
    assert.deepEqual(suggestions.strings, expected);

    query = "group-";
    suggestions = get_suggestions("", query);
    expected = ["group-", "group-pm-with:"];
    assert.deepEqual(suggestions.strings, expected);

    query = "-s";
    suggestions = get_suggestions("", query);
    expected = ["-s", "-streams:public", "-sender:myself@zulip.com", "-stream:", "-sender:"];
    assert.deepEqual(suggestions.strings, expected);

    query = "-f";
    const base_query = "stream:Denmark is:alerted";
    suggestions = get_suggestions(base_query, query);
    expected = ["-f", "-from:myself@zulip.com", "-from:"];
    assert.deepEqual(suggestions.strings, expected);
});

run_test("queries_with_spaces", () => {
    global.stream_data.subscribed_streams = function () {
        return ["office", "dev help"];
    };

    global.narrow_state.stream = function () {
        return;
    };

    stream_topic_history.reset();

    // test allowing spaces with quotes surrounding operand
    let query = 'stream:"dev he"';
    let suggestions = get_suggestions("", query);
    let expected = ["stream:dev+he", "stream:dev+help"];
    assert.deepEqual(suggestions.strings, expected);

    // test mismatched quote
    query = 'stream:"dev h';
    suggestions = get_suggestions("", query);
    expected = ["stream:dev+h", "stream:dev+help"];
    assert.deepEqual(suggestions.strings, expected);

    // test extra space after operator still works
    query = "stream: offi";
    suggestions = get_suggestions("", query);
    expected = ["stream:offi", "stream:office"];
    assert.deepEqual(suggestions.strings, expected);
});

// When input search query contains multiple operators
// and a pill hasn't been formed from those operators.
run_test("multiple_operators_without_pills", () => {
    let query = "is:private al";
    let base_query = "";
    let suggestions = get_suggestions(base_query, query);
    let expected = [
        "is:private al",
        "is:private is:alerted",
        "is:private sender:alice@zulip.com",
        "is:private pm-with:alice@zulip.com",
        "is:private group-pm-with:alice@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = "abc is:alerted sender:ted@zulip.com";
    base_query = "";
    suggestions = get_suggestions(base_query, query);
    expected = ["is:alerted sender:ted@zulip.com abc"];
    assert.deepEqual(suggestions.strings, expected);
});
