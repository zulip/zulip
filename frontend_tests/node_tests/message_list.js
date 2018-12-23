// These unit tests for static/js/message_list.js emphasize the model-ish
// aspects of the MessageList class.  We have to stub out a few functions
// related to views and events to get the tests working.

var noop = function () {};

set_global('Filter', noop);
global.stub_out_jquery();
set_global('document', null);
set_global('blueslip', global.make_zblueslip());

zrequire('FetchStatus', 'js/fetch_status');
zrequire('util');
zrequire('muting');
zrequire('MessageListData', 'js/message_list_data');
zrequire('MessageListView', 'js/message_list_view');
var MessageList = zrequire('message_list').MessageList;

set_global('i18n', global.stub_i18n);
set_global('feature_flags', {});

var with_overrides = global.with_overrides; // make lint happy

function accept_all_filter() {
    var filter = {
        predicate: () => {
            return () => true;
        },
    };

    return filter;
}

run_test('basics', () => {
    var filter = accept_all_filter();

    var list = new MessageList({
        filter: filter,
    });

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
    list.add_messages(old_messages);
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
});

run_test('prev_next', () => {
    var list = new MessageList({});

    assert.equal(list.prev(), undefined);
    assert.equal(list.next(), undefined);
    assert.equal(list.is_at_end(), false);

    // try to confuse things with bogus selected id
    list.data.set_selected_id(33);
    assert.equal(list.prev(), undefined);
    assert.equal(list.next(), undefined);
    assert.equal(list.is_at_end(), false);

    var messages = [{id: 30}, {id: 40}, {id: 50}, {id: 60}];
    list.append(messages, true);
    assert.equal(list.prev(), undefined);
    assert.equal(list.next(), undefined);

    // The next case is for defensive code.
    list.data.set_selected_id(45);
    assert.equal(list.prev(), undefined);
    assert.equal(list.next(), undefined);
    assert.equal(list.is_at_end(), false);

    list.data.set_selected_id(30);
    assert.equal(list.prev(), undefined);
    assert.equal(list.next(), 40);

    list.data.set_selected_id(50);
    assert.equal(list.prev(), 40);
    assert.equal(list.next(), 60);
    assert.equal(list.is_at_end(), false);

    list.data.set_selected_id(60);
    assert.equal(list.prev(), 50);
    assert.equal(list.next(), undefined);
    assert.equal(list.is_at_end(), true);
});

run_test('message_range', () => {
    var list = new MessageList({});

    var messages = [{id: 30}, {id: 40}, {id: 50}, {id: 60}];
    list.append(messages, true);
    assert.deepEqual(list.message_range(2, 30), [{id: 30}]);
    assert.deepEqual(list.message_range(2, 31), [{id: 30}, {id: 40}]);
    assert.deepEqual(list.message_range(30, 40), [{id: 30}, {id: 40}]);
    assert.deepEqual(list.message_range(31, 39), [{id: 40}]);
    assert.deepEqual(list.message_range(31, 1000), [{id: 40}, {id: 50}, {id: 60}]);
    blueslip.set_test_data('error', 'message_range given a start of -1');
    assert.deepEqual(list.message_range(-1, 40), [{id: 30}, {id: 40}]);
});

run_test('updates', () => {
    var list = new MessageList({});
    list.view.rerender_the_whole_thing = noop;

    var messages = [
        {
            id: 1,
            sender_id: 100,
            sender_full_name: "tony",
            stream_id: 32,
            stream: "denmark",
            small_avatar_url: "http://zulip.spork",
        },
        {
            id: 2,
            sender_id: 39,
            sender_full_name: "jeff",
            stream_id: 64,
            stream: "russia",
            small_avatar_url: "http://github.com",
        },
    ];

    list.append(messages, true);
    list.update_user_full_name(100, "Anthony");
    assert.equal(list.get(1).sender_full_name, "Anthony");
    assert.equal(list.get(2).sender_full_name, "jeff");

    list.update_user_avatar(100, "http://zulip.org");
    assert.equal(list.get(1).small_avatar_url, "http://zulip.org");
    assert.equal(list.get(2).small_avatar_url, "http://github.com");

    list.update_stream_name(64, "Finland");
    assert.equal(list.get(2).stream, "Finland");
    assert.equal(list.get(1).stream, "denmark");
});

run_test('nth_most_recent_id', () => {
    var list = new MessageList({});
    list.append([{id: 10}, {id: 20}, {id: 30}]);
    assert.equal(list.nth_most_recent_id(1), 30);
    assert.equal(list.nth_most_recent_id(2), 20);
    assert.equal(list.nth_most_recent_id(3), 10);
    assert.equal(list.nth_most_recent_id(4), -1);
});

run_test('change_message_id', () => {
    var list = new MessageList({});
    list.data._add_to_hash([{id: 10.5, content: "good job"}, {id: 20.5, content: "ok!"}]);

    // local to local
    list.change_message_id(10.5, 11.5);
    assert.equal(list.get(11.5).content, "good job");

    list.change_message_id(11.5, 11);
    assert.equal(list.get(11).content, "good job");

    list.change_message_id(20.5, 10);
    assert.equal(list.get(10).content, "ok!");

    // test nonexistent id
    assert.equal(list.change_message_id(13, 15), undefined);
});

run_test('last_sent_by_me', () => {
    var list = new MessageList({});
    var items = [
        {
            id: 1,
            sender_id: 3,
        },
        {
            id: 2,
            sender_id: 3,
        },
        {
            id: 3,
            sender_id: 6,
        },
    ];

    list.append(items);
    set_global("page_params", {user_id: 3});
    // Look for the last message where user_id == 3 (our ID)
    assert.equal(list.get_last_message_sent_by_me().id, 2);
});

run_test('local_echo', () => {
    var list = new MessageList({});
    list.append([{id: 10}, {id: 20}, {id: 30}, {id: 20.02},
                 {id: 20.03}, {id: 40}, {id: 50}, {id: 60}]);
    list._local_only = {20.02: {id: 20.02}, 20.03: {id: 20.03}};

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


    list = new MessageList({});
    list.append([
        {id: 10}, {id: 20}, {id: 30}, {id: 20.02}, {id: 20.03}, {id: 40},
        {id: 50}, {id: 50.01}, {id: 50.02}, {id: 60}]);
    list._local_only = {20.02: {id: 20.02}, 20.03: {id: 20.03},
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
});

run_test('bookend', () => {
    var list = new MessageList({});

    with_overrides(function (override) {
        var expected = "translated: You subscribed to stream IceCream";
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
            var bookend = stub.get_args('content', 'subscribed', 'show_button');
            assert.equal(bookend.content, expected);
            assert.equal(bookend.subscribed, true);
            assert.equal(bookend.show_button, true);
        });

        expected = "translated: You unsubscribed from stream IceCream";
        list.last_message_historical = false;
        override("stream_data.is_subscribed", function () {
            return false;
        });

        override("stream_data.get_sub", function () {
            return {invite_only: false};
        });

        global.with_stub(function (stub) {
            list.view.render_trailing_bookend = stub.f;
            list.update_trailing_bookend();
            var bookend = stub.get_args('content', 'subscribed', 'show_button');
            assert.equal(bookend.content, expected);
            assert.equal(bookend.subscribed, false);
            assert.equal(bookend.show_button, true);
        });

        // Test when the stream is privates (invite only)
        expected = "translated: You unsubscribed from stream IceCream";
        override("stream_data.is_subscribed", function () {
            return false;
        });

        override("stream_data.get_sub", function () {
            return {invite_only: true};
        });

        global.with_stub(function (stub) {
            list.view.render_trailing_bookend = stub.f;
            list.update_trailing_bookend();
            var bookend = stub.get_args('content', 'subscribed', 'show_button');
            assert.equal(bookend.content, expected);
            assert.equal(bookend.subscribed, false);
            assert.equal(bookend.show_button, false);
        });

        expected = "translated: You are not subscribed to stream IceCream";
        list.last_message_historical = true;

        global.with_stub(function (stub) {
            list.view.render_trailing_bookend = stub.f;
            list.update_trailing_bookend();
            var bookend = stub.get_args('content', 'subscribed', 'show_button');
            assert.equal(bookend.content, expected);
            assert.equal(bookend.subscribed, false);
            assert.equal(bookend.show_button, true);
        });
    });
});

run_test('unmuted_messages', () => {
    var list = new MessageList({});

    var muted_stream_id = 999;

    var unmuted = [
        {
            id: 50,
            stream_id: muted_stream_id,
            mentioned: true, // overrides mute
            topic: 'whatever',
        },
        {
            id: 60,
            stream_id: 42,
            mentioned: false,
            topic: 'whatever',
        },
    ];
    var muted = [
        {
            id: 70,
            stream_id: muted_stream_id,
            mentioned: false,
            topic: 'whatever',
        },
    ];

    with_overrides(function (override) {
        override('muting.is_topic_muted', function (stream_id) {
            return stream_id === muted_stream_id;
        });

        // Make sure unmuted_message filters out the "muted" entry,
        // which we mark as having a muted topic, and not mentioned.
        var test_unmuted = list.unmuted_messages(unmuted.concat(muted));
        assert.deepEqual(unmuted, test_unmuted);
    });
});

run_test('add_remove_rerender', () => {
    var filter = accept_all_filter();

    var list = new MessageList({filter: filter});

    var messages = [{id: 1}, {id: 2}, {id: 3}];

    list.data.unmuted_messages = function (msgs) { return msgs; };
    list.add_messages(messages);
    assert.equal(list.num_items(), 3);

    global.with_stub(function (stub) {
        list.rerender = stub.f;
        list.remove_and_rerender(messages);
        assert.equal(stub.num_calls, 1);
        assert.equal(list.num_items(), 0);
    });
});
