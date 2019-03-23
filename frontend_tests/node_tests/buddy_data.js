const _page_params = {};

set_global('page_params', _page_params);
set_global('i18n', global.stub_i18n);
zrequire('people');
zrequire('presence');
zrequire('util');
zrequire('user_status');
zrequire('buddy_data');
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
};

function make_people() {
    _.each(_.range(1002, 2000), (i) => {
        const person = {
            user_id: i,
            full_name: `Human ${i}`,
            email: `person${i}@example.com`,
        };
        people.add_in_realm(person);
    });

    people.add_in_realm(bot);
    people.add_in_realm(selma);
    people.add_in_realm(me);
    people.add_in_realm(old_user);

    people.initialize_current_user(me.user_id);
}


function activate_people() {
    const server_time = 9999;
    const info = {
        website: {
            status: "active",
            timestamp: server_time,
        },
    };

    // Make 400 of the users active
    presence.set_info_for_user(selma.user_id, info, server_time);
    presence.set_info_for_user(me.user_id, info, server_time);

    _.each(_.range(1000, 1400), (user_id) => {
        presence.set_info_for_user(user_id, info, server_time);
    });


    // And then 300 not active
    _.each(_.range(1400, 1700), (user_id) => {
        presence.set_info_for_user(user_id, {}, server_time);
    });
}


make_people();
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

run_test('user_title', () => {
    assert.equal(buddy_data.user_title(me.user_id), 'Human Myself is active');
    user_status.set_status_text({
        user_id: me.user_id,
        status_text: 'out to lunch',
    });
    assert.equal(buddy_data.user_title(me.user_id), 'out to lunch');
});

run_test('simple search', () => {
    const user_ids = buddy_data.get_filtered_and_sorted_user_ids('sel');

    assert.deepEqual(user_ids, [selma.user_id]);
});

run_test('bulk_data_hacks', () => {
    var user_ids;

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
    assert.equal(user_ids.length, 999);

    // We match on "p" for the email.
    user_ids = buddy_data.get_filtered_and_sorted_user_ids('p');
    assert.equal(user_ids.length, 998);


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
    presence.presence_info = {};
    assert.equal(buddy_data.level(me.user_id), 0);
    assert.equal(buddy_data.level(selma.user_id), 3);

    const server_time = 9999;
    const info = {
        website: {
            status: "active",
            timestamp: server_time,
        },
    };
    presence.set_info_for_user(me.user_id, info, server_time);
    presence.set_info_for_user(selma.user_id, info, server_time);

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
