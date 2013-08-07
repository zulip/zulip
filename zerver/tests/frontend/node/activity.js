var assert = require('assert');

(function set_up_dependencies () {
    global._ = require('third/underscore/underscore.js');
    global.activity = require('js/activity.js');
    global.util = require('js/util.js');
    global.Dict = require('js/dict.js');
}());

var activity = global.activity;

(function test_sort_users() {
    var users = ['alice@zulip.com', 'fred@zulip.com', 'jill@zulip.com'];

    var user_info = {
        'alice@zulip.com': 'inactive',
        'fred@zulip.com': 'active',
        'jill@zulip.com': 'active'
    };


    global.people_dict = new global.Dict({
        'alice@zulip.com': 'Alice Smith',
        'fred@zulip.com': 'Fred Flintstone',
        'jill@zulip.com': 'Jill Hill'
    });

    activity._sort_users(users, user_info);

    assert.deepEqual(users, [
        'fred@zulip.com',
        'jill@zulip.com',
        'alice@zulip.com'
    ]);
}());
