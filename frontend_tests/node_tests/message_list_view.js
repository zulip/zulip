"use strict";

const {strict: assert} = require("assert");

const _ = require("lodash");

const {mock_esm, set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const {user_settings} = require("../zjsunit/zpage_params");

set_global("document", "document-stub");

const noop = () => {};

user_settings.twenty_four_hour_time = false;

mock_esm("../../static/js/message_lists", {home: "stub"});

// timerender calls setInterval when imported
mock_esm("../../static/js/timerender", {
    render_date(time1, time2) {
        if (time2 === undefined) {
            return [{outerHTML: String(time1.getTime())}];
        }
        return [{outerHTML: String(time1.getTime()) + " - " + String(time2.getTime())}];
    },
    stringify_time(time) {
        if (user_settings.twenty_four_hour_time) {
            return time.toString("HH:mm");
        }
        return time.toString("h:mm TT");
    },
});

mock_esm("../../static/js/rows", {
    get_table() {
        return {
            children() {
                return {
                    detach: noop,
                };
            },
        };
    },
});

const {Filter} = zrequire("../js/filter");
const {MessageListView} = zrequire("../js/message_list_view");
const message_list = zrequire("message_list");
const muted_users = zrequire("muted_users");

let next_timestamp = 1500000000;

function test(label, f) {
    run_test(label, ({override}) => {
        muted_users.set_muted_users([]);
        f({override});
    });
}

test("msg_edited_vars", () => {
    // This is a test to verify that only one of the three bools,
    // `edited_in_left_col`, `edited_alongside_sender`, `edited_status_msg`
    // is not false; Tests for three different kinds of messages:
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
            ...message,
        };
        return message_context;
    }

    function build_message_group(messages) {
        return {message_containers: messages};
    }

    function build_list(message_groups) {
        const list = new MessageListView(undefined, undefined, true);
        list._message_groups = message_groups;
        return list;
    }

    function assert_left_col(message_container) {
        assert.equal(message_container.edited_in_left_col, true);
        assert.equal(message_container.edited_alongside_sender, false);
        assert.equal(message_container.edited_status_msg, false);
    }

    function assert_alongside_sender(message_container) {
        assert.equal(message_container.edited_in_left_col, false);
        assert.equal(message_container.edited_alongside_sender, true);
        assert.equal(message_container.edited_status_msg, false);
    }

    function assert_status_msg(message_container) {
        assert.equal(message_container.edited_in_left_col, false);
        assert.equal(message_container.edited_alongside_sender, false);
        assert.equal(message_container.edited_status_msg, true);
    }

    (function test_msg_edited_vars() {
        const messages = [
            build_message_context(),
            build_message_context({}, {include_sender: false}),
            build_message_context({is_me_message: true, content: "<p>/me test</p>"}),
        ];
        const message_group = build_message_group(messages);
        const list = build_list([message_group]);

        for (const message_container of messages) {
            list._maybe_format_me_message(message_container);
            list._add_msg_edited_vars(message_container);
        }

        const result = list._message_groups[0].message_containers;

        assert_alongside_sender(result[0]);
        assert_left_col(result[1]);
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
        const list = new MessageListView(undefined, undefined, true);
        list._message_groups = message_groups;
        return list;
    }

    function calculate_variables(list, messages, is_revealed) {
        list.set_calculated_message_container_variables(messages[0], is_revealed);
        list.set_calculated_message_container_variables(messages[1], is_revealed);
        list.set_calculated_message_container_variables(messages[2], is_revealed);
        return list._message_groups[0].message_containers;
    }

    (function test_hidden_message_variables() {
        // Make a representative message group of three messages.
        const messages = [
            build_message_context({sender_id: 10}, {include_sender: true}),
            build_message_context({mentioned: true, sender_id: 10}, {include_sender: false}),
            build_message_context({sender_id: 10}, {include_sender: false}),
        ];
        const message_group = build_message_group(messages);
        const list = build_list([message_group]);
        list._add_msg_edited_vars = noop;

        // Sender is not muted.
        let result = calculate_variables(list, messages);

        // Check that `is_hidden` is false on all messages, and `include_sender` has not changed.
        assert.equal(result[0].is_hidden, false);
        assert.equal(result[1].is_hidden, false);
        assert.equal(result[2].is_hidden, false);

        assert.equal(result[0].include_sender, true);
        assert.equal(result[1].include_sender, false);
        assert.equal(result[2].include_sender, false);

        // Additionally test that, `contains_mention` is true on that message has a mention.
        assert.equal(result[1].contains_mention, true);

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

        // Additionally test that, `contains_mention` is false even on that message which has a mention.
        assert.equal(result[1].contains_mention, false);

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

        // Additionally test that, `contains_mention` is true on that message which has a mention.
        assert.equal(result[1].contains_mention, true);

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

        // Additionally test that, `contains_mention` is false on that message which has a mention.
        assert.equal(result[1].contains_mention, false);
    })();
});

test("merge_message_groups", () => {
    // MessageListView has lots of DOM code, so we are going to test the message
    // group mearging logic on its own.

    function build_message_context(message = {}, message_context = {}) {
        message_context = {
            include_sender: true,
            ...message_context,
        };
        message_context.msg = {
            id: _.uniqueId("test_message_"),
            status_message: false,
            type: "stream",
            stream: "Test stream 1",
            topic: "Test subject 1",
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
        const list = new MessageListView(undefined, undefined, true);
        list._message_groups = message_groups;
        list.list = {
            unsubscribed_bookend_content() {},
            subscribed_bookend_content() {},
        };
        return list;
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
        assert.deepEqual(result.rerender_messages_next_same_sender, []);
    })();

    (function test_append_message_same_subject() {
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
        assert_message_list_equal(result.rerender_messages_next_same_sender, [message1]);
    })();

    (function test_append_message_different_subject() {
        const message1 = build_message_context();
        const message_group1 = build_message_group([message1]);

        const message2 = build_message_context({topic: "Test subject 2"});
        const message_group2 = build_message_group([message2]);

        const list = build_list([message_group1]);
        const result = list.merge_message_groups([message_group2], "bottom");

        assert.ok(!message_group2.group_date_divider_html);
        assert_message_groups_list_equal(list._message_groups, [message_group1, message_group2]);
        assert_message_groups_list_equal(result.append_groups, [message_group2]);
        assert.deepEqual(result.prepend_groups, []);
        assert.deepEqual(result.rerender_groups, []);
        assert.deepEqual(result.append_messages, []);
        assert.deepEqual(result.rerender_messages_next_same_sender, []);
    })();

    (function test_append_message_different_subject_and_days() {
        const message1 = build_message_context({timestamp: 1000});
        const message_group1 = build_message_group([message1]);

        const message2 = build_message_context({topic: "Test subject 2", timestamp: 900000});
        const message_group2 = build_message_group([message2]);

        const list = build_list([message_group1]);
        const result = list.merge_message_groups([message_group2], "bottom");

        assert_message_groups_list_equal(list._message_groups, [message_group1, message_group2]);
        assert_message_groups_list_equal(result.append_groups, [message_group2]);
        assert.deepEqual(result.prepend_groups, []);
        assert.deepEqual(result.rerender_groups, []);
        assert.deepEqual(result.append_messages, []);
        assert.deepEqual(result.rerender_messages_next_same_sender, []);
        assert.equal(message_group2.group_date_divider_html, "900000000 - 1000000");
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
        assert.deepEqual(result.rerender_messages_next_same_sender, [message1]);
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
        assert.deepEqual(result.rerender_messages_next_same_sender, []);
    })();

    (function test_append_message_same_subject_me_message() {
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
        assert_message_list_equal(result.rerender_messages_next_same_sender, [message1]);
    })();

    (function test_prepend_message_same_subject() {
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
        assert.deepEqual(result.rerender_messages_next_same_sender, []);
    })();

    (function test_prepend_message_different_subject() {
        const message1 = build_message_context();
        const message_group1 = build_message_group([message1]);

        const message2 = build_message_context({topic: "Test subject 2"});
        const message_group2 = build_message_group([message2]);

        const list = build_list([message_group1]);
        const result = list.merge_message_groups([message_group2], "top");

        assert_message_groups_list_equal(list._message_groups, [message_group2, message_group1]);
        assert.deepEqual(result.append_groups, []);
        assert_message_groups_list_equal(result.prepend_groups, [message_group2]);
        assert.deepEqual(result.rerender_groups, []);
        assert.deepEqual(result.append_messages, []);
        assert.deepEqual(result.rerender_messages_next_same_sender, []);
    })();

    (function test_prepend_message_different_subject_and_day() {
        const message1 = build_message_context({timestamp: 900000});
        const message_group1 = build_message_group([message1]);

        const message2 = build_message_context({topic: "Test subject 2", timestamp: 1000});
        const message_group2 = build_message_group([message2]);

        const list = build_list([message_group1]);
        const result = list.merge_message_groups([message_group2], "top");

        // We should have a group date divider between the recipient blocks.
        assert.equal(message_group1.group_date_divider_html, "900000000 - 1000000");
        assert_message_groups_list_equal(list._message_groups, [message_group2, message_group1]);
        assert.deepEqual(result.append_groups, []);
        assert_message_groups_list_equal(result.prepend_groups, [message_group2]);
        assert.deepEqual(result.rerender_groups, [message_group1]);
        assert.deepEqual(result.append_messages, []);
        assert.deepEqual(result.rerender_messages_next_same_sender, []);
    })();

    (function test_prepend_message_different_day() {
        const message1 = build_message_context({timestamp: 900000});
        const message_group1 = build_message_group([message1]);

        const message2 = build_message_context({timestamp: 1000});
        const message_group2 = build_message_group([message2]);

        const list = build_list([message_group1]);
        const result = list.merge_message_groups([message_group2], "top");

        // We should have a group date divider within the single recipient block.
        assert.equal(message_group2.message_containers[1].date_divider_html, "900000000 - 1000000");
        assert_message_groups_list_equal(list._message_groups, [message_group2]);
        assert.deepEqual(result.append_groups, []);
        assert.deepEqual(result.prepend_groups, []);
        assert_message_groups_list_equal(result.rerender_groups, [message_group2]);
        assert.deepEqual(result.append_messages, []);
        assert.deepEqual(result.rerender_messages_next_same_sender, []);
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
        assert.deepEqual(result.rerender_messages_next_same_sender, []);
    })();
});

// TODO: Add a test suite for rerender_messages_next_same_sender() that includes cases
// where new messages added via local echo have a different date from
// the older messages.

test("render_windows", () => {
    // We only render up to 400 messages at a time in our message list,
    // and we only change the window (which is a range, really, with
    // start/end) when the pointer moves outside of the window or close
    // to the edges.

    const view = (function make_view() {
        const table_name = "zfilt";
        const filter = new Filter();

        const list = new message_list.MessageList({
            table_name,
            filter,
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
        list.clear();

        list.add_messages(messages, {});
    }

    function verify_no_move_range(start, end) {
        // In our render window, there are up to 300 positions in
        // the list where we can move the pointer without forcing
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

    reset_list({count: 51});
    verify_no_move_range(0, 51);

    reset_list({count: 450});
    verify_no_move_range(0, 350);

    verify_move(350, [150, 450]);
    verify_no_move_range(200, 400);

    verify_move(199, [0, 400]);
    verify_no_move_range(50, 350);

    verify_move(350, [150, 450]);
    verify_no_move_range(200, 400);

    verify_move(199, [0, 400]);
    verify_no_move_range(0, 350);

    verify_move(400, [200, 450]);

    reset_list({count: 800});
    verify_no_move_range(0, 350);

    verify_move(350, [150, 550]);
    verify_no_move_range(200, 500);

    verify_move(500, [300, 700]);
    verify_no_move_range(350, 650);

    verify_move(650, [450, 800]);
    verify_no_move_range(500, 750);

    verify_move(499, [299, 699]);
    verify_no_move_range(349, 649);

    verify_move(348, [148, 548]);
    verify_no_move_range(198, 398);

    verify_move(197, [0, 400]);
    verify_no_move_range(0, 350);
});
