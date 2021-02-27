"use strict";

const {strict: assert} = require("assert");

const rewiremock = require("rewiremock/node");

const {set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");

const noop = () => {};

set_global("page_params", {});

set_global("document", {
    location: {}, // we need this to load compose.js
    to_$: () => $("document-stub"),
});

const compose_pm_pill = {__esModule: true};

rewiremock("../../static/js/compose_pm_pill").with(compose_pm_pill);

const hash_util = set_global("hash_util", {});

rewiremock("../../static/js/reload_state").with({
    is_in_progress: () => false,
});

set_global("notifications", {
    clear_compose_notifications: noop,
});

const compose_fade = set_global("compose_fade", {
    clear_compose: noop,
});

rewiremock("../../static/js/drafts").with({
    update_draft: noop,
});

const narrow_state = {
    __esModule: true,
    set_compose_defaults: noop,
};

rewiremock("../../static/js/narrow_state").with(narrow_state);

set_global("unread_ops", {
    notify_server_message_read: noop,
});

rewiremock("../../static/js/common").with({
    status_classes: "status_classes",
});

set_global("current_msg_list", {
    can_mark_messages_read() {
        return true;
    },
});

const channel = {__esModule: true};

rewiremock("../../static/js/channel").with(channel);

rewiremock.enable();

const people = zrequire("people");
const compose_ui = zrequire("compose_ui");
const compose = zrequire("compose");
const compose_state = zrequire("compose_state");
const compose_actions = zrequire("compose_actions");
const stream_data = zrequire("stream_data");

compose_actions.update_placeholder_text = noop;

const start = compose_actions.start;
const cancel = compose_actions.cancel;
const get_focus_area = compose_actions._get_focus_area;
const respond_to_message = compose_actions.respond_to_message;
const reply_with_mention = compose_actions.reply_with_mention;
const quote_and_reply = compose_actions.quote_and_reply;

compose_state.private_message_recipient = (function () {
    let recipient;

    return function (arg) {
        if (arg === undefined) {
            return recipient;
        }

        recipient = arg;
        return undefined;
    };
})();

function stub_selected_message(msg) {
    current_msg_list.selected_message = () => msg;
}

function stub_channel_get(success_value) {
    channel.get = (opts) => {
        opts.success(success_value);
    };
}

function assert_visible(sel) {
    assert($(sel).visible());
}

function assert_hidden(sel) {
    assert(!$(sel).visible());
}

run_test("initial_state", () => {
    assert.equal(compose_state.composing(), false);
    assert.equal(compose_state.get_message_type(), false);
    assert.equal(compose_state.has_message_content(), false);
});

run_test("start", (override) => {
    compose_actions.autosize_message_content = noop;
    compose_actions.expand_compose_box = noop;
    compose_actions.set_focus = noop;
    compose_actions.complete_starting_tasks = noop;
    compose_actions.blur_compose_inputs = noop;
    compose_actions.clear_textarea = noop;

    let compose_defaults;
    override(narrow_state, "set_compose_defaults", () => compose_defaults);

    // Start stream message
    compose_defaults = {
        stream: "stream1",
        topic: "topic1",
    };

    let opts = {};
    start("stream", opts);

    assert_visible("#stream-message");
    assert_hidden("#private-message");

    assert.equal($("#stream_message_recipient_stream").val(), "stream1");
    assert.equal($("#stream_message_recipient_topic").val(), "topic1");
    assert.equal(compose_state.get_message_type(), "stream");
    assert(compose_state.composing());

    // Autofill stream field for single subscription
    const denmark = {
        subscribed: true,
        color: "blue",
        name: "Denmark",
        stream_id: 1,
    };
    stream_data.add_sub(denmark);

    compose_defaults = {
        trigger: "new topic button",
    };

    opts = {};
    start("stream", opts);
    assert.equal($("#stream_message_recipient_stream").val(), "Denmark");
    assert.equal($("#stream_message_recipient_topic").val(), "");

    compose_defaults = {
        trigger: "compose_hotkey",
    };

    opts = {};
    start("stream", opts);
    assert.equal($("#stream_message_recipient_stream").val(), "Denmark");
    assert.equal($("#stream_message_recipient_topic").val(), "");

    const social = {
        subscribed: true,
        color: "red",
        name: "social",
        stream_id: 2,
    };
    stream_data.add_sub(social);

    // More than 1 subscription, do not autofill
    opts = {};
    start("stream", opts);
    assert.equal($("#stream_message_recipient_stream").val(), "");
    assert.equal($("#stream_message_recipient_topic").val(), "");
    stream_data.clear_subscriptions();

    // Start PM
    compose_defaults = {
        private_message_recipient: "foo@example.com",
    };

    opts = {
        content: "hello",
    };

    start("private", opts);

    assert_hidden("#stream-message");
    assert_visible("#private-message");

    assert.equal(compose_state.private_message_recipient(), "foo@example.com");
    assert.equal($("#compose-textarea").val(), "hello");
    assert.equal(compose_state.get_message_type(), "private");
    assert(compose_state.composing());

    // Cancel compose.
    let pill_cleared;
    compose_pm_pill.clear = () => {
        pill_cleared = true;
    };

    let abort_xhr_called = false;
    compose.abort_xhr = () => {
        abort_xhr_called = true;
    };

    $("#compose-textarea").set_height(50);

    assert_hidden("#compose_controls");
    cancel();
    assert(abort_xhr_called);
    assert(pill_cleared);
    assert_visible("#compose_controls");
    assert_hidden("#private-message");
    assert(!compose_state.composing());
});

run_test("respond_to_message", () => {
    // Test PM
    const person = {
        user_id: 22,
        email: "alice@example.com",
        full_name: "Alice",
    };
    people.add_active_user(person);

    let msg = {
        type: "private",
        sender_id: person.user_id,
    };
    stub_selected_message(msg);

    let opts = {
        reply_type: "personal",
    };

    respond_to_message(opts);
    assert.equal(compose_state.private_message_recipient(), "alice@example.com");

    // Test stream
    msg = {
        type: "stream",
        stream: "devel",
        topic: "python",
        reply_to: "bob", // compose.start needs this for dubious reasons
    };
    stub_selected_message(msg);

    opts = {};

    respond_to_message(opts);
    assert.equal($("#stream_message_recipient_stream").val(), "devel");
});

run_test("reply_with_mention", (override) => {
    const msg = {
        type: "stream",
        stream: "devel",
        topic: "python",
        reply_to: "bob", // compose.start needs this for dubious reasons
        sender_full_name: "Bob Roberts",
        sender_id: 40,
    };
    stub_selected_message(msg);

    let syntax_to_insert;
    override(compose_ui, "insert_syntax_and_focus", (syntax) => {
        syntax_to_insert = syntax;
    });

    const opts = {};

    reply_with_mention(opts);
    assert.equal($("#stream_message_recipient_stream").val(), "devel");
    assert.equal(syntax_to_insert, "@**Bob Roberts**");

    // Test for extended mention syntax
    const bob_1 = {
        user_id: 30,
        email: "bob1@example.com",
        full_name: "Bob Roberts",
    };
    people.add_active_user(bob_1);
    const bob_2 = {
        user_id: 40,
        email: "bob2@example.com",
        full_name: "Bob Roberts",
    };
    people.add_active_user(bob_2);

    reply_with_mention(opts);
    assert.equal($("#stream_message_recipient_stream").val(), "devel");
    assert.equal(syntax_to_insert, "@**Bob Roberts|40**");
});

run_test("quote_and_reply", (override) => {
    let selected_message;
    override(current_msg_list, "selected_message", () => selected_message);

    let expected_replacement;
    let replaced;
    override(compose_ui, "replace_syntax", (syntax, replacement) => {
        assert.equal(syntax, "[Quoting…]");
        assert.equal(replacement, expected_replacement);
        replaced = true;
    });

    selected_message = {
        type: "stream",
        stream: "devel",
        topic: "python",
        reply_to: "bob",
        sender_full_name: "Bob Roberts",
        sender_id: 40,
    };
    hash_util.by_conversation_and_time_uri = () => "link_to_message";
    stub_channel_get({
        raw_content: "Testing.",
    });

    current_msg_list.selected_id = () => 100;

    compose_ui.insert_syntax_and_focus = (syntax) => {
        assert.equal(syntax, "[Quoting…]\n");
    };

    const opts = {
        reply_type: "personal",
    };

    $("#compose-textarea").caret = (pos) => {
        assert.equal(pos, 0);
    };

    replaced = false;
    expected_replacement = "@_**Bob Roberts|40** [said](link_to_message):\n```quote\nTesting.\n```";

    quote_and_reply(opts);
    assert(replaced);

    selected_message = {
        type: "stream",
        stream: "devel",
        topic: "test",
        reply_to: "bob",
        sender_full_name: "Bob Roberts",
        sender_id: 40,
        raw_content: "Testing.",
    };

    rewiremock("../../static/js/channel").with({
        get() {
            assert.fail("channel.get should not be used if raw_content is present");
        },
    });

    replaced = false;
    quote_and_reply(opts);
    assert(replaced);

    selected_message = {
        type: "stream",
        stream: "devel",
        topic: "test",
        reply_to: "bob",
        sender_full_name: "Bob Roberts",
        sender_id: 40,
        raw_content: "```\nmultiline code block\nshoudln't mess with quotes\n```",
    };

    replaced = false;
    expected_replacement =
        "@_**Bob Roberts|40** [said](link_to_message):\n````quote\n```\nmultiline code block\nshoudln't mess with quotes\n```\n````";
    quote_and_reply(opts);
    assert(replaced);
});

run_test("get_focus_area", () => {
    assert.equal(get_focus_area("private", {}), "#private_message_recipient");
    assert.equal(
        get_focus_area("private", {
            private_message_recipient: "bob@example.com",
        }),
        "#compose-textarea",
    );
    assert.equal(get_focus_area("stream", {}), "#stream_message_recipient_stream");
    assert.equal(get_focus_area("stream", {stream: "fun"}), "#stream_message_recipient_topic");
    assert.equal(get_focus_area("stream", {stream: "fun", topic: "more"}), "#compose-textarea");
    assert.equal(
        get_focus_area("stream", {stream: "fun", topic: "more", trigger: "new topic button"}),
        "#stream_message_recipient_topic",
    );
});

run_test("focus_in_empty_compose", () => {
    $("#compose-textarea").is = (attr) => {
        assert.equal(attr, ":focus");
        return $("#compose-textarea").is_focused;
    };

    compose_state.composing = () => true;
    $("#compose-textarea").val("");
    $("#compose-textarea").trigger("focus");
    assert(compose_state.focus_in_empty_compose());

    compose_state.composing = () => false;
    assert(!compose_state.focus_in_empty_compose());

    $("#compose-textarea").val("foo");
    assert(!compose_state.focus_in_empty_compose());

    $("#compose-textarea").trigger("blur");
    assert(!compose_state.focus_in_empty_compose());
});

run_test("on_narrow", (override) => {
    let narrowed_by_topic_reply;
    override(narrow_state, "narrowed_by_topic_reply", () => narrowed_by_topic_reply);

    let narrowed_by_pm_reply;
    override(narrow_state, "narrowed_by_pm_reply", () => narrowed_by_pm_reply);

    let has_message_content;
    override(compose_state, "has_message_content", () => has_message_content);

    let cancel_called = false;
    compose_actions.cancel = () => {
        cancel_called = true;
    };
    compose_actions.on_narrow({
        force_close: true,
    });
    assert(cancel_called);

    let on_topic_narrow_called = false;
    compose_actions.on_topic_narrow = () => {
        on_topic_narrow_called = true;
    };
    narrowed_by_topic_reply = true;
    compose_actions.on_narrow({
        force_close: false,
    });
    assert(on_topic_narrow_called);

    let update_message_list_called = false;
    narrowed_by_topic_reply = false;
    compose_fade.update_message_list = () => {
        update_message_list_called = true;
    };
    has_message_content = true;
    compose_actions.on_narrow({
        force_close: false,
    });
    assert(update_message_list_called);

    has_message_content = false;
    let start_called = false;
    compose_actions.start = () => {
        start_called = true;
    };
    narrowed_by_pm_reply = true;
    compose_actions.on_narrow({
        force_close: false,
        trigger: "not-search",
        private_message_recipient: "not@empty.com",
    });
    assert(start_called);

    start_called = false;
    compose_actions.on_narrow({
        force_close: false,
        trigger: "search",
        private_message_recipient: "",
    });
    assert(!start_called);

    narrowed_by_pm_reply = false;
    cancel_called = false;
    compose_actions.on_narrow({
        force_close: false,
    });
    assert(cancel_called);
});
rewiremock.disable();
