set_global('page_params', {
    is_admin: false,
    realm_users: [],
});

set_global('$', function () {
});

set_global('blueslip', global.make_zblueslip());

zrequire('color_data');
zrequire('util');
zrequire('hash_util');
zrequire('topic_data');
zrequire('people');
zrequire('stream_color');
zrequire('stream_data');
zrequire('marked', 'third/marked/lib/marked');

run_test('basics', () => {
    var denmark = {
        subscribed: false,
        color: 'blue',
        name: 'Denmark',
        stream_id: 1,
        in_home_view: false,
    };
    var social = {
        subscribed: true,
        color: 'red',
        name: 'social',
        stream_id: 2,
        in_home_view: true,
        invite_only: true,
        is_announcement_only: true,
    };
    var test = {
        subscribed: true,
        color: 'yellow',
        name: 'test',
        stream_id: 3,
        in_home_view: false,
        invite_only: false,
    };
    stream_data.add_sub('Denmark', denmark);
    stream_data.add_sub('social', social);
    assert(stream_data.all_subscribed_streams_are_in_home_view());
    stream_data.add_sub('test', test);
    assert(!stream_data.all_subscribed_streams_are_in_home_view());

    assert.equal(stream_data.get_sub('denmark'), denmark);
    assert.equal(stream_data.get_sub('Social'), social);

    assert.deepEqual(stream_data.home_view_stream_names(), ['social']);
    assert.deepEqual(stream_data.subscribed_streams(), ['social', 'test']);
    assert.deepEqual(stream_data.get_colors(), ['red', 'yellow']);

    assert(stream_data.is_subscribed('social'));
    assert(stream_data.is_subscribed('Social'));
    assert(!stream_data.is_subscribed('Denmark'));
    assert(!stream_data.is_subscribed('Rome'));

    assert(stream_data.get_invite_only('social'));
    assert(!stream_data.get_invite_only('unknown'));
    assert(stream_data.get_announcement_only('social'));
    assert(!stream_data.get_announcement_only('unknown'));

    assert.equal(stream_data.get_color('social'), 'red');
    assert.equal(stream_data.get_color('unknown'), global.stream_color.default_color);

    assert.equal(stream_data.get_name('denMARK'), 'Denmark');
    assert.equal(stream_data.get_name('unknown Stream'), 'unknown Stream');

    assert(stream_data.in_home_view(social.stream_id));
    assert(!stream_data.in_home_view(denmark.stream_id));

    assert.equal(stream_data.maybe_get_stream_name(), undefined);
    assert.equal(stream_data.maybe_get_stream_name(social.stream_id), 'social');
    assert.equal(stream_data.maybe_get_stream_name(42), undefined);

    stream_data.set_realm_default_streams([denmark]);
    assert(stream_data.get_default_status('Denmark'));
    assert(!stream_data.get_default_status('social'));
    assert(!stream_data.get_default_status('UNKNOWN'));
});

run_test('renames', () => {
    stream_data.clear_subscriptions();
    var id = 42;
    var sub = {
        name: 'Denmark',
        subscribed: true,
        color: 'red',
        stream_id: id,
    };
    stream_data.add_sub('Denmark', sub);
    sub = stream_data.get_sub('Denmark');
    assert.equal(sub.color, 'red');
    sub = stream_data.get_sub_by_id(id);
    assert.equal(sub.color, 'red');

    stream_data.rename_sub(sub, 'Sweden');
    sub = stream_data.get_sub_by_id(id);
    assert.equal(sub.color, 'red');
    assert.equal(sub.name, 'Sweden');

    sub = stream_data.get_sub('Denmark');
    assert.equal(sub, undefined);

    sub = stream_data.get_sub_by_name('Denmark');
    assert.equal(sub.name, 'Sweden');

    var actual_id = stream_data.get_stream_id('Denmark');
    assert.equal(actual_id, 42);
});

run_test('unsubscribe', () => {
    stream_data.clear_subscriptions();

    var sub = {name: 'devel', subscribed: false, stream_id: 1};
    var me = {
        email: 'me@zulip.com',
        full_name: 'Current User',
        user_id: 81,
    };

    // set up user data
    people.add(me);
    people.initialize_current_user(me.user_id);

    // set up our subscription
    stream_data.add_sub('devel', sub);
    sub.subscribed = true;
    stream_data.set_subscribers(sub, [me.user_id]);

    // ensure our setup is accurate
    assert(stream_data.is_subscribed('devel'));

    // DO THE UNSUBSCRIBE HERE
    stream_data.unsubscribe_myself(sub);
    assert(!sub.subscribed);
    assert(!stream_data.is_subscribed('devel'));

    // make sure subsequent calls work
    sub = stream_data.get_sub('devel');
    assert(!sub.subscribed);
});

run_test('subscribers', () => {
    stream_data.clear_subscriptions();
    var sub = {name: 'Rome', subscribed: true, stream_id: 1};

    stream_data.add_sub('Rome', sub);

    var fred = {
        email: 'fred@zulip.com',
        full_name: 'Fred',
        user_id: 101,
    };
    var not_fred = {
        email: 'not_fred@zulip.com',
        full_name: 'Not Fred',
        user_id: 102,
    };
    var george = {
        email: 'george@zulip.com',
        full_name: 'George',
        user_id: 103,
    };
    people.add(fred);
    people.add(not_fred);
    people.add(george);

    stream_data.set_subscribers(sub, [fred.user_id, george.user_id]);
    stream_data.update_calculated_fields(sub);
    assert(stream_data.is_user_subscribed('Rome', fred.user_id));
    assert(stream_data.is_user_subscribed('Rome', george.user_id));
    assert(!stream_data.is_user_subscribed('Rome', not_fred.user_id));

    stream_data.set_subscribers(sub, []);

    var brutus = {
        email: 'brutus@zulip.com',
        full_name: 'Brutus',
        user_id: 104,
    };
    people.add(brutus);
    assert(!stream_data.is_user_subscribed('Rome', brutus.user_id));

    // add
    var ok = stream_data.add_subscriber('Rome', brutus.user_id);
    assert(ok);
    assert(stream_data.is_user_subscribed('Rome', brutus.user_id));
    sub = stream_data.get_sub('Rome');
    stream_data.update_subscribers_count(sub);
    assert.equal(sub.subscriber_count, 1);
    var sub_email = "Rome:214125235@zulipdev.com:9991";
    stream_data.update_stream_email_address(sub, sub_email);
    assert.equal(sub.email_address, sub_email);

    // verify that adding an already-added subscriber is a noop
    stream_data.add_subscriber('Rome', brutus.user_id);
    assert(stream_data.is_user_subscribed('Rome', brutus.user_id));
    sub = stream_data.get_sub('Rome');
    stream_data.update_subscribers_count(sub);
    assert.equal(sub.subscriber_count, 1);

    // remove
    ok = stream_data.remove_subscriber('Rome', brutus.user_id);
    assert(ok);
    assert(!stream_data.is_user_subscribed('Rome', brutus.user_id));
    sub = stream_data.get_sub('Rome');
    stream_data.update_subscribers_count(sub);
    assert.equal(sub.subscriber_count, 0);

    // verify that checking subscription with undefined user id

    blueslip.set_test_data('warn', 'Undefined user_id passed to function is_user_subscribed');
    assert.equal(stream_data.is_user_subscribed('Rome', undefined), undefined);
    assert.equal(blueslip.get_test_logs('warn').length, 1);

    // Verify noop for bad stream when removing subscriber
    var bad_stream = 'UNKNOWN';
    blueslip.set_test_data('warn', 'We got a remove_subscriber call for a non-existent stream ' + bad_stream);
    ok = stream_data.remove_subscriber(bad_stream, brutus.user_id);
    assert(!ok);
    assert.equal(blueslip.get_test_logs('warn').length, 2);

    // Defensive code will give warnings, which we ignore for the
    // tests, but the defensive code needs to not actually blow up.
    set_global('blueslip', global.make_zblueslip({
        warn: false,
    }));

    // verify that removing an already-removed subscriber is a noop
    ok = stream_data.remove_subscriber('Rome', brutus.user_id);
    assert(!ok);
    assert(!stream_data.is_user_subscribed('Rome', brutus.user_id));
    sub = stream_data.get_sub('Rome');
    stream_data.update_subscribers_count(sub);
    assert.equal(sub.subscriber_count, 0);

    // Verify defensive code in set_subscribers, where the second parameter
    // can be undefined.
    stream_data.set_subscribers(sub);
    stream_data.add_sub('Rome', sub);
    stream_data.add_subscriber('Rome', brutus.user_id);
    sub.subscribed = true;
    assert(stream_data.is_user_subscribed('Rome', brutus.user_id));

    // Verify that we noop and don't crash when unsubscribed.
    sub.subscribed = false;
    stream_data.update_calculated_fields(sub);
    ok = stream_data.add_subscriber('Rome', brutus.user_id);
    assert(ok);
    assert.equal(stream_data.is_user_subscribed('Rome', brutus.user_id), true);
    stream_data.remove_subscriber('Rome', brutus.user_id);
    assert.equal(stream_data.is_user_subscribed('Rome', brutus.user_id), false);
    stream_data.add_subscriber('Rome', brutus.user_id);
    assert.equal(stream_data.is_user_subscribed('Rome', brutus.user_id), true);

    sub.invite_only = true;
    stream_data.update_calculated_fields(sub);
    assert.equal(stream_data.is_user_subscribed('Rome', brutus.user_id), undefined);
    stream_data.remove_subscriber('Rome', brutus.user_id);
    assert.equal(stream_data.is_user_subscribed('Rome', brutus.user_id), undefined);

    // Verify that we don't crash and return false for a bad stream.
    ok = stream_data.add_subscriber('UNKNOWN', brutus.user_id);
    assert(!ok);

    // Verify that we don't crash and return false for a bad user id.
    blueslip.set_test_data('error', 'Unknown user_id in get_person_from_user_id: 9999999');
    blueslip.set_test_data('error', 'We tried to add invalid subscriber: 9999999');
    ok = stream_data.add_subscriber('Rome', 9999999);
    assert(!ok);
    assert.equal(blueslip.get_test_logs('error').length, 2);
    blueslip.clear_test_data();
});

run_test('is_active', () => {
    stream_data.clear_subscriptions();

    var sub;

    sub = {name: 'pets', subscribed: false, stream_id: 111};
    stream_data.add_sub('pets', sub);

    assert(stream_data.is_active(sub));

    stream_data.set_filter_out_inactives(true);

    assert(!stream_data.is_active(sub));

    stream_data.subscribe_myself(sub);
    assert(stream_data.is_active(sub));

    stream_data.unsubscribe_myself(sub);
    assert(!stream_data.is_active(sub));

    sub = {name: 'lunch', subscribed: false, stream_id: 222};
    stream_data.add_sub('lunch', sub);

    assert(!stream_data.is_active(sub));

    var opts = {
        stream_id: 222,
        message_id: 108,
        topic_name: 'topic2',
    };
    topic_data.add_message(opts);

    assert(stream_data.is_active(sub));
});

run_test('admin_options', () => {
    function make_sub() {
        var sub = {
            subscribed: false,
            color: 'blue',
            name: 'stream_to_admin',
            stream_id: 1,
            in_home_view: false,
            invite_only: false,
        };
        stream_data.add_sub(sub.name, sub);
        return sub;
    }

    // non-admins can't do anything
    global.page_params.is_admin = false;
    var sub = make_sub();
    stream_data.update_calculated_fields(sub);
    assert(!sub.is_admin);
    assert(!sub.can_change_stream_permissions);

    // just a sanity check that we leave "normal" fields alone
    assert.equal(sub.color, 'blue');

    // the remaining cases are for admin users
    global.page_params.is_admin = true;

    // admins can make public streams become private
    sub = make_sub();
    stream_data.update_calculated_fields(sub);
    assert(sub.is_admin);
    assert(sub.can_change_stream_permissions);

    // admins can only make private streams become public
    // if they are subscribed
    sub = make_sub();
    sub.invite_only = true;
    sub.subscribed = false;
    stream_data.update_calculated_fields(sub);
    assert(sub.is_admin);
    assert(!sub.can_change_stream_permissions);

    sub = make_sub();
    sub.invite_only = true;
    sub.subscribed = true;
    stream_data.update_calculated_fields(sub);
    assert(sub.is_admin);
    assert(sub.can_change_stream_permissions);
});

run_test('stream_settings', () => {
    var cinnamon = {
        stream_id: 1,
        name: 'c',
        color: 'cinnamon',
        subscribed: true,
        invite_only: false,
    };

    var blue = {
        stream_id: 2,
        name: 'b',
        color: 'blue',
        subscribed: false,
        invite_only: false,
    };

    var amber = {
        stream_id: 3,
        name: 'a',
        color: 'amber',
        subscribed: true,
        invite_only: true,
    };
    stream_data.clear_subscriptions();
    stream_data.add_sub(cinnamon.name, cinnamon);
    stream_data.add_sub(amber.name, amber);
    stream_data.add_sub(blue.name, blue);

    var sub_rows = stream_data.get_streams_for_settings_page();
    assert.equal(sub_rows[0].color, 'blue');
    assert.equal(sub_rows[1].color, 'amber');
    assert.equal(sub_rows[2].color, 'cinnamon');

    sub_rows = stream_data.get_streams_for_admin();
    assert.equal(sub_rows[0].name, 'a');
    assert.equal(sub_rows[1].name, 'b');
    assert.equal(sub_rows[2].name, 'c');
    assert.equal(sub_rows[0].invite_only, true);
    assert.equal(sub_rows[1].invite_only, false);
    assert.equal(sub_rows[2].invite_only, false);

});

run_test('default_stream_names', () => {
    var announce = {
        stream_id: 101,
        name: 'announce',
        subscribed: true,
    };

    var public_stream = {
        stream_id: 102,
        name: 'public',
        subscribed: true,
    };

    var private_stream = {
        stream_id: 103,
        name: 'private',
        subscribed: true,
        invite_only: true,
    };

    var general = {
        stream_id: 104,
        name: 'general',
        subscribed: true,
        invite_only: false,
    };

    stream_data.clear_subscriptions();
    stream_data.set_realm_default_streams([announce, general]);
    stream_data.add_sub('announce', announce);
    stream_data.add_sub('public_stream', public_stream);
    stream_data.add_sub('private_stream', private_stream);
    stream_data.add_sub('general', general);

    var names = stream_data.get_non_default_stream_names();
    assert.deepEqual(names, ['public', 'private']);

    names = stream_data.get_default_stream_names();
    assert.deepEqual(names, ['announce', 'general']);
});

run_test('delete_sub', () => {
    var canada = {
        stream_id: 101,
        name: 'Canada',
        subscribed: true,
    };

    stream_data.clear_subscriptions();
    stream_data.add_sub('Canada', canada);

    assert(stream_data.is_subscribed('Canada'));
    assert(stream_data.get_sub('Canada').stream_id, canada.stream_id);
    assert(stream_data.get_sub_by_id(canada.stream_id).name, 'Canada');

    stream_data.delete_sub(canada.stream_id);
    assert(!stream_data.is_subscribed('Canada'));
    assert(!stream_data.get_sub('Canada'));
    assert(!stream_data.get_sub_by_id(canada.stream_id));

    // We had earlier disabled warnings, so we need to remake zblueslip.
    set_global('blueslip', global.make_zblueslip());
    blueslip.set_test_data('warn', 'Failed to delete stream does_not_exist');
    blueslip.set_test_data('warn', 'We got a get_subscriber_count count call for a non-existent stream.');
    stream_data.delete_sub('does_not_exist');
    assert.equal(blueslip.get_test_logs('warn').length, 1);
    blueslip.clear_test_data();
});

run_test('get_subscriber_count', () => {
    var india = {
        stream_id: 102,
        name: 'India',
        subscribed: true,
    };
    stream_data.clear_subscriptions();

    blueslip.set_test_data('warn', 'We got a get_subscriber_count count call for a non-existent stream.');
    assert.equal(stream_data.get_subscriber_count('India'), undefined);
    assert.equal(blueslip.get_test_logs('warn').length, 1);
    blueslip.clear_test_data();

    stream_data.add_sub('India', india);
    assert.equal(stream_data.get_subscriber_count('India'), 0);

    var fred = {
        email: 'fred@zulip.com',
        full_name: 'Fred',
        user_id: 101,
    };
    people.add(fred);
    stream_data.add_subscriber('India', 102);
    assert.equal(stream_data.get_subscriber_count('India'), 1);
    var george = {
        email: 'george@zulip.com',
        full_name: 'George',
        user_id: 103,
    };
    people.add(george);
    stream_data.add_subscriber('India', 103);
    assert.equal(stream_data.get_subscriber_count('India'), 2);

    var sub = stream_data.get_sub_by_name('India');
    delete sub.subscribers;
    assert.deepStrictEqual(stream_data.get_subscriber_count('India'), 0);
});

run_test('notifications', () => {
    var india = {
        stream_id: 102,
        name: 'India',
        subscribed: true,
        desktop_notifications: true,
        audible_notifications: true,
    };
    stream_data.clear_subscriptions();
    stream_data.add_sub('India', india);
    assert(stream_data.receives_desktop_notifications('India'));
    assert(!stream_data.receives_desktop_notifications('Indiana'));

    assert(stream_data.receives_audible_notifications('India'));
    assert(!stream_data.receives_audible_notifications('Indiana'));
});

run_test('in_home_view', () => {
    var tony = {
        stream_id: 999,
        name: 'tony',
        subscribed: true,
        in_home_view: true,
    };

    var jazy = {
        stream_id: 500,
        name: 'jazy',
        subscribed: false,
        in_home_view: false,
    };

    stream_data.add_sub('tony', tony);
    stream_data.add_sub('jazy', jazy);
    assert(stream_data.name_in_home_view('tony'));
    assert(!stream_data.name_in_home_view('jazy'));
    assert(!stream_data.name_in_home_view('EEXISTS'));
});

run_test('notifications_in_home_view', () => {
    page_params.notifications_stream = 'tony';
    assert(stream_data.notifications_in_home_view());

    page_params.notifications_stream = 'jazy';
    assert(!stream_data.notifications_in_home_view());
});

run_test('remove_default_stream', () => {
    var remove_me = {
        stream_id: 674,
        name: 'remove_me',
        subscribed: false,
        in_home_view: false,
    };

    stream_data.add_sub('remove_me', remove_me);
    stream_data.set_realm_default_streams([remove_me]);
    stream_data.remove_default_stream(remove_me.stream_id);
    assert(!stream_data.get_default_status('remove_me'));
    assert.equal(page_params.realm_default_streams.length, 0);
});

run_test('canonicalized_name', () => {
    assert.deepStrictEqual(
        stream_data.canonicalized_name('Stream_Bar'),
        "stream_bar"
    );
});

run_test('create_sub', () => {
    stream_data.clear_subscriptions();
    var india = {
        stream_id: 102,
        name: 'India',
        subscribed: true,
    };

    var canada = {
        name: 'Canada',
        subscribed: true,
    };

    var antarctica = {
        stream_id: 103,
        name: 'Antarctica',
        subscribed: true,
        color: '#76ce90',
    };

    color_data.pick_color = function () {
        return '#bd86e5';
    };

    var india_sub = stream_data.create_sub_from_server_data('India', india);
    assert(india_sub);
    assert.equal(india_sub.color, '#bd86e5');
    var new_sub = stream_data.create_sub_from_server_data('India', india); // make sure sub doesn't get created twice
    assert.equal(india_sub, new_sub);

    blueslip.set_test_data('fatal', 'We cannot create a sub without a stream_id');
    var ok = stream_data.create_sub_from_server_data('Canada', canada);
    assert.equal(ok, undefined);
    assert.equal(blueslip.get_test_logs('fatal').length, 1);
    blueslip.clear_test_data();

    var antarctica_sub = stream_data.create_sub_from_server_data('Antarctica', antarctica);
    assert(antarctica_sub);
    assert.equal(antarctica_sub.color, '#76ce90');
});

run_test('initialize', () => {
    function initialize() {
        page_params.subscriptions = [{
            name: 'subscriptions',
            stream_id: '2001',
        }];

        page_params.unsubscribed = [{
            name: 'unsubscribed',
            stream_id: '2002',
        }];

        page_params.never_subscribed = [{
            name: 'never_subscribed',
            stream_id: '2003',
        }];
    }

    initialize();
    page_params.realm_notifications_stream_id = -1;
    stream_data.initialize();
    assert(!stream_data.is_filtering_inactives());

    const stream_names = stream_data.get_streams_for_admin().map(elem => elem.name);
    assert(stream_names.indexOf('subscriptions') !== -1);
    assert(stream_names.indexOf('unsubscribed') !== -1);
    assert(stream_names.indexOf('never_subscribed') !== -1);
    assert(!page_params.subscriptions);
    assert(!page_params.unsubscribed);
    assert(!page_params.never_subscribed);
    assert.equal(page_params.notifications_stream, "");

    // Simulate a private stream the user isn't subscribed to
    initialize();
    page_params.realm_notifications_stream_id = 89;
    stream_data.initialize();
    assert.equal(page_params.notifications_stream, "");

    // Now actually subscribe the user to the stream
    initialize();
    var foo = {
        name: 'foo',
        stream_id: 89,
    };

    stream_data.add_sub('foo', foo);
    stream_data.initialize();
    assert.equal(page_params.notifications_stream, "foo");
});

run_test('filter inactives', () => {
    page_params.unsubscribed = [];
    page_params.never_subscribed = [];
    page_params.subscriptions = [];

    stream_data.initialize();
    assert(!stream_data.is_filtering_inactives());

    page_params.unsubscribed = [];
    page_params.never_subscribed = [];
    page_params.subscriptions = [];

    _.times(30, function (i) {
        var name = 'random' + i.toString();
        var stream_id = 100 + i;

        var sub = {
            name: name,
            subscribed: true,
            newly_subscribed: false,
            stream_id: stream_id,
        };
        stream_data.add_sub(name, sub);
    });
    stream_data.initialize();
    assert(stream_data.is_filtering_inactives());
});

run_test('get_newbie_stream', () => {
    var newbie = {
        name: 'newbie',
        stream_id: 234,
        subscribed: true,
        in_home_view: true,
    };

    var new_members = {
        subscribed: true,
        name: 'new members',
        stream_id: 531,
    };

    assert.equal(stream_data.get_newbie_stream(), undefined);

    stream_data.add_sub('newbie', newbie);
    page_params.notifications_stream = 'newbie';
    assert.equal(stream_data.get_newbie_stream(), 'newbie');

    newbie.in_home_view = false;
    assert.equal(stream_data.get_newbie_stream(), undefined);

    stream_data.add_sub('new members', new_members);
    assert.equal(stream_data.get_newbie_stream(), 'new members');

    new_members.subscribed = false;
    assert.equal(stream_data.get_newbie_stream(), undefined);
});

run_test('invite_streams', () => {
    // add default stream
    var orie = {
        stream_id: 320,
        name: 'Orie',
        subscribed: true,
    };

    // clear all the data form stream_data, and people
    stream_data.clear_subscriptions();
    people.init();

    stream_data.add_sub('Orie', orie);
    stream_data.set_realm_default_streams([orie]);

    var expected_list = ['Orie'];
    assert.deepEqual(stream_data.invite_streams(), expected_list);

    var inviter = {
        stream_id: 25,
        name: 'Inviter',
        subscribed: true,
    };
    stream_data.add_sub('Inviter', inviter);

    expected_list.push('Inviter');
    assert.deepEqual(stream_data.invite_streams(), expected_list);
});

run_test('edge_cases', () => {
    var bad_stream_ids = [555555, 99999];

    // just make sure we don't explode
    stream_data.sort_for_stream_settings(bad_stream_ids);
});

run_test('get_invite_stream_data', () => {
    // add default stream
    var orie = {
        name: 'Orie',
        stream_id: 320,
        invite_only: false,
        subscribed: true,
    };

    // clear all the data form stream_data, and people
    stream_data.clear_subscriptions();
    people.init();

    stream_data.add_sub('Orie', orie);
    stream_data.set_realm_default_streams([orie]);

    var expected_list = [{
        name: 'Orie',
        stream_id: 320,
        invite_only: false,
        default_stream: true,
    }];
    assert.deepEqual(stream_data.get_invite_stream_data(), expected_list);

    var inviter = {
        name: 'Inviter',
        stream_id: 25,
        invite_only: true,
        subscribed: true,
    };
    stream_data.add_sub('Inviter', inviter);

    expected_list.push({
        name: 'Inviter',
        stream_id: 25,
        invite_only: true,
        default_stream: false,
    });
    assert.deepEqual(stream_data.get_invite_stream_data(), expected_list);
});
