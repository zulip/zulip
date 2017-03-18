global.stub_out_jquery();

set_global('page_params', {
    is_admin: false,
    people_list: [],
});

add_dependencies({
    people: 'js/people.js',
    stream_color: 'js/stream_color.js',
    narrow: 'js/narrow.js',
    hashchange: 'js/hashchange.js',
    util: 'js/util.js',
});

set_global('blueslip', {});

var stream_data = require('js/stream_data.js');
var people = global.people;

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

    assert(stream_data.in_home_view('social'));
    assert(!stream_data.in_home_view('denmark'));
}());

(function test_get_by_id() {
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

(function test_process_message_for_recent_topics() {
    var message = {
        stream: 'Rome',
        timestamp: 101,
        subject: 'toPic1',
    };
    stream_data.process_message_for_recent_topics(message);

    var history = stream_data.get_recent_topics('Rome');
    assert.deepEqual(history, [
        {
            subject: 'toPic1',
            canon_subject: 'topic1',
            count: 1,
            timestamp: 101,
        },
    ]);

    message = {
        stream: 'Rome',
        timestamp: 102,
        subject: 'Topic1',
    };
    stream_data.process_message_for_recent_topics(message);
    history = stream_data.get_recent_topics('Rome');
    assert.deepEqual(history, [
        {
            subject: 'Topic1',
            canon_subject: 'topic1',
            count: 2,
            timestamp: 102,
        },
    ]);

    message = {
        stream: 'Rome',
        timestamp: 103,
        subject: 'topic2',
    };
    stream_data.process_message_for_recent_topics(message);
    history = stream_data.get_recent_topics('Rome');
    assert.deepEqual(history, [
        {
            subject: 'topic2',
            canon_subject: 'topic2',
            count: 1,
            timestamp: 103,
        },
        {
            subject: 'Topic1',
            canon_subject: 'topic1',
            count: 2,
            timestamp: 102,
        },
    ]);

    stream_data.process_message_for_recent_topics(message, true);
    history = stream_data.get_recent_topics('Rome');
    assert.deepEqual(history, [
        {
            subject: 'Topic1',
            canon_subject: 'topic1',
            count: 2,
            timestamp: 102,
        },
    ]);
}());

(function test_admin_options() {
    function make_sub() {
        return {
            subscribed: false,
            color: 'blue',
            name: 'stream_to_admin',
            stream_id: 1,
            in_home_view: false,
            invite_only: false,
        };
    }

    // non-admins can't do anything
    global.page_params.is_admin = false;
    var sub = make_sub();
    stream_data.add_admin_options(sub);
    assert(!sub.is_admin);
    assert(!sub.can_make_public);
    assert(!sub.can_make_private);

    // just a sanity check that we leave "normal" fields alone
    assert.equal(sub.color, 'blue');

    // the remaining cases are for admin users
    global.page_params.is_admin = true;

    // admins can make public streams become private
    sub = make_sub();
    stream_data.add_admin_options(sub);
    assert(sub.is_admin);
    assert(!sub.can_make_public);
    assert(sub.can_make_private);

    // admins can only make private streams become public
    // if they are subscribed
    sub = make_sub();
    sub.invite_only = true;
    sub.subscribed = false;
    stream_data.add_admin_options(sub);
    assert(sub.is_admin);
    assert(!sub.can_make_public);
    assert(!sub.can_make_private);

    sub = make_sub();
    sub.invite_only = true;
    sub.subscribed = true;
    stream_data.add_admin_options(sub);
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
    };

    var blue = {
        stream_id: 2,
        name: 'b',
        color: 'blue',
        subscribed: false,
    };

    var amber = {
        stream_id: 3,
        name: 'a',
        color: 'amber',
        subscribed: true,
    };
    stream_data.clear_subscriptions();
    stream_data.add_sub(cinnamon.name, cinnamon);
    stream_data.add_sub(amber.name, amber);
    stream_data.add_sub(blue.name, blue);

    var sub_rows = stream_data.get_streams_for_settings_page();
    assert.equal(sub_rows[0].color, 'blue');
    assert.equal(sub_rows[1].color, 'amber');
    assert.equal(sub_rows[2].color, 'cinnamon');

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
