"use strict";

const {strict: assert} = require("assert");

const {mock_stream_header_colorblock} = require("./lib/compose");
const {mock_banners} = require("./lib/compose_banner");
const {mock_esm, set_global, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");
const {page_params} = require("./lib/zpage_params");

const settings_config = zrequire("settings_config");

const noop = () => {};

set_global("document", {
    to_$: () => $("document-stub"),
});

const autosize = () => {};
autosize.update = () => {};
mock_esm("autosize", {default: autosize});

const channel = mock_esm("../src/channel");
const compose_fade = mock_esm("../src/compose_fade", {
    clear_compose: noop,
    set_focused_recipient: noop,
    update_all: noop,
});
const compose_pm_pill = mock_esm("../src/compose_pm_pill");
const compose_ui = mock_esm("../src/compose_ui", {
    autosize_textarea: noop,
    is_full_size: () => false,
    set_focus: noop,
    compute_placeholder_text: noop,
});
const hash_util = mock_esm("../src/hash_util");
const narrow_state = mock_esm("../src/narrow_state", {
    set_compose_defaults: noop,
});

mock_esm("../src/reload_state", {
    is_in_progress: () => false,
});
mock_esm("../src/recent_view_util", {
    is_visible: noop,
});
mock_esm("../src/drafts", {
    update_draft: noop,
});
mock_esm("../src/unread_ops", {
    notify_server_message_read: noop,
});
mock_esm("../src/message_lists", {
    current: {
        can_mark_messages_read: () => true,
    },
});
mock_esm("../src/resize", {
    reset_compose_message_max_height: noop,
});

const people = zrequire("people");

const compose = zrequire("compose");
const compose_state = zrequire("compose_state");
const compose_actions = zrequire("compose_actions");
const message_lists = zrequire("message_lists");
const stream_data = zrequire("stream_data");
const compose_recipient = zrequire("compose_recipient");

const start = compose_actions.start;
const cancel = compose_actions.cancel;
const respond_to_message = compose_actions.respond_to_message;
const reply_with_mention = compose_actions.reply_with_mention;
const quote_and_reply = compose_actions.quote_and_reply;

function assert_visible(sel) {
    assert.ok($(sel).visible());
}

function assert_hidden(sel) {
    assert.ok(!$(sel).visible());
}

function override_private_message_recipient({override}) {
    let recipient;
    override(compose_pm_pill, "set_from_emails", (value) => {
        recipient = value;
    });
    override(compose_pm_pill, "get_emails", () => recipient, {unused: false});
}

function test(label, f) {
    run_test(label, (helpers) => {
        // We don't test the css calls; we just skip over them.
        $("#compose").css = () => {};
        $(".new_message_textarea").css = () => {};

        people.init();
        compose_state.set_message_type(false);
        f(helpers);
    });
}

test("initial_state", () => {
    assert.equal(compose_state.composing(), false);
    assert.equal(compose_state.get_message_type(), false);
    assert.equal(compose_state.has_message_content(), false);
});

test("start", ({override, override_rewire, mock_template}) => {
    mock_banners();
    override_private_message_recipient({override});
    override_rewire(compose_actions, "autosize_message_content", () => {});
    override_rewire(compose_actions, "expand_compose_box", () => {});
    override_rewire(compose_actions, "complete_starting_tasks", () => {});
    override_rewire(compose_actions, "blur_compose_inputs", () => {});
    override_rewire(compose_actions, "clear_textarea", () => {});
    override_rewire(compose_recipient, "on_compose_select_recipient_update", () => {});
    override_rewire(compose_recipient, "check_posting_policy_for_compose_box", () => {});
    mock_template("inline_decorated_stream_name.hbs", false, () => {});
    mock_stream_header_colorblock();

    let compose_defaults;
    override(narrow_state, "set_compose_defaults", () => compose_defaults);

    // Start stream message
    compose_defaults = {
        stream_id: "",
        topic: "topic1",
    };

    let opts = {};
    start("stream", opts);

    assert_visible("#stream_message_recipient_topic");
    assert_hidden("#compose-direct-recipient");

    assert.equal(compose_state.stream_name(), "");
    assert.equal(compose_state.topic(), "topic1");
    assert.equal(compose_state.get_message_type(), "stream");
    assert.ok(compose_state.composing());

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
    assert.equal(compose_state.stream_name(), "Denmark");
    assert.equal(compose_state.topic(), "");

    compose_defaults = {
        trigger: "compose_hotkey",
    };

    opts = {};
    start("stream", opts);
    assert.equal(compose_state.stream_name(), "Denmark");
    assert.equal(compose_state.topic(), "");

    const social = {
        subscribed: true,
        color: "red",
        name: "social",
        stream_id: 2,
    };
    stream_data.add_sub(social);

    compose_state.set_stream_id("");
    // More than 1 subscription, do not autofill
    opts = {};
    start("stream", opts);
    assert.equal(compose_state.stream_name(), "");
    assert.equal(compose_state.topic(), "");
    stream_data.clear_subscriptions();

    // Start direct message
    compose_defaults = {
        private_message_recipient: "foo@example.com",
    };

    opts = {
        content: "hello",
    };

    start("private", opts);

    assert_hidden("#stream_message_recipient_topic");
    assert_visible("#compose-direct-recipient");

    assert.equal(compose_state.private_message_recipient(), "foo@example.com");
    assert.equal($("#compose-textarea").val(), "hello");
    assert.equal(compose_state.get_message_type(), "private");
    assert.ok(compose_state.composing());

    // Triggered by new direct message
    opts = {
        trigger: "new direct message",
    };

    start("private", opts);

    assert.equal(compose_state.private_message_recipient(), "");
    assert.equal(compose_state.get_message_type(), "private");
    assert.ok(compose_state.composing());

    // Cancel compose.
    let pill_cleared;
    compose_pm_pill.clear = () => {
        pill_cleared = true;
    };

    let abort_xhr_called = false;
    override_rewire(compose, "abort_xhr", () => {
        abort_xhr_called = true;
    });

    compose_actions.register_compose_cancel_hook(compose.abort_xhr);
    $("#compose-textarea").set_height(50);

    assert_hidden("#compose_controls");
    cancel();
    assert.ok(abort_xhr_called);
    assert.ok(pill_cleared);
    assert_visible("#compose_controls");
    assert_hidden("#compose-direct-recipient");
    assert.ok(!compose_state.composing());
});

test("respond_to_message", ({override, override_rewire, mock_template}) => {
    mock_banners();
    override_rewire(compose_actions, "complete_starting_tasks", () => {});
    override_rewire(compose_actions, "clear_textarea", () => {});
    override_rewire(compose_recipient, "on_compose_select_recipient_update", noop);
    override_rewire(compose_recipient, "check_posting_policy_for_compose_box", noop);
    override_private_message_recipient({override});
    mock_template("inline_decorated_stream_name.hbs", false, () => {});
    mock_stream_header_colorblock();

    // Test direct message
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
    override(message_lists.current, "selected_message", () => msg);

    let opts = {
        reply_type: "personal",
    };

    respond_to_message(opts);
    assert.equal(compose_state.private_message_recipient(), "alice@example.com");

    // Test stream
    const denmark = {
        subscribed: true,
        color: "blue",
        name: "Denmark",
        stream_id: 1,
    };
    stream_data.add_sub(denmark);

    msg = {
        type: "stream",
        stream_id: denmark.stream_id,
        topic: "python",
    };

    opts = {};

    respond_to_message(opts);
    assert.equal(compose_state.stream_name(), "Denmark");
});

test("reply_with_mention", ({override, override_rewire, mock_template}) => {
    mock_banners();
    mock_stream_header_colorblock();
    compose_state.set_message_type("stream");
    override_rewire(compose_recipient, "on_compose_select_recipient_update", () => {});
    override_rewire(compose_actions, "complete_starting_tasks", () => {});
    override_rewire(compose_actions, "clear_textarea", () => {});
    override_private_message_recipient({override});
    override_rewire(compose_recipient, "check_posting_policy_for_compose_box", noop);
    mock_template("inline_decorated_stream_name.hbs", false, () => {});

    const denmark = {
        subscribed: true,
        color: "blue",
        name: "Denmark",
        stream_id: 1,
    };
    stream_data.add_sub(denmark);

    const msg = {
        type: "stream",
        stream_id: denmark.stream_id,
        topic: "python",
        sender_full_name: "Bob Roberts",
        sender_id: 40,
    };
    override(message_lists.current, "selected_message", () => msg);

    let syntax_to_insert;
    override(compose_ui, "insert_syntax_and_focus", (syntax) => {
        syntax_to_insert = syntax;
    });

    const opts = {};

    reply_with_mention(opts);
    assert.equal(compose_state.stream_name(), "Denmark");
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
    assert.equal(compose_state.stream_name(), "Denmark");
    assert.equal(syntax_to_insert, "@**Bob Roberts|40**");
});

test("quote_and_reply", ({disallow, override, override_rewire}) => {
    override_rewire(compose_recipient, "on_compose_select_recipient_update", noop);

    mock_banners();
    mock_stream_header_colorblock();
    compose_state.set_message_type("stream");
    const steve = {
        user_id: 90,
        email: "steve@example.com",
        full_name: "Steve Stephenson",
    };
    people.add_active_user(steve);

    override_rewire(compose_actions, "complete_starting_tasks", () => {});
    override_rewire(compose_actions, "clear_textarea", () => {});
    override_private_message_recipient({override});

    let selected_message;
    override(message_lists.current, "selected_message", () => selected_message);

    let expected_replacement;
    let replaced;
    override(compose_ui, "replace_syntax", (syntax, replacement) => {
        assert.equal(syntax, "translated: [Quoting…]");
        assert.equal(replacement, expected_replacement);
        replaced = true;
    });

    const denmark_stream = {
        subscribed: false,
        name: "Denmark",
        stream_id: 20,
    };

    selected_message = {
        type: "stream",
        stream_id: denmark_stream.stream_id,
        topic: "python",
        sender_full_name: "Steve Stephenson",
        sender_id: 90,
    };
    hash_util.by_conversation_and_time_url = () =>
        "https://chat.zulip.org/#narrow/stream/92-learning/topic/Tornado";

    let success_function;
    override(channel, "get", (opts) => {
        success_function = opts.success;
    });

    override(message_lists.current, "selected_id", () => 100);

    override(compose_ui, "insert_syntax_and_focus", (syntax, _$textarea, mode) => {
        assert.equal(syntax, "translated: [Quoting…]");
        assert.equal(mode, "block");
    });

    const opts = {
        reply_type: "personal",
    };

    $("#compose-textarea").caret = noop;

    replaced = false;
    expected_replacement =
        "translated: @_**Steve Stephenson|90** [said](https://chat.zulip.org/#narrow/stream/92-learning/topic/Tornado):\n```quote\nTesting.\n```";

    quote_and_reply(opts);

    success_function({
        raw_content: "Testing.",
    });
    assert.ok(replaced);

    selected_message = {
        type: "stream",
        stream_id: denmark_stream.stream_id,
        topic: "test",
        sender_full_name: "Steve Stephenson",
        sender_id: 90,
        raw_content: "Testing.",
    };

    replaced = false;
    disallow(channel, "get");
    quote_and_reply(opts);
    assert.ok(replaced);

    selected_message = {
        type: "stream",
        stream_id: denmark_stream.stream_id,
        topic: "test",
        sender_full_name: "Steve Stephenson",
        sender_id: 90,
        raw_content: "```\nmultiline code block\nshoudln't mess with quotes\n```",
    };

    replaced = false;
    expected_replacement =
        "translated: @_**Steve Stephenson|90** [said](https://chat.zulip.org/#narrow/stream/92-learning/topic/Tornado):\n````quote\n```\nmultiline code block\nshoudln't mess with quotes\n```\n````";
    quote_and_reply(opts);
    assert.ok(replaced);
});

test("focus_in_empty_compose", () => {
    document.activeElement = {id: "compose-textarea"};
    compose_state.set_message_type("stream");
    $("#compose-textarea").val("");
    assert.ok(compose_state.focus_in_empty_compose());

    compose_state.set_message_type(false);
    assert.ok(!compose_state.focus_in_empty_compose());

    $("#compose-textarea").val("foo");
    assert.ok(!compose_state.focus_in_empty_compose());

    $("#compose-textarea").trigger("blur");
    assert.ok(!compose_state.focus_in_empty_compose());
});

test("on_narrow", ({override, override_rewire}) => {
    let narrowed_by_topic_reply;
    override(narrow_state, "narrowed_by_topic_reply", () => narrowed_by_topic_reply);

    let narrowed_by_pm_reply;
    override(narrow_state, "narrowed_by_pm_reply", () => narrowed_by_pm_reply);

    const steve = {
        user_id: 90,
        email: "steve@example.com",
        full_name: "Steve Stephenson",
        is_bot: false,
    };
    people.add_active_user(steve);

    const bot = {
        user_id: 91,
        email: "bot@example.com",
        full_name: "Steve's bot",
        is_bot: true,
    };
    people.add_active_user(bot);

    let cancel_called = false;
    override_rewire(compose_actions, "cancel", () => {
        cancel_called = true;
    });
    compose_actions.on_narrow({
        force_close: true,
    });
    assert.ok(cancel_called);

    let on_topic_narrow_called = false;
    override_rewire(compose_actions, "on_topic_narrow", () => {
        on_topic_narrow_called = true;
    });
    narrowed_by_topic_reply = true;
    compose_actions.on_narrow({
        force_close: false,
    });
    assert.ok(on_topic_narrow_called);

    let update_message_list_called = false;
    narrowed_by_topic_reply = false;
    compose_fade.update_message_list = () => {
        update_message_list_called = true;
    };
    compose_state.message_content("foo");
    compose_actions.on_narrow({
        force_close: false,
    });
    assert.ok(update_message_list_called);

    compose_state.message_content("");
    let start_called = false;
    override_rewire(compose_actions, "start", () => {
        start_called = true;
    });
    narrowed_by_pm_reply = true;
    page_params.realm_private_message_policy =
        settings_config.private_message_policy_values.disabled.code;
    compose_actions.on_narrow({
        force_close: false,
        trigger: "not-search",
        private_message_recipient: "steve@example.com",
    });
    assert.ok(!start_called);

    compose_actions.on_narrow({
        force_close: false,
        trigger: "not-search",
        private_message_recipient: "bot@example.com",
    });
    assert.ok(start_called);

    page_params.realm_private_message_policy =
        settings_config.private_message_policy_values.by_anyone.code;
    compose_actions.on_narrow({
        force_close: false,
        trigger: "not-search",
        private_message_recipient: "not@empty.com",
    });
    assert.ok(start_called);

    start_called = false;
    compose_actions.on_narrow({
        force_close: false,
        trigger: "search",
        private_message_recipient: "",
    });
    assert.ok(!start_called);

    narrowed_by_pm_reply = false;
    cancel_called = false;
    compose_actions.on_narrow({
        force_close: false,
    });
    assert.ok(cancel_called);
});
