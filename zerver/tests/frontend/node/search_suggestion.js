// Unit test the search_suggestion.js module.
//
// These tests are framework-free and run sequentially; they are invoked
// immediately after being defined.  The contract here is that tests should
// clean up after themselves, and they should explicitly stub all
// dependencies.

var assert = require('assert');

function set_up_dependencies() {
    var _ = global._ = require('third/underscore/underscore.js');
    global.Handlebars = require('handlebars');

    var actual_narrow = require('js/narrow.js');
    var search = require('js/search_suggestion.js');
    global.narrow = require('js/narrow.js');

    global.page_params = {
        email: 'bob@zulip.com'
    };

    global.subs = {
        canonicalized_name: function (name) { return name; }
    };

    global.typeahead_helper = require('js/typeahead_helper.js');

    global.util = require('js/util.js');
    global.Dict = require('js/dict.js');
    global.recent_subjects = new global.Dict();

    global.Filter = require('js/filter.js');

    return search;
}

var search = set_up_dependencies();

(function test_basic_get_suggestions() {
    var query = 'fred';

    global.subs.subscribed_streams = function () {
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

    global.subs.subscribed_streams = function () {
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

    global.subs.subscribed_streams = function () {
        return ['office'];
    };

    global.narrow.stream = function () {
        return 'office';
    };

    global.recent_subjects = new global.Dict({
        office: [
            {subject: 'team'},
            {subject: 'ignore'},
            {subject: 'test'}
        ]
    });

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

    global.subs.subscribed_streams = function () {
        return ['office'];
    };

    global.narrow.stream = function () {
        return;
    };

    global.recent_subjects = new global.Dict();

    var suggestions = search.get_suggestions(query);

    var expected = [
        "stream:office"
    ];

    assert.deepEqual(suggestions.strings, expected);
}());

(function test_people_suggestions() {
    var query = 'te';

    global.subs.subscribed_streams = function () {
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

    global.recent_subjects = new global.Dict({
        office: [
            {subject: 'team'},
            {subject: 'ignore'},
            {subject: 'test'}
        ]
    });

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
