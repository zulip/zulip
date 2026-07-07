"use strict";

// Setup
const assert = require("node:assert/strict");

const {make_realm} = require("./lib/example_realm.cjs");
const {make_stream} = require("./lib/example_stream.cjs");
const {make_user} = require("./lib/example_user.cjs");
const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");
const {page_params} = require("./lib/zpage_params.cjs");

// Mocking and stubbing things
set_global("document", "document-stub");
const message_lists = mock_esm("../src/message_lists");
const recent_view_util = mock_esm("../src/recent_view_util");
function MessageListView() {
    return {
        maybe_rerender: noop,
        append: noop,
        prepend: noop,
        is_current_message_list: () => true,
    };
}
mock_esm("../src/message_list_view", {
    MessageListView,
});
mock_esm("../src/settings_data", {
    user_can_access_all_other_users: () => true,
    user_has_permission_for_group_setting: () => true,
});
const message_util = mock_esm("../src/message_util", {
    user_can_send_direct_message: () => true,
});
const compose_state = mock_esm("../src/compose_state");
const message_store = mock_esm("../src/message_store", {
    get_pm_full_names(user_ids) {
        const other_ids = people.sorted_other_user_ids(user_ids);
        return people.get_display_full_names(other_ids).toSorted().join(", ");
    },
});

const stream_data = zrequire("stream_data");
// Code we're actually using/testing
const compose_closed_ui = zrequire("compose_closed_ui");
const people = zrequire("people");
const {Filter} = zrequire("filter");
const {MessageList} = zrequire("message_list");
const {MessageListData} = zrequire("message_list_data");
const {set_current_user, set_realm} = zrequire("state_data");

const current_user = make_user({
    email: "alice@zulip.com",
    user_id: 1,
    full_name: "Alice",
});
set_current_user(current_user);
people.add_active_user(current_user);
people.add_active_user(
    make_user({
        email: "bob@zulip.com",
        user_id: 2,
        full_name: "Bob",
    }),
);
people.add_active_user(
    make_user({
        email: "zoe@zulip.com",
        user_id: 3,
        full_name: "Zoe",
    }),
);
people.initialize_current_user(1);

const REALM_EMPTY_TOPIC_DISPLAY_NAME = "general chat";
set_realm(make_realm({realm_empty_topic_display_name: REALM_EMPTY_TOPIC_DISPLAY_NAME}));

// Helper test function
function test_reply_label(expected_label) {
    assert.equal(
        $("#left_bar_compose_reply_button_big")
            .html()
            .replace(/^(translated: )?Message /, ""),
        expected_label,
    );
}

run_test("reply_label", ({mock_template}) => {
    mock_template(
        "decorated_channel_name.hbs",
        false,
        (data) => `<rendered-channel-stub:${data.stream.name}>`,
    );
    // Mocking up a test message list
    const filter = new Filter([]);
    const list = new MessageList({
        data: new MessageListData({
            excludes_muted_topics: false,
            filter,
        }),
    });
    message_lists.current = list;
    const stream_one = make_stream({
        subscribed: true,
        name: "first_stream",
        stream_id: 1,
    });
    stream_data.add_sub_for_tests(stream_one);
    const stream_two = make_stream({
        subscribed: true,
        name: "second_stream",
        stream_id: 2,
    });
    stream_data.add_sub_for_tests(stream_two);
    list.add_messages(
        [
            {
                id: 0,
                is_stream: true,
                is_private: false,
                stream_id: stream_one.stream_id,
                topic: "first_topic",
                sent_by_me: false,
                sender_id: 2,
            },
            {
                id: 1,
                is_stream: true,
                is_private: false,
                stream_id: stream_one.stream_id,
                topic: "second_topic",
                sent_by_me: false,
                sender_id: 2,
            },
            {
                id: 2,
                is_stream: true,
                is_private: false,
                stream_id: stream_two.stream_id,
                topic: "third_topic",
                sent_by_me: false,
                sender_id: 2,
            },
            {
                id: 3,
                is_stream: true,
                is_private: false,
                stream_id: stream_two.stream_id,
                topic: "second_topic",
                sent_by_me: false,
                sender_id: 2,
            },
            {
                id: 4,
                is_stream: false,
                is_private: true,
                to_user_ids: "2",
                sent_by_me: false,
                sender_id: 2,
            },
            {
                id: 5,
                is_stream: false,
                is_private: true,
                to_user_ids: "2,3",
                sent_by_me: false,
                sender_id: 2,
            },
            {
                id: 6,
                is_stream: true,
                is_private: false,
                stream_id: stream_two.stream_id,
                topic: "",
                sent_by_me: false,
                sender_id: 2,
            },
        ],
        {},
        true,
    );

    const expected_labels = [
        "<rendered-channel-stub:first_stream> &gt; first_topic",
        "<rendered-channel-stub:first_stream> &gt; second_topic",
        "<rendered-channel-stub:second_stream> &gt; third_topic",
        "<rendered-channel-stub:second_stream> &gt; second_topic",
        "Bob",
        "Bob, Zoe",
    ];

    // Initialize the code we're testing.
    compose_closed_ui.initialize();

    // Run the tests!
    let first = true;
    for (const expected_label of expected_labels) {
        if (first) {
            list.select_id(list.first().id);
            first = false;
        } else {
            list.select_id(list.next());
        }
        test_reply_label(expected_label);
    }

    // Separately test for empty string topic as the topic is specially decorated here.
    list.select_id(list.next());
    const label_html = $("#left_bar_compose_reply_button_big").html();
    assert.equal(
        label_html,
        `translated: Message <rendered-channel-stub:second_stream> &gt; <span class="empty-topic-display">translated: ${REALM_EMPTY_TOPIC_DISPLAY_NAME}</span>`,
    );
});

run_test("empty_narrow", () => {
    message_lists.current.visibly_empty = () => true;
    compose_closed_ui.update_reply_button_with_recipient_context();
    const label = $("#left_bar_compose_reply_button_big").text();
    assert.equal(label, "translated: Compose message");
});

run_test("test_non_message_list_input", ({mock_template}) => {
    mock_template(
        "decorated_channel_name.hbs",
        false,
        (data) => `<rendered-channel-stub:${data.stream.name}>`,
    );
    message_lists.current = undefined;
    recent_view_util.is_visible = () => true;
    const stream = make_stream({
        subscribed: true,
        name: "stream test",
        stream_id: 10,
    });
    stream_data.add_sub_for_tests(stream);

    // Channel and topic row.
    compose_closed_ui.update_reply_button_with_recipient_context({
        stream_id: stream.stream_id,
        topic: "topic test",
    });
    test_reply_label("<rendered-channel-stub:stream test> &gt; topic test");

    // Direct message conversation with current user row.
    compose_closed_ui.update_reply_button_with_recipient_context({
        user_ids: [current_user.user_id],
    });
    let label = $("#left_bar_compose_reply_button_big").html();
    assert.equal(label, "translated: Write yourself a note");

    // Invalid data for a the reply button text.
    compose_closed_ui.update_reply_button_with_recipient_context({
        invalid_field: "something unexpected",
    });
    label = $("#left_bar_compose_reply_button_big").text();
    assert.equal(label, "translated: Compose message");
});

run_test("get_recipient_label_for_call", ({override}) => {
    const stream = make_stream({
        subscribed: true,
        name: "design",
        stream_id: 200,
    });
    stream_data.add_sub_for_tests(stream);

    // --- Compose-box branch (edit_message_id === undefined) ---

    // Stream + non-empty topic.
    override(compose_state, "get_message_type", () => "stream");
    override(compose_state, "stream_id", () => stream.stream_id);
    override(compose_state, "topic", () => "typography");
    assert.equal(
        compose_closed_ui.get_recipient_label_for_call(undefined).label_text,
        "#design > typography",
    );

    // Stream + empty topic uses the realm's empty-topic display name.
    override(compose_state, "topic", () => "");
    assert.equal(
        compose_closed_ui.get_recipient_label_for_call(undefined).label_text,
        `#design > translated: ${REALM_EMPTY_TOPIC_DISPLAY_NAME}`,
    );

    // Stream with no stream_id → undefined.
    override(compose_state, "stream_id", () => undefined);
    assert.equal(compose_closed_ui.get_recipient_label_for_call(undefined), undefined);

    // Stream lookup miss → undefined.
    override(compose_state, "stream_id", () => 999);
    assert.equal(compose_closed_ui.get_recipient_label_for_call(undefined), undefined);

    // DM with distinct recipients uses the recipient full names. User 2 is
    // "Bob", set up at the top of this file.
    override(compose_state, "get_message_type", () => "private");
    override(compose_state, "private_message_recipient_ids", () => [2]);
    assert.equal(compose_closed_ui.get_recipient_label_for_call(undefined).label_text, "Bob");

    // DM with only self → empty label_text, so the meeting name doesn't
    // start with the current user's own name.
    override(compose_state, "private_message_recipient_ids", () => [current_user.user_id]);
    assert.equal(compose_closed_ui.get_recipient_label_for_call(undefined).label_text, "");

    // Unknown message type → undefined.
    override(compose_state, "get_message_type", () => undefined);
    assert.equal(compose_closed_ui.get_recipient_label_for_call(undefined), undefined);

    // --- Edit-form branch (edit_message_id !== undefined) ---
    // The edit-form path reads from message_store, not compose_state, so we
    // deliberately don't override compose_state here.

    // Stream edit target uses the message's own stream/topic.
    override(message_store, "get", () => ({
        type: "stream",
        stream_id: stream.stream_id,
        topic: "reviews",
    }));
    assert.equal(
        compose_closed_ui.get_recipient_label_for_call("42").label_text,
        "#design > reviews",
    );

    // DM edit target uses the message's own recipients.
    override(message_store, "get", () => ({
        type: "private",
        to_user_ids: "2",
    }));
    assert.equal(compose_closed_ui.get_recipient_label_for_call("43").label_text, "Bob");

    // DM-to-self edit target → empty label_text.
    override(message_store, "get", () => ({
        type: "private",
        to_user_ids: String(current_user.user_id),
    }));
    assert.equal(compose_closed_ui.get_recipient_label_for_call("44").label_text, "");

    // Unknown/evicted message id → undefined.
    override(message_store, "get", () => undefined);
    assert.equal(compose_closed_ui.get_recipient_label_for_call("999"), undefined);
});

run_test("update_reply_button_state", ({override, override_rewire}) => {
    const $compose_reply_wrapper = $("#legacy-closed-compose-box .compose-reply-button-wrapper");
    const $reply_button = $(".compose_reply_button");

    const postable_stream = make_stream({
        subscribed: true,
        name: "postable_stream",
        stream_id: 20,
    });
    stream_data.add_sub_for_tests(postable_stream);

    const restricted_stream = make_stream({
        subscribed: true,
        name: "restricted_stream",
        stream_id: 21,
    });
    stream_data.add_sub_for_tests(restricted_stream);
    override_rewire(
        stream_data,
        "can_post_messages_in_stream",
        (stream) => stream.stream_id !== restricted_stream.stream_id,
    );

    // Reply button is enabled for stream where user can post.
    message_lists.current = {};
    $compose_reply_wrapper.attr("data-stream-id", postable_stream.stream_id.toString());
    $compose_reply_wrapper.removeAttr("data-user-ids-string");
    compose_closed_ui.update_reply_button_state();
    assert.notEqual($reply_button.attr("disabled"), "disabled");
    assert.equal($compose_reply_wrapper.attr("data-reply-button-type"), "selected_message");

    // Reply button is disabled for stream where user cannot post.
    $compose_reply_wrapper.attr("data-stream-id", restricted_stream.stream_id.toString());
    compose_closed_ui.update_reply_button_state();
    assert.equal($reply_button.attr("disabled"), "disabled");
    assert.equal($compose_reply_wrapper.attr("data-reply-button-type"), "stream_disabled");

    // Reply button is enabled for DM where user can send.
    override(message_util, "user_can_send_direct_message", () => true);
    $compose_reply_wrapper.removeAttr("data-stream-id");
    $compose_reply_wrapper.attr("data-user-ids-string", "2");
    compose_closed_ui.update_reply_button_state();
    assert.notEqual($reply_button.attr("disabled"), "disabled");
    assert.equal($compose_reply_wrapper.attr("data-reply-button-type"), "selected_message");

    // Reply button is disabled for DM where user cannot send.
    override(message_util, "user_can_send_direct_message", () => false);
    compose_closed_ui.update_reply_button_state();
    assert.equal($reply_button.attr("disabled"), "disabled");
    assert.equal($compose_reply_wrapper.attr("data-reply-button-type"), "direct_disabled");

    // No data attributes leads to enabled reply button.
    message_lists.current = undefined;
    $compose_reply_wrapper.removeAttr("data-stream-id");
    $compose_reply_wrapper.removeAttr("data-user-ids-string");
    compose_closed_ui.update_reply_button_state();
    assert.notEqual($reply_button.attr("disabled"), "disabled");

    // Button is not disabled for spectators.
    page_params.is_spectator = true;
    message_lists.current = {};
    $compose_reply_wrapper.attr("data-stream-id", restricted_stream.stream_id.toString());
    compose_closed_ui.update_reply_button_state();
    assert.notEqual($reply_button.attr("disabled"), "disabled");
    assert.equal($compose_reply_wrapper.attr("data-reply-button-type"), "selected_message");
    page_params.is_spectator = false;
});

run_test("set_standard_text_resets_stale_state", ({override}) => {
    const $compose_reply_wrapper = $("#legacy-closed-compose-box .compose-reply-button-wrapper");
    const $reply_button = $(".compose_reply_button");

    // Put the button in the "direct_disabled" state, with a recipient the
    // user cannot message, so it carries a data-user-ids-string attribute.
    override(message_util, "user_can_send_direct_message", () => false);
    message_lists.current = {};
    $compose_reply_wrapper.removeAttr("data-stream-id");
    $compose_reply_wrapper.attr("data-user-ids-string", "2");
    compose_closed_ui.update_reply_button_state();
    assert.equal($reply_button.attr("disabled"), "disabled");
    assert.equal($compose_reply_wrapper.attr("data-reply-button-type"), "direct_disabled");

    // Resetting to the standard text must clear the recipient context along
    // with the stale button type and disabled state, so the hover tooltip
    // never sees "direct_disabled" without a data-user-ids-string attribute.
    compose_closed_ui.set_standard_text_for_reply_button();
    assert.equal($("#left_bar_compose_reply_button_big").text(), "translated: Compose message");
    assert.equal($compose_reply_wrapper.attr("data-user-ids-string"), undefined);
    assert.equal($compose_reply_wrapper.attr("data-reply-button-type"), undefined);
    assert.notEqual($reply_button.attr("disabled"), "disabled");
});
