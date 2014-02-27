set_global('$', function () {
    return {
        on: function () {
            return;
        }
    };
});
$.fn = {};

add_dependencies({
    util: 'js/util.js',
    people: 'js/people.js'
});

set_global('document', {
    hasFocus: function () {
        return true;
    }
});

var people = require("js/people.js");
people.test_set_people_dict({
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
    },
    'norbert@zulip.com': {
        full_name: 'Norbert Oswald'
    }
});

var activity = require('js/activity.js');

(function test_sort_users() {
    var users = ['alice@zulip.com', 'fred@zulip.com', 'jill@zulip.com'];

    var user_info = {
        'alice@zulip.com': {status: 'inactive'},
        'fred@zulip.com': {status: 'active'},
        'jill@zulip.com': {status: 'active'}
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
        'Alice Smith, Fred Flintstone, Jill Hill'
    );

    assert.equal(
        activity.short_huddle_name('alice@zulip.com,fred@zulip.com,jill@zulip.com,mark@zulip.com'),
        'Alice Smith, Fred Flintstone, Jill Hill, + 1 other'
    );

    assert.equal(
        activity.short_huddle_name('alice@zulip.com,fred@zulip.com,jill@zulip.com,mark@zulip.com,norbert@zulip.com'),
        'Alice Smith, Fred Flintstone, Jill Hill, + 2 others'
    );

}());

(function test_huddle_fraction_present() {
    var huddle = 'alice@zulip.com,fred@zulip.com,jill@zulip.com,mark@zulip.com';

    var presence_list = {
        'alice@zulip.com': {status: 'active'},
        'fred@zulip.com': {status: 'idle'}, // counts as present
        // jill not in list
        'mark@zulip.com': {status: 'offline'} // does not count
    };

    assert.equal(
        activity.huddle_fraction_present(huddle, presence_list),
        '0.50'
    );
}());


(function test_on_mobile_property() {
    var base_time = 500;
    var presence = {
        website: {
            status: "active",
            timestamp: base_time
        }
    };
    var status = activity._status_from_timestamp(
        base_time + activity._OFFLINE_THRESHOLD_SECS - 1, presence
    );
    assert.equal(status.mobile, false);

    presence.Android = {
        status: "active",
        timestamp: base_time + activity._OFFLINE_THRESHOLD_SECS / 2,
        pushable: false
    };
    status = activity._status_from_timestamp(
        base_time + activity._OFFLINE_THRESHOLD_SECS, presence
    );
    assert.equal(status.mobile, true);
    assert.equal(status.status, "active");

    status = activity._status_from_timestamp(
        base_time + activity._OFFLINE_THRESHOLD_SECS - 1, presence
    );
    assert.equal(status.mobile, false);
    assert.equal(status.status, "active");

    status = activity._status_from_timestamp(
        base_time + activity._OFFLINE_THRESHOLD_SECS * 2, presence
    );
    assert.equal(status.mobile, false);
    assert.equal(status.status, "offline");

    presence.Android = {
        status: "idle",
        timestamp: base_time + activity._OFFLINE_THRESHOLD_SECS / 2,
        pushable: true
    };
    status = activity._status_from_timestamp(
        base_time + activity._OFFLINE_THRESHOLD_SECS, presence
    );
    assert.equal(status.mobile, true);
    assert.equal(status.status, "idle");

    status = activity._status_from_timestamp(
        base_time + activity._OFFLINE_THRESHOLD_SECS - 1, presence
    );
    assert.equal(status.mobile, false);
    assert.equal(status.status, "active");

    status = activity._status_from_timestamp(
        base_time + activity._OFFLINE_THRESHOLD_SECS * 2, presence
    );
    assert.equal(status.mobile, true);
    assert.equal(status.status, "offline");

}());
