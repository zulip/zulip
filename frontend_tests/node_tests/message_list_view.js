"use strict";

const {strict: assert} = require("assert");

const _ = require("lodash");

const {set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const {make_zjquery} = require("../zjsunit/zjquery");

set_global("$", make_zjquery());
set_global("document", "document-stub");

zrequire("Filter", "js/filter");
zrequire("FetchStatus", "js/fetch_status");
zrequire("MessageListData", "js/message_list_data");
zrequire("MessageListView", "js/message_list_view");
zrequire("message_list");

const noop = function () {};

set_global("page_params", {
    twenty_four_hour_time: false,
});
set_global("home_msg_list", null);
set_global("people", {
    small_avatar_url() {
        return "";
    },
});
set_global("unread", {message_unread() {}});
// timerender calls setInterval when imported
set_global("timerender", {
    render_date(time1, time2) {
        if (time2 === undefined) {
            return [{outerHTML: String(time1.getTime())}];
        }
        return [{outerHTML: String(time1.getTime()) + " - " + String(time2.getTime())}];
    },
    stringify_time(time) {
        if (page_params.twenty_four_hour_time) {
            return time.toString("HH:mm");
        }
        return time.toString("h:mm TT");
    },
});

set_global("rows", {
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

let next_timestamp = 1500000000;

run_test("msg_edited_vars", () => {
    // This is a test to verify that only one of the three bools,
    // `edited_in_left_col`, `edited_alongside_sender`, `edited_status_msg`
    // is not false; Tests for three different kinds of messages:
    //   * "/me" message
    //   * message that includes sender
    //   * message without sender

    function build_message_context(message, message_context) {
        if (message_context === undefined) {
            message_context = {};
        }
        if (message === undefined) {
            message = {};
        }
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

run_test("merge_message_groups", () => {
    // MessageListView has lots of DOM code, so we are going to test the message
    // group mearging logic on its own.

    function build_message_context(message, message_context) {
        if (message_context === undefined) {
            message_context = {};
        }
        if (message === undefined) {
            message = {};
        }
        message_context = {
            include_sender: true,
            ...message_context,
        };
        message_context.msg = {
            id: _.uniqueId("test_message_"),
            status_message: false,
            type: "stream",
            stream: "Test Stream 1",
            topic: "Test Subject 1",
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
        assert(ids1.length);
        assert.deepEqual(ids1, ids2);
    }

    function extract_group(group) {
        return extract_message_ids(group.message_containers);
    }

    function assert_message_groups_list_equal(list1, list2) {
        const ids1 = list1.map((group) => extract_group(group));
        const ids2 = list2.map((group) => extract_group(group));
        assert(ids1.length);
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

        assert(!message_group2.group_date_divider_html);
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
        assert(list._message_groups[0].message_containers[1].want_date_divider);
    })();

    (function test_append_message_historical() {
        const message1 = build_message_context({historical: false});
        const message_group1 = build_message_group([message1]);

        const message2 = build_message_context({historical: true});
        const message_group2 = build_message_group([message2]);

        const list = build_list([message_group1]);
        const result = list.merge_message_groups([message_group2], "bottom");

        assert(message_group2.bookend_top);
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

        assert(message2.include_sender);
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

        const message2 = build_message_context({topic: "Test Subject 2"});
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

        const message2 = build_message_context({topic: "Test Subject 2", timestamp: 1000});
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

        assert(message_group1.bookend_top);
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

run_test("render_windows", () => {
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
        list.data.unmuted_messages = function (messages) {
            return messages;
        };

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
        list.selected_idx = function () {
            return 0;
        };
        list.clear();

        list.add_messages(messages, {});
    }

    function verify_no_move_range(start, end) {
        // In our render window, there are up to 300 positions in
        // the list where we can move the pointer without forcing
        // a re-render.  The code avoids hasty re-renders for
        // performance reasons.
        for (const idx of _.range(start, end)) {
            list.selected_idx = function () {
                return idx;
            };
            const rendered = view.maybe_rerender();
            assert.equal(rendered, false);
        }
    }

    function verify_move(idx, range) {
        const start = range[0];
        const end = range[1];

        list.selected_idx = function () {
            return idx;
        };
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
