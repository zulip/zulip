var assert = require('assert');
var noop = function () {};
set_global('$', global.make_zjquery());

set_global('colorspace', {
    sRGB_to_linear: noop,
    luminance_to_lightness: function () {
        return 1;
    },
});

add_dependencies({
    stream_data: 'js/stream_data.js',
});

var stream_events = require('js/stream_events.js');
var with_overrides = global.with_overrides;

var frontend = {
    subscribed: true,
    color: 'yellow',
    name: 'frontend',
    stream_id: 1,
    in_home_view: false,
    invite_only: false,
};
stream_data.add_sub('Frontend', frontend);

(function test_update_property() {
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
}());
