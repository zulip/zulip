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
    get_muted_user_avatar_url: () => "fake/muted_user/avatar/url",
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
        assert.equal(result[0].widget_edited, false);
        // edit timestamp: EDITED
        assert.equal(result[1].edited, true);
        assert.equal(result[1].moved, false);
        assert.equal(result[1].modified, true);
        assert.equal(result[1].widget_edited, false);
        // moved timestamp: MOVED
        assert.equal(result[2].edited, false);
        assert.equal(result[2].moved, true);
        assert.equal(result[2].modified, true);
        assert.equal(result[2].widget_edited, false);
        // both edit and moved timestamp: EDITED
        assert.equal(result[3].edited, true);
        assert.equal(result[3].moved, true);
        assert.equal(result[3].modified, true);
        assert.equal(result[3].widget_edited, false);
    })();

    (function test_widget_edited_var() {
        function make_submessage(id, content) {
            return {id, sender_id: 1, msg_type: "widget", content: JSON.stringify(content)};
        }

        const poll_widget_data = {widget_type: "poll", extra_data: {question: "Q?", options: []}};

        const messages = [
            // Poll with question edit → EDITED
            {
                msg: {
                    submessages: [
                        make_submessage(1, poll_widget_data),
                        make_submessage(2, {type: "question", question: "New Q?"}),
                    ],
                },
            },
            // Poll with new_option → EDITED
            {
                msg: {
                    submessages: [
                        make_submessage(3, poll_widget_data),
                        make_submessage(4, {type: "new_option", option: "Option A"}),
                    ],
                },
            },
            // Poll with only votes → NOT edited
            {
                msg: {
                    submessages: [
                        make_submessage(5, poll_widget_data),
                        make_submessage(6, {type: "vote", key: "1,1", vote: 1}),
                    ],
                },
            },
            // Non-poll message with submessages → NOT edited
            {
                msg: {
                    submessages: [
                        make_submessage(7, {widget_type: "todo"}),
                        make_submessage(8, {type: "new_task", task: "Do stuff"}),
                    ],
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

        // Poll with question edit
        assert.equal(result[0].widget_edited, true);
        assert.equal(result[0].edited, true);
        assert.equal(result[0].modified, true);
        // Poll with new_option
        assert.equal(result[1].widget_edited, true);
        assert.equal(result[1].edited, true);
        assert.equal(result[1].modified, true);
        // Poll with only votes
        assert.equal(result[2].widget_edited, false);
        assert.equal(result[2].edited, false);
        assert.equal(result[2].modified, false);
        // Non-poll widget
        assert.equal(result[3].widget_edited, false);
        assert.equal(result[3].edited, false);
        assert.equal(result[3].modified, false);
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
        return {
            include_sender: true,
            ...message_context,
            msg: {
                is_me_message: false,
                last_edit_timestamp: (next_timestamp += 1),
                edit_history: [{prev_content: "test_content", timestamp: 1000, user_id: 1}],
                ...message,
            },
        };
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

test("rerender_messages rebuilds every distinct recipient bar", () => {
    // A user can show up in several recipient bars at once -- e.g. DMs
    // with the same user spread through Combined feed or search views.
    // When that user is renamed, rerender_messages gets all their
    // messages together and must rebuild every one of those bars, not
    // just the first. The bars share a recipient, so we identify each bar
    // by its rendered group id rather than by recipient.
    const view = new MessageListView({id: 1}, true, true);

    const dm1 = {msg: {id: 1, type: "private", to_user_ids: "5"}};
    const dm2 = {msg: {id: 2, type: "private", to_user_ids: "5"}};
    // dm3 has a container but no rendered row (e.g. a muted stream or
    // topic), so there is no recipient bar to rebuild for it.
    const dm3 = {msg: {id: 3, type: "private", to_user_ids: "5"}};
    view.message_containers = new Map([
        [1, dm1],
        [2, dm2],
        [3, dm3],
    ]);

    // dm1 and dm2 share a recipient but render in different bars; dm3 has
    // no row. The stub row mirrors how rows.get_message_recipient_row
    // reads the bar id from the DOM, and returns an empty set (length 0)
    // for the unrendered message -- which must be skipped before any DOM
    // lookup.
    const group_id_by_msg_id = {1: "group-A", 2: "group-B"};
    view.get_row = (id) => {
        const group_id = group_id_by_msg_id[id];
        if (group_id === undefined) {
            return {length: 0};
        }
        return {length: 1, parent: () => ({expectOne: () => ({attr: () => group_id})})};
    };

    view._message_groups = [{message_group_id: "group-A"}, {message_group_id: "group-B"}];

    view._rerender_message = () => [];
    const rerendered_group_ids = [];
    view._rerender_header = (group) => {
        rerendered_group_ids.push(group.message_group_id);
    };

    view.rerender_messages([dm1.msg, dm2.msg, dm3.msg]);

    // One header rerender per distinct bar; the rowless message is skipped.
    assert.deepEqual(rerendered_group_ids, ["group-A", "group-B"]);
});

test("muted_message_vars", () => {
    // This verifies that the variables for muted/hidden messages are set
    // correctly.

    function build_message_context(message = {}, message_context = {}) {
        return {...message_context, msg: {...message}};
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
        const empty_list_stub = $.set_results("empty-stub", []);
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

        // Check that `is_hidden` is true on all messages and `include_sender` is true for the first one.
        assert.equal(result[0].is_hidden, true);
        assert.equal(result[1].is_hidden, true);
        assert.equal(result[2].is_hidden, true);

        assert.equal(result[0].include_sender, true);
        assert.equal(result[1].include_sender, false);
        assert.equal(result[2].include_sender, false);

        // Ensure that `small_avatar_url` is the Muted sender avatar URL.
        assert.equal(result[0].small_avatar_url, "fake/muted_user/avatar/url");

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

        // Ensure that `small_avatar_url` is now set to the sender's avatar URL.
        assert.equal(result[0].small_avatar_url, "fake/small/avatar/url");

        // Additionally test that the message with a mention is marked as such.
        assert.equal(result[1].mention_classname, "group_mention");

        // Now test rehiding muted user's message
        is_revealed = false;
        result = calculate_variables(list, messages, is_revealed);

        // Check that `is_hidden` is true and `include_sender` is true on all messages.
        assert.equal(result[0].is_hidden, true);
        assert.equal(result[1].is_hidden, true);
        assert.equal(result[2].is_hidden, true);

        assert.equal(result[0].include_sender, true);
        assert.equal(result[1].include_sender, true);
        assert.equal(result[2].include_sender, true);

        // Ensure that `small_avatar_url` is the Muted sender avatar URL.
        assert.equal(result[0].small_avatar_url, "fake/muted_user/avatar/url");
        assert.equal(result[1].small_avatar_url, "fake/muted_user/avatar/url");
        assert.equal(result[2].small_avatar_url, "fake/muted_user/avatar/url");

        // Additionally test that, both there is no mention classname even on that message
        // which has a mention, since we don't want to display hidden mentions so visibly.
        assert.equal(result[1].mention_classname, undefined);
    })();
});

test("merge_message_groups", ({mock_template}) => {
    mock_template("message_list.hbs", false, () => "<message-list-stub>");
    mock_template("bookend.hbs", false, () => "<bookend-stub>");
    // MessageListView has lots of DOM code, so we are going to test the message
    // group merging logic on its own.

    function build_message_context(message = {}, message_context = {}) {
        return {
            include_sender: true,
            ...message_context,
            msg: {
                id: _.uniqueId("test_message_"),
                status_message: false,
                type: "stream",
                stream_id: 2,
                topic: "Test topic 1",
                sender_email: "test@example.com",
                timestamp: (next_timestamp += 1),
                ...message,
            },
        };
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

    // Mirror the order in which render() computes subscription-status
    // dividers and markers on the new groups before merging them into
    // the rendered list.
    function add_message_groups(list, new_message_groups, where) {
        list.set_subscription_dividers_and_markers(new_message_groups, where);
        return list.merge_message_groups(new_message_groups, where);
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
        const result = add_message_groups(list, [message_group2], "bottom");

        // Flipping the historical flag should not split the message group
        // when the recipient is the same: the change is shown as an inline
        // divider on message2 rather than as a bookend on the joined group.
        assert.equal(list._message_groups[0].bookend_top, undefined);
        assert.equal(message2.want_subscription_status_divider, true);
        assert_message_groups_list_equal(list._message_groups, [
            build_message_group([message1, message2]),
        ]);
        assert.deepEqual(result.append_groups, []);
        assert.deepEqual(result.prepend_groups, []);
        assert.deepEqual(result.rerender_groups, []);
        assert.deepEqual(result.append_messages, [message2]);
        assert.ok(!list._message_groups[0].message_containers[0].want_subscription_status_divider);
        assert.ok(list._message_groups[0].message_containers[1].want_subscription_status_divider);

        const message3 = build_message_context({historical: false, topic: "test"});
        const message_group3 = build_message_group([message3]);

        const result2 = add_message_groups(list, [message_group3], "bottom");

        assert.ok(message_group3.bookend_top);
        assert_message_groups_list_equal(list._message_groups, [
            build_message_group([message1, message2]),
            message_group3,
        ]);
        assert_message_groups_list_equal(result2.append_groups, [message_group3]);
        assert.deepEqual(result2.prepend_groups, []);
        assert.deepEqual(result2.rerender_groups, []);
        assert.deepEqual(result2.append_messages, []);
        assert.ok(!list._message_groups[1].message_containers[0].want_subscription_status_divider);
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
        list.$list[0].prepend = noop;
        const result = add_message_groups(list, [message_group2], "top");

        assert.equal(list._message_groups[0].bookend_top, undefined);
        assert_message_groups_list_equal(list._message_groups, [
            build_message_group([message2, message1]),
        ]);
        assert.deepEqual(result.append_groups, []);
        assert.deepEqual(result.prepend_groups, []);
        assert_message_groups_list_equal(result.rerender_groups, [
            build_message_group([message2, message1]),
        ]);
        assert.deepEqual(result.append_messages, []);
        assert.ok(!list._message_groups[0].message_containers[0].want_subscription_status_divider);
        assert.ok(list._message_groups[0].message_containers[1].want_subscription_status_divider);

        const message3 = build_message_context({historical: false, topic: "test"});
        const message_group3 = build_message_group([message3]);

        const result2 = add_message_groups(list, [message_group3], "top");

        assert.ok(message_group2.bookend_top);
        assert_message_groups_list_equal(list._message_groups, [
            message_group3,
            build_message_group([message2, message1]),
        ]);
        assert.deepEqual(result2.append_groups, []);
        assert_message_groups_list_equal(result2.prepend_groups, [message_group3]);
        assert.deepEqual(result2.rerender_groups, []);
        assert.deepEqual(result2.append_messages, []);
        assert.ok(!list._message_groups[0].message_containers[0].want_subscription_status_divider);
        assert.ok(!list._message_groups[1].message_containers[0].want_subscription_status_divider);
        assert.ok(list._message_groups[1].message_containers[1].want_subscription_status_divider);
    })();

    // Messages moved here from another channel carry a `historical` flag
    // that is meaningless in this channel, so they must not trigger
    // subscription-status dividers or bookends.
    function build_moved_message_context(message = {}) {
        // prev_stream differs from the default stream_id (2), marking the
        // message as moved here from another channel.
        return build_message_context({
            edit_history: [{prev_stream: 999}],
            ...message,
        });
    }

    (function test_append_moved_message_skips_subscription_divider() {
        const moved_message = build_moved_message_context({historical: true});
        const message_group1 = build_message_group([moved_message]);

        const message2 = build_message_context({historical: false});
        const message_group2 = build_message_group([message2]);

        const list = build_list([message_group1]);
        add_message_groups(list, [message_group2], "bottom");

        assert.ok(!message2.want_subscription_status_divider);
        assert_message_groups_list_equal(list._message_groups, [
            build_message_group([moved_message, message2]),
        ]);
    })();

    (function test_moved_message_never_gets_subscription_divider() {
        const message1 = build_message_context({historical: false});
        const message_group1 = build_message_group([message1]);

        const moved_message = build_moved_message_context({historical: true});
        const message_group2 = build_message_group([moved_message]);

        const list = build_list([message_group1]);
        add_message_groups(list, [message_group2], "bottom");

        // Assert the groups joined, so the divider check can't pass
        // vacuously on an unset field.
        assert_message_groups_list_equal(list._message_groups, [
            build_message_group([message1, moved_message]),
        ]);
        assert.equal(moved_message.want_subscription_status_divider, false);
    })();

    (function test_moved_last_message_skips_subscription_bookend() {
        // When the groups do not join (different topic), the transition is
        // shown as a group bookend; a moved message must not trigger it.
        const moved_message = build_moved_message_context({historical: true});
        const message_group1 = build_message_group([moved_message]);

        const message2 = build_message_context({historical: false, topic: "Test topic 2"});
        const message_group2 = build_message_group([message2]);

        const list = build_list([message_group1]);
        add_message_groups(list, [message_group2], "bottom");

        assert.equal(message_group2.bookend_top, undefined);
        assert.equal(message_group2.subscribed, undefined);
        assert.equal(message_group2.just_unsubscribed, undefined);
    })();

    (function test_moved_first_message_skips_subscription_bookend() {
        const message1 = build_message_context({historical: false});
        const message_group1 = build_message_group([message1]);

        const moved_message = build_moved_message_context({
            historical: true,
            topic: "Test topic 2",
        });
        const message_group2 = build_message_group([moved_message]);

        const list = build_list([message_group1]);
        add_message_groups(list, [message_group2], "bottom");

        assert.equal(message_group2.bookend_top, undefined);
        assert.equal(message_group2.just_unsubscribed, undefined);
    })();

    (function test_message_moved_back_to_original_channel() {
        // A message moved away and then back to its current channel carries
        // a meaningful historical flag, so it is treated as a normal message.
        const moved_back_message = build_message_context({
            historical: true,
            edit_history: [{prev_stream: 2}],
        });
        const message_group1 = build_message_group([moved_back_message]);

        const message2 = build_message_context({historical: false});
        const message_group2 = build_message_group([message2]);

        const list = build_list([message_group1]);
        add_message_groups(list, [message_group2], "bottom");

        assert.ok(message2.want_subscription_status_divider);
    })();

    (function test_prepend_moved_message_skips_subscription_bookend() {
        const message1 = build_message_context({historical: false});
        const message_group1 = build_message_group([message1]);

        const moved_message = build_moved_message_context({
            historical: true,
            topic: "Test topic 2",
        });
        const message_group2 = build_message_group([moved_message]);

        const list = build_list([message_group1]);
        add_message_groups(list, [message_group2], "top");

        // The bookend, if any, is added to the existing (lower) group.
        assert.equal(message_group1.bookend_top, undefined);
        assert.equal(message_group1.subscribed, undefined);
    })();

    (function test_divider_shown_across_moved_message_in_batch() {
        // A moved message between two messages with meaningful flags must
        // not hide the real transition between them: the divider belongs
        // on the first meaningful message after the flip.
        const message1 = build_message_context({historical: true});
        const message_group1 = build_message_group([message1]);

        const moved_message = build_moved_message_context({historical: true});
        const message2 = build_message_context({historical: false});
        const message_group2 = build_message_group([moved_message, message2]);

        const list = build_list([message_group1]);
        add_message_groups(list, [message_group2], "bottom");

        assert_message_groups_list_equal(list._message_groups, [
            build_message_group([message1, moved_message, message2]),
        ]);
        assert.ok(!moved_message.want_subscription_status_divider);
        assert.ok(message2.want_subscription_status_divider);
    })();

    (function test_divider_shown_when_newest_rendered_message_was_moved() {
        // Likewise when the moved message was already rendered: the new
        // message is compared with the newest meaningful flag, not with
        // the moved message just above it.
        const message1 = build_message_context({historical: true});
        const moved_message = build_moved_message_context({historical: true});
        const message_group1 = build_message_group([message1, moved_message]);

        const message2 = build_message_context({historical: false});
        const message_group2 = build_message_group([message2]);

        const list = build_list([message_group1]);
        add_message_groups(list, [message_group2], "bottom");

        assert_message_groups_list_equal(list._message_groups, [
            build_message_group([message1, moved_message, message2]),
        ]);
        assert.ok(message2.want_subscription_status_divider);
    })();

    (function test_prepend_divider_shown_across_moved_message() {
        const message1 = build_message_context({historical: false});
        const message_group1 = build_message_group([message1]);

        const message2 = build_message_context({historical: true});
        const moved_message = build_moved_message_context({historical: true});
        const message_group2 = build_message_group([message2, moved_message]);

        const list = build_list([message_group1]);
        add_message_groups(list, [message_group2], "top");

        // The existing message joins below the prepended group; its
        // divider reflects the flip from message2's flag, not the moved
        // message's.
        assert_message_groups_list_equal(list._message_groups, [
            build_message_group([message2, moved_message, message1]),
        ]);
        assert.ok(message1.want_subscription_status_divider);
        assert.ok(!moved_message.want_subscription_status_divider);
    })();

    (function test_prepend_marker_when_oldest_rendered_group_was_moved() {
        // The oldest rendered group consists only of a message moved here from
        // another channel, so the first meaningful rendered message starts a
        // later group that the prepended messages can never merge into. A
        // subscription change at that boundary belongs on the group as a
        // bookend, not as an inline divider on its first message.
        const moved_message = build_moved_message_context({
            historical: true,
            topic: "Moved topic",
        });
        const moved_group = build_message_group([moved_message]);

        const message1 = build_message_context({historical: true, topic: "Subscribed topic"});
        const message_group1 = build_message_group([message1]);

        const message2 = build_message_context({historical: false, topic: "New topic"});
        const message_group2 = build_message_group([message2]);

        const list = build_list([moved_group, message_group1]);
        add_message_groups(list, [message_group2], "top");

        // No merge happens (distinct topics), so the flip from subscribed
        // (message2) to unsubscribed (message1) shows as a bookend on
        // message1's group, and message1 keeps no inline divider.
        assert.ok(message_group1.bookend_top);
        assert.equal(message_group1.just_unsubscribed, true);
        assert.ok(!message1.want_subscription_status_divider);
    })();

    (function test_prepend_inline_divider_when_oldest_rendered_group_starts_with_moved() {
        // The oldest rendered group starts with a moved message but
        // continues with a meaningful one. The boundary against the
        // prepended messages is shown as an inline divider on that
        // meaningful continuation message, since the moved message above it
        // in the same group makes it a continuation rather than the group's
        // first message.
        const moved_message = build_moved_message_context({historical: true});
        const message1 = build_message_context({historical: true});
        // Same recipient, so both messages live in one rendered group.
        const rendered_group = build_message_group([moved_message, message1]);

        const message2 = build_message_context({historical: false, topic: "New topic"});
        const message_group2 = build_message_group([message2]);

        const list = build_list([rendered_group]);
        add_message_groups(list, [message_group2], "top");

        // No merge happens (distinct topics), so the flip from message2
        // (subscribed) to message1 (unsubscribed) is shown inline on
        // message1, not on the moved message above it.
        assert.ok(message1.want_subscription_status_divider);
        assert.ok(!moved_message.want_subscription_status_divider);
    })();

    (function test_prepend_no_boundary_update_when_all_rendered_messages_moved() {
        // Every already-rendered message was moved here from another
        // channel, so none has a meaningful flag. The prepended-boundary
        // update finds no container to mark and leaves the rendered content
        // untouched.
        const moved_message = build_moved_message_context({historical: true});
        const rendered_group = build_message_group([moved_message]);

        const message1 = build_message_context({historical: false, topic: "New topic"});
        const message_group1 = build_message_group([message1]);

        const list = build_list([rendered_group]);
        add_message_groups(list, [message_group1], "top");

        assert.ok(!moved_message.want_subscription_status_divider);
        assert.equal(rendered_group.bookend_top, undefined);
        assert.equal(rendered_group.subscribed, undefined);
        assert.equal(rendered_group.just_unsubscribed, undefined);
    })();

    (function test_no_subscription_marker_without_historical_flip() {
        // Two non-merging groups in the same subscription state produce no
        // bookend: there is no historical-flag flip between them.
        const message1 = build_message_context({historical: false});
        const message_group1 = build_message_group([message1]);

        const message2 = build_message_context({historical: false, topic: "New topic"});
        const message_group2 = build_message_group([message2]);

        const list = build_list([message_group1]);
        add_message_groups(list, [message_group2], "bottom");

        assert.equal(message_group2.bookend_top, undefined);
        assert.equal(message_group2.subscribed, undefined);
        assert.equal(message_group2.just_unsubscribed, undefined);
        assert.ok(!message2.want_subscription_status_divider);
    })();
});

test("get_boundary_message_info_with_meaningful_historical", () => {
    // get_boundary_message_info_with_meaningful_historical("newest")
    // feeds the trailing bookend, which must infer subscription status from the newest
    // message whose `historical` flag is meaningful in this channel, skipping
    // messages moved here from another channel.
    function build_message_container(message = {}) {
        return {
            msg: {
                id: _.uniqueId("test_message_"),
                type: "stream",
                stream_id: 2,
                ...message,
            },
        };
    }

    function build_list(message_groups) {
        const list = new MessageListView({id: 1}, true, true);
        list._message_groups = message_groups;
        return list;
    }

    // The newest message's flag is used directly when it is meaningful.
    let list = build_list([
        {
            message_containers: [
                build_message_container({historical: false}),
                build_message_container({historical: true}),
            ],
        },
    ]);
    assert.equal(
        list.get_boundary_message_info_with_meaningful_historical("newest")?.message_container.msg
            .historical,
        true,
    );

    // Moved messages are skipped, across group boundaries.
    list = build_list([
        {message_containers: [build_message_container({historical: false})]},
        {
            message_containers: [
                build_message_container({historical: true, edit_history: [{prev_stream: 999}]}),
            ],
        },
    ]);
    assert.equal(
        list.get_boundary_message_info_with_meaningful_historical("newest")?.message_container.msg
            .historical,
        false,
    );

    // A message moved back to its original channel has a meaningful flag.
    list = build_list([
        {
            message_containers: [
                build_message_container({historical: true, edit_history: [{prev_stream: 2}]}),
            ],
        },
    ]);
    assert.equal(
        list.get_boundary_message_info_with_meaningful_historical("newest")?.message_container.msg
            .historical,
        true,
    );

    // With no meaningful flag at all, the status is unknown.
    list = build_list([
        {
            message_containers: [
                build_message_container({historical: true, edit_history: [{prev_stream: 999}]}),
            ],
        },
    ]);
    assert.equal(
        list.get_boundary_message_info_with_meaningful_historical("newest")?.message_container.msg
            .historical,
        undefined,
    );

    list = build_list([]);
    assert.equal(
        list.get_boundary_message_info_with_meaningful_historical("newest")?.message_container.msg
            .historical,
        undefined,
    );
});

test("set_subscription_dividers_and_markers ignores non-channel narrows", () => {
    // Subscription-status dividers and bookends only make sense in a
    // single-channel narrow. In other narrows (e.g. direct messages) the
    // pass must run without adding any divider or bookend, and a non-stream
    // message is never treated as moved.
    const filter = new Filter([{operator: "is", operand: "dm"}]);
    const list = new message_list.MessageList({
        data: new MessageListData({excludes_muted_topics: false, filter}),
        is_node_test: true,
    });
    const view = new MessageListView(list, true, true);

    const dm1 = {include_sender: true, msg: {id: 1, type: "private", to_user_ids: "5"}};
    const dm2 = {include_sender: true, msg: {id: 2, type: "private", to_user_ids: "5"}};
    const rendered_group = {message_containers: [dm1], message_group_id: "dm-group-1"};
    const new_group = {message_containers: [dm2], message_group_id: "dm-group-2"};
    view._message_groups = [rendered_group];

    view.set_subscription_dividers_and_markers([new_group], "bottom");

    assert.ok(!dm2.want_subscription_status_divider);
    assert.equal(new_group.bookend_top, undefined);
    assert.equal(new_group.subscribed, undefined);
    assert.equal(new_group.just_unsubscribed, undefined);

    // Appending no new groups is a no-op: there is no boundary container to
    // mark.
    assert.doesNotThrow(() => {
        view.set_subscription_dividers_and_markers([], "bottom");
    });
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
