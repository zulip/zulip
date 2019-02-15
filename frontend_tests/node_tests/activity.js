set_global('$', global.make_zjquery());
set_global('blueslip', global.make_zblueslip());

var filter_key_handlers;

const _page_params = {
    realm_users: [],
    user_id: 999,
};

const _feature_flags = {};

const _document = {
    hasFocus: function () {
        return true;
    },
};

const _channel = {};

const _ui = {
    set_up_scrollbar: function () {},
    update_scrollbar: function () {},
};

const _keydown_util = {
    handle: (opts) => {
        filter_key_handlers = opts.handlers;
    },
};

const _compose_state = {};

const _scroll_util = {
    scroll_element_into_container: () => {},
};

const _pm_list = {
    update_private_messages: () => {},
};

const _popovers = {
    hide_all_except_userlist_sidebar: function () {},
    hide_all: function () {},
    show_userlist_sidebar: function () {
        $('.column-right').addClass('expanded');
    },
};

const _stream_popover = {
    show_streamlist_sidebar: function () {
        $('.column-left').addClass('expanded');
    },
};

const _reload_state = {
    is_in_progress: () => false,
};

const _resize = {
    resize_page_components: () => {},
};

set_global('i18n', global.stub_i18n);
set_global('padded_widget', {
    update_padding: () => {},
});
set_global('channel', _channel);
set_global('compose_state', _compose_state);
set_global('document', _document);
set_global('feature_flags', _feature_flags);
set_global('keydown_util', _keydown_util);
set_global('page_params', _page_params);
set_global('pm_list', _pm_list);
set_global('popovers', _popovers);
set_global('reload_state', _reload_state);
set_global('resize', _resize);
set_global('scroll_util', _scroll_util);
set_global('stream_popover', _stream_popover);
set_global('ui', _ui);

zrequire('compose_fade');
zrequire('Handlebars', 'handlebars');
zrequire('templates');
zrequire('unread');
zrequire('hash_util');
zrequire('narrow');
zrequire('util');
zrequire('presence');
zrequire('people');
zrequire('buddy_data');
zrequire('buddy_list');
zrequire('user_search');
zrequire('user_status');
zrequire('list_cursor');
zrequire('activity');

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

// Simulate a small window by having the
// fill_screen_with_content render the entire
// list in one pass.  We will do more refined
// testing in the buddy_list node tests.
buddy_list.fill_screen_with_content = () => {
    buddy_list.render_more({
        chunk_size: 100,
    });
};

run_test('get_status', () => {
    assert.equal(presence.get_status(page_params.user_id), "active");
    assert.equal(presence.get_status(alice.user_id), "inactive");
    assert.equal(presence.get_status(fred.user_id), "active");
    assert.equal(presence.get_status(zoe.user_id), "offline");
});

run_test('reload_defaults', () => {
    blueslip.set_test_data('warn', 'get_filter_text() is called before initialization');
    assert.equal(activity.get_filter_text(), '');
    assert.equal(blueslip.get_test_logs('warn').length, 1);
    blueslip.clear_test_data();
});

run_test('sort_users', () => {
    const user_ids = [alice.user_id, fred.user_id, jill.user_id];

    buddy_data.sort_users(user_ids);

    assert.deepEqual(user_ids, [
        fred.user_id,
        jill.user_id,
        alice.user_id,
    ]);
});

run_test('process_loaded_messages', () => {

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
});

run_test('full_huddle_name', () => {
    function full_name(emails_string) {
        const user_ids_string = people.emails_strings_to_user_ids_string(emails_string);
        return activity.full_huddle_name(user_ids_string);
    }

    assert.equal(
        full_name('alice@zulip.com,jill@zulip.com'),
        'Alice Smith, Jill Hill');

    assert.equal(
        full_name('alice@zulip.com,fred@zulip.com,jill@zulip.com'),
        'Alice Smith, Fred Flintstone, Jill Hill');
});

run_test('short_huddle_name', () => {
    function short_name(emails_string) {
        const user_ids_string = people.emails_strings_to_user_ids_string(emails_string);
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

});

run_test('huddle_fraction_present', () => {
    let huddle = 'alice@zulip.com,fred@zulip.com,jill@zulip.com,mark@zulip.com';
    huddle = people.emails_strings_to_user_ids_string(huddle);

    var presence_info = {};
    presence_info[alice.user_id] = { status: 'active' }; // counts as present
    presence_info[fred.user_id] = { status: 'idle' }; // doest not count as present
    // jill not in list
    presence_info[mark.user_id] = { status: 'offline' }; // does not count
    presence.presence_info = presence_info;

    assert.equal(
        buddy_data.huddle_fraction_present(huddle),
        '0.50');

    huddle = 'alice@zulip.com,fred@zulip.com,jill@zulip.com,mark@zulip.com';
    huddle = people.emails_strings_to_user_ids_string(huddle);
    presence_info = {};
    presence_info[alice.user_id] = { status: 'idle' };
    presence_info[fred.user_id] = { status: 'idle' }; // does not count as present
    // jill not in list
    presence_info[mark.user_id] = { status: 'offline' }; // does not count
    presence.presence_info = presence_info;

    assert.equal(
        buddy_data.huddle_fraction_present(huddle),
        false);
});

presence.presence_info = {};
presence.presence_info[alice.user_id] = { status: activity.IDLE };
presence.presence_info[fred.user_id] = { status: activity.ACTIVE };
presence.presence_info[jill.user_id] = { status: activity.ACTIVE };
presence.presence_info[mark.user_id] = { status: activity.IDLE };
presence.presence_info[norbert.user_id] = { status: activity.ACTIVE };
presence.presence_info[zoe.user_id] = { status: activity.ACTIVE };
presence.presence_info[me.user_id] = { status: activity.ACTIVE };

function clear_buddy_list() {
    buddy_list.populate({
        keys: [],
    });
}

function reset_setup() {
    set_global('$', global.make_zjquery());
    activity.set_cursor_and_filter();

    buddy_list.container = $('#user_presences');

    buddy_list.container.append = () => {};
    clear_buddy_list();
}

reset_setup();

run_test('presence_list_full_update', () => {
    $('.user-list-filter').focus();
    compose_state.recipient = () => fred.email;
    compose_fade.set_focused_recipient("private");

    var user_ids = activity.build_user_sidebar();

    user_ids = _.map(user_ids, function (user_id) {
        return parseInt(user_id, 10);
    });

    assert.deepEqual(user_ids, [
        me.user_id,
        fred.user_id,
        jill.user_id,
        norbert.user_id,
        zoe.user_id,
        alice.user_id,
        mark.user_id,
    ]);
});

function simulate_right_column_buddy_list() {
    $('.user-list-filter').closest = function (selector) {
        assert.equal(selector, ".app-main [class^='column-']");
        return $.create('right-sidebar').addClass('column-right');
    };
}

function simulate_left_column_buddy_list() {
    $('.user-list-filter').closest = function (selector) {
        assert.equal(selector, ".app-main [class^='column-']");
        return $.create('left-sidebar').addClass('column-left');
    };
}

function buddy_list_add(user_id, stub) {
    if (stub.attr) {
        stub.attr('data-user-id', user_id);
    }
    stub.length = 1;
    const sel = `li.user_sidebar_entry[data-user-id='${user_id}']`;
    $('#user_presences').set_find_results(sel, stub);
}

run_test('PM_update_dom_counts', () => {
    const value = $.create('alice-value');
    const count = $.create('alice-count');
    const pm_key = alice.user_id.toString();
    const li = $.create('alice stub');
    buddy_list_add(pm_key, li);
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
});

run_test('group_update_dom_counts', () => {
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
});

run_test('handlers', () => {
    // This is kind of weak coverage; we are mostly making sure that
    // keys and clicks got mapped to functions that don't crash.
    let me_li;
    let alice_li;
    let fred_li;

    function init() {
        reset_setup();
        buddy_list.populate({
            keys: [me.user_id, alice.user_id, fred.user_id],
        });

        me_li = $.create('me stub');
        alice_li = $.create('alice stub');
        fred_li = $.create('fred stub');

        buddy_list_add(me.user_id, me_li);
        buddy_list_add(alice.user_id, alice_li);
        buddy_list_add(fred.user_id, fred_li);
    }

    (function test_filter_keys() {
        init();
        activity.user_cursor.go_to(alice.user_id);
        filter_key_handlers.down_arrow();
        filter_key_handlers.up_arrow();
    }());

    (function test_click_filter() {
        init();
        const e = {
            stopPropagation: () => {},
        };

        const handler = $('.user-list-filter').get_on_handler('focus');
        handler(e);
    }());

    (function test_click_header_filter() {
        init();
        const e = {};
        const handler = $('#userlist-header').get_on_handler('click');

        simulate_right_column_buddy_list();

        handler(e);
        // and click again
        handler(e);
    }());

    (function test_enter_key() {
        init();
        var narrowed;

        narrow.by = (method, email) => {
            assert.equal(email, 'alice@zulip.com');
            narrowed = true;
        };

        $('.user-list-filter').val('al');
        activity.user_cursor.go_to(alice.user_id);

        filter_key_handlers.enter_key();
        assert(narrowed);

        // get line coverage for cleared case
        activity.user_cursor.clear();
        filter_key_handlers.enter_key();
    }());

    (function test_click_handler() {
        init();
        // We wire up the click handler in click_handlers.js,
        // so this just tests the called function.
        var narrowed;

        narrow.by = (method, email) => {
            assert.equal(email, 'alice@zulip.com');
            narrowed = true;
        };

        activity.narrow_for_user({li: alice_li});
        assert(narrowed);
    }());

    (function test_blur_filter() {
        init();
        const e = {};
        const handler = $('.user-list-filter').get_on_handler('blur');
        handler(e);
    }());
});

presence.presence_info = {};
presence.presence_info[alice.user_id] = { status: activity.ACTIVE };
presence.presence_info[fred.user_id] = { status: activity.ACTIVE };
presence.presence_info[jill.user_id] = { status: activity.ACTIVE };
presence.presence_info[mark.user_id] = { status: activity.IDLE };
presence.presence_info[norbert.user_id] = { status: activity.ACTIVE };
presence.presence_info[zoe.user_id] = { status: activity.ACTIVE };

reset_setup();

run_test('first/prev/next', () => {
    clear_buddy_list();

    assert.equal(buddy_list.first_key(), undefined);
    assert.equal(buddy_list.prev_key(alice.user_id), undefined);
    assert.equal(buddy_list.next_key(alice.user_id), undefined);

    buddy_list.container.append = () => {};

    activity.redraw_user(alice.user_id);
    activity.redraw_user(fred.user_id);

    assert.equal(buddy_list.first_key(), alice.user_id);
    assert.equal(buddy_list.prev_key(alice.user_id), undefined);
    assert.equal(buddy_list.prev_key(fred.user_id), alice.user_id);

    assert.equal(buddy_list.next_key(alice.user_id), fred.user_id);
    assert.equal(buddy_list.next_key(fred.user_id), undefined);
});

reset_setup();

run_test('filter_user_ids', () => {
    const user_filter = $('.user-list-filter');
    user_filter.val(''); // no search filter

    function get_user_ids() {
        var filter_text = activity.get_filter_text();
        var user_ids = buddy_data.get_filtered_and_sorted_user_ids(filter_text);
        return user_ids;
    }

    var user_ids = buddy_data.get_filtered_and_sorted_user_ids();
    assert.deepEqual(user_ids, [
        alice.user_id,
        fred.user_id,
        jill.user_id,
        norbert.user_id,
        zoe.user_id,
        mark.user_id,
    ]);

    user_filter.val('abc'); // no match
    user_ids = get_user_ids();
    assert.deepEqual(user_ids, []);

    user_filter.val('fred'); // match fred
    user_ids = get_user_ids();
    assert.deepEqual(user_ids, [fred.user_id]);

    user_filter.val('fred,alice'); // match fred and alice
    user_ids = get_user_ids();
    assert.deepEqual(user_ids, [alice.user_id, fred.user_id]);

    user_filter.val('fr,al'); // match fred and alice partials
    user_ids = get_user_ids();
    assert.deepEqual(user_ids, [alice.user_id, fred.user_id]);

    presence.presence_info[alice.user_id] = { status: activity.IDLE };
    user_filter.val('fr,al'); // match fred and alice partials and idle user
    user_ids = get_user_ids();
    assert.deepEqual(user_ids, [fred.user_id, alice.user_id]);

    $.stub_selector('.user-list-filter', []);
    presence.presence_info[alice.user_id] = { status: activity.ACTIVE };
    user_ids = get_user_ids();
    assert.deepEqual(user_ids, [alice.user_id, fred.user_id]);
});

run_test('insert_one_user_into_empty_list', () => {
    let appended_html;
    $('#user_presences').append = function (html) {
        appended_html = html;
    };

    clear_buddy_list();
    activity.redraw_user(alice.user_id);
    assert(appended_html.indexOf('data-user-id="1"') > 0);
    assert(appended_html.indexOf('user_circle_green') > 0);
});

reset_setup();

run_test('insert_alice_then_fred', () => {
    clear_buddy_list();

    let appended_html;
    $('#user_presences').append = function (html) {
        appended_html = html;
    };

    activity.redraw_user(alice.user_id);
    assert(appended_html.indexOf('data-user-id="1"') > 0);
    assert(appended_html.indexOf('user_circle_green') > 0);

    activity.redraw_user(fred.user_id);
    assert(appended_html.indexOf('data-user-id="2"') > 0);
    assert(appended_html.indexOf('user_circle_green') > 0);
});

reset_setup();

run_test('insert_fred_then_alice_then_rename', () => {
    clear_buddy_list();

    let appended_html;
    $('#user_presences').append = function (html) {
        appended_html = html;
    };

    activity.redraw_user(fred.user_id);
    assert(appended_html.indexOf('data-user-id="2"') > 0);
    assert(appended_html.indexOf('user_circle_green') > 0);

    var fred_stub = $.create('fred-first');
    buddy_list_add(fred.user_id, fred_stub);

    var inserted_html;
    fred_stub.before = (html) => {
        inserted_html = html;
    };

    activity.redraw_user(alice.user_id);
    assert(inserted_html.indexOf('data-user-id="1"') > 0);
    assert(inserted_html.indexOf('user_circle_green') > 0);

    // Next rename fred to Aaron.
    const fred_with_new_name = {
        email: fred.email,
        user_id: fred.user_id,
        full_name: "Aaron",
    };
    people.add(fred_with_new_name);

    var alice_stub = $.create('alice-first');
    buddy_list_add(alice.user_id, alice_stub);

    alice_stub.before = (html) => {
        inserted_html = html;
    };

    activity.redraw_user(fred_with_new_name.user_id);
    assert(appended_html.indexOf('data-user-id="2"') > 0);

    // restore old Fred data
    people.add(fred);
});

// Reset jquery here.
reset_setup();

run_test('insert_unfiltered_user_with_filter', () => {
    // This test only tests that we do not explode when
    // try to insert Fred into a list where he does not
    // match the search filter.
    const user_filter = $('.user-list-filter');
    user_filter.val('do-not-match-filter');
    activity.redraw_user(fred.user_id);
});

run_test('realm_presence_disabled', () => {
    page_params.realm_presence_disabled = true;
    unread.suppress_unread_counts = false;

    activity.redraw_user();
    activity.build_user_sidebar();

    real_update_huddles();
});

run_test('clear_search', () => {
    $('.user-list-filter').val('somevalue');
    activity.user_filter.clear_search();
    assert.equal($('.user-list-filter').val(), '');
    activity.user_filter.clear_search();
    assert($('#user_search_section').hasClass('notdisplayed'));
});

run_test('escape_search', () => {
    clear_buddy_list();
    $('.user-list-filter').val('somevalue');
    activity.escape_search();
    assert.equal($('.user-list-filter').val(), '');
    activity.escape_search();
    assert($('#user_search_section').hasClass('notdisplayed'));
});

reset_setup();

run_test('initiate_search', () => {
    $('.user-list-filter').blur();
    simulate_right_column_buddy_list();
    activity.initiate_search();
    assert.equal($('.column-right').hasClass('expanded'), true);
    assert.equal($('.user-list-filter').is_focused(), true);

    simulate_left_column_buddy_list();
    activity.initiate_search();
    assert.equal($('.column-left').hasClass('expanded'), true);
    assert.equal($('.user-list-filter').is_focused(), true);
});

run_test('toggle_filter_display', () => {
    activity.user_filter.toggle_filter_displayed();
    assert($('#user_search_section').hasClass('notdisplayed'));
    $('.user-list-filter').closest = function (selector) {
        assert.equal(selector, ".app-main [class^='column-']");
        return $.create('sidebar').addClass('column-right');
    };
    activity.user_filter.toggle_filter_displayed();
    assert.equal($('#user_search_section').hasClass('notdisplayed'), false);
});

run_test('searching', () => {
    $('.user-list-filter').focus();
    assert.equal(activity.searching(), true);
    $('.user-list-filter').blur();
    assert.equal(activity.searching(), false);
});

run_test('update_huddles_and_redraw', () => {
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
});

reset_setup();

run_test('update_presence_info', () => {
    const server_time = 500;
    const info = {
        website: {
            status: "active",
            timestamp: server_time,
        },
    };

    buddy_data.matches_filter = () => true;

    const alice_li = $.create('alice stub');
    buddy_list_add(alice.user_id, alice_li);

    var inserted;
    buddy_list.insert_or_move = () => {
        inserted = true;
    };

    presence.presence_info[me.user_id] = undefined;
    activity.update_presence_info(me.email, info, server_time);
    assert(inserted);
    assert.deepEqual(presence.presence_info[me.user_id].status, 'active');

    presence.presence_info[alice.user_id] = undefined;
    activity.update_presence_info(alice.email, info, server_time);
    assert(inserted);

    const expected = { status: 'active', mobile: false, last_active: 500 };
    assert.deepEqual(presence.presence_info[alice.user_id], expected);

    activity.update_presence_info(alice.email, info, server_time);
    blueslip.set_test_data('warn', 'unknown email: foo@bar.com');
    blueslip.set_test_data('error', 'Unknown email for get_user_id: foo@bar.com');
    activity.update_presence_info('foo@bar.com', info, server_time);
    assert.equal(blueslip.get_test_logs('warn').length, 1);
    assert.equal(blueslip.get_test_logs('error').length, 1);
    blueslip.clear_test_data();
});

run_test('initialize', () => {
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

    var scroll_handler_started;
    buddy_list.start_scroll_handler = () => {
        scroll_handler_started = true;
    };

    activity.has_focus = false;
    activity.initialize();
    assert(scroll_handler_started);
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
    _reload_state.is_in_progress = function () {
        return true;
    };

    activity.initialize();
});

run_test('away_status', () => {
    assert(!user_status.is_away(alice.user_id));
    activity.on_set_away(alice.user_id);
    assert(user_status.is_away(alice.user_id));
    activity.on_revoke_away(alice.user_id);
    assert(!user_status.is_away(alice.user_id));
});
