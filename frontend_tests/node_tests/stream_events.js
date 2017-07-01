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
    stream_events: 'js/stream_events.js',
    stream_data: 'js/stream_data.js',
    stream_color: 'js/stream_color.js',
    util: 'js/util.js',
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
}());
