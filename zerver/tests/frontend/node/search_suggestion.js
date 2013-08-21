// Unit test the search_suggestion.js module.
//
// These tests are framework-free and run sequentially; they are invoked
// immediately after being defined.  The contract here is that tests should
// clean up after themselves, and they should explicitly stub all
// dependencies.

var assert = require('assert');
var clean_up;

add_dependencies({
    _: 'third/underscore/underscore.js',
    util: 'js/util.js',
    Dict: 'js/dict.js',
    Handlebars: 'handlebars',
    Filter: 'js/filter.js',
    typeahead_helper: 'js/typeahead_helper.js',
    stream_data: 'js/stream_data.js',
    narrow: 'js/narrow.js'
});

function set_up_dependencies() {
    var search = require('js/search_suggestion.js');

    set_global('page_params', {
        email: 'bob@zulip.com'
    });
    set_global('recent_subjects', new global.Dict({fold_case: true}));

    var narrow = global.narrow;
    var stream_data = global.stream_data;

    var narrow_stream = narrow.stream;
    var stream_data_subscribed_streams = stream_data.subscribed_streams;
    clean_up = function () {
        narrow.stream = narrow_stream;
        stream_data.subscribed_streams = stream_data_subscribed_streams;
        delete global.recent_subjects;
    };

    return search;
}

var search = set_up_dependencies();

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
    assert.equal(describe('sender:bob@zulip.com'), 'Sent by me');
    assert.equal(describe('stream:devel'), 'Narrow to stream <strong>devel</strong>');
}());

(function test_topic_suggestions() {
    var query = 'te';

    global.stream_data.subscribed_streams = function () {
        return ['office'];
    };

    global.narrow.stream = function () {
        return 'office';
    };

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
        "stream:office topic:team",
        "stream:office topic:test"
    ];

    assert.deepEqual(suggestions.strings, expected);

    function describe(q) {
        return suggestions.lookup_table[q].description;
    }
    assert.equal(describe('te'), "Search for te");
    assert.equal(describe('stream:office topic:team'), "Narrow to office > team");

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
        "pm-with:ted@zulip.com",
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

clean_up();

