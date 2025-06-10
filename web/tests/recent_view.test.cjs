"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");
const {page_params} = require("./lib/zpage_params.cjs");

const {initialize_user_settings} = zrequire("user_settings");

const user_settings = {};
initialize_user_settings({user_settings});

window.scrollTo = noop;
const test_url = () => "https://www.example.com";
const test_permalink = () => "https://www.example.com/with/12";

// We assign this in our test() wrapper.
let messages;

const private_messages = [];

// sender1 == current user
// sender2 == any other user
const sender1 = 1;
const sender2 = 2;

// New stream
const stream1 = 1;
const stream2 = 2;
const stream3 = 3;
const stream4 = 4;
const stream5 = 5; // Deleted stream
const stream6 = 6; // Muted stream

// Topics in the stream, all unread except topic1 & stream1.
const topic1 = "topic-1"; // No other sender & read.
const topic2 = "topic-2"; // Other sender
const topic3 = "topic-3"; // User not present
const topic4 = "topic-4"; // User not present
const topic5 = "topic-5"; // other sender
const topic6 = "topic-6"; // other sender
const topic7 = "topic-7"; // muted topic
const topic8 = "topic-8";
const topic9 = "topic-9";
const topic10 = "topic-10";
const topic11 = "topic-11"; // unmuted topic
const topic12 = "topic-12"; // followed topic

const all_visibility_policies = {
    INHERIT: 0,
    MUTED: 1,
    UNMUTED: 2,
    FOLLOWED: 3,
};

let expected_data_to_replace_in_list_widget;

const ListWidget = mock_esm("../src/list_widget", {
    modifier_html: noop,
    generic_sort_functions: noop,
    create(_container, mapped_topic_values, opts) {
        const formatted_topics = [];
        ListWidget.modifier_html = opts.modifier_html;
        for (const item of mapped_topic_values) {
            formatted_topics.push(opts.modifier_html(item));
            opts.filter.predicate(item);
        }
        // Just for coverage, the mechanisms
        // are tested in list_widget.test.cjs
        if (mapped_topic_values.length >= 2) {
            opts.sort_fields.stream_sort(mapped_topic_values[0], mapped_topic_values[1]);
            opts.sort_fields.stream_sort(mapped_topic_values[1], mapped_topic_values[0]);
            opts.sort_fields.stream_sort(mapped_topic_values[0], mapped_topic_values[0]);
            opts.sort_fields.topic_sort(mapped_topic_values[0], mapped_topic_values[1]);
            opts.sort_fields.topic_sort(mapped_topic_values[1], mapped_topic_values[0]);
            opts.sort_fields.topic_sort(mapped_topic_values[0], mapped_topic_values[0]);
        }
        return ListWidget;
    },

    hard_redraw: noop,
    filter_and_sort: noop,
    replace_list_data(data) {
        assert.notEqual(
            expected_data_to_replace_in_list_widget,
            undefined,
            "You must set expected_data_to_replace_in_list_widget",
        );
        assert.deepEqual(data, expected_data_to_replace_in_list_widget);
        expected_data_to_replace_in_list_widget = undefined;
    },
});

mock_esm("../src/compose_closed_ui", {
    set_standard_text_for_reply_button: noop,
    update_buttons_for_non_specific_views: noop,
});
mock_esm("../src/hash_util", {
    channel_url_by_user_setting: test_url,
    by_stream_topic_url: test_url,
    by_channel_topic_permalink: test_permalink,
    by_conversation_and_time_url: test_url,
});
mock_esm("../src/message_list_data", {
    MessageListData: class {},
});
mock_esm("../src/message_store", {
    get(msg_id) {
        if (msg_id < 15) {
            return messages[msg_id - 1];
        }
        return private_messages[msg_id - 15];
    },
});
mock_esm("../src/message_view_header", {
    render_title_area: noop,
});
mock_esm("../src/settings_data", {
    user_can_access_all_other_users: () => true,
});
mock_esm("../src/user_topics", {
    is_topic_muted(stream_id, topic) {
        if (stream_id === stream1 && topic === topic7) {
            return true;
        }
        return false;
    },
    is_topic_unmuted_or_followed(stream_id, topic) {
        if (stream_id === stream6 && (topic === topic11 || topic === topic12)) {
            return true;
        }
        return false;
    },
    get_topic_visibility_policy(stream_id, topic) {
        if (stream_id === stream1 && topic === topic7) {
            return all_visibility_policies.MUTED;
        } else if (stream_id === stream6 && topic === topic11) {
            return all_visibility_policies.UNMUTED;
        } else if (stream_id === stream6 && topic === topic12) {
            return all_visibility_policies.FOLLOWED;
        }
        return all_visibility_policies.INHERIT;
    },
    all_visibility_policies,
});
mock_esm("../src/narrow_title", {
    update_narrow_title() {},
});
mock_esm("../src/pm_list", {
    update_private_messages: noop,
    handle_message_view_deactivated: noop,
});
mock_esm("../src/recent_senders", {
    get_topic_recent_senders: () => [2, 1],
    get_pm_recent_senders(user_ids_string) {
        return {
            participants: user_ids_string.split(",").map((user_id) => Number.parseInt(user_id, 10)),
        };
    },
});
mock_esm("../src/stream_data", {
    is_muted(stream_id) {
        return stream_id === stream6;
    },
    get_stream_name_from_id: () => "stream_name",
});
mock_esm("../src/stream_list", {
    handle_message_view_deactivated: noop,
});
mock_esm("../src/timerender", {
    relative_time_string_from_date: () => "Just now",
    get_full_datetime_clarification: () => "date at time",
});
mock_esm("../src/left_sidebar_navigation_area", {
    highlight_recent_view: noop,
});
mock_esm("../src/unread", {
    num_unread_for_topic(stream_id, topic) {
        if (stream_id === 1 && topic === "topic-1") {
            return 0;
        }
        return 1;
    },
    num_unread_for_user_ids_string() {
        return 0;
    },
    topic_has_any_unread_mentions: () => false,
    num_unread_mentions_for_user_ids_strings(user_ids_string) {
        if (user_ids_string === "2,3") {
            return false;
        }
        return true;
    },
});
mock_esm("../src/resize", {
    update_recent_view: noop,
});
const dropdown_widget = mock_esm("../src/dropdown_widget");
dropdown_widget.DropdownWidget = function DropdownWidget() {
    this.setup = noop;
    this.render = noop;
};

const {all_messages_data} = zrequire("all_messages_data");
const {buddy_list} = zrequire("buddy_list");
const activity_ui = zrequire("activity_ui");
const people = zrequire("people");
const rt = zrequire("recent_view_ui");
rt.set_hide_other_views(noop);
const recent_view_util = zrequire("recent_view_util");
const rt_data = zrequire("recent_view_data");
const muted_users = zrequire("muted_users");
const {set_realm} = zrequire("state_data");
const sub_store = zrequire("sub_store");
const util = zrequire("util");

const REALM_EMPTY_TOPIC_DISPLAY_NAME = "test general chat";
set_realm({realm_empty_topic_display_name: REALM_EMPTY_TOPIC_DISPLAY_NAME});

for (const stream_id of [stream1, stream2, stream3, stream4, stream6]) {
    sub_store.add_hydrated_sub(stream_id, {
        color: "",
        invite_only: false,
        is_web_public: true,
        is_archived: false,
        subscribed: true,
    });
}

people.add_active_user({
    email: "alice@zulip.com",
    user_id: 1,
    full_name: "Alice Smith",
});
people.add_active_user({
    email: "fred@zulip.com",
    user_id: 2,
    full_name: "Fred Flintstone",
});
people.add_active_user({
    email: "spike@zulip.com",
    user_id: 3,
    full_name: "Spike Spiegel",
});
people.add_active_user({
    email: "eren@zulip.com",
    user_id: 4,
    full_name: "Eren Yeager",
});

people.initialize_current_user(1);
muted_users.add_muted_user(2, 17947949);
muted_users.add_muted_user(4, 17947949);

let id = 0;

const sample_messages = [];
sample_messages[0] = {
    stream_id: stream1,
    id: (id += 1),
    topic: topic1,
    sender_id: sender1,
    type: "stream",
};

sample_messages[1] = {
    stream_id: stream1,
    id: (id += 1),
    topic: topic2,
    sender_id: sender1,
    type: "stream",
};

sample_messages[2] = {
    stream_id: stream1,
    id: (id += 1),
    topic: topic2,
    sender_id: sender2,
    type: "stream",
};

sample_messages[3] = {
    stream_id: stream1,
    id: (id += 1),
    topic: topic3,
    sender_id: sender2,
    type: "stream",
};

sample_messages[4] = {
    stream_id: stream1,
    id: (id += 1),
    topic: topic4,
    sender_id: sender2,
    type: "stream",
};

sample_messages[5] = {
    stream_id: stream1,
    id: (id += 1),
    topic: topic5,
    sender_id: sender1,
    type: "stream",
};

sample_messages[6] = {
    stream_id: stream1,
    id: (id += 1),
    topic: topic5,
    sender_id: sender2,
    type: "stream",
};

sample_messages[7] = {
    stream_id: stream1,
    id: (id += 1),
    topic: topic6,
    sender_id: sender1,
    type: "stream",
};

sample_messages[8] = {
    stream_id: stream1,
    id: (id += 1),
    topic: topic6,
    sender_id: sender2,
    type: "stream",
};

sample_messages[9] = {
    stream_id: stream1,
    id: (id += 1),
    topic: topic7,
    sender_id: sender1,
    type: "stream",
};

// a message of stream4
sample_messages[10] = {
    stream_id: stream4,
    id: (id += 1),
    topic: topic10,
    sender_id: sender1,
    type: "stream",
};

// normal topic in muted stream
sample_messages[11] = {
    stream_id: stream6,
    id: (id += 1),
    topic: topic8,
    sender_id: sender1,
    type: "stream",
};

// unmuted topic in muted stream
sample_messages[12] = {
    stream_id: stream6,
    id: (id += 1),
    topic: topic11,
    sender_id: sender1,
    type: "stream",
};

// followed topic in muted stream
sample_messages[13] = {
    stream_id: stream6,
    id: (id += 1),
    topic: topic12,
    sender_id: sender1,
    type: "stream",
};

private_messages[0] = {
    id: (id += 1),
    sender_id: sender1,
    to_user_ids: "2,3",
    type: "private",
    display_recipient: [{id: 1}, {id: 2}, {id: 3}],
    pm_with_url: test_url(),
};
private_messages[1] = {
    id: (id += 1),
    sender_id: sender1,
    to_user_ids: "2,4",
    type: "private",
    display_recipient: [{id: 1}, {id: 2}, {id: 4}],
    pm_with_url: test_url(),
};
private_messages[2] = {
    id: (id += 1),
    sender_id: sender1,
    to_user_ids: "3",
    type: "private",
    display_recipient: [{id: 1}, {id: 3}],
    pm_with_url: test_url(),
};

function get_topic_key(stream_id, topic) {
    return stream_id + ":" + topic.toLowerCase();
}

function generate_topic_data(topic_info_array) {
    // Since most of the fields are common, this function helps generate fixtures
    // with non-common fields.
    $.clear_all_elements();
    const data = [];

    for (const [stream_id, topic, unread_count, visibility_policy] of topic_info_array) {
        data.push({
            other_senders_count: 0,
            other_sender_names_html: "",
            invite_only: false,
            is_web_public: true,
            is_private: false,
            is_archived: false,
            last_msg_time: "Just now",
            last_msg_url: "https://www.example.com",
            full_last_msg_date_time: "date at time",
            senders: people.sender_info_for_recent_view_row([1, 2]),
            stream_name: "stream_name",
            stream_color: "",
            stream_id,
            stream_url: "https://www.example.com",
            topic,
            topic_display_name: util.get_final_topic_display_name(topic),
            is_empty_string_topic: topic === "",
            conversation_key: get_topic_key(stream_id, topic),
            topic_url: "https://www.example.com/with/12",
            unread_count,
            mention_in_unread: false,
            visibility_policy,
            all_visibility_policies,
            is_spectator: page_params.is_spectator,
            column_indexes: rt.COLUMNS,
        });
    }
    return data;
}

function verify_topic_data(all_topics, stream, topic, last_msg_id, participated) {
    const topic_data = all_topics.get(stream + ":" + topic);
    assert.equal(topic_data.last_msg_id, last_msg_id);
    assert.equal(topic_data.participated, participated);
}

rt.set_default_focus();

function stub_out_filter_buttons() {
    // TODO: We probably want more direct tests that make sure
    //       the widgets get updated correctly, but the stubs here
    //       should accurately simulate toggling the filters.
    //
    //       See show_selected_filters() and set_filter() in the
    //       implementation.
    for (const filter of ["unread", "muted", "participated", "include_private"]) {
        const $stub = $.create(`filter-${filter}-stub`);
        const selector = `[data-filter="${filter}"]`;
        $("#recent_view_filter_buttons").set_find_results(selector, $stub);
    }
}

function test(label, f) {
    run_test(label, (helpers) => {
        page_params.development_environment = true;
        page_params.is_node_test = true;
        messages = sample_messages.map((message) => ({...message}));
        f(helpers);
    });
}

test("test_recent_view_show", ({override, mock_template}) => {
    // Note: unread count and urls are fake,
    // since they are generated in external libraries
    // and are not to be tested here.
    page_params.is_spectator = false;
    const expected = {
        filter_unread: false,
        filter_participated: false,
        filter_muted: false,
        filter_pm: false,
        search_val: "",
        is_spectator: false,
    };

    activity_ui.set_cursor_and_filter();

    mock_template("recent_view_table.hbs", false, (data) => {
        assert.deepEqual(data, expected);
        return "<recent_view table stub>";
    });

    mock_template("recent_view_row.hbs", false, noop);

    let buddy_list_populated = false;
    override(buddy_list, "populate", () => {
        buddy_list_populated = true;
    });

    stub_out_filter_buttons();
    // We don't test the css calls; we just skip over them.
    $("#mark_read_on_scroll_state_banner").toggleClass = noop;

    rt.clear_for_tests();
    rt.set_filters_for_tests();
    rt.process_messages(messages);

    rt.show();

    assert.ok(buddy_list_populated);

    // incorrect topic_key
    assert.equal(rt.inplace_rerender("stream_unknown:topic_unknown"), false);
});

test("test_filter_is_spectator", ({mock_template}) => {
    page_params.is_spectator = true;
    const expected = {
        filter_unread: false,
        filter_participated: false,
        filter_muted: false,
        filter_pm: false,
        search_val: "",
        is_spectator: true,
    };
    let row_data;
    let i;

    mock_template("recent_view_table.hbs", false, (data) => {
        assert.deepEqual(data, expected);
    });

    mock_template("recent_view_row.hbs", false, (data) => {
        i -= 1;
        assert.deepEqual(data, row_data[i]);
        return "<recent_view row stub>";
    });

    row_data = generate_topic_data([[1, "topic-1", 0, all_visibility_policies.INHERIT]]);
    i = row_data.length;
    rt.clear_for_tests();
    rt.set_filters_for_tests();
    stub_out_filter_buttons();
    recent_view_util.set_visible(true);
    rt.process_messages([messages[0]]);
});

test("test_no_filter", ({mock_template}) => {
    // Just tests inplace rerender of a message
    // in All topics filter.
    page_params.is_spectator = false;
    const expected = {
        filter_unread: false,
        filter_participated: false,
        filter_muted: false,
        filter_pm: false,
        search_val: "",
        is_spectator: false,
    };
    let row_data;
    let i;

    mock_template("recent_view_table.hbs", false, (data) => {
        assert.deepEqual(data, expected);
    });

    mock_template("recent_view_row.hbs", false, (data) => {
        i -= 1;
        assert.deepEqual(data, row_data[i]);
        return "<recent_view row stub>";
    });

    // topic is not muted
    row_data = generate_topic_data([[1, "topic-1", 0, all_visibility_policies.INHERIT]]);
    i = row_data.length;
    rt.clear_for_tests();
    rt.set_filters_for_tests();
    stub_out_filter_buttons();
    recent_view_util.set_visible(true);
    rt.process_messages([messages[0]]);
    assert.equal(
        rt.filters_should_hide_row({last_msg_id: 1, participated: true, type: "stream"}),
        false,
    );

    // TODO: Modify this test to work with dropdown widget.
    // expected_data_to_replace_in_list_widget = [
    //     {last_msg_id: 10, participated: true, type: "stream"},
    //     {last_msg_id: 1, participated: true, type: "stream"},
    // ];

    // // topic is muted
    // row_data = [
    //     ...row_data,
    //     ...generate_topic_data([[1, "topic-7", 1, all_visibility_policies.MUTED]]),
    // ];
    // i = row_data.length;
    // stub_out_filter_buttons();
    // rt.process_messages([messages[9]]);
    // assert.equal(
    //     rt.filters_should_hide_row({last_msg_id: 10, participated: true, type: "stream"}),
    //     true,
    // );

    // expected_data_to_replace_in_list_widget = [
    //     {last_msg_id: 12, participated: true, type: "stream"},
    //     {last_msg_id: 10, participated: true, type: "stream"},
    //     {last_msg_id: 1, participated: true, type: "stream"},
    // ];
    // // normal topic in muted stream
    // row_data = [
    //     ...row_data,
    //     ...generate_topic_data([[6, "topic-8", 1, all_visibility_policies.INHERIT]]),
    // ];
    // i = row_data.length;
    // stub_out_filter_buttons();
    // rt.process_messages([messages[11]]);
    // assert.equal(
    //     rt.filters_should_hide_row({last_msg_id: 12, participated: true, type: "stream"}),
    //     true,
    // );

    // expected_data_to_replace_in_list_widget = [
    //     {last_msg_id: 13, participated: true, type: "stream"},
    //     {last_msg_id: 12, participated: true, type: "stream"},
    //     {last_msg_id: 10, participated: true, type: "stream"},
    //     {last_msg_id: 1, participated: true, type: "stream"},
    // ];
    // // unmuted topic in muted stream
    // row_data = [
    //     ...row_data,
    //     ...generate_topic_data([[6, "topic-11", 1, all_visibility_policies.UNMUTED]]),
    // ];
    // i = row_data.length;
    // stub_out_filter_buttons();
    // rt.process_messages([messages[12]]);
    // assert.equal(
    //     rt.filters_should_hide_row({last_msg_id: 13, participated: true, type: "stream"}),
    //     false,
    // );

    // expected_data_to_replace_in_list_widget = [
    //     {last_msg_id: 14, participated: true, type: "stream"},
    //     {last_msg_id: 13, participated: true, type: "stream"},
    //     {last_msg_id: 12, participated: true, type: "stream"},
    //     {last_msg_id: 10, participated: true, type: "stream"},
    //     {last_msg_id: 1, participated: true, type: "stream"},
    // ];
    // // followed topic in muted stream
    // row_data = [
    //     ...row_data,
    //     ...generate_topic_data([[6, "topic-12", 1, all_visibility_policies.FOLLOWED]]),
    // ];
    // i = row_data.length;
    // stub_out_filter_buttons();
    // rt.process_messages([messages[13]]);
    // assert.equal(
    //     rt.filters_should_hide_row({last_msg_id: 14, participated: true, type: "stream"}),
    //     false,
    // );

    // Test search
    expected.search_val = "topic-1";
    row_data = generate_topic_data([[1, "topic-1", 0, all_visibility_policies.INHERIT]]);
    i = row_data.length;
    rt.set_default_focus();
    $(".home-page-input").trigger("focus");
    assert.equal(
        rt.filters_should_hide_row({last_msg_id: 1, participated: true, type: "stream"}),
        false,
    );
});

test("test_filter_pm", ({mock_template}) => {
    page_params.is_spectator = false;
    const expected = {
        filter_unread: false,
        filter_participated: false,
        filter_muted: false,
        filter_pm: true,
        search_val: "",
        is_spectator: false,
    };

    const expected_user_with_icon = [
        {name: "translated: Muted user", status_emoji_info: undefined},
        {name: "Spike Spiegel", status_emoji_info: undefined},
    ];
    let i = 0;

    mock_template("recent_view_table.hbs", false, (data) => {
        assert.deepEqual(data, expected);
    });

    mock_template("user_with_status_icon.hbs", false, (data) => {
        assert.deepEqual(data, expected_user_with_icon[i]);
        i += 1;
        return "<user_with_status_icon stub>";
    });

    mock_template("recent_view_row.hbs", true, (_data, html) => {
        assert.ok(html.startsWith('<tr id="recent_conversation'));
    });

    rt.clear_for_tests();
    rt.set_filters_for_tests();
    stub_out_filter_buttons();
    recent_view_util.set_visible(true);
    rt.set_filter("include_private");

    expected_data_to_replace_in_list_widget = [
        {last_msg_id: 15, participated: true, type: "private"},
    ];

    rt.process_messages([private_messages[0]]);

    assert.deepEqual(rt.filters_should_hide_row({type: "private", last_msg_id: 15}), false);
    assert.deepEqual(rt.filters_should_hide_row({type: "private", last_msg_id: 16}), true);
    assert.deepEqual(rt.filters_should_hide_row({type: "private", last_msg_id: 17}), false);
});

test("test_filter_participated", ({mock_template}) => {
    let expected_filter_participated;

    page_params.is_spectator = false;
    mock_template("recent_view_table.hbs", false, (data) => {
        assert.deepEqual(data, {
            filter_unread: false,
            filter_participated: expected_filter_participated,
            filter_muted: false,
            filter_pm: false,
            search_val: "",
            is_spectator: false,
        });
    });

    mock_template("recent_view_filters.hbs", false, (data) => {
        assert.equal(data.filter_participated, expected_filter_participated);
        return "<recent_view table stub>";
    });

    const row_data = generate_topic_data([
        // stream_id, topic, unread_count, visibility_policy
        [6, "topic-12", 1, all_visibility_policies.FOLLOWED],
        [6, "topic-11", 1, all_visibility_policies.UNMUTED],
        [6, "topic-8", 1, all_visibility_policies.INHERIT],
        [4, "topic-10", 1, all_visibility_policies.INHERIT],
        [1, "topic-7", 1, all_visibility_policies.MUTED],
        [1, "topic-6", 1, all_visibility_policies.INHERIT],
        [1, "topic-5", 1, all_visibility_policies.INHERIT],
        [1, "topic-4", 1, all_visibility_policies.INHERIT],
        [1, "topic-3", 1, all_visibility_policies.INHERIT],
        [1, "topic-2", 1, all_visibility_policies.INHERIT],
        [1, "topic-1", 0, all_visibility_policies.INHERIT],
    ]);
    let i = 0;

    mock_template("recent_view_row.hbs", false, (data) => {
        // All the row will be processed.
        if (row_data[i]) {
            assert.deepEqual(data, row_data[i]);
            i += 1;
        }
        return "<recent_view row stub>";
    });

    rt.clear_for_tests();
    rt.set_filters_for_tests();
    recent_view_util.set_visible(true);
    rt.set_default_focus();
    stub_out_filter_buttons();
    expected_filter_participated = false;
    rt.process_messages(messages);

    $(".home-page-input").trigger("focus");
    assert.equal(
        rt.filters_should_hide_row({last_msg_id: 4, participated: true, type: "stream"}),
        false,
    );

    // Set muted filter
    rt.set_filter("muted");
    assert.equal(
        rt.filters_should_hide_row({last_msg_id: 7, participated: true, type: "stream"}),
        false,
    );

    // remove muted filter
    rt.set_filter("muted");

    $("#recent_view_filter_buttons").removeClass("button-recent-selected");

    expected_filter_participated = true;

    rt.set_filter("participated");
    rt.update_filters_view();

    assert.equal(i, row_data.length);

    expected_data_to_replace_in_list_widget = [
        {
            last_msg_id: 11,
            participated: true,
            type: "stream",
        },
        {
            last_msg_id: 10,
            participated: true,
            type: "stream",
        },
        {
            last_msg_id: 9,
            participated: true,
            type: "stream",
        },
        {
            last_msg_id: 7,
            participated: true,
            type: "stream",
        },
        {
            last_msg_id: 5,
            participated: false,
            type: "stream",
        },
        {
            last_msg_id: 4,
            participated: false,
            type: "stream",
        },
        {
            last_msg_id: 3,
            participated: true,
            type: "stream",
        },
        {
            last_msg_id: 1,
            participated: true,
            type: "stream",
        },
    ];

    rt.process_messages([messages[4]]);
});

test("test_update_unread_count", () => {
    recent_view_util.set_visible(false);
    rt.clear_for_tests();
    stub_out_filter_buttons();
    rt.process_messages(messages);

    // update a message
    generate_topic_data([[1, "topic-7", 1, all_visibility_policies.INHERIT]]);
    rt.update_topic_unread_count(messages[9]);
});

test("basic assertions", ({mock_template, override_rewire}) => {
    override_rewire(rt, "inplace_rerender", noop);
    rt.clear_for_tests();
    rt.set_filters_for_tests();

    mock_template("recent_view_table.hbs", false, noop);
    mock_template("recent_view_row.hbs", true, (_data, html) => {
        assert.ok(html.startsWith('<tr id="recent_conversation'));
    });

    stub_out_filter_buttons();
    recent_view_util.set_visible(true);
    rt.set_default_focus();
    rt.process_messages(messages);
    let all_topics = rt_data.get_conversations();

    // update a message
    generate_topic_data([[1, "topic-7", 1, all_visibility_policies.INHERIT]]);
    stub_out_filter_buttons();
    expected_data_to_replace_in_list_widget = [
        {
            last_msg_id: 11,
            participated: true,
            type: "stream",
        },
        {
            last_msg_id: 10,
            participated: true,
            type: "stream",
        },
        {
            last_msg_id: 9,
            participated: true,
            type: "stream",
        },
        {
            last_msg_id: 7,
            participated: true,
            type: "stream",
        },
        {
            last_msg_id: 5,
            participated: false,
            type: "stream",
        },
        {
            last_msg_id: 4,
            participated: false,
            type: "stream",
        },
        {
            last_msg_id: 3,
            participated: true,
            type: "stream",
        },
        {
            last_msg_id: 1,
            participated: true,
            type: "stream",
        },
    ];

    rt.process_messages([messages[9]]);
    // Check for expected lengths.
    // total 8 topics, 1 muted
    assert.equal(all_topics.size, 11);
    assert.equal(
        [...all_topics.keys()].toString(),
        "6:topic-12,6:topic-11,6:topic-8,4:topic-10,1:topic-7,1:topic-6,1:topic-5,1:topic-4,1:topic-3,1:topic-2,1:topic-1",
    );

    // Process direct message
    rt_data.process_message({
        type: "private",
        to_user_ids: "6,7,8",
    });
    all_topics = rt_data.get_conversations();
    assert.equal(all_topics.size, 12);
    assert.equal(
        [...all_topics.keys()].toString(),
        "6:topic-12,6:topic-11,6:topic-8,4:topic-10,1:topic-7,1:topic-6,1:topic-5,1:topic-4,1:topic-3,1:topic-2,1:topic-1,6,7,8",
    );

    // participated
    verify_topic_data(all_topics, stream1, topic1, messages[0].id, true);

    // No message was sent by us.
    verify_topic_data(all_topics, stream1, topic3, messages[3].id, false);

    // Not participated
    verify_topic_data(all_topics, stream1, topic4, messages[4].id, false);

    // topic3 now participated
    rt_data.process_message({
        stream_id: stream1,
        id: (id += 1),
        topic: topic3,
        sender_id: sender1,
        type: "stream",
    });

    all_topics = rt_data.get_conversations();
    assert.equal(
        [...all_topics.keys()].toString(),
        "1:topic-3,6:topic-12,6:topic-11,6:topic-8,4:topic-10,1:topic-7,1:topic-6,1:topic-5,1:topic-4,1:topic-2,1:topic-1,6,7,8",
    );
    verify_topic_data(all_topics, stream1, topic3, id, true);

    // Send new message to topic7 (muted)
    // The topic will be hidden when displayed
    rt_data.process_message({
        stream_id: stream1,
        id: (id += 1),
        topic: topic7,
        sender_id: sender1,
        type: "stream",
    });

    all_topics = rt_data.get_conversations();
    assert.equal(
        [...all_topics.keys()].toString(),
        "1:topic-7,1:topic-3,6:topic-12,6:topic-11,6:topic-8,4:topic-10,1:topic-6,1:topic-5,1:topic-4,1:topic-2,1:topic-1,6,7,8",
    );

    // update_topic_visibility_policy now relies on external libraries completely
    // so we don't need to check anythere here.
    generate_topic_data([[1, topic1, 0, all_visibility_policies.INHERIT]]);
    $(".home-page-input").trigger("focus");
    assert.equal(rt.update_topic_visibility_policy(stream1, topic1), true);
    // a topic gets muted which we are not tracking
    assert.equal(rt.update_topic_visibility_policy(stream1, "topic-10"), false);
});

test("test_reify_local_echo_message", ({mock_template}) => {
    mock_template("recent_view_table.hbs", false, noop);
    mock_template("recent_view_row.hbs", false, noop);

    rt.clear_for_tests();
    rt.set_filters_for_tests();
    stub_out_filter_buttons();
    recent_view_util.set_visible(true);
    rt.process_messages(messages);

    rt_data.process_message({
        stream_id: stream1,
        id: 1000.01,
        topic: topic7,
        sender_id: sender1,
        type: "stream",
    });

    assert.equal(
        rt_data.reify_message_id_if_available({
            old_id: 1000.01,
            new_id: 1001,
        }),
        true,
    );

    rt_data.process_message({
        stream_id: stream1,
        id: 1001.01,
        topic: topic7,
        sender_id: sender1,
        type: "stream",
    });

    // A new message arrived in the same topic before we could reify the message_id
    rt_data.process_message({
        stream_id: stream1,
        id: 1003,
        topic: topic7,
        sender_id: sender1,
        type: "stream",
    });

    assert.equal(
        rt_data.reify_message_id_if_available({
            old_id: 1000.01,
            new_id: 1001,
        }),
        false,
    );
});

test("test_delete_messages", ({override}) => {
    recent_view_util.set_visible(false);
    rt.clear_for_tests();
    stub_out_filter_buttons();
    rt.process_messages(messages);

    // messages[0] was removed.
    let reduced_msgs = messages.slice(1);
    override(all_messages_data, "all_messages", () => reduced_msgs);

    let all_topics = rt_data.get_conversations();
    assert.equal(
        [...all_topics.keys()].toString(),
        "6:topic-12,6:topic-11,6:topic-8,4:topic-10,1:topic-7,1:topic-6,1:topic-5,1:topic-4,1:topic-3,1:topic-2,1:topic-1",
    );
    rt.update_topics_of_deleted_message_ids([messages[0].id]);

    all_topics = rt_data.get_conversations();
    assert.equal(
        [...all_topics.keys()].toString(),
        "6:topic-12,6:topic-11,6:topic-8,4:topic-10,1:topic-7,1:topic-6,1:topic-5,1:topic-4,1:topic-3,1:topic-2",
    );

    // messages[0], messages[1] and message[2] were removed.
    reduced_msgs = messages.slice(3);

    rt.update_topics_of_deleted_message_ids([messages[1].id, messages[2].id]);

    all_topics = rt_data.get_conversations();
    assert.equal(
        [...all_topics.keys()].toString(),
        "6:topic-12,6:topic-11,6:topic-8,4:topic-10,1:topic-7,1:topic-6,1:topic-5,1:topic-4,1:topic-3",
    );
    // test deleting a message which is not locally
    // stored, doesn't raise any errors.
    rt.update_topics_of_deleted_message_ids([-1]);
});

test("test_topic_edit", ({override}) => {
    override(all_messages_data, "all_messages", () => messages);
    recent_view_util.set_visible(false);

    // NOTE: This test should always run in the end as it modified the messages data.
    rt.clear_for_tests();
    stub_out_filter_buttons();
    rt.process_messages(messages);

    let all_topics = rt_data.get_conversations();
    assert.equal(
        [...all_topics.keys()].toString(),
        "6:topic-12,6:topic-11,6:topic-8,4:topic-10,1:topic-7,1:topic-6,1:topic-5,1:topic-4,1:topic-3,1:topic-2,1:topic-1",
    );

    // ---------------- test change topic ----------------
    verify_topic_data(all_topics, stream1, topic6, messages[8].id, true);
    assert.equal(all_topics.get(get_topic_key(stream1, topic8)), undefined);

    // change topic of topic6 to topic8
    messages[7].topic = topic8;
    messages[8].topic = topic8;
    rt.process_topic_edit(stream1, topic6, topic8);
    all_topics = rt_data.get_conversations();

    verify_topic_data(all_topics, stream1, topic8, messages[8].id, true);
    assert.equal(all_topics.get(get_topic_key(stream1, topic6)), undefined);

    // ---------------- test stream change ----------------
    verify_topic_data(all_topics, stream1, topic1, messages[0].id, true);
    assert.equal(all_topics.get(get_topic_key(stream2, topic1)), undefined);

    messages[0].stream_id = stream2;
    rt.process_topic_edit(stream1, topic1, topic1, stream2);
    all_topics = rt_data.get_conversations();

    assert.equal(all_topics.get(get_topic_key(stream1, topic1)), undefined);
    verify_topic_data(all_topics, stream2, topic1, messages[0].id, true);

    // ---------------- test stream & topic change ----------------
    verify_topic_data(all_topics, stream2, topic1, messages[0].id, true);
    assert.equal(all_topics.get(get_topic_key(stream3, topic9)), undefined);

    messages[0].stream_id = stream3;
    messages[0].topic = topic9;
    rt.process_topic_edit(stream2, topic1, topic9, stream3);
    all_topics = rt_data.get_conversations();

    assert.equal(all_topics.get(get_topic_key(stream2, topic1)), undefined);
    verify_topic_data(all_topics, stream3, topic9, messages[0].id, true);

    // Message was moved to a deleted stream, hence hidden regardless of filter.
    messages[0].stream_id = stream5;
    messages[0].topic = topic8;
    rt.process_topic_edit(stream3, topic9, topic8, stream5);
    all_topics = rt_data.get_conversations();
    assert.equal(rt.filters_should_hide_row(all_topics.get("5:topic-8")), true);
});

test("test_search", () => {
    rt.clear_for_tests();
    assert.equal(rt.topic_in_search_results("t", "general", "Recent topic"), true);
    assert.equal(rt.topic_in_search_results("T", "general", "Recent topic"), true);
    assert.equal(rt.topic_in_search_results("to", "general", "Recent topic"), true);
    assert.equal(rt.topic_in_search_results("top", "general", "Recent topic"), true);
    assert.equal(rt.topic_in_search_results("ToP", "general", "Recent topic"), true);
    assert.equal(rt.topic_in_search_results("Topi", "general", "Recent topic"), true);
    assert.equal(rt.topic_in_search_results("tOpi", "general", "Recent topic"), true);
    assert.equal(rt.topic_in_search_results("toPic", "general", "Recent topic"), true);
    assert.equal(rt.topic_in_search_results("Topic", "general", "Recent topic"), true);
    assert.equal(rt.topic_in_search_results("topic", "general", "Recent topic"), true);
    assert.equal(rt.topic_in_search_results("recent", "general", "Recent topic"), true);
    assert.equal(rt.topic_in_search_results("RECENT", "general", "Recent topic"), true);

    // Match (by prefix) in any order of words.
    assert.equal(rt.topic_in_search_results("topic recent", "general", "Recent topic"), true);
    assert.equal(rt.topic_in_search_results("o", "general", "Recent topic"), false);
    assert.equal(rt.topic_in_search_results("to recen", "general", "Recent topic"), true);
    assert.equal(rt.topic_in_search_results("ner opic", "general", "Recent topic"), false);
    assert.equal(rt.topic_in_search_results("pr pro", "general", "pro PRs"), true);
    assert.equal(rt.topic_in_search_results("pr pro pr pro", "general", "pro PRs"), false);
    assert.equal(rt.topic_in_search_results("co cows", "general", "one cow 2 cows"), true);
    assert.equal(rt.topic_in_search_results("cows cows", "general", "one cow 2 cows"), false);

    assert.equal(rt.topic_in_search_results("?", "general", "Recent topic"), false);

    // Test special character match
    assert.equal(rt.topic_in_search_results(".*+?^${}()[]\\", "general", "Recent topic"), false);
    assert.equal(rt.topic_in_search_results("?", "general", "?at-start"), true);

    assert.equal(rt.topic_in_search_results("?", "general", "?"), true);
    assert.equal(rt.topic_in_search_results("?", "general", "\\?"), false);

    assert.equal(rt.topic_in_search_results("\\", "general", "\\"), true);
    assert.equal(rt.topic_in_search_results("\\", "general", "\\\\"), true);

    // Test for empty string topic name.
    assert.equal(rt.topic_in_search_results("general chat", "Scotland", ""), true);
});
