global.stub_out_jquery();

set_global('page_params', {
    people_list: []
});

add_dependencies({
    util: 'js/util.js',
    people: 'js/people.js'
});

set_global('resize', {
    resize_page_components: function () {}
});

set_global('document', {
    hasFocus: function () {
        return true;
    }
});

var alice = {
    email: 'alice@zulip.com',
    user_id: 1,
    full_name: 'Alice Smith'
};
var fred = {
    email: 'fred@zulip.com',
    user_id: 2,
    full_name: "Fred Flintstone"
};
var jill = {
    email: 'jill@zulip.com',
    user_id: 3,
    full_name: 'Jill Hill'
};
var mark = {
    email: 'mark@zulip.com',
    user_id: 4,
    full_name: 'Marky Mark'
};
var norbert = {
    email: 'norbert@zulip.com',
    user_id: 5,
    full_name: 'Norbert Oswald'
};

global.people.add(alice);
global.people.add(fred);
global.people.add(jill);
global.people.add(mark);
global.people.add(norbert);


var activity = require('js/activity.js');

activity.update_huddles = function () {};

(function test_sort_users() {
    var user_ids = [alice.user_id, fred.user_id, jill.user_id];

    var user_info = {};
    user_info[alice.user_id] = {status: 'inactive'};
    user_info[fred.user_id] = {status: 'active'};
    user_info[jill.user_id] = {status: 'active'};

    activity._sort_users(user_ids, user_info);

    assert.deepEqual(user_ids, [
        fred.user_id,
        jill.user_id,
        alice.user_id
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

    var presence_list = {};
    presence_list[alice.user_id] = {status: 'active'};
    presence_list[fred.user_id] = {status: 'idle'}; // counts as present
    // jill not in list
    presence_list[mark.user_id] = {status: 'offline'}; // does not count

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
