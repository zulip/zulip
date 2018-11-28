var noop = function () {};
var return_true = function () { return true; };
set_global('$', global.make_zjquery());
set_global('document', 'document-stub');

set_global('colorspace', {
    sRGB_to_linear: noop,
    luminance_to_lightness: function () {
        return 1;
    },
});

zrequire('people');
zrequire('stream_data');
zrequire('stream_events');
var with_overrides = global.with_overrides;

var george = {
    email: 'george@zulip.com',
    full_name: 'George',
    user_id: 103,
};
people.add(george);

var frontend = {
    subscribed: false,
    color: 'yellow',
    name: 'frontend',
    stream_id: 1,
    in_home_view: false,
    invite_only: false,
};

stream_data.add_sub(frontend.name, frontend);

run_test('update_property', () => {
    // Invoke error for non-existent stream/property
    with_overrides(function (override) {
        var errors = 0;
        override('blueslip.warn', function () {
            errors += 1;
        });

        stream_events.update_property(99, 'color', 'blue');
        assert.equal(errors, 1);

        stream_events.update_property(1, 'not_real', 42);
        assert.equal(errors, 2);
    });

    // Test update color
    with_overrides(function (override) {
        global.with_stub(function (stub) {
            override('stream_color.update_stream_color', stub.f);
            stream_events.update_property(1, 'color', 'blue');
            var args = stub.get_args('sub', 'val');
            assert.equal(args.sub.stream_id, 1);
            assert.equal(args.val, 'blue');
        });
    });

    // Test in home view
    with_overrides(function (override) {
        global.with_stub(function (stub) {
            override('stream_muting.update_in_home_view', stub.f);
            stream_events.update_property(1, 'in_home_view', true);
            var args = stub.get_args('sub', 'val');
            assert.equal(args.sub.stream_id, 1);
            assert.equal(args.val, true);
        });
    });

    // Test desktop notifications
    stream_events.update_property(1, 'desktop_notifications', true);
    assert.equal(frontend.desktop_notifications, true);
    var checkbox = $(".subscription_settings[data-stream-id='1'] #sub_desktop_notifications_setting .sub_setting_control");
    assert.equal(checkbox.prop('checked'), true);

    // Tests audible notifications
    stream_events.update_property(1, 'audible_notifications', true);
    assert.equal(frontend.audible_notifications, true);
    checkbox = $(".subscription_settings[data-stream-id='1'] #sub_audible_notifications_setting .sub_setting_control");
    assert.equal(checkbox.prop('checked'), true);

    // Tests push notifications
    stream_events.update_property(1, 'push_notifications', true);
    assert.equal(frontend.push_notifications, true);
    checkbox = $(".subscription_settings[data-stream-id='1'] #sub_push_notifications_setting .sub_setting_control");
    assert.equal(checkbox.prop('checked'), true);

    // Tests email notifications
    stream_events.update_property(1, 'email_notifications', true);
    assert.equal(frontend.email_notifications, true);
    checkbox = $(".subscription_settings[data-stream-id='1'] #sub_email_notifications_setting .sub_setting_control");
    assert.equal(checkbox.prop('checked'), true);

    // Test name change
    with_overrides(function (override) {
        global.with_stub(function (stub) {
            override('subs.update_stream_name', stub.f);
            stream_events.update_property(1, 'name', 'the frontend');
            var args = stub.get_args('sub', 'val');
            assert.equal(args.sub.stream_id, 1);
            assert.equal(args.val, 'the frontend');
        });
    });

    // Test description change
    with_overrides(function (override) {
        global.with_stub(function (stub) {
            override('subs.update_stream_description', stub.f);
            stream_events.update_property(1, 'description', 'we write code');
            var args = stub.get_args('sub', 'val');
            assert.equal(args.sub.stream_id, 1);
            assert.equal(args.val, 'we write code');
        });
    });

    // Test email address change
    stream_events.update_property(1, 'email_address', 'zooly@zulip.com');
    assert.equal(frontend.email_address, 'zooly@zulip.com');

    // Test pin to top
    with_overrides(function (override) {
        override('stream_list.refresh_pinned_or_unpinned_stream', noop);
        stream_events.update_property(1, 'pin_to_top', true);
        checkbox = $('#pinstream-1');
        assert.equal(checkbox.prop('checked'), true);
    });

});

run_test('marked_subscribed', () => {
    // Test undefined error
    with_overrides(function (override) {
        var errors = 0;
        override('stream_color.update_stream_color', noop);
        override('blueslip.error', function () {
            errors += 1;
        });
        stream_events.mark_subscribed(undefined, [], 'yellow');
        assert.equal(errors, 1);
    });

    // Test early return if subscribed
    with_overrides(function (override) {
        var completed = false;
        override('message_util.do_unread_count_updates', function () {
            completed = true; // This gets run if we continue and don't early return
        });
        var subscribed = {subscribed: true};
        stream_events.mark_subscribed(subscribed, [], 'yellow');
        assert.equal(completed, false);
    });

    set_global('message_list', {
        all: {
            all_messages: function () { return ['msg']; },
        },
    });

    stream_data.subscribe_myself = noop;
    stream_data.set_subscribers = noop;
    stream_data.get_colors = noop;
    stream_data.update_calculated_fields = noop;

    set_global('subs', { update_settings_for_subscribed: noop });
    set_global('narrow_state', { is_for_stream_id: noop });
    set_global('overlays', { streams_open: return_true });

    // Test unread count update
    with_overrides(function (override) {
        global.with_stub(function (stub) {
            override('stream_color.update_stream_color', noop);
            override('message_util.do_unread_count_updates', stub.f);
            stream_events.mark_subscribed(frontend, [], '');
            var args = stub.get_args('messages');
            assert.deepEqual(args.messages, ['msg']);
        });
    });

    set_global('message_util', { do_unread_count_updates: noop });

    // Test jQuery event
    with_overrides(function (override) {
        override('stream_color.update_stream_color', noop);
        global.with_stub(function (stub) {
            $(document).on('subscription_add_done.zulip', stub.f);
            stream_events.mark_subscribed(frontend, [], '');
            var args = stub.get_args('event');
            assert.equal(args.event.sub.stream_id, 1);
        });
    });

    // Test bookend update
    with_overrides(function (override) {
        override('stream_color.update_stream_color', noop);
        override('narrow_state.is_for_stream_id', function () {
            return true;
        });
        var updated = false;
        override('current_msg_list.update_trailing_bookend', function () {
            updated = true;
        });
        stream_events.mark_subscribed(frontend, [], '');
        assert.equal(updated, true);
    });

    // reset overridden value
    set_global('narrow_state', { is_for_stream_id: noop });

    // Test setting color
    with_overrides(function (override) {
        override('stream_color.update_stream_color', noop);
        stream_events.mark_subscribed(frontend, [], 'blue');
        assert.equal(frontend.color, 'blue');
    });

    // Test assigning generated color
    with_overrides(function (override) {
        frontend.color = undefined;
        override('color_data.pick_color', function () {
            return 'green';
        });
        var warnings = 0;
        override('blueslip.warn', function () {
            warnings += 1;
        });

        global.with_stub(function (stub) {
            override('stream_color.update_stream_color', noop);
            override('subs.set_color', stub.f);
            stream_events.mark_subscribed(frontend, [], undefined);
            var args = stub.get_args('id', 'color');
            assert.equal(args.id, 1);
            assert.equal(args.color, 'green');
            assert.equal(warnings, 1);
        });
    });

    // Test assigning subscriber emails
    with_overrides(function (override) {
        override('stream_color.update_stream_color', noop);
        global.with_stub(function (stub) {
            override('stream_data.set_subscribers', stub.f);
            var user_ids = [15, 20, 25];
            stream_events.mark_subscribed(frontend, user_ids, '');
            var args = stub.get_args('sub', 'subscribers');
            assert.deepEqual(frontend, args.sub);
            assert.deepEqual(user_ids, args.subscribers);
        });

        // assign self as well
        global.with_stub(function (stub) {
            override('stream_data.subscribe_myself', stub.f);
            stream_events.mark_subscribed(frontend, [], '');
            var args = stub.get_args('sub');
            assert.deepEqual(frontend, args.sub);
        });

        // and finally update subscriber settings
        global.with_stub(function (stub) {
            override('subs.update_settings_for_subscribed', stub.f);
            stream_events.mark_subscribed(frontend, [], '');
            var args = stub.get_args('sub');
            assert.deepEqual(frontend, args.sub);
        });
    });
});

run_test('mark_unsubscribed', () => {
    var removed_sub = false;
    $(document).on('subscription_remove_done.zulip', function () {
        removed_sub = true;
    });

    // take no action if no sub specified
    stream_events.mark_unsubscribed();
    assert.equal(removed_sub, false);

    // take no action if already unsubscribed
    frontend.subscribed = false;
    stream_events.mark_unsubscribed(frontend);
    assert.equal(removed_sub, false);

    // Test unsubscribe
    frontend.subscribed = true;
    with_overrides(function (override) {
        global.with_stub(function (stub) {
            override('stream_data.unsubscribe_myself', stub.f);
            override('subs.update_settings_for_unsubscribed', noop);
            stream_events.mark_unsubscribed(frontend);
            var args = stub.get_args('sub');
            assert.deepEqual(args.sub, frontend);
        });
    });

    // Test update settings after unsubscribe
    with_overrides(function (override) {
        global.with_stub(function (stub) {
            override('subs.update_settings_for_unsubscribed', stub.f);
            override('stream_data.unsubscribe_myself', noop);
            stream_events.mark_unsubscribed(frontend);
            var args = stub.get_args('sub');
            assert.deepEqual(args.sub, frontend);
        });
    });

    // Test update bookend and remove done event
    with_overrides(function (override) {
        override('stream_data.unsubscribe_myself', noop);
        override('subs.update_settings_for_unsubscribed', noop);
        override('narrow_state.is_for_stream_id', function () {
            return true;
        });

        var updated = false;
        override('current_msg_list.update_trailing_bookend', function () {
            updated = true;
        });

        var event_triggered = false;
        $(document).trigger = function (ev) {
            assert.equal(ev.name, 'subscription_remove_done.zulip');
            assert.deepEqual(ev.data.sub, frontend);
            event_triggered = true;
        };

        stream_events.mark_unsubscribed(frontend);
        assert.equal(updated, true);
        assert.equal(event_triggered, true);
    });
});

stream_data.clear_subscriptions();
var dev_help = {
    subscribed: true,
    color: 'blue',
    name: 'dev help',
    stream_id: 2,
    in_home_view: false,
    invite_only: false,
};
stream_data.add_sub(dev_help.name, dev_help);

run_test('remove_deactivated_user_from_all_streams', () => {
    subs.rerender_subscriptions_settings = () => {};

    dev_help.can_access_subscribers = true;

    // verify that deactivating user should unsubscribe user from all streams
    assert(stream_data.add_subscriber(dev_help.name, george.user_id));
    assert(dev_help.subscribers.has(george.user_id));

    stream_events.remove_deactivated_user_from_all_streams(george.user_id);

    assert(!dev_help.subscribers.has(george.user_id));
});

