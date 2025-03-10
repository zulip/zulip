"use strict";

const assert = require("node:assert/strict");

const _ = require("lodash");

const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

set_global("document", "document-stub");

// timerender calls setInterval when imported
mock_esm("../src/timerender", {
    render_date(time) {
        return {outerHTML: String(time.getTime())};
    },
    stringify_time(time) {
        return time.toString("h:mm TT");
    },
});

mock_esm("../src/people", {
    sender_is_bot: () => false,
    sender_is_guest: () => false,
    sender_is_deactivated: () => false,
    should_add_guest_user_indicator: () => false,
    small_avatar_url: () => "fake/small/avatar/url",
    maybe_get_user_by_id: noop,
});

const {Filter} = zrequire("../src/filter");
const {MessageListView} = zrequire("../src/message_list_view");
const message_list = zrequire("message_list");
const {MessageListData} = zrequire("message_list_data");
const muted_users = zrequire("muted_users");

let next_timestamp = 1500000000;

function test(label, f) {
    run_test(label, ({override, mock_template}) => {
        muted_users.set_muted_users([]);
        mock_template("message_list.hbs", false, () => "<message-list-stub>");
        f({override, mock_template});
    });
}

test("msg_edited_and_moved_vars", () => {
    // This is a test to verify that when the stream or topic is changed
    // (and the content is not), the message says "MOVED" rather than "EDITED."

    function build_message_group(messages) {
        return {message_containers: messages};
    }

    function build_list(message_groups) {
        const list = new MessageListView(
            {
                id: 1,
            },
            true,
            true,
        );
        list._message_groups = message_groups;
        return list;
    }

    (function test_msg_moved_var() {
        const messages = [
            // no edit or moved timestamps
            {msg: {}},
            // edit timestamp: EDITED
            {
                msg: {
                    last_edit_timestamp: (next_timestamp += 1),
                },
            },
            // moved timestamp: MOVED
            {
                msg: {
                    last_moved_timestamp: (next_timestamp += 1),
                },
            },
            // both edit and moved timestamp: EDITED
            {
                msg: {
                    last_edit_timestamp: (next_timestamp += 1),
                    last_moved_timestamp: (next_timestamp += 1),
                },
            },
        ];

        const message_group = build_message_group(messages);
        const list = build_list([message_group]);

        for (const message_container of messages) {
            Object.assign(
                message_container,
                list._maybe_get_me_message(message_container.is_hidden, message_container.msg),
                list._get_message_edited_and_moved_vars(message_container.msg),
            );
        }

        const result = list._message_groups[0].message_containers;

        // no edit or moved timestamps
        assert.equal(result[0].edited, false);
        assert.equal(result[0].moved, false);
        assert.equal(result[0].modified, false);
        // edit timestamp: EDITED
        assert.equal(result[1].edited, true);
        assert.equal(result[1].moved, false);
        assert.equal(result[1].modified, true);
        // moved timestamp: MOVED
        assert.equal(result[2].edited, false);
        assert.equal(result[2].moved, true);
        assert.equal(result[2].modified, true);
        // both edit and moved timestamp: EDITED
        assert.equal(result[3].edited, true);
        assert.equal(result[3].moved, true);
        assert.equal(result[3].modified, true);
    })();
});

test("message_edited_vars", () => {
    // This is a test to verify that only one of the three bools,
    // `message_edit_notices_in_left_col`, `message_edit_notices_alongside_sender`,
    // `message_edit_notices_for_status_message` is not false; Tests for three
    // different kinds of messages:
    //   * "/me" message
    //   * message that includes sender
    //   * message without sender

    function build_message_context(message = {}, message_context = {}) {
        message_context = {
            include_sender: true,
            ...message_context,
        };
        message_context.msg = {
            is_me_message: false,
            last_edit_timestamp: (next_timestamp += 1),
            edit_history: [{prev_content: "test_content", timestamp: 1000, user_id: 1}],
            ...message,
        };
        return message_context;
    }

    function build_message_group(messages) {
        return {message_containers: messages};
    }

    function build_list(message_groups) {
        const list = new MessageListView(
            {
                id: 1,
            },
            true,
            true,
        );
        list._message_groups = message_groups;
        return list;
    }

    function assert_left_col(message_container) {
        assert.equal(message_container.modified, true);
        assert.equal(message_container.message_edit_notices_in_left_col, true);
        assert.equal(message_container.message_edit_notices_alongside_sender, false);
        assert.equal(message_container.message_edit_notices_for_status_message, false);
    }

    function assert_alongside_sender(message_container) {
        assert.equal(message_container.modified, true);
        assert.equal(message_container.message_edit_notices_in_left_col, false);
        assert.equal(message_container.message_edit_notices_alongside_sender, true);
        assert.equal(message_container.message_edit_notices_for_status_message, false);
    }

    function assert_status_msg(message_container) {
        assert.equal(message_container.modified, true);
        assert.equal(message_container.message_edit_notices_in_left_col, false);
        assert.equal(message_container.message_edit_notices_alongside_sender, false);
        assert.equal(message_container.message_edit_notices_for_status_message, true);
    }

    function set_edited_notice_locations(message_container) {
        const include_sender = message_container.include_sender;
        const is_hidden = message_container.is_hidden;
        const status_message = Boolean(message_container.status_message);
        message_container.message_edit_notices_in_left_col = !include_sender && !is_hidden;
        message_container.message_edit_notices_alongside_sender = include_sender && !status_message;
        message_container.message_edit_notices_for_status_message =
            include_sender && status_message;
    }

    (function test_message_edited_vars() {
        const messages = [
            build_message_context(),
            build_message_context({}, {include_sender: false}),
            build_message_context({is_me_message: true, content: "<p>/me test</p>"}),
        ];
        const message_group = build_message_group(messages);
        const list = build_list([message_group]);

        for (const message_container of messages) {
            Object.assign(
                message_container,
                list._maybe_get_me_message(message_container.is_hidden, message_container.msg),
                list._get_message_edited_and_moved_vars(message_container.msg),
            );
        }

        const result = list._message_groups[0].message_containers;

        set_edited_notice_locations(result[0]);
        assert_alongside_sender(result[0]);

        set_edited_notice_locations(result[1]);
        assert_left_col(result[1]);

        set_edited_notice_locations(result[2]);
        assert_status_msg(result[2]);
    })();
});

test("muted_message_vars", () => {
    // This verifies that the variables for muted/hidden messages are set
    // correctly.

    function build_message_context(message = {}, message_context = {}) {
        message_context = {
            ...message_context,
        };
        message_context.msg = {
            ...message,
        };
        return message_context;
    }

    function build_message_group(messages) {
        return {message_containers: messages};
    }

    function build_list(message_groups) {
        const list = new MessageListView(
            {
                id: 1,
            },
            true,
            true,
        );
        list._message_groups = message_groups;
        return list;
    }

    function calculate_variables(list, message_containers, is_revealed) {
        for (const container of message_containers) {
            Object.assign(
                container,
                list.get_calculated_message_container_variables(
                    container.msg,
                    container.include_sender,
                    is_revealed,
                ),
            );
        }
        return list._message_groups[0].message_containers;
    }

    (function test_hidden_message_variables() {
        // We want to have no search results, which apparently works like this.
        // See https://chat.zulip.org/#narrow/channel/6-frontend/topic/set_find_results.20with.20no.20results/near/1414799
        const empty_list_stub = $.create("empty-stub", {children: []});
        $("<message-stub-1>").set_find_results(".user-mention:not(.silent)", empty_list_stub);
        $("<message-stub2>").set_find_results(".user-mention:not(.silent)", empty_list_stub);
        $("<message-stub-3>").set_find_results(".user-mention:not(.silent)", empty_list_stub);
        // Make a representative message group of three messages.
        const messages = [
            build_message_context(
                {sender_id: 10, content: "<message-stub-1>"},
                {include_sender: true},
            ),
            build_message_context(
                {mentioned: true, sender_id: 10, content: "<message-stub2>"},
                {include_sender: false},
            ),
            build_message_context(
                {sender_id: 10, content: "<message-stub-3>"},
                {include_sender: false},
            ),
        ];
        const message_group = build_message_group(messages);
        const list = build_list([message_group]);
        list._get_message_edited_and_moved_vars = noop;

        // Sender is not muted.
        let result = calculate_variables(list, messages);

        // sanity check on mocked values
        assert.equal(result[1].sender_is_bot, false);
        assert.equal(result[1].sender_is_deactivated, false);
        assert.equal(result[1].sender_is_guest, false);
        assert.equal(result[1].small_avatar_url, "fake/small/avatar/url");

        // Check that `is_hidden` is false on all messages, and `include_sender` has not changed.
        assert.equal(result[0].is_hidden, false);
        assert.equal(result[1].is_hidden, false);
        assert.equal(result[2].is_hidden, false);

        assert.equal(result[0].include_sender, true);
        assert.equal(result[1].include_sender, false);
        assert.equal(result[2].include_sender, false);

        // Additionally test that the message with a mention is marked as such.
        assert.equal(result[1].mention_classname, "group_mention");

        // Now, mute the sender.
        muted_users.add_muted_user(10);
        result = calculate_variables(list, messages);

        // Check that `is_hidden` is true and `include_sender` is false on all messages.
        assert.equal(result[0].is_hidden, true);
        assert.equal(result[1].is_hidden, true);
        assert.equal(result[2].is_hidden, true);

        assert.equal(result[0].include_sender, false);
        assert.equal(result[1].include_sender, false);
        assert.equal(result[2].include_sender, false);

        // Additionally test that, both there is no mention classname even on that message
        // which has a mention, since we don't want to display muted mentions so visibly.
        assert.equal(result[1].mention_classname, undefined);

        // Now, reveal the hidden messages.
        let is_revealed = true;
        result = calculate_variables(list, messages, is_revealed);

        // Check that `is_hidden` is false and `include_sender` is true on all messages.
        assert.equal(result[0].is_hidden, false);
        assert.equal(result[1].is_hidden, false);
        assert.equal(result[2].is_hidden, false);

        assert.equal(result[0].include_sender, true);
        assert.equal(result[1].include_sender, true);
        assert.equal(result[2].include_sender, true);

        // Additionally test that the message with a mention is marked as such.
        assert.equal(result[1].mention_classname, "group_mention");

        // Now test rehiding muted user's message
        is_revealed = false;
        result = calculate_variables(list, messages, is_revealed);

        // Check that `is_hidden` is false and `include_sender` is false on all messages.
        assert.equal(result[0].is_hidden, true);
        assert.equal(result[1].is_hidden, true);
        assert.equal(result[2].is_hidden, true);

        assert.equal(result[0].include_sender, false);
        assert.equal(result[1].include_sender, false);
        assert.equal(result[2].include_sender, false);

        // Additionally test that, both there is no mention classname even on that message
        // which has a mention, since we don't want to display hidden mentions so visibly.
        assert.equal(result[1].mention_classname, undefined);
    })();
});

test("merge_message_groups", ({mock_template}) => {
    mock_template("message_list.hbs", false, () => "<message-list-stub>");
    // MessageListView has lots of DOM code, so we are going to test the message
    // group merging logic on its own.

    function build_message_context(message = {}, message_context = {}) {
        message_context = {
            include_sender: true,
            ...message_context,
        };
        message_context.msg = {
            id: _.uniqueId("test_message_"),
            status_message: false,
            type: "stream",
            stream_id: 2,
            topic: "Test topic 1",
            sender_email: "test@example.com",
            timestamp: (next_timestamp += 1),
            ...message,
        };
        return message_context;
    }

    function build_message_group(messages) {
        return {
            message_containers: messages,
            message_group_id: _.uniqueId("test_message_group_"),
        };
    }

    function build_list(message_groups) {
        const filter = new Filter([{operator: "stream", operand: "foo"}]);

        const list = new message_list.MessageList({
            data: new MessageListData({
                excludes_muted_topics: false,
                filter,
            }),
            is_node_test: true,
        });

        const view = new MessageListView(list, true, true);
        view._message_groups = message_groups;
        view.list.unsubscribed_bookend_content = noop;
        view.list.subscribed_bookend_content = noop;
        return view;
    }

    function extract_message_ids(lst) {
        return lst.map((item) => item.msg.id);
    }

    function assert_message_list_equal(list1, list2) {
        const ids1 = extract_message_ids(list1);
        const ids2 = extract_message_ids(list2);
        assert.ok(ids1.length);
        assert.deepEqual(ids1, ids2);
    }

    function extract_group(group) {
        return extract_message_ids(group.message_containers);
    }

    function assert_message_groups_list_equal(list1, list2) {
        const ids1 = list1.map((group) => extract_group(group));
        const ids2 = list2.map((group) => extract_group(group));
        assert.ok(ids1.length);
        assert.deepEqual(ids1, ids2);
    }

    (function test_empty_list_bottom() {
        const list = build_list([]);
        const message_group = build_message_group([build_message_context()]);

        const result = list.merge_message_groups([message_group], "bottom");

        assert_message_groups_list_equal(list._message_groups, [message_group]);
        assert_message_groups_list_equal(result.append_groups, [message_group]);
        assert.deepEqual(result.prepend_groups, []);
        assert.deepEqual(result.rerender_groups, []);
        assert.deepEqual(result.append_messages, []);
    })();

    (function test_append_message_same_topic() {
        const message1 = build_message_context();
        const message_group1 = build_message_group([message1]);

        const message2 = build_message_context();
        const message_group2 = build_message_group([message2]);

        const list = build_list([message_group1]);
        const result = list.merge_message_groups([message_group2], "bottom");

        assert_message_groups_list_equal(list._message_groups, [
            build_message_group([message1, message2]),
        ]);
        assert.deepEqual(result.append_groups, []);
        assert.deepEqual(result.prepend_groups, []);
        assert.deepEqual(result.rerender_groups, []);
        assert_message_list_equal(result.append_messages, [message2]);
    })();

    (function test_append_message_different_topic() {
        const message1 = build_message_context();
        const message_group1 = build_message_group([message1]);

        const message2 = build_message_context({topic: "Test topic 2"});
        const message_group2 = build_message_group([message2]);

        const list = build_list([message_group1]);
        const result = list.merge_message_groups([message_group2], "bottom");

        assert.ok(!message_group2.date_unchanged, true);
        assert_message_groups_list_equal(list._message_groups, [message_group1, message_group2]);
        assert_message_groups_list_equal(result.append_groups, [message_group2]);
        assert.deepEqual(result.prepend_groups, []);
        assert.deepEqual(result.rerender_groups, []);
        assert.deepEqual(result.append_messages, []);
    })();

    (function test_append_message_different_topic_and_days() {
        const message1 = build_message_context({timestamp: 1000});
        const message_group1 = build_message_group([message1]);

        const message2 = build_message_context({topic: "Test topic 2", timestamp: 900000});
        const message_group2 = build_message_group([message2]);

        const list = build_list([message_group1]);
        const result = list.merge_message_groups([message_group2], "bottom");

        assert_message_groups_list_equal(list._message_groups, [message_group1, message_group2]);
        assert_message_groups_list_equal(result.append_groups, [message_group2]);
        assert.deepEqual(result.prepend_groups, []);
        assert.deepEqual(result.rerender_groups, []);
        assert.deepEqual(result.append_messages, []);
        assert.equal(message_group2.date_unchanged, false);
    })();

    (function test_append_message_different_day() {
        const message1 = build_message_context({timestamp: 1000});
        const message_group1 = build_message_group([message1]);

        const message2 = build_message_context({timestamp: 900000});
        const message_group2 = build_message_group([message2]);

        const list = build_list([message_group1]);
        const result = list.merge_message_groups([message_group2], "bottom");

        assert_message_groups_list_equal(list._message_groups, [message_group1]);
        assert.deepEqual(result.append_groups, []);
        assert.deepEqual(result.prepend_groups, []);
        assert.deepEqual(result.rerender_groups, []);
        assert.deepEqual(result.append_messages, [message2]);
        assert.ok(list._message_groups[0].message_containers[1].want_date_divider);
    })();

    (function test_append_message_historical() {
        const message1 = build_message_context({historical: false});
        const message_group1 = build_message_group([message1]);

        const message2 = build_message_context({historical: true});
        const message_group2 = build_message_group([message2]);

        const list = build_list([message_group1]);
        const result = list.merge_message_groups([message_group2], "bottom");

        assert.ok(message_group2.bookend_top);
        assert_message_groups_list_equal(list._message_groups, [message_group1, message_group2]);
        assert_message_groups_list_equal(result.append_groups, [message_group2]);
        assert.deepEqual(result.prepend_groups, []);
        assert.deepEqual(result.rerender_groups, []);
        assert.deepEqual(result.append_messages, []);
    })();

    (function test_append_message_same_topic_me_message() {
        const message1 = build_message_context();
        const message_group1 = build_message_group([message1]);

        const message2 = build_message_context({is_me_message: true});
        const message_group2 = build_message_group([message2]);

        const list = build_list([message_group1]);
        const result = list.merge_message_groups([message_group2], "bottom");

        assert.ok(message2.include_sender);
        assert_message_groups_list_equal(list._message_groups, [
            build_message_group([message1, message2]),
        ]);
        assert.deepEqual(result.append_groups, []);
        assert.deepEqual(result.prepend_groups, []);
        assert.deepEqual(result.rerender_groups, []);
        assert_message_list_equal(result.append_messages, [message2]);
    })();

    (function test_prepend_message_same_topic() {
        const message1 = build_message_context();
        const message_group1 = build_message_group([message1]);

        const message2 = build_message_context();
        const message_group2 = build_message_group([message2]);

        const list = build_list([message_group1]);
        const result = list.merge_message_groups([message_group2], "top");

        assert_message_groups_list_equal(list._message_groups, [
            build_message_group([message2, message1]),
        ]);
        assert.deepEqual(result.append_groups, []);
        assert.deepEqual(result.prepend_groups, []);
        assert_message_groups_list_equal(result.rerender_groups, [
            build_message_group([message2, message1]),
        ]);
        assert.deepEqual(result.append_messages, []);
    })();

    (function test_prepend_message_different_topic() {
        const message1 = build_message_context();
        const message_group1 = build_message_group([message1]);

        const message2 = build_message_context({topic: "Test topic 2"});
        const message_group2 = build_message_group([message2]);

        const list = build_list([message_group1]);
        const result = list.merge_message_groups([message_group2], "top");

        assert_message_groups_list_equal(list._message_groups, [message_group2, message_group1]);
        assert.deepEqual(result.append_groups, []);
        assert_message_groups_list_equal(result.prepend_groups, [message_group2]);
        assert.deepEqual(result.rerender_groups, []);
        assert.deepEqual(result.append_messages, []);
    })();

    (function test_prepend_message_different_topic_and_day() {
        const message1 = build_message_context({timestamp: 900000});
        const message_group1 = build_message_group([message1]);

        const message2 = build_message_context({topic: "Test topic 2", timestamp: 1000});
        const message_group2 = build_message_group([message2]);

        const list = build_list([message_group1]);
        const result = list.merge_message_groups([message_group2], "top");

        assert.equal(message_group1.date_unchanged, false);
        assert_message_groups_list_equal(list._message_groups, [message_group2, message_group1]);
        assert.deepEqual(result.append_groups, []);
        assert_message_groups_list_equal(result.prepend_groups, [message_group2]);
        assert.deepEqual(result.rerender_groups, [message_group1]);
        assert.deepEqual(result.append_messages, []);
    })();

    (function test_prepend_message_different_day() {
        const message1 = build_message_context({timestamp: 900000});
        const message_group1 = build_message_group([message1]);

        const message2 = build_message_context({timestamp: 1000});
        const message_group2 = build_message_group([message2]);

        const list = build_list([message_group1]);
        const result = list.merge_message_groups([message_group2], "top");

        assert.equal(message_group2.message_containers[1].date_divider_html, "900000000");
        assert_message_groups_list_equal(list._message_groups, [message_group2]);
        assert.deepEqual(result.append_groups, []);
        assert.deepEqual(result.prepend_groups, []);
        assert_message_groups_list_equal(result.rerender_groups, [message_group2]);
        assert.deepEqual(result.append_messages, []);
    })();

    (function test_prepend_message_historical() {
        const message1 = build_message_context({historical: false});
        const message_group1 = build_message_group([message1]);

        const message2 = build_message_context({historical: true});
        const message_group2 = build_message_group([message2]);

        const list = build_list([message_group1]);
        const result = list.merge_message_groups([message_group2], "top");

        assert.ok(message_group1.bookend_top);
        assert_message_groups_list_equal(list._message_groups, [message_group2, message_group1]);
        assert.deepEqual(result.append_groups, []);
        assert_message_groups_list_equal(result.prepend_groups, [message_group2]);
        assert.deepEqual(result.rerender_groups, []);
        assert.deepEqual(result.append_messages, []);
    })();
});

test("render_windows", ({mock_template}) => {
    mock_template("message_list.hbs", false, () => "<message-list-stub>");
    // We only render up to 400 messages at a time in our message list,
    // and we only change the window (which is a range, really, with
    // start/end) when the pointer moves outside of the window or close
    // to the edges.

    const view = (function make_view() {
        const filter = new Filter([]);

        const list = new message_list.MessageList({
            data: new MessageListData({
                excludes_muted_topics: false,
                filter,
            }),
            is_node_test: true,
        });

        const view = list.view;

        // Stub out functionality that is not core to the rendering window
        // logic.
        list.data.unmuted_messages = (messages) => messages;

        // We don't need to actually render the DOM.  The windowing logic
        // sits above that layer.
        view.render = noop;
        view.rerender_preserving_scrolltop = noop;

        return view;
    })();

    const list = view.list;

    (function test_with_empty_list() {
        // The function should early exit here.
        const rendered = view.maybe_rerender();
        assert.equal(rendered, false);
    })();

    let messages;

    function reset_list(opts) {
        messages = _.range(opts.count).map((i) => ({
            id: i,
        }));
        list.selected_idx = () => 0;
        list.view.clear_table = noop;
        list.clear();

        list.add_messages(messages, {}, true);
    }

    function verify_no_move_range(start, end) {
        // In our render window, there are up to 150 positions in
        // the list (with potentially 50 at the start if the range
        // starts with 0) where we can move the pointer without forcing
        // a re-render.  The code avoids hasty re-renders for
        // performance reasons.
        for (const idx of _.range(start, end)) {
            list.selected_idx = () => idx;
            const rendered = view.maybe_rerender();
            assert.equal(rendered, false);
        }
    }

    function verify_move(idx, range) {
        const start = range[0];
        const end = range[1];

        list.selected_idx = () => idx;
        const rendered = view.maybe_rerender();
        assert.equal(rendered, true);
        assert.equal(view._render_win_start, start);
        assert.equal(view._render_win_end, end);
    }

    function verify_move_and_no_move_range(move_target, opts = {}) {
        // When we move to position X, we expect 250/2 = 125 messages on
        // either side, unless that goes outside the `count`, in which
        // case we'll specify it in `opts`.
        const move_start = opts.move_start ?? move_target - 125;
        const move_end = opts.move_end ?? move_target + 125;
        verify_move(move_target, [move_start, move_end]);
        // the no-move range is a 50 buffer on each side
        const no_move_start = opts.no_move_start ?? move_start + 50;
        const no_move_end = move_end - 50;
        verify_no_move_range(no_move_start, no_move_end);
    }

    reset_list({count: 51});
    verify_no_move_range(0, 51); // This is the whole list

    // Start a new list with more messages. Note that the order of
    // these checks matters; each time we call `verify_move` or
    // `verify_move_and_no_move_range`, we are moving the currently
    // selected position in the list.
    reset_list({count: 450});

    // 250 messages rendered, with the last 50 in the move range
    verify_no_move_range(0, 200);

    verify_move_and_no_move_range(350, {
        // top maxes out at 450
        move_end: 450,
    });

    // We load more than 125 on the upper end, because we load the full 250
    // messages and 124 is less than half of that.
    verify_move_and_no_move_range(124, {
        move_start: 0,
        move_end: 250,
    });

    // If we now jump to a message ID close enough to the end of the
    // range, the render window is limited.
    verify_move_and_no_move_range(350, {
        move_end: 450,
    });

    // Now jump the selected ID close to the start again.
    verify_move_and_no_move_range(124, {
        move_start: 0,
        move_end: 250,
        // The first 50 aren't in a move range, because we can't load earlier
        // messages than 0.
        no_move_start: 0,
    });

    verify_move_and_no_move_range(400, {
        // top maxes out at 450
        move_end: 450,
    });

    reset_list({count: 800});
    verify_no_move_range(0, 200);

    verify_move_and_no_move_range(350);

    verify_move_and_no_move_range(500);

    verify_move_and_no_move_range(750, {
        // top maxes out at 800
        move_end: 800,
    });

    verify_move_and_no_move_range(499);

    verify_move_and_no_move_range(348);

    // We load more than 125 on the upper end, because we load the full 250
    // messages and 122 is less than half of that.
    verify_move_and_no_move_range(122, {
        move_start: 0,
        move_end: 250,
        no_move_start: 0,
    });
});
