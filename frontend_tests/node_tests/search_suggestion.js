set_global('page_params', {
    search_pills_enabled: true,
});
zrequire('util');
zrequire('typeahead_helper');
zrequire('Handlebars', 'handlebars');
zrequire('Filter', 'js/filter');
zrequire('narrow_state');
zrequire('stream_data');
zrequire('topic_data');
zrequire('people');
zrequire('unread');
zrequire('common');
var search = zrequire('search_suggestion');

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

run_test('basic_get_suggestions', () => {
    var query = 'fred';

    global.stream_data.subscribed_streams = function () {
        return [];
    };

    global.narrow_state.stream = function () {
        return 'office';
    };

    var suggestions = search.get_suggestions('', query);

    var expected = [
        'fred',
    ];
    assert.deepEqual(suggestions.strings, expected);
});

run_test('subset_suggestions', () => {
    var query = 'shakespeare';
    var base_query = 'stream:Denmark topic:Hamlet';

    global.stream_data.subscribed_streams = function () {
        return [];
    };

    global.narrow_state.stream = function () {
        return;
    };

    var suggestions = search.get_suggestions(base_query, query);

    var expected = [
        "shakespeare",
    ];

    assert.deepEqual(suggestions.strings, expected);
});

run_test('private_suggestions', () => {
    global.stream_data.subscribed_streams = function () {
        return [];
    };

    global.narrow_state.stream = function () {
        return;
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
    var suggestions = search.get_suggestions('', query);
    var expected = [
        "is:private",
        "pm-with:alice@zulip.com",
        "pm-with:bob@zulip.com",
        "pm-with:ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'al';
    var base_query = 'is:private';
    suggestions = search.get_suggestions(base_query, query);
    expected = [
        "al",
        "is:alerted",
        "sender:alice@zulip.com",
        "pm-with:alice@zulip.com",
        "group-pm-with:alice@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'pm-with:t';
    suggestions = search.get_suggestions('', query);
    expected = [
        "pm-with:t",
        "pm-with:ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = '-pm-with:t';
    suggestions = search.get_suggestions('', query);
    expected = [
        "-pm-with:t",
        "is:private -pm-with:ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'pm-with:ted@zulip.com';
    suggestions = search.get_suggestions('', query);
    expected = [
        "pm-with:ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'sender:ted';
    suggestions = search.get_suggestions('', query);
    expected = [
        "sender:ted",
        "sender:ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'sender:te';
    suggestions = search.get_suggestions('', query);
    expected = [
        "sender:te",
        "sender:ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = '-sender:te';
    suggestions = search.get_suggestions('', query);
    expected = [
        "-sender:te",
        "-sender:ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'sender:ted@zulip.com';
    suggestions = search.get_suggestions('', query);
    expected = [
        "sender:ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'from:ted';
    base_query = 'is:unread';
    suggestions = search.get_suggestions(base_query, query);
    expected = [
        "from:ted",
        "from:ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);


    // Users can enter bizarre queries, and if they do, we want to
    // be conservative with suggestions.
    query = 'near:3';
    base_query = 'is:private';
    suggestions = search.get_suggestions(base_query, query);
    expected = [
        "near:3",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'near:3';
    base_query = 'pm-with:ted@zulip.com';
    suggestions = search.get_suggestions(base_query, query);
    expected = [
        "near:3",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // Make sure suggestions still work if preceding tokens
    query = 'sender:ted@zulip.com';
    base_query = 'is:alerted';
    suggestions = search.get_suggestions(base_query, query);
    expected = [
        "sender:ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'al';
    base_query = 'is:starred has:link is:private';
    suggestions = search.get_suggestions(base_query, query);
    expected = [
        "al",
        "is:alerted",
        "sender:alice@zulip.com",
        "pm-with:alice@zulip.com",
        "group-pm-with:alice@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // Make sure it handles past context correctly
    query = 'pm-with:';
    base_query = 'stream:Denmark';
    suggestions = search.get_suggestions(base_query, query);
    expected = [
        'pm-with:',
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'sender:';
    base_query = 'sender:ted@zulip.com';
    suggestions = search.get_suggestions(base_query, query);
    expected = [
        'sender:',
    ];
    assert.deepEqual(suggestions.strings, expected);
});

run_test('group_suggestions', () => {
    global.stream_data.subscribed_streams = function () {
        return [];
    };

    global.narrow_state.stream = function () {
        return;
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
    var suggestions = search.get_suggestions('', query);
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
    suggestions = search.get_suggestions('', query);
    expected = [
        "pm-with:bob@zulip.com,t",
        "pm-with:bob@zulip.com,ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // Smit should also generate ted@zulip.com (Ted Smith) as a suggestion.
    query = 'pm-with:bob@zulip.com,Smit';
    suggestions = search.get_suggestions('', query);
    expected = [
        "pm-with:bob@zulip.com,Smit",
        "pm-with:bob@zulip.com,ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // Do not suggest "bob@zulip.com" (the name of the current user)
    query = 'pm-with:ted@zulip.com,bo';
    suggestions = search.get_suggestions('', query);
    expected = [
        "pm-with:ted@zulip.com,bo",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // No superfluous suggestions should be generated.
    query = 'pm-with:bob@zulip.com,red';
    suggestions = search.get_suggestions('', query);
    expected = [
        "pm-with:bob@zulip.com,red",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // is:private should be properly prepended to each suggestion if the pm-with
    // operator is negated.

    query = '-pm-with:bob@zulip.com,';
    suggestions = search.get_suggestions('', query);
    expected = [
        "-pm-with:bob@zulip.com,",
        "is:private -pm-with:bob@zulip.com,alice@zulip.com",
        "is:private -pm-with:bob@zulip.com,jeff@zulip.com",
        "is:private -pm-with:bob@zulip.com,ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = '-pm-with:bob@zulip.com,t';
    suggestions = search.get_suggestions('', query);
    expected = [
        "-pm-with:bob@zulip.com,t",
        "is:private -pm-with:bob@zulip.com,ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = '-pm-with:bob@zulip.com,Smit';
    suggestions = search.get_suggestions('', query);
    expected = [
        "-pm-with:bob@zulip.com,Smit",
        "is:private -pm-with:bob@zulip.com,ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = '-pm-with:bob@zulip.com,red';
    suggestions = search.get_suggestions('', query);
    expected = [
        "-pm-with:bob@zulip.com,red",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // Test multiple operators
    query = 'pm-with:bob@zulip.com,Smit';
    var base_query = 'is:starred has:link';
    suggestions = search.get_suggestions(base_query, query);
    expected = [
        "pm-with:bob@zulip.com,Smit",
        "pm-with:bob@zulip.com,ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'pm-with:bob@zulip.com,Smit';
    base_query = 'stream:Denmark has:link';
    suggestions = search.get_suggestions(base_query, query);
    expected = [
        "pm-with:bob@zulip.com,Smit",
    ];
    assert.deepEqual(suggestions.strings, expected);

    set_global('activity', {
        get_huddles: function () {
            return ['101,42', '101,103,42'];
        },
    });

    // Simulate a past huddle which should now prioritize ted over alice
    query = 'pm-with:bob@zulip.com,';
    suggestions = search.get_suggestions('', query);
    expected = [
        "pm-with:bob@zulip.com,",
        "pm-with:bob@zulip.com,ted@zulip.com",
        "pm-with:bob@zulip.com,alice@zulip.com",
        "pm-with:bob@zulip.com,jeff@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // bob,ted,jeff is already an existing huddle, so prioritize this one
    query = 'pm-with:bob@zulip.com,ted@zulip.com,';
    suggestions = search.get_suggestions('', query);
    expected = [
        "pm-with:bob@zulip.com,ted@zulip.com,",
        "pm-with:bob@zulip.com,ted@zulip.com,jeff@zulip.com",
        "pm-with:bob@zulip.com,ted@zulip.com,alice@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // bob,ted,jeff is already an existing huddle, but if we start with just bob,
    // then don't prioritize ted over alice because it doesn't complete the full huddle.
    query = 'pm-with:jeff@zulip.com,';
    suggestions = search.get_suggestions('', query);
    expected = [
        "pm-with:jeff@zulip.com,",
        "pm-with:jeff@zulip.com,alice@zulip.com",
        "pm-with:jeff@zulip.com,ted@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);
});

init();

run_test('empty_query_suggestions', () => {
    var query = '';

    global.stream_data.subscribed_streams = function () {
        return ['devel', 'office'];
    };

    global.narrow_state.stream = function () {
        return;
    };

    var suggestions = search.get_suggestions('', query);

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
        'has:link',
        'has:image',
        'has:attachment',
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
    assert.equal(describe('has:link'), 'Messages with one or more link');
    assert.equal(describe('has:image'), 'Messages with one or more image');
    assert.equal(describe('has:attachment'), 'Messages with one or more attachment');
});

run_test('has_suggestions', () => {
    // Checks that category wise suggestions are displayed instead of a single
    // default suggestion when suggesting `has` operator.
    var query = 'h';
    global.stream_data.subscribed_streams = function () {
        return ['devel', 'office'];
    };
    global.narrow_state.stream = function () {
        return;
    };

    var suggestions = search.get_suggestions('', query);
    var expected = [
        "h",
        'has:link',
        'has:image',
        'has:attachment',
    ];
    assert.deepEqual(suggestions.strings, expected);

    function describe(q) {
        return suggestions.lookup_table[q].description;
    }

    assert.equal(describe('has:link'), 'Messages with one or more link');
    assert.equal(describe('has:image'), 'Messages with one or more image');
    assert.equal(describe('has:attachment'), 'Messages with one or more attachment');

    query = '-h';
    suggestions = search.get_suggestions('', query);
    expected = [
        "-h",
        '-has:link',
        '-has:image',
        '-has:attachment',
    ];
    assert.deepEqual(suggestions.strings, expected);
    assert.equal(describe('-has:link'), 'Exclude messages with one or more link');
    assert.equal(describe('-has:image'), 'Exclude messages with one or more image');
    assert.equal(describe('-has:attachment'), 'Exclude messages with one or more attachment');

    // operand suggestions follow.

    query = 'has:';
    suggestions = search.get_suggestions('', query);
    expected = [
        'has:link',
        'has:image',
        'has:attachment',
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'has:im';
    suggestions = search.get_suggestions('', query);
    expected = [
        'has:image',
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = '-has:im';
    suggestions = search.get_suggestions('', query);
    expected = [
        '-has:image',
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'att';
    suggestions = search.get_suggestions('', query);
    expected = [
        'att',
        'has:attachment',
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'has:lin';
    var base_query = 'stream:Denmark is:alerted';
    suggestions = search.get_suggestions(base_query, query);
    expected = [
        'has:link',
    ];
    assert.deepEqual(suggestions.strings, expected);
});

run_test('check_is_suggestions', () => {
    var query = 'i';
    global.stream_data.subscribed_streams = function () {
        return ['devel', 'office'];
    };
    global.narrow_state.stream = function () {
        return;
    };

    var suggestions = search.get_suggestions('', query);
    var expected = [
        'i',
        'is:private',
        'is:starred',
        'is:mentioned',
        'is:alerted',
        'is:unread',
        'has:image',
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

    query = '-i';
    suggestions = search.get_suggestions('', query);
    expected = [
        '-i',
        '-is:private',
        '-is:starred',
        '-is:mentioned',
        '-is:alerted',
        '-is:unread',
    ];
    assert.deepEqual(suggestions.strings, expected);

    assert.equal(describe('-is:private'), 'Exclude private messages');
    assert.equal(describe('-is:starred'), 'Exclude starred messages');
    assert.equal(describe('-is:mentioned'), 'Exclude @-mentions');
    assert.equal(describe('-is:alerted'), 'Exclude alerted messages');
    assert.equal(describe('-is:unread'), 'Exclude unread messages');

    query = '';
    suggestions = search.get_suggestions('', query);
    expected = [
        '',
        'is:private',
        'is:starred',
        'is:mentioned',
        'is:alerted',
        'is:unread',
        'sender:bob@zulip.com',
        'stream:devel',
        'stream:office',
        'has:link',
        'has:image',
        'has:attachment',
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = '';
    var base_query = 'is:private';
    suggestions = search.get_suggestions(base_query, query);
    expected = [
        'is:starred',
        'is:mentioned',
        'is:alerted',
        'is:unread',
        'sender:bob@zulip.com',
        'has:link',
        'has:image',
        'has:attachment',
    ];
    assert.deepEqual(suggestions.strings, expected);

    // operand suggestions follow.

    query = 'is:';
    suggestions = search.get_suggestions('', query);
    expected = [
        'is:private',
        'is:starred',
        'is:mentioned',
        'is:alerted',
        'is:unread',
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'is:st';
    suggestions = search.get_suggestions('', query);
    expected = [
        'is:starred',
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = '-is:st';
    suggestions = search.get_suggestions('', query);
    expected = [
        '-is:starred',
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'st';
    suggestions = search.get_suggestions('', query);
    expected = [
        'st',
        'is:starred',
        'stream:',
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'is:sta';
    base_query = 'stream:Denmark has:link';
    suggestions = search.get_suggestions(base_query, query);
    expected = [
        'is:starred',
    ];
    assert.deepEqual(suggestions.strings, expected);
});

run_test('sent_by_me_suggestions', () => {
    global.stream_data.subscribed_streams = function () {
        return [];
    };

    global.narrow_state.stream = function () {
        return;
    };

    var query = '';
    var suggestions = search.get_suggestions('', query);
    assert(suggestions.strings.indexOf('sender:bob@zulip.com') !== -1);
    assert.equal(suggestions.lookup_table['sender:bob@zulip.com'].description,
                 'Sent by me');

    query = 'sender';
    suggestions = search.get_suggestions('', query);
    var expected = [
        "sender",
        "sender:bob@zulip.com",
        "sender:",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = '-sender';
    suggestions = search.get_suggestions('', query);
    expected = [
        "-sender",
        "-sender:bob@zulip.com",
        "-sender:",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'from';
    suggestions = search.get_suggestions('', query);
    expected = [
        "from",
        "from:bob@zulip.com",
        "from:",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = '-from';
    suggestions = search.get_suggestions('', query);
    expected = [
        "-from",
        "-from:bob@zulip.com",
        "-from:",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'sender:bob@zulip.com';
    suggestions = search.get_suggestions('', query);
    expected = [
        "sender:bob@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'from:bob@zulip.com';
    suggestions = search.get_suggestions('', query);
    expected = [
        "from:bob@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'sent';
    suggestions = search.get_suggestions('', query);
    expected = [
        "sent",
        "sender:bob@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = '-sent';
    suggestions = search.get_suggestions('', query);
    expected = [
        "-sent",
        "-sender:bob@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'sent';
    var base_query = 'stream:Denmark topic:Denmark1';
    suggestions = search.get_suggestions(base_query, query);
    expected = [
        "sent",
        "sender:bob@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'sender:m';
    base_query = 'is:starred';
    suggestions = search.get_suggestions(base_query, query);
    expected = [
        "sender:m",
        "sender:bob@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'sender:';
    base_query = 'is:starred';
    suggestions = search.get_suggestions(base_query, query);
    expected = [
        "sender:",
        "sender:bob@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);
});

run_test('topic_suggestions', () => {
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
    suggestions = search.get_suggestions('', 'te');
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

    suggestions = search.get_suggestions('', 'te');
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
    assert.equal(describe('stream:office topic:team'), "Stream office &gt; team");

    suggestions = search.get_suggestions('topic:staplers',  'stream:office');
    expected = [
        'stream:office',
    ];
    assert.deepEqual(suggestions.strings, expected);

    suggestions = search.get_suggestions('stream:devel', 'topic:');
    expected = [
        'topic:',
        'topic:REXX',
    ];
    assert.deepEqual(suggestions.strings, expected);

    suggestions = search.get_suggestions('stream:devel', '-topic:');
    expected = [
        '-topic:',
        '-topic:REXX',
    ];
    assert.deepEqual(suggestions.strings, expected);

    suggestions = search.get_suggestions('', '-topic:te');
    expected = [
        '-topic:te',
        'stream:office -topic:team',
        'stream:office -topic:test',
    ];
    assert.deepEqual(suggestions.strings, expected);

    suggestions = search.get_suggestions('is:alerted stream:devel is:starred', 'topic:');
    expected = [
        'topic:',
        'topic:REXX',
    ];
    assert.deepEqual(suggestions.strings, expected);

    suggestions = search.get_suggestions('is:private stream:devel', 'topic:');
    expected = [
        'topic:',
    ];
    assert.deepEqual(suggestions.strings, expected);

    suggestions = search.get_suggestions('topic:REXX stream:devel', 'topic:');
    expected = [
        'topic:',
    ];
    assert.deepEqual(suggestions.strings, expected);
});

run_test('whitespace_glitch', () => {
    var query = 'stream:office '; // note trailing space

    global.stream_data.subscribed_streams = function () {
        return ['office'];
    };

    global.narrow_state.stream = function () {
        return;
    };

    topic_data.reset();

    var suggestions = search.get_suggestions('', query);

    var expected = [
        "stream:office",
    ];

    assert.deepEqual(suggestions.strings, expected);
});

run_test('stream_completion', () => {
    global.stream_data.subscribed_streams = function () {
        return ['office', 'dev help'];
    };

    global.narrow_state.stream = function () {
        return;
    };

    topic_data.reset();

    var query = 'stream:of';
    var suggestions = search.get_suggestions('s', query);
    var expected = [
        "stream:of",
        "stream:office",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = '-stream:of';
    suggestions = search.get_suggestions('', query);
    expected = [
        "-stream:of",
        "-stream:office",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'hel';
    suggestions = search.get_suggestions('', query);
    expected = [
        "hel",
        "stream:dev+help",
    ];
    assert.deepEqual(suggestions.strings, expected);
});

run_test('people_suggestions', () => {
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

    var suggestions = search.get_suggestions('', query);

    var expected = [
        "te",
        "sender:bob@zulip.com",
        "sender:ted@zulip.com",
        "pm-with:bob@zulip.com", // bob térry
        "pm-with:ted@zulip.com",
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

    suggestions = search.get_suggestions('', 'Ted '); // note space

    expected = [
        "Ted",
        "sender:ted@zulip.com",
        "pm-with:ted@zulip.com",
        "group-pm-with:ted@zulip.com",
    ];

    assert.deepEqual(suggestions.strings, expected);

    query = 'sender:ted sm';
    var base_query = '';
    expected = [
        'sender:ted+sm',
        'sender:ted@zulip.com',
    ];
    suggestions = search.get_suggestions(base_query, query);
    assert.deepEqual(suggestions.strings, expected);

    query = 'new';
    base_query = 'sender:ted@zulip.com';
    expected = [
        'new',
    ];
    suggestions = search.get_suggestions(base_query, query);
    assert.deepEqual(suggestions.strings, expected);

    query = 'sender:ted@tulip.com new';
    base_query = '';
    expected = [
        'sender:ted@tulip.com+new',
    ];
    suggestions = search.get_suggestions(base_query, query);
    assert.deepEqual(suggestions.strings, expected);

    query = 'new';
    base_query = 'sender:ted@tulip.com';
    expected = [
        'new',
    ];
    suggestions = search.get_suggestions(base_query, query);
    assert.deepEqual(suggestions.strings, expected);
});

run_test('operator_suggestions', () => {
    // Completed operator should return nothing
    var query = 'stream:';
    var suggestions = search.get_suggestions('', query);
    var expected = [
        'stream:',
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'st';
    suggestions = search.get_suggestions('', query);
    expected = [
        'st',
        'is:starred',
        'stream:',
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'group-';
    suggestions = search.get_suggestions('', query);
    expected = [
        'group-',
        'group-pm-with:',
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = '-s';
    suggestions = search.get_suggestions('', query);
    expected = [
        '-s',
        '-sender:bob@zulip.com',
        '-stream:',
        '-sender:',
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = '-f';
    var base_query = 'stream:Denmark is:alerted';
    suggestions = search.get_suggestions(base_query, query);
    expected = [
        '-f',
        '-from:bob@zulip.com',
        '-from:',
    ];
    assert.deepEqual(suggestions.strings, expected);
});

run_test('queries_with_spaces', () => {
    global.stream_data.subscribed_streams = function () {
        return ['office', 'dev help'];
    };

    global.narrow_state.stream = function () {
        return;
    };

    topic_data.reset();

    // test allowing spaces with quotes surrounding operand
    var query = 'stream:"dev he"';
    var suggestions = search.get_suggestions('', query);
    var expected = [
        "stream:dev+he",
        "stream:dev+help",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // test mismatched quote
    query = 'stream:"dev h';
    suggestions = search.get_suggestions('', query);
    expected = [
        "stream:dev+h",
        "stream:dev+help",
    ];
    assert.deepEqual(suggestions.strings, expected);

    // test extra space after operator still works
    query = 'stream: offi';
    suggestions = search.get_suggestions('', query);
    expected = [
        "stream:offi",
        "stream:office",
    ];
    assert.deepEqual(suggestions.strings, expected);
});

// When input search query contains multiple operators
// and a pill hasn't been formed from those operators.
run_test('multiple_operators_without_pills', () => {
    var query = 'is:private al';
    var base_query = '';
    var suggestions = search.get_suggestions(base_query, query);
    var expected = [
        "is:private al",
        "is:private is:alerted",
        "is:private sender:alice@zulip.com",
        "is:private pm-with:alice@zulip.com",
        "is:private group-pm-with:alice@zulip.com",
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'abc is:alerted sender:ted@zulip.com';
    base_query = '';
    suggestions = search.get_suggestions(base_query, query);
    expected = [
        "is:alerted sender:ted@zulip.com abc",
    ];
    assert.deepEqual(suggestions.strings, expected);
});
