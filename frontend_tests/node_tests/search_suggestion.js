// Unit test the search_suggestion.js module.
//
// These tests are framework-free and run sequentially; they are invoked
// immediately after being defined.  The contract here is that tests should
// clean up after themselves, and they should explicitly stub all
// dependencies.

add_dependencies({
    util: 'js/util.js',
    Handlebars: 'handlebars',
    Filter: 'js/filter.js',
    typeahead_helper: 'js/typeahead_helper.js',
    people: 'js/people.js',
    stream_data: 'js/stream_data.js',
    topic_data: 'js/topic_data.js',
    narrow_state: 'js/narrow_state.js',
});

var people = global.people;

var search = require('js/search_suggestion.js');

var bob = {
    email: 'bob@zulip.com',
    full_name: 'Bob Roberts',
    user_id: 42,
};


function init() {
    people.init();
    people.add(bob);
    people.initialize_current_user(bob.user_id);
}
init();

set_global('narrow', {});

topic_data.reset();

(function test_basic_get_suggestions() {
    var query = 'fred';

    global.stream_data.subscribed_streams = function () {
        return [];
    };

    global.narrow_state.stream = function () {
        return 'office';
    };

    var suggestions = search.get_suggestions(query);

    var expected = [
        'fred',
    ];
    assert.deepEqual(suggestions.strings, expected);
}());

(function test_subset_suggestions() {
    var query = 'stream:Denmark topic:Hamlet shakespeare';

    global.stream_data.subscribed_streams = function () {
        return [];
    };

    global.narrow_state.stream = function () {
        return undefined;
    };

    var suggestions = search.get_suggestions(query);

    var expected = [
        "stream:Denmark topic:Hamlet shakespeare",
        "stream:Denmark topic:Hamlet",
        "stream:Denmark",
    ];

    assert.deepEqual(suggestions.strings, expected);
}());

(function test_private_suggestions() {
    global.stream_data.subscribed_streams = function () {
        return [];
    };

    global.narrow_state.stream = function () {
        return undefined;
    };

    var ted =
    {
        email: 'ted@zulip.com',
        user_id: 101,
        full_name: 'Ted Smith',
    };

    var alice =
    {
        email: 'alice@zulip.com',
        user_id: 102,
        full_name: 'Alice Ignore',
    };

    people.add(ted);
    people.add(alice);

    var query = 'is:private';
    var suggestions = search.get_suggestions(query);
    var expected = [
        "is:private",
        "pm-with:alice@zulip.com",
        "pm-with:bob@zulip.com",
        "pm-with:ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'is:private al';
    suggestions = search.get_suggestions(query);
    expected = [
        "is:private al",
        "is:private is:alerted",
        "is:private pm-with:alice@zulip.com",
        "is:private sender:alice@zulip.com",
        "is:private group-pm-with:alice@zulip.com",
        "is:private",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'pm-with:t';
    suggestions = search.get_suggestions(query);
    expected = [
        "pm-with:t",
        "pm-with:ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = '-pm-with:t';
    suggestions = search.get_suggestions(query);
    expected = [
        "-pm-with:t",
        "is:private -pm-with:ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'pm-with:ted@zulip.com';
    suggestions = search.get_suggestions(query);
    expected = [
        "pm-with:ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'sender:ted';
    suggestions = search.get_suggestions(query);
    expected = [
        "sender:ted",
        "sender:ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'sender:te';
    suggestions = search.get_suggestions(query);
    expected = [
        "sender:te",
        "sender:ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = '-sender:te';
    suggestions = search.get_suggestions(query);
    expected = [
        "-sender:te",
        "-sender:ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'sender:ted@zulip.com';
    suggestions = search.get_suggestions(query);
    expected = [
        "sender:ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'is:unread from:ted';
    suggestions = search.get_suggestions(query);
    expected = [
        "is:unread from:ted",
        "is:unread from:ted@zulip.com",
        "is:unread",
    ];
    assert.deepEqual(suggestions.strings, expected);


    // Users can enter bizarre queries, and if they do, we want to
    // be conservative with suggestions.
    query = 'is:private near:3';
    suggestions = search.get_suggestions(query);
    expected = [
        "is:private near:3",
        "is:private",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'pm-with:ted@zulip.com near:3';
    suggestions = search.get_suggestions(query);
    expected = [
        "pm-with:ted@zulip.com near:3",
        "pm-with:ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // Make sure suggestions still work if preceding tokens
    query = 'is:alerted sender:ted@zulip.com';
    suggestions = search.get_suggestions(query);
    expected = [
        "is:alerted sender:ted@zulip.com",
        "is:alerted",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'is:starred has:link is:private al';
    suggestions = search.get_suggestions(query);
    expected = [
        "is:starred has:link is:private al",
        "is:starred has:link is:private is:alerted",
        "is:starred has:link is:private pm-with:alice@zulip.com",
        "is:starred has:link is:private sender:alice@zulip.com",
        "is:starred has:link is:private group-pm-with:alice@zulip.com",
        "is:starred has:link is:private",
        "is:starred has:link",
        "is:starred",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // Make sure it handles past context correctly
    query = 'stream:Denmark pm-with:';
    suggestions = search.get_suggestions(query);
    expected = [
        'stream:Denmark pm-with:',
        'stream:Denmark',
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'sender:ted@zulip.com sender:';
    suggestions = search.get_suggestions(query);
    expected = [
        'sender:ted@zulip.com sender:',
        'sender:ted@zulip.com',
    ];
    assert.deepEqual(suggestions.strings, expected);
}());

(function test_group_suggestions() {
    global.stream_data.subscribed_streams = function () {
        return [];
    };

    global.narrow_state.stream = function () {
        return undefined;
    };

    set_global('activity', {
            get_huddles: function () {
                return [];
            },
    });

    var ted =
    {
        email: 'ted@zulip.com',
        user_id: 101,
        full_name: 'Ted Smith',
    };

    var alice =
    {
        email: 'alice@zulip.com',
        user_id: 102,
        full_name: 'Alice Ignore',
    };

    var jeff =
    {
        email: 'jeff@zulip.com',
        user_id: 103,
        full_name: 'Jeff Zoolipson',
    };

    people.add(ted);
    people.add(alice);
    people.add(jeff);

    // Entering a comma in a pm-with query should immediately generate
    // suggestions for the next person.
    var query = 'pm-with:bob@zulip.com,';
    var suggestions = search.get_suggestions(query);
    var expected = [
        "pm-with:bob@zulip.com,",
        "pm-with:bob@zulip.com,alice@zulip.com",
        "pm-with:bob@zulip.com,jeff@zulip.com",
        "pm-with:bob@zulip.com,ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // Only the last part of a comma-separated pm-with query should be used to
    // generate suggestions.
    query = 'pm-with:bob@zulip.com,t';
    suggestions = search.get_suggestions(query);
    expected = [
        "pm-with:bob@zulip.com,t",
        "pm-with:bob@zulip.com,ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // Smit should also generate ted@zulip.com (Ted Smith) as a suggestion.
    query = 'pm-with:bob@zulip.com,Smit';
    suggestions = search.get_suggestions(query);
    expected = [
        "pm-with:bob@zulip.com,Smit",
        "pm-with:bob@zulip.com,ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // Do not suggest "bob@zulip.com" (the name of the current user)
    query = 'pm-with:ted@zulip.com,bo';
    suggestions = search.get_suggestions(query);
    expected = [
        "pm-with:ted@zulip.com,bo",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // No superfluous suggestions should be generated.
    query = 'pm-with:bob@zulip.com,red';
    suggestions = search.get_suggestions(query);
    expected = [
        "pm-with:bob@zulip.com,red",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // is:private should be properly prepended to each suggestion if the pm-with
    // operator is negated.

    query = '-pm-with:bob@zulip.com,';
    suggestions = search.get_suggestions(query);
    expected = [
        "-pm-with:bob@zulip.com,",
        "is:private -pm-with:bob@zulip.com,alice@zulip.com",
        "is:private -pm-with:bob@zulip.com,jeff@zulip.com",
        "is:private -pm-with:bob@zulip.com,ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = '-pm-with:bob@zulip.com,t';
    suggestions = search.get_suggestions(query);
    expected = [
        "-pm-with:bob@zulip.com,t",
        "is:private -pm-with:bob@zulip.com,ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = '-pm-with:bob@zulip.com,Smit';
    suggestions = search.get_suggestions(query);
    expected = [
        "-pm-with:bob@zulip.com,Smit",
        "is:private -pm-with:bob@zulip.com,ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = '-pm-with:bob@zulip.com,red';
    suggestions = search.get_suggestions(query);
    expected = [
        "-pm-with:bob@zulip.com,red",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // Test multiple operators
    query = 'is:starred has:link pm-with:bob@zulip.com,Smit';
    suggestions = search.get_suggestions(query);
    expected = [
        "is:starred has:link pm-with:bob@zulip.com,Smit",
        "is:starred has:link pm-with:bob@zulip.com,ted@zulip.com",
        "is:starred has:link",
        "is:starred",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'stream:Denmark has:link pm-with:bob@zulip.com,Smit';
    suggestions = search.get_suggestions(query);
    expected = [
        "stream:Denmark has:link pm-with:bob@zulip.com,Smit",
        "stream:Denmark has:link",
        "stream:Denmark",
    ];
    assert.deepEqual(suggestions.strings, expected);

    set_global('activity', {
            get_huddles: function () {
                return ['101,42', '101,103,42'];
            },
    });

    // Simulate a past huddle which should now prioritize ted over alice
    query = 'pm-with:bob@zulip.com,';
    suggestions = search.get_suggestions(query);
    expected = [
        "pm-with:bob@zulip.com,",
        "pm-with:bob@zulip.com,ted@zulip.com",
        "pm-with:bob@zulip.com,alice@zulip.com",
        "pm-with:bob@zulip.com,jeff@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // bob,ted,jeff is already an existing huddle, so prioritize this one
    query = 'pm-with:bob@zulip.com,ted@zulip.com,';
    suggestions = search.get_suggestions(query);
    expected = [
        "pm-with:bob@zulip.com,ted@zulip.com,",
        "pm-with:bob@zulip.com,ted@zulip.com,jeff@zulip.com",
        "pm-with:bob@zulip.com,ted@zulip.com,alice@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // bob,ted,jeff is already an existing huddle, but if we start with just bob,
    // then don't prioritize ted over alice because it doesn't complete the full huddle.
    query = 'pm-with:jeff@zulip.com,';
    suggestions = search.get_suggestions(query);
    expected = [
        "pm-with:jeff@zulip.com,",
        "pm-with:jeff@zulip.com,alice@zulip.com",
        "pm-with:jeff@zulip.com,ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);
}());

init();

(function test_empty_query_suggestions() {
    var query = '';

    global.stream_data.subscribed_streams = function () {
        return ['devel', 'office'];
    };

    global.narrow_state.stream = function () {
        return undefined;
    };

    var suggestions = search.get_suggestions(query);

    var expected = [
        "",
        "is:private",
        "is:starred",
        "is:mentioned",
        "is:alerted",
        "is:unread",
        "sender:bob@zulip.com",
        "stream:devel",
        "stream:office",
    ];

    assert.deepEqual(suggestions.strings, expected);

    function describe(q) {
        return suggestions.lookup_table[q].description;
    }
    assert.equal(describe('is:private'), 'Private messages');
    assert.equal(describe('is:starred'), 'Starred messages');
    assert.equal(describe('is:mentioned'), '@-mentions');
    assert.equal(describe('is:alerted'), 'Alerted messages');
    assert.equal(describe('is:unread'), 'Unread messages');
    assert.equal(describe('sender:bob@zulip.com'), 'Sent by me');
}());

(function test_sent_by_me_suggestions() {
    global.stream_data.subscribed_streams = function () {
        return [];
    };

    global.narrow_state.stream = function () {
        return undefined;
    };

    var query = '';
    var suggestions = search.get_suggestions(query);
    assert(suggestions.strings.indexOf('sender:bob@zulip.com') !== -1);
    assert.equal(suggestions.lookup_table['sender:bob@zulip.com'].description,
                 'Sent by me');

    query = 'sender';
    suggestions = search.get_suggestions(query);
    var expected = [
        "sender",
        "sender:bob@zulip.com",
        "sender:",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'from';
    suggestions = search.get_suggestions(query);
    expected = [
        "from",
        "from:bob@zulip.com",
        "from:",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'sender:bob@zulip.com';
    suggestions = search.get_suggestions(query);
    expected = [
        "sender:bob@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'from:bob@zulip.com';
    suggestions = search.get_suggestions(query);
    expected = [
        "from:bob@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'sent';
    suggestions = search.get_suggestions(query);
    expected = [
        "sent",
        "sender:bob@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'stream:Denmark topic:Denmark1 sent';
    suggestions = search.get_suggestions(query);
    expected = [
        "stream:Denmark topic:Denmark1 sent",
        "stream:Denmark topic:Denmark1 sender:bob@zulip.com",
        "stream:Denmark topic:Denmark1",
        "stream:Denmark",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'is:starred sender:m';
    suggestions = search.get_suggestions(query);
    expected = [
        "is:starred sender:m",
        "is:starred sender:bob@zulip.com",
        "is:starred",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'sender:alice@zulip.com sender:';
    suggestions = search.get_suggestions(query);
    expected = [
        "sender:alice@zulip.com sender:",
        "sender:alice@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);
}());

(function test_topic_suggestions() {
    var suggestions;
    var expected;

    global.stream_data.subscribed_streams = function () {
        return ['office'];
    };

    global.narrow_state.stream = function () {
        return 'office';
    };

    var devel_id = 44;
    var office_id = 77;

    global.stream_data.get_stream_id = function (stream_name) {
        switch (stream_name) {
            case 'office': return office_id;
            case 'devel': return devel_id;
        }
    };

    topic_data.reset();
    suggestions = search.get_suggestions('te');
    expected = [
        "te",
    ];
    assert.deepEqual(suggestions.strings, expected);

    topic_data.add_message({
        stream_id: devel_id,
        topic_name: 'REXX',
    });

    _.each(['team', 'ignore', 'test'], function (topic_name) {
        topic_data.add_message({
            stream_id: office_id,
            topic_name: topic_name,
        });
    });

    suggestions = search.get_suggestions('te');
    expected = [
        "te",
        "stream:office topic:team",
        "stream:office topic:test",
    ];
    assert.deepEqual(suggestions.strings, expected);

    function describe(q) {
        return suggestions.lookup_table[q].description;
    }
    assert.equal(describe('te'), "Search for te");
    assert.equal(describe('stream:office topic:team'), "Stream office > team");

    suggestions = search.get_suggestions('topic:staplers stream:office');
    expected = [
        'topic:staplers stream:office',
        'topic:staplers',
    ];
    assert.deepEqual(suggestions.strings, expected);

    suggestions = search.get_suggestions('stream:devel topic:');
    expected = [
        'stream:devel topic:',
        'stream:devel topic:REXX',
        'stream:devel',
    ];
    assert.deepEqual(suggestions.strings, expected);

    suggestions = search.get_suggestions('stream:devel -topic:');
    expected = [
        'stream:devel -topic:',
        'stream:devel -topic:REXX',
        'stream:devel',
    ];
    assert.deepEqual(suggestions.strings, expected);

    suggestions = search.get_suggestions('-topic:te');
    expected = [
        '-topic:te',
        'stream:office -topic:team',
        'stream:office -topic:test',
    ];
    assert.deepEqual(suggestions.strings, expected);

    suggestions = search.get_suggestions('is:alerted stream:devel is:starred topic:');
    expected = [
        'is:alerted stream:devel is:starred topic:',
        'is:alerted stream:devel is:starred topic:REXX',
        'is:alerted stream:devel is:starred',
        'is:alerted stream:devel',
        'is:alerted',
    ];
    assert.deepEqual(suggestions.strings, expected);

    suggestions = search.get_suggestions('is:private stream:devel topic:');
    expected = [
        'is:private stream:devel topic:',
        'is:private stream:devel',
        'is:private',
    ];
    assert.deepEqual(suggestions.strings, expected);

    suggestions = search.get_suggestions('topic:REXX stream:devel topic:');
    expected = [
        'topic:REXX stream:devel topic:',
        'topic:REXX stream:devel',
        'topic:REXX',
    ];
    assert.deepEqual(suggestions.strings, expected);
}());

(function test_whitespace_glitch() {
    var query = 'stream:office '; // note trailing space

    global.stream_data.subscribed_streams = function () {
        return ['office'];
    };

    global.narrow_state.stream = function () {
        return;
    };

    topic_data.reset();

    var suggestions = search.get_suggestions(query);

    var expected = [
        "stream:office",
    ];

    assert.deepEqual(suggestions.strings, expected);
}());

(function test_stream_completion() {
    global.stream_data.subscribed_streams = function () {
        return ['office', 'dev help'];
    };

    global.narrow_state.stream = function () {
        return;
    };

    topic_data.reset();

    var query = 'stream:of';
    var suggestions = search.get_suggestions(query);
    var expected = [
        "stream:of",
        "stream:office",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'hel';
    suggestions = search.get_suggestions(query);
    expected = [
        "hel",
        "stream:dev+help",
    ];
    assert.deepEqual(suggestions.strings, expected);
}());

(function test_people_suggestions() {
    var query = 'te';

    global.stream_data.subscribed_streams = function () {
        return [];
    };

    global.narrow_state.stream = function () {
        return;
    };

    var ted = {
        email: 'ted@zulip.com',
        user_id: 201,
        full_name: 'Ted Smith',
    };

    var bob = {
        email: 'bob@zulip.com',
        user_id: 202,
        full_name: 'Bob Térry',
    };

    var alice = {
        email: 'alice@zulip.com',
        user_id: 203,
        full_name: 'Alice Ignore',
    };
    people.add(ted);
    people.add(bob);
    people.add(alice);


    topic_data.reset();

    var suggestions = search.get_suggestions(query);

    var expected = [
        "te",
        "pm-with:bob@zulip.com", // bob térry
        "pm-with:ted@zulip.com",
        "sender:bob@zulip.com",
        "sender:ted@zulip.com",
        "group-pm-with:bob@zulip.com",
        "group-pm-with:ted@zulip.com",
    ];

    assert.deepEqual(suggestions.strings, expected);
    function describe(q) {
        return suggestions.lookup_table[q].description;
    }
    assert.equal(describe('pm-with:ted@zulip.com'),
        "Private messages with <strong>Te</strong>d Smith &lt;<strong>te</strong>d@zulip.com&gt;");
    assert.equal(describe('sender:ted@zulip.com'),
        "Sent by <strong>Te</strong>d Smith &lt;<strong>te</strong>d@zulip.com&gt;");

    suggestions = search.get_suggestions('Ted '); // note space

    expected = [
        "Ted",
        "pm-with:ted@zulip.com",
        "sender:ted@zulip.com",
        "group-pm-with:ted@zulip.com",
    ];

    assert.deepEqual(suggestions.strings, expected);

}());

(function test_contains_suggestions() {
    var query = 'has:';
    var suggestions = search.get_suggestions(query);
    var expected = [
        'has:',
        'has:link',
        'has:image',
        'has:attachment',
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'has:im';
    suggestions = search.get_suggestions(query);
    expected = [
        'has:im',
        'has:image',
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = '-has:im';
    suggestions = search.get_suggestions(query);
    expected = [
        '-has:im',
        '-has:image',
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'att';
    suggestions = search.get_suggestions(query);
    expected = [
        'att',
        'has:attachment',
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'stream:Denmark is:alerted has:lin';
    suggestions = search.get_suggestions(query);
    expected = [
        'stream:Denmark is:alerted has:lin',
        'stream:Denmark is:alerted has:link',
        'stream:Denmark is:alerted',
        'stream:Denmark',
    ];
    assert.deepEqual(suggestions.strings, expected);
}());

(function test_operator_suggestions() {
    // Completed operator should return nothing
    var query = 'stream:';
    var suggestions = search.get_suggestions(query);
    var expected = [
        'stream:',
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'st';
    suggestions = search.get_suggestions(query);
    expected = [
        'st',
        'is:starred',
        'stream:',
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'group-';
    suggestions = search.get_suggestions(query);
    expected = [
        'group-',
        'group-pm-with:',
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = '-s';
    suggestions = search.get_suggestions(query);
    expected = [
        '-s',
        '-stream:',
        '-sender:',
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'stream:Denmark is:alerted -f';
    suggestions = search.get_suggestions(query);
    expected = [
        'stream:Denmark is:alerted -f',
        'stream:Denmark is:alerted -from:',
        'stream:Denmark is:alerted',
        'stream:Denmark',
    ];
    assert.deepEqual(suggestions.strings, expected);
}());

(function test_queries_with_spaces() {
    global.stream_data.subscribed_streams = function () {
        return ['office', 'dev help'];
    };

    global.narrow_state.stream = function () {
        return;
    };

    topic_data.reset();

    // test allowing spaces with quotes surrounding operand
    var query = 'stream:"dev he"';
    var suggestions = search.get_suggestions(query);
    var expected = [
        "stream:dev+he",
        "stream:dev+help",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // test mismatched quote
    query = 'stream:"dev h';
    suggestions = search.get_suggestions(query);
    expected = [
        "stream:dev+h",
        "stream:dev+help",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // test extra space after operator still works
    query = 'stream: offi';
    suggestions = search.get_suggestions(query);
    expected = [
        "stream:offi",
        "stream:office",
    ];
    assert.deepEqual(suggestions.strings, expected);
}());
