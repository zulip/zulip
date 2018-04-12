set_global('$', global.make_zjquery());

set_global('page_params', {
    realm_users: [],
    user_id: 999,
});

set_global('ui', {
    set_up_scrollbar: function () {},
});

set_global('feature_flags', {});

set_global('document', {
    hasFocus: function () {
        return true;
    },
});

set_global('blueslip', function () {});
set_global('channel', {});
set_global('compose_actions', {});

set_global('ui', {
    set_up_scrollbar: function () {},
    update_scrollbar: function () {},
});

zrequire('compose_fade');
zrequire('Handlebars', 'handlebars');
zrequire('templates');
zrequire('unread');
zrequire('hash_util');
zrequire('hashchange');
zrequire('narrow');
zrequire('util');
zrequire('presence');
zrequire('people');
zrequire('activity');
zrequire('stream_list');

set_global('blueslip', {
    log: () => {},
});

set_global('popovers', {
    hide_all: function () {},
    show_userlist_sidebar: function () {
        $('.column-right').addClass('expanded');
    },
});

set_global('stream_popover', {
    show_streamlist_sidebar: function () {
        $('.column-left').addClass('expanded');
    },
});


set_global('reload', {
    is_in_progress: () => false,
});
set_global('resize', {
    resize_page_components: () => {},
});
set_global('window', 'window-stub');

const me = {
    email: 'me@zulip.com',
    user_id: 999,
    full_name: 'Me Myself',
};

const alice = {
    email: 'alice@zulip.com',
    user_id: 1,
    full_name: 'Alice Smith',
};
const fred = {
    email: 'fred@zulip.com',
    user_id: 2,
    full_name: "Fred Flintstone",
};
const jill = {
    email: 'jill@zulip.com',
    user_id: 3,
    full_name: 'Jill Hill',
};
const mark = {
    email: 'mark@zulip.com',
    user_id: 4,
    full_name: 'Marky Mark',
};
const norbert = {
    email: 'norbert@zulip.com',
    user_id: 5,
    full_name: 'Norbert Oswald',
};

const zoe = {
    email: 'zoe@example.com',
    user_id: 6,
    full_name: 'Zoe Yang',
};

const people = global.people;

people.add_in_realm(alice);
people.add_in_realm(fred);
people.add_in_realm(jill);
people.add_in_realm(mark);
people.add_in_realm(norbert);
people.add_in_realm(zoe);
people.add_in_realm(me);
people.initialize_current_user(me.user_id);

compose_fade.update_faded_users = () => {};

const real_update_huddles = activity.update_huddles;
activity.update_huddles = () => {};

global.compile_template('user_presence_row');
global.compile_template('user_presence_rows');
global.compile_template('group_pms');

const presence_info = {};
presence_info[alice.user_id] = { status: 'inactive' };
presence_info[fred.user_id] = { status: 'active' };
presence_info[jill.user_id] = { status: 'active' };

presence.presence_info = presence_info;

(function test_get_status() {
    assert.equal(presence.get_status(page_params.user_id), "active");
    assert.equal(presence.get_status(alice.user_id), "inactive");
    assert.equal(presence.get_status(fred.user_id), "active");
    assert.equal(presence.get_status(zoe.user_id), "offline");
}());

(function test_reload_defaults() {
    var warned;

    blueslip.warn = function (msg) {
        assert.equal(msg, 'get_filter_text() is called before initialization');
        warned = true;
    };
    assert.equal(activity.get_filter_text(), '');
    assert(warned);
}());

(function test_sort_users() {
    const user_ids = [alice.user_id, fred.user_id, jill.user_id];

    activity._sort_users(user_ids);

    assert.deepEqual(user_ids, [
        fred.user_id,
        jill.user_id,
        alice.user_id,
    ]);
}());

(function test_process_loaded_messages() {

    const huddle1 = 'jill@zulip.com,norbert@zulip.com';
    const timestamp1 = 1382479029; // older

    const huddle2 = 'alice@zulip.com,fred@zulip.com';
    const timestamp2 = 1382479033; // newer

    const old_timestamp = 1382479000;

    const messages = [
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

    const user_ids_string1 = people.emails_strings_to_user_ids_string(huddle1);
    const user_ids_string2 = people.emails_strings_to_user_ids_string(huddle2);
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

    const presence_info = {};
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
presence.presence_info[zoe.user_id] = { status: activity.ACTIVE };
presence.presence_info[me.user_id] = { status: activity.ACTIVE };

activity.set_user_list_filter();

const user_order = [fred.user_id, jill.user_id, norbert.user_id,
                     zoe.user_id, alice.user_id, mark.user_id];
const user_count = 6;

// Mock the jquery is func
$('.user-list-filter').is = function (sel) {
    if (sel === ':focus') {
        return $('.user-list-filter').is_focused();
    }
};

// Mock the jquery first func
$('#user_presences li.user_sidebar_entry.narrow-filter').first = function () {
    return $('li.user_sidebar_entry[data-user-id="' + user_order[0] + '"]');
};
$('#user_presences li.user_sidebar_entry.narrow-filter').last = function () {
    return $('li.user_sidebar_entry[data-user-id="' + user_order[user_count - 1] + '"]');
};

(function test_presence_list_full_update() {
    // No element is selected
    $('#user_presences li.user_sidebar_entry.narrow-filter.highlighted_user').length = 0;
    $('.user-list-filter').focus();

    $('#user_presences li.user_sidebar_entry.narrow-filter');
    const users = activity.build_user_sidebar();
    assert.deepEqual(users, [{
            name: 'Fred Flintstone',
            href: '#narrow/pm-with/2-fred',
            user_id: fred.user_id,
            num_unread: 0,
            type: 'active',
            type_desc: 'is active',
        },
        {
            name: 'Jill Hill',
            href: '#narrow/pm-with/3-jill',
            user_id: jill.user_id,
            num_unread: 0,
            type: 'active',
            type_desc: 'is active',
        },
        {
            name: 'Norbert Oswald',
            href: '#narrow/pm-with/5-norbert',
            user_id: norbert.user_id,
            num_unread: 0,
            type: 'active',
            type_desc: 'is active',
        },
        {
            name: 'Zoe Yang',
            href: '#narrow/pm-with/6-zoe',
            user_id: zoe.user_id,
            num_unread: 0,
            type: 'active',
            type_desc: 'is active',
        },
        {
            name: 'Alice Smith',
            href: '#narrow/pm-with/1-alice',
            user_id: alice.user_id,
            num_unread: 0,
            type: 'idle',
            type_desc: 'is not active',
        },
        {
            name: 'Marky Mark',
            href: '#narrow/pm-with/4-mark',
            user_id: mark.user_id,
            num_unread: 0,
            type: 'idle',
            type_desc: 'is not active',
        },
    ]);
}());

(function test_PM_update_dom_counts() {
    const value = $.create('alice-value');
    const count = $.create('alice-count');
    const pm_key = alice.user_id.toString();
    const li = $("li.user_sidebar_entry[data-user-id='" + pm_key + "']");
    count.set_find_results('.value', value);
    li.set_find_results('.count', count);
    count.set_parent(li);

    const counts = new Dict();
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
    const value = $.create('alice-fred-value');
    const count = $.create('alice-fred-count');
    const pm_key = alice.user_id.toString() + "," + fred.user_id.toString();
    const li_selector = "li.group-pms-sidebar-entry[data-user-ids='" + pm_key + "']";
    const li = $(li_selector);
    count.set_find_results('.value', value);
    li.set_find_results('.count', count);
    count.set_parent(li);

    const counts = new Dict();
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

(function test_key_input() {
    var sel_index = 0;
    // Returns which element is selected
    $('#user_presences li.user_sidebar_entry.narrow-filter.highlighted_user')
        .expectOne().attr = function () {
            return user_order[sel_index];
        };

    // Returns element before selected one
    $('#user_presences li.user_sidebar_entry.narrow-filter.highlighted_user')
        .expectOne().prev = function () {
            if (sel_index === 0) {
                // Top, no prev element
                return $('div.no_user');
            }
            return $('li.user_sidebar_entry[data-user-id="' + user_order[sel_index-1] + '"]');
        };

    // Returns element after selected one
    $('#user_presences li.user_sidebar_entry.narrow-filter.highlighted_user')
        .expectOne().next = function () {
            if (sel_index === user_count - 1) {
                // Bottom, no next element
                return $('div.no_user');
            }
            return $('li.user_sidebar_entry[data-user-id="' + user_order[sel_index + 1] + '"]');
        };

    $('li.user_sidebar_entry[data-user-id="' + fred.user_id + '"]').is = function () {
            return true;
    };
    $('li.user_sidebar_entry[data-user-id="' + mark.user_id + '"]').is = function () {
            return true;
    };
    $('li.user_sidebar_entry[data-user-id="' + alice.user_id + '"]').is = function () {
            return true;
    };
    $('div.no_user').is = function () {
        return false;
    };

    $('#user_presences li.user_sidebar_entry.narrow-filter').length = user_count;

    activity.set_user_list_filter_handlers();

    // Disable scrolling into place
    stream_list.scroll_element_into_container = function () {};
    // up
    const e = {
        keyCode: 38,
        stopPropagation: function () {},
        preventDefault: function () {},
    };
    const keydown_handler = $('.user-list-filter').get_on_handler('keydown');
    keydown_handler(e);
    // Now the last element is selected
    sel_index = user_count - 1;
    keydown_handler(e);
    sel_index = sel_index - 1;

    // down
    e.keyCode = 40;
    keydown_handler(e);
    sel_index = sel_index + 1;
    keydown_handler(e);

    e.keyCode = 13;

    // Enter text and narrow users
    $(".user-list-filter").expectOne().val('ali');
    narrow.by = function (method, email) {
      assert.equal(email, 'alice@zulip.com');
    };
    compose_actions.start = function () {};
    sel_index = 4;

    keydown_handler(e);
}());

(function test_focus_user_filter() {
    const e = {
        stopPropagation: () => {},
    };
    var click_handler = $('.user-list-filter').get_on_handler('click');
    click_handler(e);
}());

(function test_focusout_user_filter() {
    const e = { };
    const click_handler = $('.user-list-filter').get_on_handler('blur');
    click_handler(e);
}());

presence.presence_info = {};
presence.presence_info[alice.user_id] = { status: activity.ACTIVE };
presence.presence_info[fred.user_id] = { status: activity.ACTIVE };
presence.presence_info[jill.user_id] = { status: activity.ACTIVE };
presence.presence_info[mark.user_id] = { status: activity.IDLE };
presence.presence_info[norbert.user_id] = { status: activity.ACTIVE };
presence.presence_info[zoe.user_id] = { status: activity.ACTIVE };

(function test_filter_user_ids() {
    const user_filter = $('.user-list-filter');
    user_filter.val(''); // no search filter

    activity.set_user_list_filter();

    var user_ids = activity.get_filtered_and_sorted_user_ids();
    assert.deepEqual(user_ids, [
        alice.user_id,
        fred.user_id,
        jill.user_id,
        norbert.user_id,
        zoe.user_id,
        mark.user_id,
    ]);

    user_filter.val('abc'); // no match
    user_ids = activity.get_filtered_and_sorted_user_ids();
    assert.deepEqual(user_ids, []);

    user_filter.val('fred'); // match fred
    user_ids = activity.get_filtered_and_sorted_user_ids();
    assert.deepEqual(user_ids, [fred.user_id]);

    user_filter.val('fred,alice'); // match fred and alice
    user_ids = activity.get_filtered_and_sorted_user_ids();
    assert.deepEqual(user_ids, [alice.user_id, fred.user_id]);

    user_filter.val('fr,al'); // match fred and alice partials
    user_ids = activity.get_filtered_and_sorted_user_ids();
    assert.deepEqual(user_ids, [alice.user_id, fred.user_id]);

    presence.presence_info[alice.user_id] = { status: activity.IDLE };
    user_filter.val('fr,al'); // match fred and alice partials and idle user
    user_ids = activity.get_filtered_and_sorted_user_ids();
    assert.deepEqual(user_ids, [fred.user_id, alice.user_id]);

    $.stub_selector('.user-list-filter', []);
    presence.presence_info[alice.user_id] = { status: activity.ACTIVE };
    user_ids = activity.get_filtered_and_sorted_user_ids();
    assert.deepEqual(user_ids, [alice.user_id, fred.user_id]);
}());

(function test_insert_one_user_into_empty_list() {
    const alice_li = $.create('alice list item');

    // These selectors are here to avoid some short-circuit logic.
    $('#user_presences').set_find_results('[data-user-id="1"]', alice_li);

    var appended_html;
    $('#user_presences').append = function (html) {
        appended_html = html;
    };

    $.stub_selector('#user_presences li', {
        toArray: () => [],
    });
    activity.insert_user_into_list(alice.user_id);
    assert(appended_html.indexOf('data-user-id="1"') > 0);
    assert(appended_html.indexOf('user_active') > 0);
}());

(function test_insert_fred_after_alice() {
    const fred_li = $.create('fred list item');

    // These selectors are here to avoid some short-circuit logic.
    $('#user_presences').set_find_results('[data-user-id="2"]', fred_li);

    var appended_html;
    $('#user_presences').append = function (html) {
        appended_html = html;
    };

    $('<fake html for alice>').attr = function (attr_name) {
        assert.equal(attr_name, 'data-user-id');
        return alice.user_id;
    };

    $.stub_selector('#user_presences li', {
        toArray: function () {
            return [
                '<fake html for alice>',
            ];
        },
    });
    activity.insert_user_into_list(fred.user_id);

    assert(appended_html.indexOf('data-user-id="2"') > 0);
    assert(appended_html.indexOf('user_active') > 0);
}());

(function test_insert_fred_before_jill() {
    const fred_li = $.create('fred-li');

    // These selectors are here to avoid some short-circuit logic.
    $('#user_presences').set_find_results('[data-user-id="2"]', fred_li);

    $('<fake-dom-for-jill').attr = function (attr_name) {
        assert.equal(attr_name, 'data-user-id');
        return jill.user_id;
    };

    $.stub_selector('#user_presences li', {
        toArray: function () {
            return [
                '<fake-dom-for-jill',
            ];
        },
    });

    var before_html;
    $('<fake-dom-for-jill').before = function (html) {
        before_html = html;
    };
    activity.insert_user_into_list(fred.user_id);

    assert(before_html.indexOf('data-user-id="2"') > 0);
    assert(before_html.indexOf('user_active') > 0);
}());

// Reset jquery here.
set_global('$', global.make_zjquery());
activity.set_user_list_filter();

(function test_insert_unfiltered_user_with_filter() {
    // This test only tests that we do not explode when
    // try to insert Fred into a list where he does not
    // match the search filter.
    const user_filter = $('.user-list-filter');
    user_filter.val('do-not-match-filter');
    activity.insert_user_into_list(fred.user_id);
}());

(function test_realm_presence_disabled() {
    page_params.realm_presence_disabled = true;
    unread.suppress_unread_counts = false;

    activity.insert_user_into_list();
    activity.build_user_sidebar();

    real_update_huddles();
}());

// Mock the jquery is func
$('.user-list-filter').is = function (sel) {
    if (sel === ':focus') {
        return $('.user-list-filter').is_focused();
    }
};

$('.user-list-filter').parent = function () {
    return $('#user-list .input-append');
};

(function test_clear_search() {
    $('.user-list-filter').val('somevalue');
    activity.clear_search();
    assert.equal($('.user-list-filter').val(), '');
    activity.clear_search();
    assert($('#user-list .input-append').hasClass('notdisplayed'));
}());

(function test_escape_search() {
    $('.user-list-filter').val('somevalue');
    activity.escape_search();
    assert.equal($('.user-list-filter').val(), '');
    activity.escape_search();
    assert($('#user-list .input-append').hasClass('notdisplayed'));
}());

(function test_initiate_search() {
    $('.user-list-filter').blur();
    $('.user-list-filter').closest = function (selector) {
        assert.equal(selector, ".app-main [class^='column-']");
        return $.create('right-sidebar').addClass('column-right');
    };
    activity.initiate_search();
    assert.equal($('.column-right').hasClass('expanded'), true);
    assert.equal($('.user-list-filter').is_focused(), true);
    $('.user-list-filter').closest = function (selector) {
        assert.equal(selector, ".app-main [class^='column-']");
        return $.create('left-sidebar').addClass('column-left');
    };
    activity.initiate_search();
    assert.equal($('.column-left').hasClass('expanded'), true);
    assert.equal($('.user-list-filter').is_focused(), true);
}());

(function test_toggle_filter_display() {
    activity.toggle_filter_displayed();
    assert($('#user-list .input-append').hasClass('notdisplayed'));
    $('.user-list-filter').closest = function (selector) {
        assert.equal(selector, ".app-main [class^='column-']");
        return $.create('sidebar').addClass('column-right');
    };
    activity.toggle_filter_displayed();
    assert.equal($('#user-list .input-append').hasClass('notdisplayed'), false);
}());

(function test_searching() {
    $('.user-list-filter').focus();
    assert.equal(activity.searching(), true);
    $('.user-list-filter').blur();
    assert.equal(activity.searching(), false);
}());

(function test_update_huddles_and_redraw() {
    const value = $.create('alice-fred-value');
    const count = $.create('alice-fred-count');
    const pm_key = alice.user_id.toString() + "," + fred.user_id.toString();
    const li_selector = "li.group-pms-sidebar-entry[data-user-ids='" + pm_key + "']";
    const li = $(li_selector);
    count.set_find_results('.value', value);
    li.set_find_results('.count', count);
    count.set_parent(li);

    const real_get_huddles = activity.get_huddles;
    activity.get_huddles = () => ['1,2'];
    activity.update_huddles = real_update_huddles;
    activity.redraw();
    assert.equal($('#group-pm-list').hasClass('show'), false);
    page_params.realm_presence_disabled = false;
    activity.redraw();
    assert.equal($('#group-pm-list').hasClass('show'), true);
    activity.get_huddles = () => [];
    activity.redraw();
    assert.equal($('#group-pm-list').hasClass('show'), false);
    activity.get_huddles = real_get_huddles;
    activity.update_huddles = function () {};
}());

(function test_set_user_status() {
    const server_time = 500;
    const info = {
        website: {
            status: "active",
            timestamp: server_time,
        },
    };
    const alice_li = $.create('alice-li');

    $('#user_presences').set_find_results('[data-user-id="1"]', alice_li);

    $('#user_presences').append = function () {};

    $.stub_selector('#user_presences li', {
        toArray: () => [],
    });
    presence.presence_info[alice.user_id] = undefined;
    activity.set_user_status(me.email, info, server_time);
    assert.equal(presence.presence_info[alice.user_id], undefined);
    activity.set_user_status(alice.email, info, server_time);
    const expected = { status: 'active', mobile: false, last_active: 500 };
    assert.deepEqual(presence.presence_info[alice.user_id], expected);
    activity.set_user_status(alice.email, info, server_time);
    blueslip.warn = function (msg) {
        assert.equal(msg, 'unknown email: foo@bar.com');
    };
    blueslip.error = () => {};
    activity.set_user_status('foo@bar.com', info, server_time);
}());

(function test_initialize() {
  $.stub_selector('html', {
      on: function (name, func) {
          func();
      },
  });
  $(window).focus = func => func();
  $(window).idle = () => {};

  channel.post = function (payload) {
      payload.success({});
  };
  global.server_events = {
      check_for_unsuspend: function () {},
  };
  activity.has_focus = false;
  activity.initialize();
  assert(!activity.new_user_input);
  assert(!$('#zephyr-mirror-error').hasClass('show'));
  assert.equal(page_params.presences, undefined);
  assert(activity.has_focus);
  $(window).idle = function (params) {
      params.onIdle();
  };
  channel.post = function (payload) {
      payload.success({
          zephyr_mirror_active: false,
      });
  };
  global.setInterval = (func) => func();

  activity.initialize();
  assert($('#zephyr-mirror-error').hasClass('show'));
  assert(!activity.new_user_input);
  assert(!activity.has_focus);

  // Now execute the reload-in-progress code path
  reload.is_in_progress = function () {
      return true;
  };
  activity.initialize();

}());
