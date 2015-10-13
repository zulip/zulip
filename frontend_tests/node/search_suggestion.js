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
    stream_data: 'js/stream_data.js',
    narrow: 'js/narrow.js'
});

var search = require('js/search_suggestion.js');

set_global('feature_flags', {
    negated_search: true
});
set_global('page_params', {
    email: 'bob@zulip.com'
});
set_global('recent_subjects', new global.Dict({fold_case: true}));

var stream_data = require('js/stream_data.js');
set_global('stream_data', {
    get_name: stream_data.get_name
});

set_global('narrow', {});

(function test_basic_get_suggestions() {
    var query = 'fred';

    global.stream_data.subscribed_streams = function () {
        return [];
    };

    global.narrow.stream = function () {
        return 'office';
    };

    var suggestions = search.get_suggestions(query);

    var expected = [
        'fred'
    ];
    assert.deepEqual(suggestions.strings, expected);
}());

(function test_subset_suggestions() {
    var query = 'stream:Denmark topic:Hamlet shakespeare';

    global.stream_data.subscribed_streams = function () {
        return [];
    };

    global.narrow.stream = function () {
        return undefined;
    };

    var suggestions = search.get_suggestions(query);

    var expected = [
        "stream:Denmark topic:Hamlet shakespeare",
        "stream:Denmark topic:Hamlet",
        "stream:Denmark"
    ];

    assert.deepEqual(suggestions.strings, expected);
}());

(function test_private_suggestions() {
    global.stream_data.subscribed_streams = function () {
        return [];
    };

    global.narrow.stream = function () {
        return undefined;
    };

    global.page_params.people_list = [
        {
            email: 'ted@zulip.com',
            full_name: 'Ted Smith'
        },
        {
            email: 'alice@zulip.com',
            full_name: 'Alice Ignore'
        }
    ];

    var query = 'is:private';
    var suggestions = search.get_suggestions(query);
    var expected = [
        "is:private",
        "pm-with:alice@zulip.com",
        "pm-with:ted@zulip.com"
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'is:private al';
    suggestions = search.get_suggestions(query);
    expected = [
        "is:private al",
        "pm-with:alice@zulip.com",
        "is:private"
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'pm-with:t';
    suggestions = search.get_suggestions(query);
    expected = [
        "pm-with:t",
        "pm-with:ted@zulip.com",
        "is:private"
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = '-pm-with:t';
    suggestions = search.get_suggestions(query);
    expected = [
        "-pm-with:t",
        "is:private -pm-with:ted@zulip.com",
        "is:private"
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'pm-with:ted@zulip.com';
    suggestions = search.get_suggestions(query);
    expected = [
        "pm-with:ted@zulip.com",
        "is:private"
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'sender:ted';
    suggestions = search.get_suggestions(query);
    expected = [
        "sender:ted",
        "sender:ted@zulip.com",
        "is:private"
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'sender:te';
    suggestions = search.get_suggestions(query);
    expected = [
        "sender:te",
        "sender:ted@zulip.com",
        "is:private"
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = '-sender:te';
    suggestions = search.get_suggestions(query);
    expected = [
        "-sender:te",
        "is:private -sender:ted@zulip.com",
        "is:private"
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'sender:ted@zulip.com';
    suggestions = search.get_suggestions(query);
    expected = [
        "sender:ted@zulip.com",
        "is:private"
    ];
    assert.deepEqual(suggestions.strings, expected);

    // Users can enter bizarre queries, and if they do, we want to
    // be conservative with suggestions.
    query = 'is:private near:3';
    suggestions = search.get_suggestions(query);
    expected = [
        "is:private near:3",
        "is:private"
    ];
    assert.deepEqual(suggestions.strings, expected);

    query = 'pm-with:ted@zulip.com near:3';
    suggestions = search.get_suggestions(query);
    expected = [
        "pm-with:ted@zulip.com near:3",
        "pm-with:ted@zulip.com"
    ];
    assert.deepEqual(suggestions.strings, expected);

    global.page_params.people_list = [];
}());

(function test_empty_query_suggestions() {
    var query = '';

    global.stream_data.subscribed_streams = function () {
        return ['devel', 'office'];
    };

    global.narrow.stream = function () {
        return undefined;
    };

    var suggestions = search.get_suggestions(query);

    var expected = [
        "",
        "in:all",
        "is:private",
        "is:starred",
        "is:mentioned",
        "is:alerted",
        "sender:bob@zulip.com",
        "stream:devel",
        "stream:office"
    ];

    assert.deepEqual(suggestions.strings, expected);

    function describe(q) {
        return suggestions.lookup_table[q].description;
    }
    assert.equal(describe('in:all'), 'All messages');
    assert.equal(describe('is:private'), 'Private messages');
    assert.equal(describe('is:starred'), 'Starred messages');
    assert.equal(describe('is:mentioned'), '@-mentions');
    assert.equal(describe('is:alerted'), 'Alerted messages');
    assert.equal(describe('sender:bob@zulip.com'), 'Sent by me');
    assert.equal(describe('stream:devel'), 'Narrow to stream <strong>devel</strong>');
}());

(function test_topic_suggestions() {
    var suggestions;
    var expected;

    global.stream_data.subscribed_streams = function () {
        return ['office'];
    };

    global.narrow.stream = function () {
        return 'office';
    };

    global.recent_subjects = new global.Dict.from({
        'devel': [
            {subject: 'REXX'}
        ],
        'office': [
            {subject: 'team'},
            {subject: 'ignore'},
            {subject: 'test'}
        ]
    }, {fold_case: true});

    suggestions = search.get_suggestions('te');
    expected = [
        "te",
        "stream:office topic:team",
        "stream:office topic:test"
    ];
    assert.deepEqual(suggestions.strings, expected);

    function describe(q) {
        return suggestions.lookup_table[q].description;
    }
    assert.equal(describe('te'), "Search for te");
    assert.equal(describe('stream:office topic:team'), "Narrow to office > team");

    suggestions = search.get_suggestions('topic:staplers stream:office');
    expected = [
        'topic:staplers stream:office',
        'topic:staplers'
    ];
    assert.deepEqual(suggestions.strings, expected);

    suggestions = search.get_suggestions('stream:devel topic:');
    expected = [
        'stream:devel topic:',
        'stream:devel topic:REXX',
        'stream:devel'
    ];
    assert.deepEqual(suggestions.strings, expected);

    suggestions = search.get_suggestions('stream:devel -topic:');
    expected = [
        'stream:devel -topic:',
        'stream:devel -topic:REXX',
        'stream:devel'
    ];
    assert.deepEqual(suggestions.strings, expected);

    suggestions = search.get_suggestions('-topic:te');
    expected = [
        '-topic:te',
        'stream:office -topic:team',
        'stream:office -topic:test'
    ];
    assert.deepEqual(suggestions.strings, expected);
}());

(function test_whitespace_glitch() {
    var query = 'stream:office '; // note trailing space

    global.stream_data.subscribed_streams = function () {
        return ['office'];
    };

    global.narrow.stream = function () {
        return;
    };

    global.recent_subjects = new global.Dict({fold_case: true});

    var suggestions = search.get_suggestions(query);

    var expected = [
        "stream:office"
    ];

    assert.deepEqual(suggestions.strings, expected);
}());

(function test_stream_completion() {
    var query = 'stream:of';

    global.stream_data.subscribed_streams = function () {
        return ['office'];
    };

    global.narrow.stream = function () {
        return;
    };

    global.recent_subjects = new global.Dict({fold_case: true});

    var suggestions = search.get_suggestions(query);

    var expected = [
        "stream:of",
        "stream:office"
    ];

    assert.deepEqual(suggestions.strings, expected);
}());

(function test_people_suggestions() {
    var query = 'te';

    global.stream_data.subscribed_streams = function () {
        return [];
    };

    global.narrow.stream = function () {
        return;
    };

    global.page_params.people_list = [
        {
            email: 'ted@zulip.com',
            full_name: 'Ted Smith'
        },
        {
            email: 'bob@zulip.com',
            full_name: 'Bob Terry'
        },
        {
            email: 'alice@zulip.com',
            full_name: 'Alice Ignore'
        }
    ];

    global.recent_subjects = new global.Dict.from({
        office: [
            {subject: 'team'},
            {subject: 'ignore'},
            {subject: 'test'}
        ]
    }, {fold_case: true});

    var suggestions = search.get_suggestions(query);

    var expected = [
        "te",
        "pm-with:bob@zulip.com", // bob TErry
        "pm-with:ted@zulip.com",
        "sender:bob@zulip.com",
        "sender:ted@zulip.com"
    ];

    assert.deepEqual(suggestions.strings, expected);
    function describe(q) {
        return suggestions.lookup_table[q].description;
    }
    assert.equal(describe('pm-with:ted@zulip.com'),
        "Narrow to private messages with <strong>Te</strong>d Smith &lt;<strong>te</strong>d@zulip.com&gt;");
    assert.equal(describe('sender:ted@zulip.com'),
        "Narrow to messages sent by <strong>Te</strong>d Smith &lt;<strong>te</strong>d@zulip.com&gt;");

    suggestions = search.get_suggestions('Ted '); // note space

    expected = [
        "Ted",
        "pm-with:ted@zulip.com",
        "sender:ted@zulip.com"
    ];

    assert.deepEqual(suggestions.strings, expected);
}());
