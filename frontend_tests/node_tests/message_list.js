// These unit tests for static/js/message_list.js emphasize the model-ish
// aspects of the MessageList class.  We have to stub out a few functions
// related to views and events to get the tests working.

var noop = function () {};

add_dependencies({
    util: 'js/util.js',
    muting: 'js/muting.js',
    MessageListView: 'js/message_list_view.js',
    i18n: 'i18next',
});


set_global('document', null);

global.stub_out_jquery();

set_global('feature_flags', {});
set_global('Filter', noop);

var with_overrides = global.with_overrides; // make lint happy
var MessageList = require('js/message_list').MessageList;

(function test_basics() {
    var table;
    var filter = {};

    var list = new MessageList(table, filter);

    var messages = [
        {
            id: 50,
            content: 'fifty',
        },
        {
            id: 60,
        },
        {
            id: 70,
        },
        {
            id: 80,
        },
    ];

    assert.equal(list.empty(), true);

    list.append(messages, true);

    assert.equal(list.num_items(), 4);
    assert.equal(list.empty(), false);
    assert.equal(list.first().id, 50);
    assert.equal(list.last().id, 80);

    assert.equal(list.get(50).content, 'fifty');

    assert.equal(list.closest_id(49), 50);
    assert.equal(list.closest_id(50), 50);
    assert.equal(list.closest_id(51), 50);
    assert.equal(list.closest_id(59), 60);
    assert.equal(list.closest_id(60), 60);
    assert.equal(list.closest_id(61), 60);

    assert.deepEqual(list.all_messages(), messages);

    global.$.Event = function (ev) {
        assert.equal(ev, 'message_selected.zulip');
    };
    list.select_id(50);

    assert.equal(list.selected_id(), 50);
    assert.equal(list.selected_idx(), 0);

    list.advance_past_messages([60, 80]);
    assert.equal(list.selected_id(), 60);
    assert.equal(list.selected_idx(), 1);

    // Make sure not rerendered when reselected
    var num_renders = 0;
    list.rerender = function () {
        num_renders += 1;
    };
    list.reselect_selected_id();
    assert.equal(num_renders, 0);
    assert.equal(list.selected_id(), 60);

    var old_messages = [
        {
            id: 30,
        },
        {
            id: 40,
        },
    ];
    list.prepend(old_messages, true);
    assert.equal(list.first().id, 30);
    assert.equal(list.last().id, 80);

    var new_messages = [
        {
            id: 90,
        },
    ];
    list.append(new_messages, true);
    assert.equal(list.last().id, 90);

    list.view.clear_table = function () {};

    list.remove_and_rerender([{id: 60}]);
    var removed = list.all_messages().filter(function (msg) {
        return msg.id !== 60;
    });
    assert.deepEqual(list.all_messages(), removed);

    list.clear();
    assert.deepEqual(list.all_messages(), []);
}());

(function test_nth_most_recent_id() {
    var table;
    var filter = {};

    var list = new MessageList(table, filter);
    list.append([{id:10}, {id:20}, {id:30}]);
    assert.equal(list.nth_most_recent_id(1), 30);
    assert.equal(list.nth_most_recent_id(2), 20);
    assert.equal(list.nth_most_recent_id(3), 10);
    assert.equal(list.nth_most_recent_id(4), -1);
}());


(function test_local_echo() {
    var table;
    var filter = {};

    var list = new MessageList(table, filter);
    list.append([{id:10}, {id:20}, {id:30}, {id:20.02}, {id:20.03}, {id:40}, {id:50}, {id:60}]);
    list._local_only= {20.02: {id:20.02}, 20.03: {id:20.03}};

    assert.equal(list.closest_id(10), 10);
    assert.equal(list.closest_id(20), 20);
    assert.equal(list.closest_id(30), 30);
    assert.equal(list.closest_id(20.02), 20.02);
    assert.equal(list.closest_id(20.03), 20.03);
    assert.equal(list.closest_id(29), 30);
    assert.equal(list.closest_id(40), 40);
    assert.equal(list.closest_id(50), 50);
    assert.equal(list.closest_id(60), 60);

    assert.equal(list.closest_id(60), 60);
    assert.equal(list.closest_id(21), 20);
    assert.equal(list.closest_id(29), 30);
    assert.equal(list.closest_id(31), 30);
    assert.equal(list.closest_id(54), 50);
    assert.equal(list.closest_id(58), 60);


    list = new MessageList(table, filter);
    list.append([{id:10}, {id:20}, {id:30}, {id:20.02}, {id:20.03}, {id:40},
                 {id:50}, {id: 50.01}, {id: 50.02}, {id:60}]);
    list._local_only= {20.02: {id:20.02}, 20.03: {id:20.03},
                       50.01: {id: 50.01}, 50.02: {id: 50.02}};

    assert.equal(list.closest_id(10), 10);
    assert.equal(list.closest_id(20), 20);
    assert.equal(list.closest_id(30), 30);
    assert.equal(list.closest_id(20.02), 20.02);
    assert.equal(list.closest_id(20.03), 20.03);
    assert.equal(list.closest_id(40), 40);
    assert.equal(list.closest_id(50), 50);
    assert.equal(list.closest_id(60), 60);

    assert.equal(list.closest_id(60), 60);
    assert.equal(list.closest_id(21), 20);
    assert.equal(list.closest_id(29), 30);
    assert.equal(list.closest_id(31), 30);
    assert.equal(list.closest_id(47), 50);
    assert.equal(list.closest_id(51), 50.02);
    assert.equal(list.closest_id(59), 60);
    assert.equal(list.closest_id(50.01), 50.01);
}());

(function test_bookend() {
    var table;
    var filter = {};

    var list = new MessageList(table, filter);

    with_overrides(function (override) {
        var expected = "You subscribed to stream IceCream";
        list.view.clear_trailing_bookend = noop;
        list.narrowed = true;

        override("narrow_state.stream", function () {
            return "IceCream";
        });

        override("stream_data.is_subscribed", function () {
            return true;
        });

        global.with_stub(function (stub) {
            list.view.render_trailing_bookend = stub.f;
            list.update_trailing_bookend();
            var bookend = stub.get_args('content', 'subscribed');
            assert.equal(bookend.content, expected);
            assert.equal(bookend.subscribed, true);
        });

        expected = "You unsubscribed from stream IceCream";
        list.last_message_historical = false;
        override("stream_data.is_subscribed", function () {
            return false;
        });

        global.with_stub(function (stub) {
            list.view.render_trailing_bookend = stub.f;
            list.update_trailing_bookend();
            var bookend = stub.get_args('content', 'subscribed');
            assert.equal(bookend.content, expected);
            assert.equal(bookend.subscribed, false);
        });

        expected = "You are not subscribed to stream IceCream";
        list.last_message_historical = true;

        global.with_stub(function (stub) {
            list.view.render_trailing_bookend = stub.f;
            list.update_trailing_bookend();
            var bookend = stub.get_args('content', 'subscribed');
            assert.equal(bookend.content, expected);
            assert.equal(bookend.subscribed, false);
        });
    });
}());

(function test_unmuted_messages() {
    var table;
    var filter = {};

    var list = new MessageList(table, filter);

    var unmuted = [
        {
            id: 50,
            stream: 'bad',
            mentioned: true,
        },
        {
            id: 60,
            stream: 'good',
            mentioned: false,
        },
    ];
    var muted = [
        {
            id: 70,
            stream: 'bad',
            mentioned: false,
        },
    ];

    with_overrides(function (override) {
        override('muting.is_topic_muted', function (stream) {
            return stream === 'bad';
        });

        // Make sure unmuted_message filters out the "muted" entry,
        // which we mark as having a muted topic, and not mentioned.
        var test_unmuted = list.unmuted_messages(unmuted.concat(muted));
        assert.deepEqual(unmuted, test_unmuted);
    });
}());
