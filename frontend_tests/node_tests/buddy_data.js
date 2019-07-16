const _page_params = {};

set_global('page_params', _page_params);
set_global('$', global.make_zjquery());
zrequire('people');
zrequire('presence');
zrequire('user_status');

zrequire('buddy_data');
zrequire('narrow_state');
zrequire('Filter', 'js/filter');
zrequire('hash_util');
zrequire('stream_data');
const settings_config = zrequire('settings_config');

set_global('timerender', {});

// The buddy_data module is mostly tested indirectly through
// activity.js, but we should feel free to add direct tests
// here.

const selma = {
    user_id: 1000,
    full_name: 'Human Selma',
    email: 'selma@example.com',
};

const me = {
    user_id: 1001,
    full_name: 'Human Myself',
    email: 'self@example.com',
};

const alice = {
    email: 'alice@zulip.com',
    user_id: 1002,
    full_name: 'Alice Smith',
};

const fred = {
    email: 'fred@zulip.com',
    user_id: 1003,
    full_name: "Fred Flintstone",
};

const jill = {
    email: 'jill@zulip.com',
    user_id: 1004,
    full_name: 'Jill Hill',
};

const mark = {
    email: 'mark@zulip.com',
    user_id: 1005,
    full_name: 'Marky Mark',
};

const old_user = {
    user_id: 9999,
    full_name: 'Old User',
    email: 'old_user@example.com',
};

const bot = {
    user_id: 55555,
    full_name: 'Red Herring Bot',
    email: 'bot@example.com',
    is_bot: true,
    bot_owner_id: null,
};

const bot_with_owner = {
    user_id: 55556,
    full_name: 'Blue Herring Bot',
    email: 'bot_with_owner@example.com',
    is_bot: true,
    bot_owner_id: 1001,
    bot_owner_full_name: 'Human Myself',
};

function make_people() {
    // sanity check
    assert.equal(mark.user_id, 1005);

    for (const i of _.range(mark.user_id + 1, 2000)) {
        const person = {
            user_id: i,
            full_name: `Human ${i}`,
            email: `person${i}@example.com`,
        };
        people.add_active_user(person);
    }

    people.add_active_user(bot);
    people.add_active_user(bot_with_owner);
    people.add_active_user(alice);
    people.add_active_user(fred);
    people.add_active_user(jill);
    people.add_active_user(mark);
    people.add_active_user(selma);
    people.add_active_user(me);
    people.add_active_user(old_user);

    people.initialize_current_user(me.user_id);
}

make_people();

run_test('huddle_fraction_present', () => {
    let huddle = 'alice@zulip.com,fred@zulip.com,jill@zulip.com,mark@zulip.com';
    huddle = people.emails_strings_to_user_ids_string(huddle);

    let presence_info = new Map();
    presence_info.set(alice.user_id, { status: 'active' }); // counts as present
    presence_info.set(fred.user_id, { status: 'idle' }); // does not count as present
    // jill not in list
    presence_info.set(mark.user_id, { status: 'offline' }); // does not count
    presence.presence_info = presence_info;

    assert.equal(
        buddy_data.huddle_fraction_present(huddle),
        0.5);

    presence_info = new Map();
    for (const user of [alice, fred, jill, mark]) {
        presence_info.set(user.user_id, { status: 'active' }); // counts as present
    }
    presence.presence_info = presence_info;

    assert.equal(
        buddy_data.huddle_fraction_present(huddle),
        1);

    huddle = 'alice@zulip.com,fred@zulip.com,jill@zulip.com,mark@zulip.com';
    huddle = people.emails_strings_to_user_ids_string(huddle);
    presence_info = new Map();
    presence_info.set(alice.user_id, { status: 'idle' });
    presence_info.set(fred.user_id, { status: 'idle' }); // does not count as present
    // jill not in list
    presence_info.set(mark.user_id, { status: 'offline' }); // does not count
    presence.presence_info = presence_info;

    assert.equal(
        buddy_data.huddle_fraction_present(huddle),
        undefined);
});

function activate_people() {
    presence.presence_info.clear();

    function set_presence(user_id, status) {
        presence.presence_info.set(user_id, {
            status: status,
            last_active: 9999,
        });
    }

    // Make 400 of the users active
    set_presence(selma.user_id, 'active');
    set_presence(me.user_id, 'active');

    for (const user_id of _.range(1000, 1400)) {
        set_presence(user_id, 'active');
    }

    // And then 300 not active
    for (const user_id of _.range(1400, 1700)) {
        set_presence(user_id, 'offline');
    }
}

activate_people();

run_test('user_circle', () => {
    assert.equal(buddy_data.get_user_circle_class(selma.user_id), 'user_circle_green');
    user_status.set_away(selma.user_id);
    assert.equal(buddy_data.get_user_circle_class(selma.user_id), 'user_circle_empty_line');
    user_status.revoke_away(selma.user_id);
    assert.equal(buddy_data.get_user_circle_class(selma.user_id), 'user_circle_green');

    assert.equal(buddy_data.get_user_circle_class(me.user_id), 'user_circle_green');
    user_status.set_away(me.user_id);
    assert.equal(buddy_data.get_user_circle_class(me.user_id), 'user_circle_empty_line');
    user_status.revoke_away(me.user_id);
    assert.equal(buddy_data.get_user_circle_class(me.user_id), 'user_circle_green');
});

run_test('buddy_status', () => {
    assert.equal(buddy_data.buddy_status(selma.user_id), 'active');
    user_status.set_away(selma.user_id);
    assert.equal(buddy_data.buddy_status(selma.user_id), 'away_them');
    user_status.revoke_away(selma.user_id);
    assert.equal(buddy_data.buddy_status(selma.user_id), 'active');

    assert.equal(buddy_data.buddy_status(me.user_id), 'active');
    user_status.set_away(me.user_id);
    assert.equal(buddy_data.buddy_status(me.user_id), 'away_me');
    user_status.revoke_away(me.user_id);
    assert.equal(buddy_data.buddy_status(me.user_id), 'active');
});

run_test('title_data', () => {
    // Groups
    let is_group = true;
    const user_ids_string = "9999,1000";
    let expected_group_data = {
        first_line: 'Human Selma, Old User',
        second_line: '',
        third_line: '',
    };
    assert.deepEqual(buddy_data.get_title_data(user_ids_string, is_group), expected_group_data);

    is_group = '';

    // Bots with owners.
    expected_group_data = {
        first_line: 'Blue Herring Bot',
        second_line: 'translated: Owner: Human Myself',
        third_line: '',
    };
    assert.deepEqual(buddy_data.get_title_data(bot_with_owner.user_id, is_group),
                     expected_group_data);

    // Bots without owners.
    expected_group_data = {
        first_line: 'Red Herring Bot',
        second_line: '',
        third_line: '',
    };
    assert.deepEqual(buddy_data.get_title_data(bot.user_id, is_group), expected_group_data);

    // Individual Users.
    user_status.set_status_text({
        user_id: me.user_id,
        status_text: 'out to lunch',
    });

    let expected_data = {
        first_line: 'Human Myself',
        second_line: 'out to lunch',
        third_line: 'translated: Active now',

    };
    assert.deepEqual(buddy_data.get_title_data(me.user_id, is_group), expected_data);

    expected_data = {
        first_line: 'Old User',
        second_line: 'translated: Last active: translated: More than 2 weeks ago',
        third_line: '',
    };
    assert.deepEqual(buddy_data.get_title_data(old_user.user_id, is_group), expected_data);
});

run_test('simple search', () => {
    const user_ids = buddy_data.get_filtered_and_sorted_user_ids('sel');

    assert.deepEqual(user_ids, [selma.user_id]);
});

run_test('bulk_data_hacks', () => {
    let user_ids;

    // Even though we have 1000 users, we only get the 400 active
    // users.  This is a consequence of buddy_data.maybe_shrink_list.
    user_ids = buddy_data.get_filtered_and_sorted_user_ids();
    assert.equal(user_ids.length, 400);

    user_ids = buddy_data.get_filtered_and_sorted_user_ids('');
    assert.equal(user_ids.length, 400);

    // We don't match on "so", because it's not at the start of a
    // word in the name/email.
    user_ids = buddy_data.get_filtered_and_sorted_user_ids('so');
    assert.equal(user_ids.length, 0);

    // We match on "h" for the first name, and the result limit
    // is relaxed for searches.  (We exclude "me", though.)
    user_ids = buddy_data.get_filtered_and_sorted_user_ids('h');
    assert.equal(user_ids.length, 996);

    // We match on "p" for the email.
    user_ids = buddy_data.get_filtered_and_sorted_user_ids('p');
    assert.equal(user_ids.length, 994);

    // Make our shrink limit higher, and go back to an empty search.
    // We won't get all 1000 users, just the present ones.
    buddy_data.max_size_before_shrinking = 50000;

    user_ids = buddy_data.get_filtered_and_sorted_user_ids('');
    assert.equal(user_ids.length, 700);
});

run_test('level', () => {
    assert.equal(buddy_data.my_user_status(me.user_id), 'translated: (you)');
    user_status.set_away(me.user_id);
    assert.equal(buddy_data.my_user_status(me.user_id), 'translated: (unavailable)');
    user_status.revoke_away(me.user_id);
    assert.equal(buddy_data.my_user_status(me.user_id), 'translated: (you)');
});

run_test('level', () => {
    presence.presence_info.clear();
    assert.equal(buddy_data.level(me.user_id), 0);
    assert.equal(buddy_data.level(selma.user_id), 3);

    const server_time = 9999;
    const info = {
        website: {
            status: "active",
            timestamp: server_time,
        },
    };
    presence.update_info_from_event(me.user_id, info, server_time);
    presence.update_info_from_event(selma.user_id, info, server_time);

    assert.equal(buddy_data.level(me.user_id), 0);
    assert.equal(buddy_data.level(selma.user_id), 1);

    user_status.set_away(me.user_id);
    user_status.set_away(selma.user_id);

    // Selma gets demoted to level 3, but "me"
    // stays in level 0.
    assert.equal(buddy_data.level(me.user_id), 0);
    assert.equal(buddy_data.level(selma.user_id), 3);
});

run_test('user_last_seen_time_status', () => {
    assert.equal(buddy_data.user_last_seen_time_status(selma.user_id),
                 'translated: Active now');

    page_params.realm_is_zephyr_mirror_realm = true;
    assert.equal(buddy_data.user_last_seen_time_status(old_user.user_id),
                 'translated: Unknown');
    page_params.realm_is_zephyr_mirror_realm = false;
    assert.equal(buddy_data.user_last_seen_time_status(old_user.user_id),
                 'translated: More than 2 weeks ago');

    presence.last_active_date = (user_id) => {
        assert.equal(user_id, old_user.user_id);

        return {
            clone: () => 'date-stub',
        };
    };

    timerender.last_seen_status_from_date = (date) => {
        assert.equal(date, 'date-stub');
        return 'May 12';
    };

    assert.equal(buddy_data.user_last_seen_time_status(old_user.user_id),
                 'May 12');

});

function set_filter(operators) {
    operators = _.map(operators, function (op) {
        return {operator: op[0], operand: op[1]};
    });
    narrow_state.set_current_filter(new Filter(operators));
}

run_test('stream_member_functions', () => {
    // This test works on users created by the make_people() function

    function turn_on_message_recipient_list_mode() {
        _page_params.buddy_list_mode =
            settings_config.buddy_list_mode_values.stream_or_pm_members.value;
        set_global('page_params', _page_params);
    }

    function turn_off_message_recipient_list_mode() {
        _page_params.buddy_list_mode = settings_config.buddy_list_mode_values.all_users.value;
        set_global('page_params', _page_params);
    }

    turn_on_message_recipient_list_mode();
    assert(buddy_data.should_show_only_recipients()); // sanity

    // this narrow filter has the effect of excluding p1900 from the buddy list
    set_filter([
        ['pm-with', selma.email + "," + "person1200@example.com" + "," + "person1500@example.com"],
    ]);

    let user_ids = buddy_data.get_filtered_and_sorted_user_ids('');
    assert.deepEqual(user_ids, [
        me.user_id,
        1200,
        1500,
        selma.user_id,
    ]);

    user_ids = buddy_data.get_filtered_and_sorted_user_ids('person');
    assert.deepEqual(user_ids, [
        1200,
        1500,
    ]);

    stream_data.clear_subscriptions();
    const sub = {name: 'Rome', subscribed: true, stream_id: 100};
    stream_data.add_sub(sub);
    stream_data.set_subscribers(sub, [me.user_id, 1200, 1900]);
    stream_data.update_calculated_fields(sub);

    // this filter has the effect of excluding Human 1500 from the buddy list
    set_filter([
        ['stream', sub.name],
        ['topic', 'Bar'], // ensure we can handle more than one filter
    ]);

    user_ids = buddy_data.get_filtered_and_sorted_user_ids('person');
    assert.deepEqual(user_ids, [
        1200,
        1900,
    ]);

    turn_off_message_recipient_list_mode();
    assert(!buddy_data.should_show_only_recipients()); // reset for next test case
});

run_test('error handling', () => {
    presence.get_user_ids = () => [42];
    blueslip.expect('error', 'Unknown user_id in get_by_user_id: 42');
    blueslip.expect('warn', 'Got user_id in presence but not people: 42');
    buddy_data.get_filtered_and_sorted_user_ids();
});
