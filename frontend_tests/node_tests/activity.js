global.stub_out_jquery();

set_global('page_params', {
    people_list: [],
});

set_global('feature_flags', {});

set_global('document', {
    hasFocus: function () {
        return true;
    },
});

add_dependencies({
    Handlebars: 'handlebars',
    templates: 'js/templates',
    util: 'js/util.js',
    compose_fade: 'js/compose_fade.js',
    people: 'js/people.js',
    unread: 'js/unread.js',
    hashchange: 'js/hashchange.js',
    narrow: 'js/narrow.js',
    activity: 'js/activity.js',
});

set_global('resize', {
    resize_page_components: function () {},
});

var me = {
    email: 'me@zulip.com',
    user_id: 999,
    full_name: 'Me Myself',
};

var alice = {
    email: 'alice@zulip.com',
    user_id: 1,
    full_name: 'Alice Smith',
};
var fred = {
    email: 'fred@zulip.com',
    user_id: 2,
    full_name: "Fred Flintstone",
};
var jill = {
    email: 'jill@zulip.com',
    user_id: 3,
    full_name: 'Jill Hill',
};
var mark = {
    email: 'mark@zulip.com',
    user_id: 4,
    full_name: 'Marky Mark',
};
var norbert = {
    email: 'norbert@zulip.com',
    user_id: 5,
    full_name: 'Norbert Oswald',
};

global.people.add(alice);
global.people.add(fred);
global.people.add(jill);
global.people.add(mark);
global.people.add(norbert);
global.people.add(me);
global.people.initialize_current_user(me.user_id);

var people = global.people;

var activity = require('js/activity.js');
var compose_fade = require('js/compose_fade.js');
var jsdom = require('jsdom');
var window = jsdom.jsdom().defaultView;

global.$ = require('jquery')(window);
$.fn.expectOne = function () {
    assert(this.length === 1);
    return this;
};

compose_fade.update_faded_users = function () {};
activity.update_huddles = function () {};

global.compile_template('user_presence_row');
global.compile_template('user_presence_rows');

(function test_sort_users() {
    var user_ids = [alice.user_id, fred.user_id, jill.user_id];

    var presence_info = {};
    presence_info[alice.user_id] = { status: 'inactive' };
    presence_info[fred.user_id] = { status: 'active' };
    presence_info[jill.user_id] = { status: 'active' };

    activity.presence_info = presence_info;
    activity._sort_users(user_ids);

    assert.deepEqual(user_ids, [
        fred.user_id,
        jill.user_id,
        alice.user_id,
    ]);
}());

(function test_process_loaded_messages() {

    var huddle1 = 'jill@zulip.com,norbert@zulip.com';
    var timestamp1 = 1382479029; // older

    var huddle2 = 'alice@zulip.com,fred@zulip.com';
    var timestamp2 = 1382479033; // newer

    var old_timestamp = 1382479000;

    var messages = [
        {
            type: 'private',
            display_recipient: [{id: jill.user_id}, {id: norbert.user_id}],
            timestamp: timestamp1,
        },
        {
            type: 'stream',
        },
        {
            type: 'private',
            display_recipient: [{id: me.user_id}], // PM to myself
        },
        {
            type: 'private',
            display_recipient: [{id: alice.user_id}, {id: fred.user_id}],
            timestamp: timestamp2,
        },
        {
            type: 'private',
            display_recipient: [{id: fred.user_id}, {id: alice.user_id}],
            timestamp: old_timestamp,
        },
    ];

    activity.process_loaded_messages(messages);

    var user_ids_string1 = people.emails_strings_to_user_ids_string(huddle1);
    var user_ids_string2 = people.emails_strings_to_user_ids_string(huddle2);
    assert.deepEqual(activity.get_huddles(), [user_ids_string2, user_ids_string1]);
}());

(function test_full_huddle_name() {
    function full_name(emails_string) {
        var user_ids_string = people.emails_strings_to_user_ids_string(emails_string);
        return activity.full_huddle_name(user_ids_string);
    }

    assert.equal(
        full_name('alice@zulip.com,jill@zulip.com'),
        'Alice Smith, Jill Hill');

    assert.equal(
        full_name('alice@zulip.com,fred@zulip.com,jill@zulip.com'),
        'Alice Smith, Fred Flintstone, Jill Hill');
}());

(function test_short_huddle_name() {
    function short_name(emails_string) {
        var user_ids_string = people.emails_strings_to_user_ids_string(emails_string);
        return activity.short_huddle_name(user_ids_string);
    }

    assert.equal(
        short_name('alice@zulip.com'),
        'Alice Smith');

    assert.equal(
        short_name('alice@zulip.com,jill@zulip.com'),
        'Alice Smith, Jill Hill');

    assert.equal(
        short_name('alice@zulip.com,fred@zulip.com,jill@zulip.com'),
        'Alice Smith, Fred Flintstone, Jill Hill');

    assert.equal(
        short_name('alice@zulip.com,fred@zulip.com,jill@zulip.com,mark@zulip.com'),
        'Alice Smith, Fred Flintstone, Jill Hill, + 1 other');

    assert.equal(
        short_name('alice@zulip.com,fred@zulip.com,jill@zulip.com,mark@zulip.com,norbert@zulip.com'),
        'Alice Smith, Fred Flintstone, Jill Hill, + 2 others');

}());

(function test_huddle_fraction_present() {
    var huddle = 'alice@zulip.com,fred@zulip.com,jill@zulip.com,mark@zulip.com';
    huddle = people.emails_strings_to_user_ids_string(huddle);

    var presence_info = {};
    presence_info[alice.user_id] = { status: 'active' };
    presence_info[fred.user_id] = { status: 'idle' }; // counts as present
    // jill not in list
    presence_info[mark.user_id] = { status: 'offline' }; // does not count
    activity.presence_info = presence_info;

    assert.equal(
        activity.huddle_fraction_present(huddle),
        '0.50');
}());


(function test_on_mobile_property() {
    var base_time = 500;
    var presence = {
        website: {
            status: "active",
            timestamp: base_time,
        },
    };
    var status = activity._status_from_timestamp(
        base_time + activity._OFFLINE_THRESHOLD_SECS - 1, presence);
    assert.equal(status.mobile, false);

    presence.Android = {
        status: "active",
        timestamp: base_time + activity._OFFLINE_THRESHOLD_SECS / 2,
        pushable: false,
    };
    status = activity._status_from_timestamp(
        base_time + activity._OFFLINE_THRESHOLD_SECS, presence);
    assert.equal(status.mobile, true);
    assert.equal(status.status, "active");

    status = activity._status_from_timestamp(
        base_time + activity._OFFLINE_THRESHOLD_SECS - 1, presence);
    assert.equal(status.mobile, false);
    assert.equal(status.status, "active");

    status = activity._status_from_timestamp(
        base_time + activity._OFFLINE_THRESHOLD_SECS * 2, presence);
    assert.equal(status.mobile, false);
    assert.equal(status.status, "offline");

    presence.Android = {
        status: "idle",
        timestamp: base_time + activity._OFFLINE_THRESHOLD_SECS / 2,
        pushable: true,
    };
    status = activity._status_from_timestamp(
        base_time + activity._OFFLINE_THRESHOLD_SECS, presence);
    assert.equal(status.mobile, true);
    assert.equal(status.status, "idle");

    status = activity._status_from_timestamp(
        base_time + activity._OFFLINE_THRESHOLD_SECS - 1, presence);
    assert.equal(status.mobile, false);
    assert.equal(status.status, "active");

    status = activity._status_from_timestamp(
        base_time + activity._OFFLINE_THRESHOLD_SECS * 2, presence);
    assert.equal(status.mobile, true);
    assert.equal(status.status, "offline");

}());

(function test_set_presence_info() {
    var presences = {};
    var base_time = 500;

    presences[alice.email] = {
        website: {
            status: 'active',
            timestamp: base_time,
        },
    };

    presences[fred.email] = {
        website: {
            status: 'idle',
            timestamp: base_time,
        },
    };

    activity.set_presence_info(presences, base_time);

    assert.deepEqual(activity.presence_info[alice.user_id],
        { status: 'active', mobile: false}
    );

    assert.deepEqual(activity.presence_info[fred.user_id],
        { status: 'idle', mobile: false}
    );
}());

activity.presence_info = {};
activity.presence_info[alice.user_id] = { status: activity.IDLE };
activity.presence_info[fred.user_id] = { status: activity.ACTIVE };
activity.presence_info[jill.user_id] = { status: activity.ACTIVE };
activity.presence_info[mark.user_id] = { status: activity.IDLE };
activity.presence_info[norbert.user_id] = { status: activity.ACTIVE };

(function test_presence_list_full_update() {
    var users = activity.build_user_sidebar();
    assert.deepEqual(users, [{
            name: 'Fred Flintstone',
            href: '#narrow/pm-with/2-fred',
            user_id: fred.user_id,
            num_unread: 0,
            type: 'active',
            type_desc: 'is active',
            mobile: undefined,
        },
        {
            name: 'Jill Hill',
            href: '#narrow/pm-with/3-jill',
            user_id: jill.user_id,
            num_unread: 0,
            type: 'active',
            type_desc: 'is active',
            mobile: undefined,
        },
        {
            name: 'Norbert Oswald',
            href: '#narrow/pm-with/5-norbert',
            user_id: norbert.user_id,
            num_unread: 0,
            type: 'active',
            type_desc: 'is active',
            mobile: undefined,
        },
        {
            name: 'Alice Smith',
            href: '#narrow/pm-with/1-alice',
            user_id: alice.user_id,
            num_unread: 0,
            type: 'idle',
            type_desc: 'is not active',
            mobile: undefined,
        },
        {
            name: 'Marky Mark',
            href: '#narrow/pm-with/4-mark',
            user_id: mark.user_id,
            num_unread: 0,
            type: 'idle',
            type_desc: 'is not active',
            mobile: undefined,
        },
    ]);
}());

