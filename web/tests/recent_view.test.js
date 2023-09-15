"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");
const {page_params} = require("./lib/zpage_params");

const noop = () => {};
const test_url = () => "https://www.example.com";

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
        // are tested in list_widget.test.js
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
    update_buttons_for_recent_view: noop,
});
mock_esm("../src/hash_util", {
    by_stream_url: test_url,
    by_stream_topic_url: test_url,
    by_conversation_and_time_url: test_url,
});
mock_esm("../src/message_list_data", {
    MessageListData: class {},
});
mock_esm("../src/message_store", {
    get(msg_id) {
        if (msg_id < 12) {
            return messages[msg_id - 1];
        }
        return private_messages[msg_id - 12];
    },
});
mock_esm("../src/message_view_header", {
    render_title_area: noop,
});
mock_esm("../src/user_topics", {
    is_topic_muted(stream_id, topic) {
        if (stream_id === stream1 && topic === topic7) {
            return true;
        }
        return false;
    },
    is_topic_unmuted: () => false,
    get_topic_visibility_policy(stream_id, topic) {
        if (stream_id === 1 && topic === "topic-7") {
            return all_visibility_policies.MUTED;
        }
        return all_visibility_policies.INHERIT;
    },
    all_visibility_policies,
});
const narrow = mock_esm("../src/narrow", {
    update_narrow_title: noop,
    hide_unread_banner: noop,
    handle_middle_pane_transition: noop,
    has_shown_message_list_view: true,
});
mock_esm("../src/pm_list", {
    update_private_messages: noop,
    handle_narrow_deactivated: noop,
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
    is_muted: () =>
        // We only test via muted topics for now.
        // TODO: Make muted streams and test them.
        false,
    get_stream_name_from_id: () => "stream_name",
});
mock_esm("../src/stream_list", {
    handle_narrow_deactivated: noop,
});
mock_esm("../src/timerender", {
    relative_time_string_from_date: () => "Just now",
    get_full_datetime_clarification: () => "date at time",
});
mock_esm("../src/sub_store", {
    get(stream) {
        if (stream === stream5) {
            // No data is available for deactivated streams
            return undefined;
        }

        return {
            color: "",
            invite_only: false,
            is_web_public: true,
            subscribed: true,
        };
    },
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
});
mock_esm("../src/resize", {
    update_recent_view_filters_height: noop,
});

const {all_messages_data} = zrequire("all_messages_data");
const people = zrequire("people");
const rt = zrequire("recent_view_ui");
const recent_view_util = zrequire("recent_view_util");
const rt_data = zrequire("recent_view_data");
const muted_users = zrequire("muted_users");

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

    for (const [stream_id, topic, unread_count, muted] of topic_info_array) {
        data.push({
            other_senders_count: 0,
            other_sender_names_html: "",
            invite_only: false,
            is_web_public: true,
            is_private: false,
            last_msg_time: "Just now",
            last_msg_url: "https://www.example.com",
            full_last_msg_date_time: "date at time",
            senders: people.sender_info_for_recent_view_row([1, 2]),
            stream_name: "stream_name",
            stream_color: "",
            stream_id,
            stream_muted: undefined,
            stream_url: "https://www.example.com",
            topic,
            conversation_key: get_topic_key(stream_id, topic),
            topic_url: "https://www.example.com",
            unread_count,
            mention_in_unread: false,
            topic_muted: muted,
            topic_unmuted: false,
            visibility_policy: muted
                ? all_visibility_policies.MUTED
                : all_visibility_policies.INHERIT,
            development: true,
            all_visibility_policies,
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
    for (const filter of ["all", "unread", "muted", "participated", "include_private"]) {
        const $stub = $.create(`filter-${filter}-stub`);
        const selector = `[data-filter="${filter}"]`;
        $("#recent_view_filter_buttons").set_find_results(selector, $stub);
    }
}

function test(label, f) {
    run_test(label, (helpers) => {
        $(".header").css = () => {};
        page_params.development_environment = true;

        messages = sample_messages.map((message) => ({...message}));
        f(helpers);
    });
}

test("test_recent_view_show", ({mock_template, override}) => {
    override(narrow, "save_pre_narrow_offset_for_reload", () => {});

    // Note: unread count and urls are fake,
    // since they are generated in external libraries
    // and are not to be tested here.
    page_params.is_spectator = false;
    const expected = {
        filter_participated: false,
        filter_unread: false,
        filter_muted: false,
        filter_pm: false,
        search_val: "",
        is_spectator: false,
    };

    mock_template("recent_view_table.hbs", false, (data) => {
        assert.deepEqual(data, expected);
        return "<recent_view table stub>";
    });

    mock_template("recent_view_row.hbs", false, () => {});

    stub_out_filter_buttons();
    // We don't test the css calls; we just skip over them.
    $("#mark_read_on_scroll_state_banner").toggleClass = () => {};

    rt.clear_for_tests();
    rt.process_messages(messages);

    rt.show();

    // incorrect topic_key
    assert.equal(rt.inplace_rerender("stream_unknown:topic_unknown"), false);
});

test("test_filter_all", ({mock_template}) => {
    // Just tests inplace rerender of a message
    // in All topics filter.
    page_params.is_spectator = true;
    const expected = {
        filter_participated: false,
        filter_unread: false,
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

    // topic is not muted
    row_data = generate_topic_data([[1, "topic-1", 0, false]]);
    i = row_data.length;
    rt.clear_for_tests();
    stub_out_filter_buttons();
    recent_view_util.set_visible(true);
    rt.set_filter("all");
    rt.process_messages([messages[0]]);

    expected_data_to_replace_in_list_widget = [
        {last_msg_id: 10, participated: true, type: "stream"},
        {last_msg_id: 1, participated: true, type: "stream"},
    ];

    row_data = [...row_data, ...generate_topic_data([[1, "topic-7", 1, true]])];
    i = row_data.length;
    // topic is muted (=== hidden)
    stub_out_filter_buttons();
    rt.process_messages([messages[9]]);

    // Test search
    expected.search_val = "topic-1";
    row_data = generate_topic_data([[1, "topic-1", 0, false]]);
    i = row_data.length;
    rt.set_default_focus();
    $(".home-page-input").trigger("focus");
    assert.equal(
        rt.filters_should_hide_topic({last_msg_id: 1, participated: true, type: "stream"}),
        false,
    );
});

test("test_filter_pm", ({mock_template}) => {
    page_params.is_spectator = false;
    const expected = {
        filter_participated: false,
        filter_unread: false,
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
    });

    mock_template("recent_view_row.hbs", true, (_data, html) => {
        assert.ok(html.startsWith('<tr id="recent_conversation'));
    });

    rt.clear_for_tests();
    stub_out_filter_buttons();
    recent_view_util.set_visible(true);
    rt.set_filter("include_private");

    expected_data_to_replace_in_list_widget = [
        {last_msg_id: 12, participated: true, type: "private"},
    ];

    rt.process_messages([private_messages[0]]);

    assert.deepEqual(rt.filters_should_hide_topic({type: "private", last_msg_id: 12}), false);
    assert.deepEqual(rt.filters_should_hide_topic({type: "private", last_msg_id: 13}), true);
    assert.deepEqual(rt.filters_should_hide_topic({type: "private", last_msg_id: 14}), false);
});

test("test_filter_unread", ({mock_template}) => {
    let expected_filter_unread = false;
    page_params.is_spectator = false;

    mock_template("recent_view_table.hbs", false, (data) => {
        assert.deepEqual(data, {
            filter_participated: false,
            filter_unread: expected_filter_unread,
            filter_muted: false,
            filter_pm: false,
            search_val: "",
            is_spectator: false,
        });
    });

    mock_template("recent_view_filters.hbs", false, (data) => {
        assert.equal(data.filter_unread, expected_filter_unread);
        assert.equal(data.filter_participated, false);
        return "<recent_view table stub>";
    });

    let i = 0;

    const row_data = generate_topic_data([
        // stream_id, topic, unread_count,  muted
        [4, "topic-10", 1, false],
        [1, "topic-7", 1, true],
        [1, "topic-6", 1, false],
        [1, "topic-5", 1, false],
        [1, "topic-4", 1, false],
        [1, "topic-3", 1, false],
        [1, "topic-2", 1, false],
        [1, "topic-1", 0, false],
    ]);

    mock_template("recent_view_row.hbs", false, (data) => {
        // All the row will be processed.
        if (row_data[i]) {
            assert.deepEqual(data, row_data[i]);
            i += 1;
        }
        return "<recent_view row stub>";
    });

    rt.clear_for_tests();
    recent_view_util.set_visible(true);
    rt.set_default_focus();

    stub_out_filter_buttons();
    rt.process_messages(messages);
    $(".home-page-input").trigger("focus");
    assert.equal(
        rt.filters_should_hide_topic({last_msg_id: 1, participated: true, type: "stream"}),
        false,
    );

    $("#recent_view_filter_buttons").removeClass("btn-recent-selected");

    expected_filter_unread = true;
    rt.set_filter("unread");
    rt.update_filters_view();

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

    rt.process_messages([messages[0]]);

    // Unselect "unread" filter by clicking twice.
    expected_filter_unread = false;
    $("#recent_view_filter_buttons").addClass("btn-recent-selected");
    rt.set_filter("unread");

    assert.equal(i, row_data.length);

    $("#recent_view_filter_buttons").removeClass("btn-recent-selected");
    // reselect "unread" filter
    rt.set_filter("unread");

    // Now clicking "all" filter should have no change to expected data.
    rt.set_filter("all");
});

test("test_filter_participated", ({mock_template}) => {
    let expected_filter_participated;

    page_params.is_spectator = false;
    mock_template("recent_view_table.hbs", false, (data) => {
        assert.deepEqual(data, {
            filter_participated: expected_filter_participated,
            filter_unread: false,
            filter_muted: false,
            filter_pm: false,
            search_val: "",
            is_spectator: false,
        });
    });

    mock_template("recent_view_filters.hbs", false, (data) => {
        assert.equal(data.filter_unread, false);
        assert.equal(data.filter_participated, expected_filter_participated);
        return "<recent_view table stub>";
    });

    const row_data = generate_topic_data([
        // stream_id, topic, unread_count,  muted
        [4, "topic-10", 1, false],
        [1, "topic-7", 1, true],
        [1, "topic-6", 1, false],
        [1, "topic-5", 1, false],
        [1, "topic-4", 1, false],
        [1, "topic-3", 1, false],
        [1, "topic-2", 1, false],
        [1, "topic-1", 0, false],
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
    recent_view_util.set_visible(true);
    rt.set_default_focus();
    stub_out_filter_buttons();
    expected_filter_participated = false;
    rt.process_messages(messages);

    $(".home-page-input").trigger("focus");
    assert.equal(
        rt.filters_should_hide_topic({last_msg_id: 4, participated: true, type: "stream"}),
        false,
    );

    // Set muted filter
    rt.set_filter("muted");
    assert.equal(
        rt.filters_should_hide_topic({last_msg_id: 7, participated: true, type: "stream"}),
        false,
    );

    // remove muted filter
    rt.set_filter("muted");

    $("#recent_view_filter_buttons").removeClass("btn-recent-selected");

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

    expected_filter_participated = false;
    rt.set_filter("all");
});

test("test_update_unread_count", () => {
    recent_view_util.set_visible(false);
    rt.clear_for_tests();
    stub_out_filter_buttons();
    rt.set_filter("all");
    rt.process_messages(messages);

    // update a message
    generate_topic_data([[1, "topic-7", 1, false]]);
    rt.update_topic_unread_count(messages[9]);
});

test("basic assertions", ({mock_template, override_rewire}) => {
    override_rewire(rt, "inplace_rerender", noop);
    rt.clear_for_tests();

    mock_template("recent_view_table.hbs", false, () => {});
    mock_template("recent_view_row.hbs", true, (_data, html) => {
        assert.ok(html.startsWith('<tr id="recent_conversation'));
    });

    stub_out_filter_buttons();
    recent_view_util.set_visible(true);
    rt.set_default_focus();
    rt.set_filter("all");
    rt.process_messages(messages);
    let all_topics = rt_data.get();

    // update a message
    generate_topic_data([[1, "topic-7", 1, false]]);
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
    assert.equal(all_topics.size, 8);
    assert.equal(
        [...all_topics.keys()].toString(),
        "4:topic-10,1:topic-7,1:topic-6,1:topic-5,1:topic-4,1:topic-3,1:topic-2,1:topic-1",
    );

    // Process direct message
    rt_data.process_message({
        type: "private",
        to_user_ids: "6,7,8",
    });
    all_topics = rt_data.get();
    assert.equal(all_topics.size, 9);
    assert.equal(
        [...all_topics.keys()].toString(),
        "4:topic-10,1:topic-7,1:topic-6,1:topic-5,1:topic-4,1:topic-3,1:topic-2,1:topic-1,6,7,8",
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

    all_topics = rt_data.get();
    assert.equal(
        [...all_topics.keys()].toString(),
        "1:topic-3,4:topic-10,1:topic-7,1:topic-6,1:topic-5,1:topic-4,1:topic-2,1:topic-1,6,7,8",
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

    all_topics = rt_data.get();
    assert.equal(
        [...all_topics.keys()].toString(),
        "1:topic-7,1:topic-3,4:topic-10,1:topic-6,1:topic-5,1:topic-4,1:topic-2,1:topic-1,6,7,8",
    );

    // update_topic_visibility_policy now relies on external libraries completely
    // so we don't need to check anythere here.
    generate_topic_data([[1, topic1, 0, false]]);
    $(".home-page-input").trigger("focus");
    assert.equal(rt.update_topic_visibility_policy(stream1, topic1), true);
    // a topic gets muted which we are not tracking
    assert.equal(rt.update_topic_visibility_policy(stream1, "topic-10"), false);
});

test("test_reify_local_echo_message", ({mock_template}) => {
    mock_template("recent_view_table.hbs", false, () => {});
    mock_template("recent_view_row.hbs", false, () => {});

    rt.clear_for_tests();
    stub_out_filter_buttons();
    recent_view_util.set_visible(true);
    rt.set_filter("all");
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
    rt.set_filter("all");
    rt.process_messages(messages);

    // messages[0] was removed.
    let reduced_msgs = messages.slice(1);
    override(all_messages_data, "all_messages", () => reduced_msgs);

    let all_topics = rt_data.get();
    assert.equal(
        [...all_topics.keys()].toString(),
        "4:topic-10,1:topic-7,1:topic-6,1:topic-5,1:topic-4,1:topic-3,1:topic-2,1:topic-1",
    );
    rt.update_topics_of_deleted_message_ids([messages[0].id]);

    all_topics = rt_data.get();
    assert.equal(
        [...all_topics.keys()].toString(),
        "4:topic-10,1:topic-7,1:topic-6,1:topic-5,1:topic-4,1:topic-3,1:topic-2",
    );

    // messages[0], messages[1] and message[2] were removed.
    reduced_msgs = messages.slice(3);

    rt.update_topics_of_deleted_message_ids([messages[1].id, messages[2].id]);

    all_topics = rt_data.get();
    assert.equal(
        [...all_topics.keys()].toString(),
        "4:topic-10,1:topic-7,1:topic-6,1:topic-5,1:topic-4,1:topic-3",
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
    rt.set_filter("all");
    rt.process_messages(messages);

    let all_topics = rt_data.get();
    assert.equal(
        [...all_topics.keys()].toString(),
        "4:topic-10,1:topic-7,1:topic-6,1:topic-5,1:topic-4,1:topic-3,1:topic-2,1:topic-1",
    );

    // ---------------- test change topic ----------------
    verify_topic_data(all_topics, stream1, topic6, messages[8].id, true);
    assert.equal(all_topics.get(get_topic_key(stream1, topic8)), undefined);

    // change topic of topic6 to topic8
    messages[7].topic = topic8;
    messages[8].topic = topic8;
    rt.process_topic_edit(stream1, topic6, topic8);
    all_topics = rt_data.get();

    verify_topic_data(all_topics, stream1, topic8, messages[8].id, true);
    assert.equal(all_topics.get(get_topic_key(stream1, topic6)), undefined);

    // ---------------- test stream change ----------------
    verify_topic_data(all_topics, stream1, topic1, messages[0].id, true);
    assert.equal(all_topics.get(get_topic_key(stream2, topic1)), undefined);

    messages[0].stream_id = stream2;
    rt.process_topic_edit(stream1, topic1, topic1, stream2);
    all_topics = rt_data.get();

    assert.equal(all_topics.get(get_topic_key(stream1, topic1)), undefined);
    verify_topic_data(all_topics, stream2, topic1, messages[0].id, true);

    // ---------------- test stream & topic change ----------------
    verify_topic_data(all_topics, stream2, topic1, messages[0].id, true);
    assert.equal(all_topics.get(get_topic_key(stream3, topic9)), undefined);

    messages[0].stream_id = stream3;
    messages[0].topic = topic9;
    rt.process_topic_edit(stream2, topic1, topic9, stream3);
    all_topics = rt_data.get();

    assert.equal(all_topics.get(get_topic_key(stream2, topic1)), undefined);
    verify_topic_data(all_topics, stream3, topic9, messages[0].id, true);

    // Message was moved to a deleted stream, hence hidden regardless of filter.
    messages[0].stream_id = stream5;
    messages[0].topic = topic8;
    rt.process_topic_edit(stream3, topic9, topic8, stream5);
    all_topics = rt_data.get();
    assert.equal(rt.filters_should_hide_topic(all_topics.get("5:topic-8")), true);
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

    // match in any order of words
    assert.equal(rt.topic_in_search_results("topic recent", "general", "Recent topic"), true);

    // Matches any sequence of words.
    assert.equal(rt.topic_in_search_results("o", "general", "Recent topic"), true);
    assert.equal(rt.topic_in_search_results("nt to", "general", "Recent topic"), true);
    assert.equal(rt.topic_in_search_results("z", "general", "Recent topic"), false);

    assert.equal(rt.topic_in_search_results("?", "general", "Recent topic"), false);

    // Test special character match
    assert.equal(rt.topic_in_search_results(".*+?^${}()[]\\", "general", "Recent topic"), false);
    assert.equal(rt.topic_in_search_results("?", "general", "not-at-start?"), true);

    assert.equal(rt.topic_in_search_results("?", "general", "?"), true);
    assert.equal(rt.topic_in_search_results("?", "general", "\\?"), true);

    assert.equal(rt.topic_in_search_results("\\", "general", "\\"), true);
    assert.equal(rt.topic_in_search_results("\\", "general", "\\\\"), true);
});
