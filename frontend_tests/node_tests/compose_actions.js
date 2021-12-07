"use strict";

const {strict: assert} = require("assert");

const {mock_esm, set_global, with_field, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");

const noop = () => {};

set_global("document", {
    to_$: () => $("document-stub"),
});

const channel = mock_esm("../../static/js/channel");
const compose_fade = mock_esm("../../static/js/compose_fade", {
    clear_compose: noop,
});
const compose_pm_pill = mock_esm("../../static/js/compose_pm_pill");
const hash_util = mock_esm("../../static/js/hash_util");
const narrow_state = mock_esm("../../static/js/narrow_state", {
    set_compose_defaults: noop,
});
mock_esm("../../static/js/notifications", {
    clear_compose_notifications: noop,
});
mock_esm("../../static/js/reload_state", {
    is_in_progress: () => false,
});
mock_esm("../../static/js/recent_topics_util", {
    is_visible: noop,
});
mock_esm("../../static/js/drafts", {
    update_draft: noop,
});
mock_esm("../../static/js/common", {
    status_classes: "status_classes",
});
mock_esm("../../static/js/unread_ops", {
    notify_server_message_read: noop,
});
mock_esm("../../static/js/message_lists", {
    current: {
        can_mark_messages_read: () => true,
    },
});
mock_esm("../../static/js/resize", {
    reset_compose_textarea_max_height: noop,
});

const people = zrequire("people");

const compose_ui = zrequire("compose_ui");
const compose = zrequire("compose");
const compose_state = zrequire("compose_state");
const compose_actions = zrequire("compose_actions");
const message_lists = zrequire("message_lists");
const stream_data = zrequire("stream_data");

const start = compose_actions.start;
const cancel = compose_actions.cancel;
const get_focus_area = compose_actions._get_focus_area;
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
    override(
        compose_state,
        "private_message_recipient",
        (function () {
            let recipient;

            return function (arg) {
                if (arg === undefined) {
                    return recipient;
                }

                recipient = arg;
                return undefined;
            };
        })(),
    );
}

function test(label, f) {
    run_test(label, ({override}) => {
        // We don't test the css calls; we just skip over them.
        $("#compose").css = () => {};
        $(".new_message_textarea").css = () => {};

        people.init();
        compose_state.set_message_type(false);
        f({override});
    });
}

test("initial_state", () => {
    assert.equal(compose_state.composing(), false);
    assert.equal(compose_state.get_message_type(), false);
    assert.equal(compose_state.has_message_content(), false);
});

test("start", ({override}) => {
    override_private_message_recipient({override});
    override(compose_actions, "autosize_message_content", () => {});
    override(compose_actions, "expand_compose_box", () => {});
    override(compose_actions, "set_focus", () => {});
    override(compose_actions, "complete_starting_tasks", () => {});
    override(compose_actions, "blur_compose_inputs", () => {});
    override(compose_actions, "clear_textarea", () => {});

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
    assert.ok(compose_state.composing());

    // Triggered by new private message
    opts = {
        trigger: "new private message",
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
    override(compose, "abort_xhr", () => {
        abort_xhr_called = true;
    });

    $("#compose-textarea").set_height(50);

    assert_hidden("#compose_controls");
    cancel();
    assert.ok(abort_xhr_called);
    assert.ok(pill_cleared);
    assert_visible("#compose_controls");
    assert_hidden("#private-message");
    assert.ok(!compose_state.composing());
});

test("respond_to_message", ({override}) => {
    override(compose_actions, "set_focus", () => {});
    override(compose_actions, "complete_starting_tasks", () => {});
    override(compose_actions, "clear_textarea", () => {});
    override_private_message_recipient({override});

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
    override(message_lists.current, "selected_message", () => msg);

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
    };

    opts = {};

    respond_to_message(opts);
    assert.equal($("#stream_message_recipient_stream").val(), "devel");
});

test("reply_with_mention", ({override}) => {
    compose_state.set_message_type("stream");
    override(compose_actions, "set_focus", () => {});
    override(compose_actions, "complete_starting_tasks", () => {});
    override(compose_actions, "clear_textarea", () => {});
    override_private_message_recipient({override});

    const msg = {
        type: "stream",
        stream: "devel",
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

test("quote_and_reply", ({override}) => {
    compose_state.set_message_type("stream");
    const steve = {
        user_id: 90,
        email: "steve@example.com",
        full_name: "Steve Stephenson",
    };
    people.add_active_user(steve);

    override(compose_actions, "set_focus", () => {});
    override(compose_actions, "complete_starting_tasks", () => {});
    override(compose_actions, "clear_textarea", () => {});
    override_private_message_recipient({override});

    let selected_message;
    override(message_lists.current, "selected_message", () => selected_message);

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
        sender_full_name: "Steve Stephenson",
        sender_id: 90,
    };
    hash_util.by_conversation_and_time_uri = () =>
        "https://chat.zulip.org/#narrow/stream/92-learning/topic/Tornado";

    let success_function;
    override(channel, "get", (opts) => {
        success_function = opts.success;
    });

    override(message_lists.current, "selected_id", () => 100);

    override(compose_ui, "insert_syntax_and_focus", (syntax) => {
        assert.equal(syntax, "[Quoting…]\n");
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
        stream: "devel",
        topic: "test",
        sender_full_name: "Steve Stephenson",
        sender_id: 90,
        raw_content: "Testing.",
    };

    function whiny_get() {
        assert.fail("channel.get should not be used if raw_content is present");
    }

    replaced = false;
    with_field(channel, "get", whiny_get, () => {
        quote_and_reply(opts);
    });
    assert.ok(replaced);

    selected_message = {
        type: "stream",
        stream: "devel",
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

test("get_focus_area", () => {
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

test("focus_in_empty_compose", ({override}) => {
    $("#compose-textarea").is = (attr) => {
        assert.equal(attr, ":focus");
        return $("#compose-textarea").is_focused;
    };

    override(compose_state, "composing", () => true);
    $("#compose-textarea").val("");
    $("#compose-textarea").trigger("focus");
    assert.ok(compose_state.focus_in_empty_compose());

    override(compose_state, "composing", () => false);
    assert.ok(!compose_state.focus_in_empty_compose());

    $("#compose-textarea").val("foo");
    assert.ok(!compose_state.focus_in_empty_compose());

    $("#compose-textarea").trigger("blur");
    assert.ok(!compose_state.focus_in_empty_compose());
});

test("on_narrow", ({override}) => {
    let narrowed_by_topic_reply;
    override(narrow_state, "narrowed_by_topic_reply", () => narrowed_by_topic_reply);

    let narrowed_by_pm_reply;
    override(narrow_state, "narrowed_by_pm_reply", () => narrowed_by_pm_reply);

    let has_message_content;
    override(compose_state, "has_message_content", () => has_message_content);

    let cancel_called = false;
    override(compose_actions, "cancel", () => {
        cancel_called = true;
    });
    compose_actions.on_narrow({
        force_close: true,
    });
    assert.ok(cancel_called);

    let on_topic_narrow_called = false;
    override(compose_actions, "on_topic_narrow", () => {
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
    has_message_content = true;
    compose_actions.on_narrow({
        force_close: false,
    });
    assert.ok(update_message_list_called);

    has_message_content = false;
    let start_called = false;
    override(compose_actions, "start", () => {
        start_called = true;
    });
    narrowed_by_pm_reply = true;
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
