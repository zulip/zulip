"use strict";

const {strict: assert} = require("assert");

const {mock_banners} = require("./lib/compose_banner");
const {mock_esm, set_global, zrequire} = require("./lib/namespace");
const {run_test, noop} = require("./lib/test");
const $ = require("./lib/zjquery");
const {realm} = require("./lib/zpage_params");

const settings_config = zrequire("settings_config");

set_global("document", {
    to_$: () => $("document-stub"),
});

const autosize = noop;
autosize.update = noop;
mock_esm("autosize", {default: autosize});

const channel = mock_esm("../src/channel");
const compose_fade = mock_esm("../src/compose_fade", {
    clear_compose: noop,
    set_focused_recipient: noop,
    update_all: noop,
});
const compose_pm_pill = mock_esm("../src/compose_pm_pill", {
    get_user_ids_string: () => "",
});
const compose_ui = mock_esm("../src/compose_ui", {
    autosize_textarea: noop,
    is_full_size: () => false,
    set_focus: noop,
    compute_placeholder_text: noop,
});
const hash_util = mock_esm("../src/hash_util");
const narrow_state = mock_esm("../src/narrow_state", {
    set_compose_defaults: noop,
    filter: noop,
});

mock_esm("../src/reload_state", {
    is_in_progress: () => false,
});
mock_esm("../src/drafts", {
    update_draft: noop,
    update_compose_draft_count: noop,
    get_last_restorable_draft_based_on_compose_state: noop,
    set_compose_draft_id: noop,
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
mock_esm("../src/popovers", {
    hide_all: noop,
});

const people = zrequire("people");

const compose_state = zrequire("compose_state");
const compose_actions = zrequire("compose_actions");
const compose_reply = zrequire("compose_reply");
const message_lists = zrequire("message_lists");
const stream_data = zrequire("stream_data");
const compose_recipient = zrequire("compose_recipient");

const start = compose_actions.start;
const cancel = compose_actions.cancel;
const respond_to_message = compose_reply.respond_to_message;
const reply_with_mention = compose_reply.reply_with_mention;
const quote_and_reply = compose_reply.quote_and_reply;

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
        $("#compose").css = noop;
        $(".new_message_textarea").css = noop;

        people.init();
        compose_state.set_message_type(undefined);
        f(helpers);
    });
}

test("initial_state", () => {
    assert.equal(compose_state.composing(), false);
    assert.equal(compose_state.get_message_type(), undefined);
    assert.equal(compose_state.has_message_content(), false);
});

test("start", ({override, override_rewire, mock_template}) => {
    mock_banners();
    override_private_message_recipient({override});
    override_rewire(compose_actions, "autosize_message_content", noop);
    override_rewire(compose_actions, "expand_compose_box", noop);
    override_rewire(compose_actions, "complete_starting_tasks", noop);
    override_rewire(compose_actions, "blur_compose_inputs", noop);
    override_rewire(compose_actions, "clear_textarea", noop);
    override_rewire(compose_recipient, "on_compose_select_recipient_update", noop);
    override_rewire(compose_recipient, "check_posting_policy_for_compose_box", noop);
    mock_template("inline_decorated_stream_name.hbs", false, noop);

    let compose_defaults;
    override(narrow_state, "set_compose_defaults", () => compose_defaults);
    override(compose_ui, "insert_and_scroll_into_view", (content, $textarea, replace_all) => {
        $textarea.val(content);
        assert.ok(replace_all);
    });

    // Start stream message
    compose_defaults = {
        stream_id: undefined,
        topic: "topic1",
    };

    let opts = {
        message_type: "stream",
    };
    start(opts);

    assert_visible("#compose_recipient_box");
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
        trigger: "clear topic button",
    };

    opts = {
        message_type: "stream",
    };
    start(opts);
    assert.equal(compose_state.stream_name(), "Denmark");
    assert.equal(compose_state.topic(), "");

    compose_defaults = {
        trigger: "compose_hotkey",
    };

    opts = {
        message_type: "stream",
    };
    start(opts);
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
    opts = {
        message_type: "stream",
    };
    start(opts);
    assert.equal(compose_state.stream_name(), "");
    assert.equal(compose_state.topic(), "");
    stream_data.clear_subscriptions();

    // Start direct message
    compose_defaults = {
        private_message_recipient: "foo@example.com",
    };

    opts = {
        message_type: "private",
        content: "hello",
    };

    start(opts);

    assert_hidden("input#stream_message_recipient_topic");
    assert_visible("#compose-direct-recipient");

    assert.equal(compose_state.private_message_recipient(), "foo@example.com");
    assert.equal($("textarea#compose-textarea").val(), "hello");
    assert.equal(compose_state.get_message_type(), "private");
    assert.ok(compose_state.composing());

    // Triggered by new direct message
    opts = {
        message_type: "private",
        trigger: "new direct message",
    };

    start(opts);

    assert.equal(compose_state.private_message_recipient(), "");
    assert.equal(compose_state.get_message_type(), "private");
    assert.ok(compose_state.composing());

    // Cancel compose.
    let pill_cleared;
    compose_pm_pill.clear = () => {
        pill_cleared = true;
    };

    let abort_xhr_called = false;
    compose_actions.register_compose_cancel_hook(() => {
        abort_xhr_called = true;
    });
    $("textarea#compose-textarea").set_height(50);

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
    override_rewire(compose_actions, "complete_starting_tasks", noop);
    override_rewire(compose_actions, "clear_textarea", noop);
    override_rewire(compose_recipient, "on_compose_select_recipient_update", noop);
    override_rewire(compose_recipient, "check_posting_policy_for_compose_box", noop);
    override_private_message_recipient({override});
    mock_template("inline_decorated_stream_name.hbs", false, noop);

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
    override(message_lists.current, "get", (id) => (id === 100 ? msg : undefined));

    let opts = {
        reply_type: "personal",
        message_id: 100,
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
    override(message_lists.current, "selected_message", () => msg);

    opts = {};

    respond_to_message(opts);
    assert.equal(compose_state.stream_name(), "Denmark");
});

test("reply_with_mention", ({override, override_rewire, mock_template}) => {
    mock_banners();
    compose_state.set_message_type("stream");
    override_rewire(compose_recipient, "on_compose_select_recipient_update", noop);
    override_rewire(compose_actions, "complete_starting_tasks", noop);
    override_rewire(compose_actions, "clear_textarea", noop);
    override_private_message_recipient({override});
    override_rewire(compose_recipient, "check_posting_policy_for_compose_box", noop);
    mock_template("inline_decorated_stream_name.hbs", false, noop);

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
    override(message_lists.current, "get", (_id) => undefined);
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
    override_rewire(compose_reply, "selection_within_message_id", () => undefined);

    mock_banners();
    compose_state.set_message_type("stream");
    const steve = {
        user_id: 90,
        email: "steve@example.com",
        full_name: "Steve Stephenson",
    };
    people.add_active_user(steve);

    override_rewire(compose_actions, "complete_starting_tasks", noop);
    override_rewire(compose_actions, "clear_textarea", noop);
    override_private_message_recipient({override});

    let selected_message;
    override(message_lists.current, "get", (id) => (id === 100 ? selected_message : undefined));

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

    override(compose_ui, "insert_syntax_and_focus", (syntax, _$textarea, mode) => {
        assert.equal(syntax, "translated: [Quoting…]");
        assert.equal(mode, "block");
    });

    const opts = {
        reply_type: "personal",
        message_id: 100,
    };

    $("textarea#compose-textarea").caret = noop;
    $("textarea#compose-textarea").attr("id", "compose-textarea");

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

    delete opts.message_id;
    override(message_lists.current, "selected_id", () => 100);
    override(message_lists.current, "selected_message", () => selected_message);

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
    $("textarea#compose-textarea").val("");
    assert.ok(compose_state.focus_in_empty_compose());

    compose_state.set_message_type(undefined);
    assert.ok(!compose_state.focus_in_empty_compose());

    $("textarea#compose-textarea").val("foo");
    assert.ok(!compose_state.focus_in_empty_compose());

    $("textarea#compose-textarea").trigger("blur");
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
    realm.realm_private_message_policy =
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

    realm.realm_private_message_policy =
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
