var assert = require('assert');

add_dependencies({
    _: 'third/underscore/underscore.js',
    util: 'js/util.js',
    Dict: 'js/dict.js'
});

var activity = require('js/activity.js');

(function test_sort_users() {
    var users = ['alice@zulip.com', 'fred@zulip.com', 'jill@zulip.com'];

    var user_info = {
        'alice@zulip.com': 'inactive',
        'fred@zulip.com': 'active',
        'jill@zulip.com': 'active'
    };


    set_global('people_dict', new global.Dict.from({
        'alice@zulip.com': 'Alice Smith',
        'fred@zulip.com': 'Fred Flintstone',
        'jill@zulip.com': 'Jill Hill'
    }));

    activity._sort_users(users, user_info);

    assert.deepEqual(users, [
        'fred@zulip.com',
        'jill@zulip.com',
        'alice@zulip.com'
    ]);
}());
