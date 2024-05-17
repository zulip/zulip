"use strict";

const {strict: assert} = require("assert");

const {mock_esm, set_global, zrequire} = require("./lib/namespace");
const {make_stub} = require("./lib/stub");
const {run_test} = require("./lib/test");
const blueslip = require("./lib/zblueslip");
const $ = require("./lib/zjquery");
const {current_user} = require("./lib/zpage_params");

// These unit tests for web/src/message_list.js emphasize the model-ish
// aspects of the MessageList class.  We have to stub out a few functions
// related to views and events to get the tests working.

const noop = function () {};

set_global("document", {
    to_$() {
        return {
            trigger() {},
        };
    },
});

const narrow_state = mock_esm("../src/narrow_state");
const stream_data = mock_esm("../src/stream_data");

const {MessageList} = zrequire("message_list");
function MessageListView() {
    return {
        maybe_rerender: noop,
        append: noop,
        prepend: noop,
        clear_rendering_state: noop,
        is_current_message_list: () => true,
    };
}
mock_esm("../src/message_list_view", {
    MessageListView,
});
const {Filter} = zrequire("filter");

run_test("basics", ({override}) => {
    const filter = new Filter([]);

    const list = new MessageList({
        filter,
    });

    const messages = [
        {
            id: 50,
            content: "fifty",
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

    assert.equal(list.get(50).content, "fifty");

    assert.equal(list.closest_id(49), 50);
    assert.equal(list.closest_id(50), 50);
    assert.equal(list.closest_id(51), 50);
    assert.equal(list.closest_id(59), 60);
    assert.equal(list.closest_id(60), 60);
    assert.equal(list.closest_id(61), 60);

    assert.deepEqual(list.all_messages(), messages);

    override($, "Event", (ev) => {
        assert.equal(ev, "message_selected.zulip");
    });
    list.select_id(50);

    assert.equal(list.selected_id(), 50);
    assert.equal(list.selected_idx(), 0);

    list.advance_past_messages([60, 80]);
    assert.equal(list.selected_id(), 60);
    assert.equal(list.selected_idx(), 1);

    // Make sure not rerendered when reselected
    let num_renders = 0;
    list.rerender = function () {
        num_renders += 1;
    };
    list.reselect_selected_id();
    assert.equal(num_renders, 0);
    assert.equal(list.selected_id(), 60);

    const old_messages = [
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

    const new_messages = [
        {
            id: 90,
        },
    ];
    list.append(new_messages, true);
    assert.equal(list.last().id, 90);

    list.view.clear_table = function () {};

    list.remove_and_rerender([60]);
    const removed = list.all_messages().filter((msg) => msg.id !== 60);
    assert.deepEqual(list.all_messages(), removed);

    list.clear();
    assert.deepEqual(list.all_messages(), []);
});

run_test("prev_next", () => {
    const list = new MessageList({
        filter: new Filter([]),
    });

    assert.equal(list.prev(), undefined);
    assert.equal(list.next(), undefined);
    assert.equal(list.is_at_end(), false);

    // try to confuse things with bogus selected id
    list.data.set_selected_id(33);
    assert.equal(list.prev(), undefined);
    assert.equal(list.next(), undefined);
    assert.equal(list.is_at_end(), false);

    const messages = [{id: 30}, {id: 40}, {id: 50}, {id: 60}];
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

run_test("message_range", () => {
    const list = new MessageList({
        filter: new Filter([]),
    });

    const messages = [{id: 30}, {id: 40}, {id: 50}, {id: 60}];
    list.append(messages, true);
    assert.deepEqual(list.message_range(2, 30), [{id: 30}]);
    assert.deepEqual(list.message_range(2, 31), [{id: 30}, {id: 40}]);
    assert.deepEqual(list.message_range(30, 40), [{id: 30}, {id: 40}]);
    assert.deepEqual(list.message_range(31, 39), [{id: 40}]);
    assert.deepEqual(list.message_range(31, 1000), [{id: 40}, {id: 50}, {id: 60}]);
    blueslip.expect("error", "message_range given a start of -1");
    assert.deepEqual(list.message_range(-1, 40), [{id: 30}, {id: 40}]);
});

run_test("nth_most_recent_id", () => {
    const list = new MessageList({
        filter: new Filter([]),
    });
    list.append([{id: 10}, {id: 20}, {id: 30}]);
    assert.equal(list.nth_most_recent_id(1), 30);
    assert.equal(list.nth_most_recent_id(2), 20);
    assert.equal(list.nth_most_recent_id(3), 10);
    assert.equal(list.nth_most_recent_id(4), -1);
});

run_test("change_message_id", () => {
    const list = new MessageList({
        filter: new Filter([]),
    });
    list.data._add_to_hash([
        {id: 10.5, content: "good job"},
        {id: 20.5, content: "ok!"},
    ]);

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

run_test("last_sent_by_me", () => {
    const list = new MessageList({
        filter: new Filter([]),
    });
    const items = [
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
    current_user.user_id = 3;
    // Look for the last message where user_id == 3 (our ID)
    assert.equal(list.get_last_message_sent_by_me().id, 2);
});

run_test("local_echo", () => {
    let list = new MessageList({
        filter: new Filter([]),
    });
    list.append([
        {id: 10},
        {id: 20},
        {id: 30},
        {id: 20.02},
        {id: 20.03},
        {id: 40},
        {id: 50},
        {id: 60},
    ]);
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

    list = new MessageList({
        filter: new Filter([]),
    });
    list.append([
        {id: 10},
        {id: 20},
        {id: 30},
        {id: 20.02},
        {id: 20.03},
        {id: 40},
        {id: 50},
        {id: 50.01},
        {id: 50.02},
        {id: 60},
    ]);
    list._local_only = {
        20.02: {id: 20.02},
        20.03: {id: 20.03},
        50.01: {id: 50.01},
        50.02: {id: 50.02},
    };

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

run_test("bookend", ({override}) => {
    const list = new MessageList({
        filter: new Filter([]),
    });

    list.view.clear_trailing_bookend = noop;
    list.narrowed = true;

    override(narrow_state, "stream_name", () => "IceCream");

    let is_subscribed = true;
    let invite_only = false;

    override(stream_data, "is_subscribed_by_name", () => is_subscribed);
    override(stream_data, "get_sub", () => ({invite_only}));
    override(stream_data, "can_toggle_subscription", () => true);

    {
        const stub = make_stub();
        list.view.render_trailing_bookend = stub.f;
        list.update_trailing_bookend();
        assert.equal(stub.num_calls, 1);
        const bookend = stub.get_args(
            "stream_name",
            "subscribed",
            "deactivated",
            "just_unsubscribed",
        );
        assert.equal(bookend.stream_name, "IceCream");
        assert.equal(bookend.subscribed, true);
        assert.equal(bookend.deactivated, false);
        assert.equal(bookend.just_unsubscribed, false);
    }

    list.last_message_historical = false;
    is_subscribed = false;

    {
        const stub = make_stub();
        list.view.render_trailing_bookend = stub.f;
        list.update_trailing_bookend();
        assert.equal(stub.num_calls, 1);
        const bookend = stub.get_args(
            "stream_name",
            "subscribed",
            "deactivated",
            "just_unsubscribed",
        );
        assert.equal(bookend.stream_name, "IceCream");
        assert.equal(bookend.subscribed, false);
        assert.equal(bookend.deactivated, false);
        assert.equal(bookend.just_unsubscribed, true);
    }

    // Test when the stream is privates (invite only)
    invite_only = true;

    {
        const stub = make_stub();
        list.view.render_trailing_bookend = stub.f;
        list.update_trailing_bookend();
        assert.equal(stub.num_calls, 1);
        const bookend = stub.get_args(
            "stream_name",
            "subscribed",
            "deactivated",
            "just_unsubscribed",
        );
        assert.equal(bookend.stream_name, "IceCream");
        assert.equal(bookend.subscribed, false);
        assert.equal(bookend.deactivated, false);
        assert.equal(bookend.just_unsubscribed, true);
    }

    list.last_message_historical = true;

    {
        const stub = make_stub();
        list.view.render_trailing_bookend = stub.f;
        list.update_trailing_bookend();
        assert.equal(stub.num_calls, 1);
        const bookend = stub.get_args(
            "stream_name",
            "subscribed",
            "deactivated",
            "just_unsubscribed",
        );
        assert.equal(bookend.stream_name, "IceCream");
        assert.equal(bookend.subscribed, false);
        assert.equal(bookend.deactivated, false);
        assert.equal(bookend.just_unsubscribed, false);
    }
});

run_test("add_remove_rerender", () => {
    const filter = new Filter([]);
    const list = new MessageList({
        filter,
    });

    const messages = [{id: 1}, {id: 2}, {id: 3}];

    list.add_messages(messages);
    assert.equal(list.num_items(), 3);

    {
        const stub = make_stub();
        list.rerender = stub.f;
        const message_ids = messages.map((msg) => msg.id);
        list.remove_and_rerender(message_ids);
        assert.equal(stub.num_calls, 1);
        assert.equal(list.num_items(), 0);
    }
});
