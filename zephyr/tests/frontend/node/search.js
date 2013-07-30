// Unit test the search.js module.
//
// These tests are framework-free and run sequentially; they are invoked
// immediately after being defined.  The contract here is that tests should
// clean up after themselves, and they should explicitly stub all
// dependencies.

var assert = require('assert');

function set_up_dependencies() {
    var _ = global._ = require('third/underscore/underscore.js');
    global.Handlebars = require('handlebars');

    // We stub out most of jQuery, which is irrelevant to most of these tests.
    var $ = function () {};
    global.$ = $;
    $.each = function (it, cb) {
        var cb2 = function (a, b) { return cb(b,a); };
        return _.each(it, cb2);
    };
    $.map = _.map;
    $.grep = _.filter;

    var actual_narrow = require('js/narrow.js');
    var search = require('js/search.js');

    global.narrow = {
        parse: actual_narrow.parse,
        unparse: actual_narrow.unparse,
        canonicalize_operator: actual_narrow.canonicalize_operator,
        Filter: actual_narrow.Filter
    };

    global.page_params = {
        email: 'bob@zulip.com'
    };

    global.subs = {
        canonicalized_name: function (name) { return name; }
    };

    global.typeahead_helper = require('js/typeahead_helper.js');

    global.recent_subjects = {};

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
        'fred',
        ''
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
}());

(function test_topic_suggestions() {
    var query = 'te';

    global.subs.subscribed_streams = function () {
        return ['office'];
    };

    global.narrow.stream = function () {
        return 'office';
    };

    global.recent_subjects = {
        office: [
            {subject: 'team'},
            {subject: 'ignore'},
            {subject: 'test'}
        ]
    };

    var suggestions = search.get_suggestions(query);

    var expected = [
        "te",
        "stream:office topic:team",
        "stream:office topic:test",
        ""
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

    global.recent_subjects = {
        office: [
            {subject: 'team'},
            {subject: 'ignore'},
            {subject: 'test'}
        ]
    };

    var suggestions = search.get_suggestions(query);

    var expected = [
        "te",
        "pm-with:ted@zulip.com",
        "sender:ted@zulip.com",
        ""
    ];

    assert.deepEqual(suggestions.strings, expected);
}());
