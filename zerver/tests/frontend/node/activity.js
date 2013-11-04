var assert = require('assert');

add_dependencies({
    _: 'third/underscore/underscore.js',
    util: 'js/util.js',
    Dict: 'js/dict.js'
});

set_global('$', function () {
    return {
        on: function () {
            return;
        }
    };
});

set_global('document', {
    hasFocus: function () {
        return true;
    }
});

set_global('people_dict', new global.Dict.from({
    'alice@zulip.com': {
        full_name: 'Alice Smith'
    },
    'fred@zulip.com': {
        full_name: "Fred Flintstone"
    },
    'jill@zulip.com': {
        full_name: 'Jill Hill'
    },
    'mark@zulip.com': {
        full_name: 'Marky Mark'
    }
}));

var activity = require('js/activity.js');

(function test_sort_users() {
    var users = ['alice@zulip.com', 'fred@zulip.com', 'jill@zulip.com'];

    var user_info = {
        'alice@zulip.com': 'inactive',
        'fred@zulip.com': 'active',
        'jill@zulip.com': 'active'
    };

    activity._sort_users(users, user_info);

    assert.deepEqual(users, [
        'fred@zulip.com',
        'jill@zulip.com',
        'alice@zulip.com'
    ]);
}());

(function test_process_loaded_messages() {

    var huddle1 = 'bar@zulip.com,foo@zulip.com';
    var timestamp1 = 1382479029; // older

    var huddle2 = 'alice@zulip.com,bob@zulip.com';
    var timestamp2 = 1382479033; // newer

    var old_timestamp = 1382479000;

    var messages = [
        {
            type: 'private',
            reply_to: huddle1,
            timestamp: timestamp1
        },
        {
            type: 'stream'
        },
        {
            type: 'private',
            reply_to: 'ignore@zulip.com'
        },
        {
            type: 'private',
            reply_to: huddle2,
            timestamp: timestamp2
        },
        {
            type: 'private',
            reply_to: huddle2,
            timestamp: old_timestamp
        }
    ];

    activity.process_loaded_messages(messages);

    assert.deepEqual(activity.get_huddles(), [huddle2, huddle1]);
}());

(function test_full_huddle_name() {
    assert.equal(
        activity.full_huddle_name('alice@zulip.com,jill@zulip.com'),
        'Alice Smith, Jill Hill'
    );

    assert.equal(
        activity.full_huddle_name('alice@zulip.com,fred@zulip.com,jill@zulip.com'),
        'Alice Smith, Fred Flintstone, Jill Hill'
    );
}());

(function test_short_huddle_name() {
    assert.equal(
        activity.short_huddle_name('alice@zulip.com'),
        'Alice Smith'
    );

    assert.equal(
        activity.short_huddle_name('alice@zulip.com,jill@zulip.com'),
        'Alice Smith, Jill Hill'
    );

    assert.equal(
        activity.short_huddle_name('alice@zulip.com,fred@zulip.com,jill@zulip.com'),
        'Alice Smith, Fred Flintstone, + 1 other'
    );

    assert.equal(
        activity.short_huddle_name('alice@zulip.com,fred@zulip.com,jill@zulip.com,mark@zulip.com'),
        'Alice Smith, Fred Flintstone, + 2 others'
    );
}());

(function test_huddle_fraction_present() {
    var huddle = 'alice@zulip.com,fred@zulip.com,jill@zulip.com,mark@zulip.com';

    var presence_list = {
        'alice@zulip.com': 'active',
        'fred@zulip.com': 'idle', // counts as present
        // jill not in list
        'mark@zulip.com': 'offline' // does not count
    };

    assert.equal(
        activity.huddle_fraction_present(huddle, presence_list),
        '0.50'
    );
}());

