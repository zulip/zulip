set_global('page_params', {
    is_admin: false,
    realm_users: [],
});

set_global('$', function () {
});

set_global('blueslip', {});

zrequire('util');
zrequire('hash_util');
zrequire('narrow');
zrequire('topic_data');
zrequire('people');
zrequire('stream_color');
zrequire('stream_data');

(function test_basics() {
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
}());

(function test_renames() {
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
}());

(function test_unsubscribe() {
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
}());

(function test_subscribers() {
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
    assert(stream_data.user_is_subscribed('Rome', 'FRED@zulip.com'));
    assert(stream_data.user_is_subscribed('Rome', 'fred@zulip.com'));
    assert(stream_data.user_is_subscribed('Rome', 'george@zulip.com'));
    assert(!stream_data.user_is_subscribed('Rome', 'not_fred@zulip.com'));

    stream_data.set_subscribers(sub, []);

    var email = 'brutus@zulip.com';
    var brutus = {
        email: email,
        full_name: 'Brutus',
        user_id: 104,
    };
    people.add(brutus);
    assert(!stream_data.user_is_subscribed('Rome', email));

    // add
    var ok = stream_data.add_subscriber('Rome', brutus.user_id);
    assert(ok);
    assert(stream_data.user_is_subscribed('Rome', email));
    sub = stream_data.get_sub('Rome');
    stream_data.update_subscribers_count(sub);
    assert.equal(sub.subscriber_count, 1);

    // verify that adding an already-added subscriber is a noop
    stream_data.add_subscriber('Rome', brutus.user_id);
    assert(stream_data.user_is_subscribed('Rome', email));
    sub = stream_data.get_sub('Rome');
    stream_data.update_subscribers_count(sub);
    assert.equal(sub.subscriber_count, 1);

    // remove
    ok = stream_data.remove_subscriber('Rome', brutus.user_id);
    assert(ok);
    assert(!stream_data.user_is_subscribed('Rome', email));
    sub = stream_data.get_sub('Rome');
    stream_data.update_subscribers_count(sub);
    assert.equal(sub.subscriber_count, 0);

    // verify that checking subscription with bad email is a noop
    var bad_email = 'notbrutus@zulip.org';
    global.blueslip.error = function (msg) {
        assert.equal(msg, "Unknown email for get_user_id: " + bad_email);
    };
    global.blueslip.warn = function (msg) {
        assert.equal(msg, "Bad email passed to user_is_subscribed: " + bad_email);
    };
    assert(!stream_data.user_is_subscribed('Rome', bad_email));

    // Verify noop for bad stream when removing subscriber
    var bad_stream = 'UNKNOWN';
    global.blueslip.warn = function (msg) {
        assert.equal(msg, "We got a remove_subscriber call for a non-existent stream " + bad_stream);
    };
    ok = stream_data.remove_subscriber(bad_stream, brutus.user_id);
    assert(!ok);

    // Defensive code will give warnings, which we ignore for the
    // tests, but the defensive code needs to not actually blow up.
    global.blueslip.warn = function () {};

    // verify that removing an already-removed subscriber is a noop
    ok = stream_data.remove_subscriber('Rome', brutus.user_id);
    assert(!ok);
    assert(!stream_data.user_is_subscribed('Rome', email));
    sub = stream_data.get_sub('Rome');
    stream_data.update_subscribers_count(sub);
    assert.equal(sub.subscriber_count, 0);

    // Verify defensive code in set_subscribers, where the second parameter
    // can be undefined.
    stream_data.set_subscribers(sub);
    stream_data.add_sub('Rome', sub);
    stream_data.add_subscriber('Rome', brutus.user_id);
    sub.subscribed = true;
    assert(stream_data.user_is_subscribed('Rome', email));

    // Verify that we noop and don't crash when unsubscribed.
    sub.subscribed = false;
    ok = stream_data.add_subscriber('Rome', brutus.user_id);
    assert(ok);
    assert.equal(stream_data.user_is_subscribed('Rome', email), undefined);
    stream_data.remove_subscriber('Rome', brutus.user_id);
    assert.equal(stream_data.user_is_subscribed('Rome', email), undefined);

    // Verify that we don't crash and return false for a bad stream.
    ok = stream_data.add_subscriber('UNKNOWN', brutus.user_id);
    assert(!ok);

    // Verify that we don't crash and return false for a bad user id.
    global.blueslip.error = function () {};
    ok = stream_data.add_subscriber('Rome', 9999999);
    assert(!ok);
}());

(function test_is_active() {
    stream_data.clear_subscriptions();

    var sub = {name: 'pets', subscribed: false, stream_id: 1};
    stream_data.add_sub('pets', sub);

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
}());

(function test_admin_options() {
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
    assert(!sub.can_make_public);
    assert(!sub.can_make_private);

    // just a sanity check that we leave "normal" fields alone
    assert.equal(sub.color, 'blue');

    // the remaining cases are for admin users
    global.page_params.is_admin = true;

    // admins can make public streams become private
    sub = make_sub();
    stream_data.update_calculated_fields(sub);
    assert(sub.is_admin);
    assert(!sub.can_make_public);
    assert(sub.can_make_private);

    // admins can only make private streams become public
    // if they are subscribed
    sub = make_sub();
    sub.invite_only = true;
    sub.subscribed = false;
    stream_data.update_calculated_fields(sub);
    assert(sub.is_admin);
    assert(!sub.can_make_public);
    assert(!sub.can_make_private);

    sub = make_sub();
    sub.invite_only = true;
    sub.subscribed = true;
    stream_data.update_calculated_fields(sub);
    assert(sub.is_admin);
    assert(sub.can_make_public);
    assert(!sub.can_make_private);
}());

(function test_stream_settings() {
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

}());

(function test_get_non_default_stream_names() {
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

    stream_data.clear_subscriptions();
    stream_data.set_realm_default_streams([announce]);
    stream_data.add_sub('announce', announce);
    stream_data.add_sub('public_stream', public_stream);
    stream_data.add_sub('private_stream', private_stream);

    var names = stream_data.get_non_default_stream_names();
    assert.deepEqual(names, ['public']);
}());

(function test_delete_sub() {
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
}());

(function test_get_subscriber_count() {
    var india = {
        stream_id: 102,
        name: 'India',
        subscribed: true,
    };
    stream_data.clear_subscriptions();
    assert.equal(stream_data.get_subscriber_count('India'), undefined);
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
}());

(function test_notifications() {
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
}());

(function test_in_home_view() {
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
}());

(function test_notifications_in_home_view() {
    page_params.notifications_stream = 'tony';
    assert(stream_data.notifications_in_home_view());

    page_params.notifications_stream = 'jazy';
    assert(!stream_data.notifications_in_home_view());
}());

(function test_remove_default_stream() {
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
}());
