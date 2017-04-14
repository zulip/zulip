var noop = function () {};
var return_false = function () { return false; };

set_global('document', {
    location: {
    },
});

set_global('page_params', {
    use_websockets: false,
});

set_global('$', function () {
});

add_dependencies({
    compose: 'js/compose',
    util: 'js/util',
});

var compose_actions = require('js/compose_actions.js');

var start = compose_actions.start;
var cancel = compose_actions.cancel;
var get_focus_area = compose_actions._get_focus_area;

set_global('reload', {
    is_in_progress: return_false,
});

set_global('notifications', {
    clear_compose_notifications: noop,
});

set_global('compose_fade', {
    clear_compose: noop,
});

set_global('resize', {
    resize_bottom_whitespace: noop,
});

set_global('narrow_state', {
    set_compose_defaults: noop,
});

// these are shimmed in shim.js
set_global('compose_state', {
    composing: global.compose.composing,
    recipient: global.compose.recipient,
});

set_global('status_classes', 'status_classes');

var fake_jquery = function () {
    var elems = {};

    function new_elem(selector) {
        var value;
        var shown = false;
        var self = {
            val: function () {
                if (arguments.length === 0) {
                    return value || '';
                }
                value = arguments[0];
            },
            css: noop,
            data: noop,
            empty: noop,
            height: noop,
            removeAttr: noop,
            removeData: noop,
            trigger: noop,
            show: function () {
                shown = true;
            },
            hide: function () {
                shown = false;
            },
            addClass: function (class_name) {
                assert.equal(class_name, 'active');
                shown = true;
            },
            removeClass: function (class_name) {
                if (class_name === 'status_classes') {
                    return self;
                }
                assert.equal(class_name, 'active');
                shown = false;
            },
            debug: function () {
                return {
                    value: value,
                    shown: shown,
                    selector: selector,
                };
            },
            visible: function () {
                return shown;
            },
        };
        return self;
    }

    var $ = function (selector) {
        if (elems[selector] === undefined) {
            var elem = new_elem(selector);
            elems[selector] = elem;
        }
        return elems[selector];
    };

    $.trim = function (s) { return s; };

    $.state = function () {
        // useful for debugging
        var res =  _.map(elems, function (v) {
            return v.debug();
        });

        res = _.map(res, function (v) {
            return [v.selector, v.value, v.shown];
        });

        res.sort();

        return res;
    };

    $.Event = noop;

    return $;
};

set_global('$', fake_jquery());
var $ = global.$;

function assert_visible(sel) {
    assert($(sel).visible());
}

function assert_hidden(sel) {
    assert(!$(sel).visible());
}

(function test_start() {
    compose_actions.autosize_message_content = noop;
    compose_actions.expand_compose_box = noop;
    compose_actions.set_focus = noop;
    compose_actions.complete_starting_tasks = noop;
    compose_actions.blur_textarea = noop;
    compose_actions.clear_textarea = noop;

    // Start stream message
    global.narrow_state.set_compose_defaults = function (opts) {
        opts.stream = 'stream1';
        opts.subject = 'topic1';
    };

    var opts = {};
    start('stream', opts);

    assert_visible('#stream-message');
    assert_hidden('#private-message');

    assert.equal($('#stream').val(), 'stream1');
    assert.equal($('#subject').val(), 'topic1');

    // Start PM
    global.narrow_state.set_compose_defaults = function (opts) {
        opts.private_message_recipient = 'foo@example.com';
    };

    opts = {
        content: 'hello',
    };
    start('private', opts);

    assert_hidden('#stream-message');
    assert_visible('#private-message');

    assert.equal($('#private_message_recipient').val(), 'foo@example.com');
    assert.equal($('#new_message_content').val(), 'hello');

    // Cancel compose.
    assert_hidden('#compose_controls');
    cancel();
    assert_visible('#compose_controls');
    assert_hidden('#private-message');
}());


(function test_get_focus_area() {
    assert.equal(get_focus_area('private', {}), 'private_message_recipient');
    assert.equal(get_focus_area('private', {
        private_message_recipient: 'bob@example.com'}), 'new_message_content');
    assert.equal(get_focus_area('stream', {}), 'stream');
    assert.equal(get_focus_area('stream', {stream: 'fun'}),
                 'subject');
    assert.equal(get_focus_area('stream', {stream: 'fun',
                                           subject: 'more'}),
                 'new_message_content');
    assert.equal(get_focus_area('stream', {stream: 'fun',
                                           subject: 'more',
                                           trigger: 'new topic button'}),
                 'subject');
}());
