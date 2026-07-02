"use strict";

const assert = require("node:assert/strict");

const {make_message_list} = require("./lib/message_list.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");

mock_esm("../src/people.ts", {
    maybe_get_user_by_id: noop,
});

const recent_view_messages_data = zrequire("../src/recent_view_messages_data");

const {MessageListData} = zrequire("../src/message_list_data");
const narrow_state = zrequire("narrow_state");
const message_view = zrequire("message_view");
const message_lists = zrequire("message_lists");
const resolved_topic = zrequire("resolved_topic");

function verify_fixture(fixture, override_rewire) {
    const msg_list = make_message_list(fixture.filter_terms);
    const filter = msg_list.data.filter;
    message_lists.set_current(msg_list);

    // Make sure our simulated tests data satisfies the
    // invariant that the first unread message we find
    // does indeed satisfy our filter.
    if (fixture.unread_info.flavor === "found") {
        for (const msg of fixture.all_messages) {
            if (msg.id === fixture.unread_info.msg_id) {
                assert.ok(filter.predicate()(msg));
            }
        }
    }

    const excludes_muted_topics = filter.excludes_muted_topics();
    const msg_data = new MessageListData({
        filter,
        excludes_muted_topics,
    });
    const id_info = {
        target_id: fixture.target_id,
        local_select_id: undefined,
        final_select_id: undefined,
    };

    override_rewire(recent_view_messages_data, "recent_view_messages_data", {
        fetch_status: {
            has_found_newest: () => fixture.has_found_newest,
        },
        visibly_empty: () => fixture.visibly_empty,
        all_messages_after_mute_filtering() {
            assert.notEqual(fixture.all_messages, undefined);
            return fixture.all_messages;
        },
        first() {
            assert.notEqual(fixture.all_messages, undefined);
            return fixture.all_messages[0];
        },
        last() {
            assert.notEqual(fixture.all_messages, undefined);
            return fixture.all_messages.at(-1);
        },
    });

    override_rewire(narrow_state, "get_first_unread_info", () => fixture.unread_info);

    message_view.maybe_add_local_messages({
        id_info,
        msg_data,
        superset_data: recent_view_messages_data.recent_view_messages_data,
    });

    assert.deepEqual(id_info, fixture.expected_id_info);

    const msgs = msg_data.all_messages_after_mute_filtering();
    const msg_ids = msgs.map((message) => message.id);
    assert.deepEqual(msg_ids, fixture.expected_msg_ids);
}

function test_fixture(label, fixture) {
    run_test(label, ({override_rewire}) => {
        verify_fixture(fixture, override_rewire);
    });
}

test_fixture("near after unreads", {
    // Current near: behavior is to ignore the unreads and take you
    // to the target message, with reading disabled.
    filter_terms: [{operator: "near", operand: "42"}],
    target_id: 42,
    unread_info: {
        flavor: "found",
        msg_id: 37,
    },
    has_found_newest: false,
    all_messages: [
        {id: 37, topic: "whatever"},
        {id: 42, topic: "whatever"},
        {id: 44, topic: "whatever"},
    ],
    expected_id_info: {
        target_id: 42,
        final_select_id: 42,
        local_select_id: 42,
    },
    expected_msg_ids: [37, 42, 44],
});

test_fixture("near not in message list", {
    // Current behavior is to ignore the unreads and take you
    // to the closest messages, with reading disabled.
    filter_terms: [{operator: "near", operand: "42"}],
    target_id: 42,
    unread_info: {
        flavor: "found",
        msg_id: 46,
    },
    has_found_newest: false,
    all_messages: [
        {id: 41, topic: "whatever"},
        {id: 45, topic: "whatever"},
        {id: 46, topic: "whatever"},
    ],
    expected_id_info: {
        target_id: 42,
        final_select_id: 42,
        local_select_id: undefined,
    },
    expected_msg_ids: [41, 45, 46],
});

test_fixture("near before unreads", {
    filter_terms: [{operator: "near", operand: "42"}],
    target_id: 42,
    unread_info: {
        flavor: "found",
        msg_id: 43,
    },
    has_found_newest: false,
    all_messages: [
        {id: 42, topic: "whatever"},
        {id: 43, topic: "whatever"},
        {id: 44, topic: "whatever"},
    ],
    expected_id_info: {
        target_id: 42,
        final_select_id: 42,
        local_select_id: 42,
    },
    expected_msg_ids: [42, 43, 44],
});

test_fixture("near with no unreads", {
    filter_terms: [{operator: "near", operand: "42"}],
    target_id: 42,
    unread_info: {
        flavor: "not_found",
    },
    has_found_newest: false,
    visibly_empty: true,
    expected_id_info: {
        target_id: 42,
        final_select_id: 42,
        local_select_id: undefined,
    },
    expected_msg_ids: [],
});

test_fixture("is private with no target", {
    filter_terms: [{operator: "is", operand: "private"}],
    unread_info: {
        flavor: "found",
        msg_id: 550,
    },
    has_found_newest: true,
    all_messages: [
        {id: 450, type: "private", to_user_ids: "1,2"},
        {id: 500, type: "private", to_user_ids: "1,2"},
        {id: 550, type: "private", to_user_ids: "1,2"},
    ],
    expected_id_info: {
        target_id: undefined,
        final_select_id: 550,
        local_select_id: 550,
    },
    expected_msg_ids: [450, 500, 550],
});

test_fixture("dm with target outside of range", {
    filter_terms: [{operator: "dm", operand: [1]}],
    target_id: 5,
    unread_info: {
        flavor: "not_found",
    },
    has_found_newest: false,
    all_messages: [{id: 999}],
    expected_id_info: {
        target_id: 5,
        final_select_id: 5,
        local_select_id: undefined,
    },
    expected_msg_ids: [],
});

test_fixture("is:private with no unreads before fetch", {
    filter_terms: [{operator: "is", operand: "private"}],
    unread_info: {
        flavor: "not_found",
    },
    has_found_newest: false,
    visibly_empty: true,
    expected_id_info: {
        target_id: undefined,
        final_select_id: undefined,
        local_select_id: undefined,
    },
    expected_msg_ids: [],
});

test_fixture("is:private with target and no unreads", {
    filter_terms: [{operator: "is", operand: "private"}],
    target_id: 450,
    unread_info: {
        flavor: "not_found",
    },
    has_found_newest: true,
    visibly_empty: false,
    all_messages: [
        {id: 350},
        {id: 400, type: "private", to_user_ids: "1,2"},
        {id: 450, type: "private", to_user_ids: "1,2"},
        {id: 500, type: "private", to_user_ids: "1,2"},
    ],
    expected_id_info: {
        target_id: 450,
        final_select_id: 450,
        local_select_id: 450,
    },
    expected_msg_ids: [400, 450, 500],
});

test_fixture("is:mentioned with no unreads and no matches", {
    filter_terms: [{operator: "is", operand: "mentioned"}],
    unread_info: {
        flavor: "not_found",
    },
    has_found_newest: true,
    all_messages: [],
    expected_id_info: {
        target_id: undefined,
        final_select_id: undefined,
        local_select_id: undefined,
    },
    expected_msg_ids: [],
});

test_fixture("is:alerted with no unreads and one match", {
    filter_terms: [{operator: "is", operand: "alerted"}],
    unread_info: {
        flavor: "not_found",
    },
    has_found_newest: true,
    all_messages: [
        {id: 55, topic: "whatever", alerted: true},
        {id: 57, topic: "whatever", alerted: false},
    ],
    expected_id_info: {
        target_id: undefined,
        final_select_id: 55,
        local_select_id: 55,
    },
    expected_msg_ids: [55],
});

test_fixture("is:resolved with one unread", {
    filter_terms: [{operator: "is", operand: "resolved"}],
    unread_info: {
        flavor: "found",
        msg_id: 56,
    },
    has_found_newest: true,
    all_messages: [
        {id: 55, type: "stream", topic: resolved_topic.resolve_name("foo")},
        {id: 56, type: "stream", topic: resolved_topic.resolve_name("foo")},
        {id: 57, type: "stream", topic: "foo"},
    ],
    expected_id_info: {
        target_id: undefined,
        final_select_id: 56,
        local_select_id: 56,
    },
    expected_msg_ids: [55, 56],
});

test_fixture("is:resolved with no unreads", {
    filter_terms: [{operator: "is", operand: "resolved"}],
    unread_info: {
        flavor: "not_found",
    },
    has_found_newest: true,
    all_messages: [
        {id: 55, type: "stream", topic: resolved_topic.resolve_name("foo")},
        {id: 57, type: "stream", topic: "foo"},
    ],
    expected_id_info: {
        target_id: undefined,
        final_select_id: 55,
        local_select_id: 55,
    },
    expected_msg_ids: [55],
});

test_fixture("search", {
    filter_terms: [{operator: "search", operand: "whatever"}],
    unread_info: {
        flavor: "cannot_compute",
    },
    expected_id_info: {
        target_id: undefined,
        final_select_id: 10000000000000000,
        local_select_id: undefined,
    },
    expected_msg_ids: [],
});

test_fixture("search near", {
    filter_terms: [
        {operator: "search", operand: "whatever"},
        {operator: "near", operand: "22"},
    ],
    target_id: 22,
    unread_info: {
        flavor: "cannot_compute",
    },
    expected_id_info: {
        target_id: 22,
        final_select_id: 22,
        local_select_id: undefined,
    },
    expected_msg_ids: [],
});

test_fixture("stream, no unread, not in all_messages", {
    // This might be something you'd see zooming out from
    // a muted topic, maybe?  It's possibly this scenario
    // is somewhat contrived, but we exercise fairly simple
    // defensive code that just punts when messages aren't in
    // our new message list.  Note that our target_id is within
    // the range of all_messages.
    filter_terms: [{operator: "stream", operand: "whatever"}],
    target_id: 450,
    unread_info: {
        flavor: "not_found",
    },
    has_found_newest: true,
    visibly_empty: false,
    all_messages: [{id: 400}, {id: 500}],
    expected_id_info: {
        target_id: 450,
        final_select_id: 450,
        local_select_id: undefined,
    },
    expected_msg_ids: [],
});

test_fixture("search, stream, not in all_messages", {
    filter_terms: [
        {operator: "search", operand: "foo"},
        {operator: "stream", operand: "whatever"},
    ],
    unread_info: {
        flavor: "cannot_compute",
    },
    has_found_newest: true,
    visibly_empty: false,
    all_messages: [{id: 400}, {id: 500}],
    expected_id_info: {
        target_id: undefined,
        final_select_id: 10000000000000000,
        local_select_id: undefined,
    },
    expected_msg_ids: [],
});

test_fixture("stream/topic not in recent_view_messages_data", {
    // This is a bit of a corner case, but you could have a scenario
    // where you've gone way back in a topic (perhaps something that
    // has been muted a long time) and find an unread message that isn't
    // actually in recent_view_messages_data.
    filter_terms: [
        {operator: "stream", operand: "one"},
        {operator: "topic", operand: "whatever"},
    ],
    target_id: 1000,
    unread_info: {
        flavor: "found",
        msg_id: 2,
    },
    has_found_newest: true,
    all_messages: [{id: 900}, {id: 1100}],
    expected_id_info: {
        target_id: 1000,
        final_select_id: 2,
        local_select_id: undefined,
    },
    expected_msg_ids: [],
});

test_fixture("final corner case", {
    // This tries to get all the way to the end of
    // the function (as written now).  The data here
    // may be completely contrived.
    filter_terms: [{operator: "is", operand: "starred"}],
    target_id: 450,
    unread_info: {
        flavor: "not_found",
    },
    has_found_newest: true,
    visibly_empty: false,
    all_messages: [
        {id: 400, topic: "whatever"},
        {id: 425, topic: "whatever", starred: true},
        {id: 500, topic: "whatever"},
    ],
    expected_id_info: {
        target_id: 450,
        final_select_id: 450,
        local_select_id: undefined,
    },
    expected_msg_ids: [425],
});

// The `date` operator is a no-op predicate (see filter.ts), so msg_data
// holds every local message; the operator just slices where we anchor.
// maybe_add_local_messages resolves that anchor locally only when it can
// be certain of the result. 1717977600 is the Unix time for midnight on
// 2024-06-10 (tests run in UTC).
const date_operand = "2024-06-10";
const date_midnight = 1717977600;

test_fixture("date with all local messages before it and newest found", {
    // Every local message predates the date and we've found the newest,
    // so nothing matches on/after the date; select the newest we have.
    filter_terms: [{operator: "date", operand: date_operand}],
    target_id: undefined,
    unread_info: {
        flavor: "not_found",
    },
    has_found_newest: true,
    visibly_empty: false,
    all_messages: [
        {id: 10, topic: "whatever", timestamp: date_midnight - 200000},
        {id: 11, topic: "whatever", timestamp: date_midnight - 100000},
    ],
    expected_id_info: {
        target_id: undefined,
        final_select_id: 11,
        local_select_id: 11,
    },
    expected_msg_ids: [10, 11],
});

test_fixture("date with all local messages before it but newest not found", {
    // Matching messages on/after the date may exist on the server, so we
    // leave final_select_id undefined and defer to the server's anchor.
    filter_terms: [{operator: "date", operand: date_operand}],
    target_id: undefined,
    unread_info: {
        flavor: "not_found",
    },
    has_found_newest: false,
    visibly_empty: false,
    all_messages: [
        {id: 20, topic: "whatever", timestamp: date_midnight - 200000},
        {id: 21, topic: "whatever", timestamp: date_midnight - 100000},
    ],
    expected_id_info: {
        target_id: undefined,
        final_select_id: undefined,
        local_select_id: undefined,
    },
    expected_msg_ids: [20, 21],
});

test_fixture("date with earliest local message already on/after it", {
    // We can't rule out older matching messages on the server (#32150),
    // so we defer to the server's anchor.
    filter_terms: [{operator: "date", operand: date_operand}],
    target_id: undefined,
    unread_info: {
        flavor: "not_found",
    },
    has_found_newest: true,
    visibly_empty: false,
    all_messages: [
        {id: 30, topic: "whatever", timestamp: date_midnight + 100},
        {id: 31, topic: "whatever", timestamp: date_midnight + 100000},
    ],
    expected_id_info: {
        target_id: undefined,
        final_select_id: undefined,
        local_select_id: undefined,
    },
    expected_msg_ids: [30, 31],
});

test_fixture("date falling within the locally-loaded range", {
    // We have local messages both before and on/after the date, but the
    // superset cache need not be contiguous, so the first local message
    // on/after the date may not be the narrow's true first such message;
    // we defer to the server for the accurate anchor.
    filter_terms: [{operator: "date", operand: date_operand}],
    target_id: undefined,
    unread_info: {
        flavor: "not_found",
    },
    has_found_newest: true,
    visibly_empty: false,
    all_messages: [
        {id: 40, topic: "whatever", timestamp: date_midnight - 100000},
        {id: 41, topic: "whatever", timestamp: date_midnight + 100000},
    ],
    expected_id_info: {
        target_id: undefined,
        final_select_id: undefined,
        local_select_id: undefined,
    },
    expected_msg_ids: [40, 41],
});
