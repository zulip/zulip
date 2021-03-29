"use strict";

const {strict: assert} = require("assert");

const autosize = require("autosize");

const {i18n} = require("../zjsunit/i18n");
const {mock_cjs, mock_esm, set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");

mock_cjs("jquery", $);

set_global("document", {
    execCommand() {
        return false;
    },
});

mock_esm("../../static/js/message_lists", {
    current: {
        can_mark_messages_read: () => true,
    },
});

const compose_ui = zrequire("compose_ui");
const people = zrequire("people");
const user_status = zrequire("user_status");
const hash_util = mock_esm("../../static/js/hash_util");
const channel = mock_esm("../../static/js/channel");
const compose_actions = zrequire("compose_actions");
const message_lists = zrequire("message_lists");

const alice = {
    email: "alice@zulip.com",
    user_id: 101,
    full_name: "Alice",
};
const bob = {
    email: "bob@zulip.com",
    user_id: 102,
    full_name: "Bob",
};

people.add_active_user(alice);
people.add_active_user(bob);

function make_textbox(s) {
    // Simulate a jQuery textbox for testing purposes.
    const widget = {};

    widget.s = s;
    widget.focused = false;

    widget.caret = function (arg) {
        if (typeof arg === "number") {
            widget.pos = arg;
            return this;
        }

        if (arg) {
            widget.insert_pos = widget.pos;
            widget.insert_text = arg;
            const before = widget.s.slice(0, widget.pos);
            const after = widget.s.slice(widget.pos);
            widget.s = before + arg + after;
            widget.pos += arg.length;
            return this;
        }

        return widget.pos;
    };

    widget.val = function (new_val) {
        if (new_val) {
            widget.s = new_val;
            return this;
        }
        return widget.s;
    };

    widget.trigger = function (type) {
        if (type === "focus") {
            widget.focused = true;
        } else if (type === "blur") {
            widget.focused = false;
        }
        return this;
    };

    return widget;
}

run_test("autosize_textarea", (override) => {
    const textarea_autosized = {};

    override(autosize, "update", (textarea) => {
        textarea_autosized.textarea = textarea;
        textarea_autosized.autosized = true;
    });

    // Call autosize_textarea with an argument
    const container = "container-stub";
    compose_ui.autosize_textarea(container);
    assert.equal(textarea_autosized.textarea, container);
    assert(textarea_autosized.autosized);
});

run_test("insert_syntax_and_focus", () => {
    $("#compose-textarea").val("xyz ");
    $("#compose-textarea").caret = function (syntax) {
        if (syntax !== undefined) {
            $("#compose-textarea").val($("#compose-textarea").val() + syntax);
            return this;
        }
        return 4;
    };
    compose_ui.insert_syntax_and_focus(":octopus:");
    assert.equal($("#compose-textarea").caret(), 4);
    assert.equal($("#compose-textarea").val(), "xyz :octopus: ");
    assert($("#compose-textarea").is_focused());
});

run_test("smart_insert", () => {
    let textbox = make_textbox("abc");
    textbox.caret(4);

    compose_ui.smart_insert(textbox, ":smile:");
    assert.equal(textbox.insert_pos, 4);
    assert.equal(textbox.insert_text, " :smile: ");
    assert.equal(textbox.val(), "abc :smile: ");
    assert(textbox.focused);

    textbox.trigger("blur");
    compose_ui.smart_insert(textbox, ":airplane:");
    assert.equal(textbox.insert_text, ":airplane: ");
    assert.equal(textbox.val(), "abc :smile: :airplane: ");
    assert(textbox.focused);

    textbox.caret(0);
    textbox.trigger("blur");
    compose_ui.smart_insert(textbox, ":octopus:");
    assert.equal(textbox.insert_text, ":octopus: ");
    assert.equal(textbox.val(), ":octopus: abc :smile: :airplane: ");
    assert(textbox.focused);

    textbox.caret(textbox.val().length);
    textbox.trigger("blur");
    compose_ui.smart_insert(textbox, ":heart:");
    assert.equal(textbox.insert_text, ":heart: ");
    assert.equal(textbox.val(), ":octopus: abc :smile: :airplane: :heart: ");
    assert(textbox.focused);

    // Test handling of spaces for ```quote
    textbox = make_textbox("");
    textbox.caret(0);
    textbox.trigger("blur");
    compose_ui.smart_insert(textbox, "```quote\nquoted message\n```\n");
    assert.equal(textbox.insert_text, "```quote\nquoted message\n```\n");
    assert.equal(textbox.val(), "```quote\nquoted message\n```\n");
    assert(textbox.focused);

    textbox = make_textbox("");
    textbox.caret(0);
    textbox.trigger("blur");
    compose_ui.smart_insert(textbox, "[Quoting…]\n");
    assert.equal(textbox.insert_text, "[Quoting…]\n");
    assert.equal(textbox.val(), "[Quoting…]\n");
    assert(textbox.focused);

    textbox = make_textbox("abc");
    textbox.caret(3);
    textbox.trigger("blur");
    compose_ui.smart_insert(textbox, " test with space");
    assert.equal(textbox.insert_text, " test with space ");
    assert.equal(textbox.val(), "abc test with space ");
    assert(textbox.focused);

    // Note that we don't have any special logic for strings that are
    // already surrounded by spaces, since we are usually inserting things
    // like emojis and file links.
});

run_test("replace_syntax", () => {
    $("#compose-textarea").val("abcabc");

    compose_ui.replace_syntax("a", "A");
    assert.equal($("#compose-textarea").val(), "Abcabc");

    compose_ui.replace_syntax(/b/g, "B");
    assert.equal($("#compose-textarea").val(), "ABcaBc");

    // Verify we correctly handle `$`s in the replacement syntax
    compose_ui.replace_syntax("Bca", "$$\\pi$$");
    assert.equal($("#compose-textarea").val(), "A$$\\pi$$Bc");
});

run_test("compute_placeholder_text", () => {
    let opts = {
        message_type: "stream",
        stream: "",
        topic: "",
        private_message_recipient: "",
    };

    // Stream narrows
    assert.equal(compose_ui.compute_placeholder_text(opts), i18n.t("Compose your message here"));

    opts.stream = "all";
    assert.equal(compose_ui.compute_placeholder_text(opts), i18n.t("Message #all"));

    opts.topic = "Test";
    assert.equal(compose_ui.compute_placeholder_text(opts), i18n.t("Message #all > Test"));

    // PM Narrows
    opts = {
        message_type: "private",
        stream: "",
        topic: "",
        private_message_recipient: "",
    };
    assert.equal(compose_ui.compute_placeholder_text(opts), i18n.t("Compose your message here"));

    opts.private_message_recipient = "bob@zulip.com";
    user_status.set_status_text({
        user_id: bob.user_id,
        status_text: "out to lunch",
    });
    assert.equal(compose_ui.compute_placeholder_text(opts), i18n.t("Message Bob (out to lunch)"));

    opts.private_message_recipient = "alice@zulip.com";
    user_status.set_status_text({
        user_id: alice.user_id,
        status_text: "",
    });
    assert.equal(compose_ui.compute_placeholder_text(opts), i18n.t("Message Alice"));

    // Group PM
    opts.private_message_recipient = "alice@zulip.com,bob@zulip.com";
    assert.equal(compose_ui.compute_placeholder_text(opts), i18n.t("Message Alice, Bob"));
});

run_test("quote_and_reply", (override) => {
    const selected_message = {
        type: "stream",
        stream: "devel",
        topic: "python",
        sender_full_name: "Steve Stephenson",
        sender_id: 90,
    };
    hash_util.by_conversation_and_time_uri = () =>
        "https://chat.zulip.org/#narrow/stream/92-learning/topic/Tornado";
    override(message_lists.current, "selected_message", () => selected_message);
    override(message_lists.current, "selected_id", () => 100);

    let success_function;
    override(channel, "get", (opts) => {
        success_function = opts.success;
    });

    $("#compose-textarea").val = function (...args) {
        if (args.length === 0) {
            return this.value || "";
        }
        [this.value] = args;
        if (args[0]) {
            this.pos = args[0].length;
        }
        return this;
    };

    $("#compose-textarea").caret = function (arg) {
        if (typeof arg === "number") {
            this.pos = arg;
            return this;
        }
        if (arg) {
            const insert_pos = this.pos;
            const before = this.val().slice(0, this.pos);
            const after = this.val().slice(this.pos);
            this.val(before + arg + after);
            // the val() we're using within this function will break the value of pos, resetting it to the end,
            // so we make sure to correct this
            this.pos = insert_pos + arg.length;
            return this;
        }
        return this.pos;
    };

    function set_compose_content_with_caret(content) {
        const caret_position = content.indexOf("%");
        content = content.slice(0, caret_position) + content.slice(caret_position + 1); // remove the "%"
        $("#compose-textarea").val(content);
        $("#compose-textarea").caret(caret_position);
        $("#compose-textarea").trigger("focus");
    }
    function get_compose_content_with_caret() {
        const caret_position = $("#compose-textarea").caret();
        const content =
            $("#compose-textarea").val().slice(0, caret_position) +
            "%" +
            $("#compose-textarea").val().slice(caret_position); // insert the "%"
        return content;
    }

    set_compose_content_with_caret("hello %there"); // "%" is used to encode/display position of focus before change
    compose_actions.quote_and_reply();
    assert.equal(get_compose_content_with_caret(), "[Quoting…]\n%hello there");
    success_function({
        raw_content: "Testing caret position",
    });
    assert.equal(
        get_compose_content_with_caret(),
        "translated: @_**Steve Stephenson|90** [said](https://chat.zulip.org/#narrow/stream/92-learning/topic/Tornado):\n```quote\nTesting caret position\n```\nhello there%",
    );
});
