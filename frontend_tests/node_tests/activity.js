set_global('$', global.make_zjquery());

set_global('page_params', {
    realm_users: [],
    user_id: 5,
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
    hash_util: 'js/hash_util.js',
    hashchange: 'js/hashchange.js',
    narrow: 'js/narrow.js',
    presence: 'js/presence.js',
    activity: 'js/activity.js',
});

var presence = global.presence;

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

var zoe = {
    email: 'zoe@example.com',
    user_id: 6,
    full_name: 'Zoe Yang',
};

var people = global.people;

people.add_in_realm(alice);
people.add_in_realm(fred);
people.add_in_realm(jill);
people.add_in_realm(mark);
people.add_in_realm(norbert);
people.add_in_realm(zoe);
people.add_in_realm(me);
people.initialize_current_user(me.user_id);

var activity = require('js/activity.js');
var compose_fade = require('js/compose_fade.js');

compose_fade.update_faded_users = function () {};

var real_update_huddles = activity.update_huddles;
activity.update_huddles = function () {};

global.compile_template('user_presence_row');
global.compile_template('user_presence_rows');

var presence_info = {};
presence_info[alice.user_id] = { status: 'inactive' };
presence_info[fred.user_id] = { status: 'active' };
presence_info[jill.user_id] = { status: 'active' };

presence.presence_info = presence_info;

(function test_get_status() {
    assert.equal(presence.get_status(page_params.user_id), "active");
    assert.equal(presence.get_status(alice.user_id), "inactive");
    assert.equal(presence.get_status(fred.user_id), "active");
}());

(function test_sort_users() {
    var user_ids = [alice.user_id, fred.user_id, jill.user_id];

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
    presence.presence_info = presence_info;

    assert.equal(
        activity.huddle_fraction_present(huddle),
        '0.50');
}());

presence.presence_info = {};
presence.presence_info[alice.user_id] = { status: activity.IDLE };
presence.presence_info[fred.user_id] = { status: activity.ACTIVE };
presence.presence_info[jill.user_id] = { status: activity.ACTIVE };
presence.presence_info[mark.user_id] = { status: activity.IDLE };
presence.presence_info[norbert.user_id] = { status: activity.ACTIVE };

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

(function test_PM_update_dom_counts() {
    var value = $('alice-value');
    var count = $('alice-count');
    var pm_key = alice.user_id.toString();
    var li = $("li.user_sidebar_entry[data-user-id='" + pm_key + "']");
    count.add_child('.value', value);
    li.add_child('.count', count);

    var counts = new Dict();
    counts.set(pm_key, 5);
    li.addClass('user_sidebar_entry');

    activity.update_dom_with_unread_counts({pm_count: counts});
    assert(li.hasClass('user-with-count'));
    assert.equal(value.text(), 5);

    counts.set(pm_key, 0);

    activity.update_dom_with_unread_counts({pm_count: counts});
    assert(!li.hasClass('user-with-count'));
    assert.equal(value.text(), '');
}());

(function test_group_update_dom_counts() {
    var value = $('alice-fred-value');
    var count = $('alice-fred-count');
    var pm_key = alice.user_id.toString() + "," + fred.user_id.toString();
    var li_selector = "li.group-pms-sidebar-entry[data-user-ids='" + pm_key + "']";
    var li = $(li_selector);
    count.add_child('.value', value);
    li.add_child('.count', count);

    var counts = new Dict();
    counts.set(pm_key, 5);
    li.addClass('group-pms-sidebar-entry');

    activity.update_dom_with_unread_counts({pm_count: counts});
    assert(li.hasClass('group-with-count'));
    assert.equal(value.text(), 5);

    counts.set(pm_key, 0);

    activity.update_dom_with_unread_counts({pm_count: counts});
    assert(!li.hasClass('group-with-count'));
    assert.equal(value.text(), '');
}());

presence.presence_info = {};
presence.presence_info[alice.user_id] = { status: activity.ACTIVE };
presence.presence_info[fred.user_id] = { status: activity.ACTIVE };
presence.presence_info[jill.user_id] = { status: activity.ACTIVE };

(function test_filter_user_ids() {
    var user_filter = $('.user-list-filter');
    user_filter.val(''); // no search filter

    var user_ids = activity._filter_and_sort([alice.user_id, fred.user_id]);
    assert.deepEqual(user_ids, [alice.user_id, fred.user_id]);

    user_filter.val('abc'); // no match
    user_ids = activity._filter_and_sort([alice.user_id, fred.user_id]);
    assert.deepEqual(user_ids, []);

    user_filter.val('fred'); // match fred
    user_ids = activity._filter_and_sort([alice.user_id, fred.user_id]);
    assert.deepEqual(user_ids, [fred.user_id]);

    user_filter.val('fred,alice'); // match fred and alice
    user_ids = activity._filter_and_sort([alice.user_id, fred.user_id]);
    assert.deepEqual(user_ids, [alice.user_id, fred.user_id]);

    user_filter.val('fr,al'); // match fred and alice partials
    user_ids = activity._filter_and_sort([alice.user_id, fred.user_id]);
    assert.deepEqual(user_ids, [alice.user_id, fred.user_id]);

    presence.presence_info[alice.user_id] = { status: activity.IDLE };
    user_filter.val('fr,al'); // match fred and alice partials and idle user
    user_ids = activity._filter_and_sort([alice.user_id, fred.user_id]);
    assert.deepEqual(user_ids, [fred.user_id, alice.user_id]);

    $.stub_selector('.user-list-filter', []);
    presence.presence_info[alice.user_id] = { status: activity.ACTIVE };
    user_ids = activity._filter_and_sort([alice.user_id, fred.user_id]);
    assert.deepEqual(user_ids, [alice.user_id, fred.user_id]);
}());

(function test_insert_one_user_into_empty_list() {
    var alice_li = $('alice-li');

    // These selectors are here to avoid some short-circuit logic.
    $('#user_presences').add_child('[data-user-id="1"]', alice_li);

    var appended_html;
    $('#user_presences').append = function (html) {
        appended_html = html;
    };

    $.stub_selector('#user_presences li', {
        toArray: function () {
            return [];
        },
    });
    activity.insert_user_into_list(alice.user_id);
    assert(appended_html.indexOf('data-user-id="1"') > 0);
    assert(appended_html.indexOf('user_active') > 0);
}());

(function test_insert_fred_after_alice() {
    var fred_li = $('fred-li');

    // These selectors are here to avoid some short-circuit logic.
    $('#user_presences').add_child('[data-user-id="2"]', fred_li);

    var appended_html;
    $('#user_presences').append = function (html) {
        appended_html = html;
    };

    $('fake-dom-for-alice').attr = function (attr_name) {
        assert.equal(attr_name, 'data-user-id');
        return alice.user_id;
    };

    $.stub_selector('#user_presences li', {
        toArray: function () {
            return [
                'fake-dom-for-alice',
            ];
        },
    });
    activity.insert_user_into_list(fred.user_id);

    assert(appended_html.indexOf('data-user-id="2"') > 0);
    assert(appended_html.indexOf('user_active') > 0);
}());

(function test_insert_fred_before_jill() {
    var fred_li = $('fred-li');

    // These selectors are here to avoid some short-circuit logic.
    $('#user_presences').add_child('[data-user-id="2"]', fred_li);

    $('fake-dom-for-jill').attr = function (attr_name) {
        assert.equal(attr_name, 'data-user-id');
        return jill.user_id;
    };

    $.stub_selector('#user_presences li', {
        toArray: function () {
            return [
                'fake-dom-for-jill',
            ];
        },
    });

    var before_html;
    $('fake-dom-for-jill').before = function (html) {
        before_html = html;
    };
    activity.insert_user_into_list(fred.user_id);

    assert(before_html.indexOf('data-user-id="2"') > 0);
    assert(before_html.indexOf('user_active') > 0);
}());

// Reset jquery here.
set_global('$', global.make_zjquery());

(function test_insert_unfiltered_user_with_filter() {
    // This test only tests that we do not explode when
    // try to insert Fred into a list where he does not
    // match the search filter.
    var user_filter = $('.user-list-filter');
    user_filter.val('do-not-match-filter');
    activity.insert_user_into_list(fred.user_id);
}());

(function test_realm_presence_disabled() {
    page_params.realm_presence_disabled = true;

    activity.insert_user_into_list();
    activity.build_user_sidebar();

    real_update_huddles();
}());

