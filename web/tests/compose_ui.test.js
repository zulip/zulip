"use strict";

const {strict: assert} = require("assert");

const {$t} = require("./lib/i18n");
const {mock_esm, set_global, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");

const noop = () => {};

set_global("navigator", {});

const autosize = () => {};
autosize.update = () => {};
mock_esm("autosize", {default: autosize});

mock_esm("../src/message_lists", {
    current: {},
});

const compose_ui = zrequire("compose_ui");
const stream_data = zrequire("stream_data");
const people = zrequire("people");
const user_status = zrequire("user_status");
const hash_util = mock_esm("../src/hash_util");
const channel = mock_esm("../src/channel");
const compose_actions = zrequire("compose_actions");
const message_lists = zrequire("message_lists");
const text_field_edit = mock_esm("text-field-edit");

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
    const $widget = {};

    $widget.s = s;
    $widget[0] = "textarea";
    $widget.focused = false;

    $widget.caret = function (arg) {
        if (typeof arg === "number") {
            $widget.pos = arg;
            return this;
        }

        // Not used right now, but could be in future.
        // if (arg) {
        //     $widget.insert_pos = $widget.pos;
        //     $widget.insert_text = arg;
        //     const before = $widget.s.slice(0, $widget.pos);
        //     const after = $widget.s.slice($widget.pos);
        //     $widget.s = before + arg + after;
        //     $widget.pos += arg.length;
        //     return this;
        // }

        return $widget.pos;
    };

    $widget.val = function (new_val) {
        /* istanbul ignore if */
        if (new_val) {
            $widget.s = new_val;
            return this;
        }
        return $widget.s;
    };

    return $widget;
}

run_test("autosize_textarea", ({override}) => {
    const textarea_autosized = {};

    override(autosize, "update", (textarea) => {
        textarea_autosized.textarea = textarea;
        textarea_autosized.autosized = true;
    });

    // Call autosize_textarea with an argument
    const container = "container-stub";
    compose_ui.autosize_textarea(container);
    assert.equal(textarea_autosized.textarea, container);
    assert.ok(textarea_autosized.autosized);
});

run_test("insert_syntax_and_focus", ({override}) => {
    $("#compose-textarea").val("xyz ");
    $("#compose-textarea").caret = () => 4;
    $("#compose-textarea")[0] = "compose-textarea";
    // Since we are using a third party library, we just
    // need to ensure it is being called with the right params.
    override(text_field_edit, "insert", (elt, syntax) => {
        assert.equal(elt, "compose-textarea");
        assert.equal(syntax, ":octopus: ");
    });
    compose_ui.insert_syntax_and_focus(":octopus:");
});

run_test("smart_insert", ({override}) => {
    let $textbox = make_textbox("abc");
    $textbox.caret(4);
    function override_with_expected_syntax(expected_syntax) {
        override(text_field_edit, "insert", (elt, syntax) => {
            assert.equal(elt, "textarea");
            assert.equal(syntax, expected_syntax);
        });
    }
    override_with_expected_syntax(" :smile: ");
    compose_ui.smart_insert_inline($textbox, ":smile:");

    override_with_expected_syntax(" :airplane: ");
    compose_ui.smart_insert_inline($textbox, ":airplane:");

    $textbox.caret(0);
    override_with_expected_syntax(":octopus: ");
    compose_ui.smart_insert_inline($textbox, ":octopus:");

    $textbox.caret($textbox.val().length);
    override_with_expected_syntax(" :heart: ");
    compose_ui.smart_insert_inline($textbox, ":heart:");

    // Test handling of spaces for ```quote
    $textbox = make_textbox("");
    $textbox.caret(0);
    override_with_expected_syntax("```quote\nquoted message\n```\n\n");
    compose_ui.smart_insert_block($textbox, "```quote\nquoted message\n```");

    $textbox = make_textbox("");
    $textbox.caret(0);
    override_with_expected_syntax("translated: [Quoting…]\n\n");
    compose_ui.smart_insert_block($textbox, "translated: [Quoting…]");

    $textbox = make_textbox("abc");
    $textbox.caret(3);
    override_with_expected_syntax("\n\n test with space\n\n");
    compose_ui.smart_insert_block($textbox, " test with space");

    // Note that we don't have any special logic for strings that are
    // already surrounded by spaces, since we are usually inserting things
    // like emojis and file links.
});

run_test("replace_syntax", ({override}) => {
    const $textbox = make_textbox("aBca$$");
    $textbox.caret(2);
    override(text_field_edit, "replace", (elt, old_syntax, new_syntax) => {
        assert.equal(elt, "textarea");
        assert.equal(old_syntax, "a");
        assert.equal(new_syntax(), "A");
    });
    let prev_caret = $textbox.caret();
    compose_ui.replace_syntax("a", "A", $textbox);
    assert.equal(prev_caret, $textbox.caret());

    override(text_field_edit, "replace", (elt, old_syntax, new_syntax) => {
        assert.equal(elt, "textarea");
        assert.equal(old_syntax, "Bca");
        assert.equal(new_syntax(), "$$\\pi$$");
    });

    // Verify we correctly handle `$`s in the replacement syntax
    // and that on replacing with a different length string, the
    // cursor is shifted accordingly as expected
    $textbox.caret(5);
    prev_caret = $textbox.caret();
    compose_ui.replace_syntax("Bca", "$$\\pi$$", $textbox);
    assert.equal(prev_caret + "$$\\pi$$".length - "Bca".length, $textbox.caret());
});

run_test("compute_placeholder_text", () => {
    let opts = {
        message_type: "stream",
        stream_id: "",
        topic: "",
        private_message_recipient: "",
    };

    // Stream narrows
    assert.equal(
        compose_ui.compute_placeholder_text(opts),
        $t({defaultMessage: "Compose your message here"}),
    );

    const stream_all = {
        subscribed: true,
        name: "all",
        stream_id: 2,
    };
    stream_data.add_sub(stream_all);
    opts.stream_id = stream_all.stream_id;
    assert.equal(compose_ui.compute_placeholder_text(opts), $t({defaultMessage: "Message #all"}));

    opts.topic = "Test";
    assert.equal(
        compose_ui.compute_placeholder_text(opts),
        $t({defaultMessage: "Message #all > Test"}),
    );

    // direct message narrows
    opts = {
        message_type: "private",
        stream_id: "",
        topic: "",
        private_message_recipient: "",
    };
    assert.equal(
        compose_ui.compute_placeholder_text(opts),
        $t({defaultMessage: "Compose your message here"}),
    );

    opts.private_message_recipient = "bob@zulip.com";
    user_status.set_status_text({
        user_id: bob.user_id,
        status_text: "out to lunch",
    });
    assert.equal(
        compose_ui.compute_placeholder_text(opts),
        $t({defaultMessage: "Message Bob (out to lunch)"}),
    );

    opts.private_message_recipient = "alice@zulip.com";
    user_status.set_status_text({
        user_id: alice.user_id,
        status_text: "",
    });
    assert.equal(compose_ui.compute_placeholder_text(opts), $t({defaultMessage: "Message Alice"}));

    // group direct message
    opts.private_message_recipient = "alice@zulip.com,bob@zulip.com";
    assert.equal(
        compose_ui.compute_placeholder_text(opts),
        $t({defaultMessage: "Message Alice, Bob"}),
    );
});

run_test("quote_and_reply", ({override, override_rewire}) => {
    const devel_stream = {
        subscribed: false,
        name: "devel",
        stream_id: 20,
    };

    const selected_message = {
        type: "stream",
        stream_id: devel_stream.stream_id,
        topic: "python",
        sender_full_name: "Steve Stephenson",
        sender_id: 90,
    };

    override(
        hash_util,
        "by_conversation_and_time_url",
        () => "https://chat.zulip.org/#narrow/stream/92-learning/topic/Tornado",
    );

    override(message_lists.current, "selected_message", () => selected_message);
    override(message_lists.current, "selected_id", () => 100);

    let success_function;
    override(channel, "get", (opts) => {
        success_function = opts.success;
    });

    // zjquery does not simulate caret handling, so we provide
    // our own versions of val() and caret()
    let textarea_val = "";
    let textarea_caret_pos;

    $("#compose-textarea").val = function () {
        return textarea_val;
    };

    $("#compose-textarea").caret = function (arg) {
        if (arg === undefined) {
            return textarea_caret_pos;
        }
        if (typeof arg === "number") {
            textarea_caret_pos = arg;
            return this;
        }

        /* This next block of mocking code is currently unused, but
           is preserved, since it may be useful in the future. */
        /* istanbul ignore next */
        {
            if (typeof arg !== "string") {
                console.info(arg);
                throw new Error("We expected the actual code to pass in a string.");
            }

            const before = textarea_val.slice(0, textarea_caret_pos);
            const after = textarea_val.slice(textarea_caret_pos);

            textarea_val = before + arg + after;
            textarea_caret_pos += arg.length;
            return this;
        }
    };
    $("#compose-textarea")[0] = "compose-textarea";
    override(text_field_edit, "insert", (elt, syntax) => {
        assert.equal(elt, "compose-textarea");
        assert.equal(syntax, "\n\ntranslated: [Quoting…]\n\n");
    });

    function set_compose_content_with_caret(content) {
        const caret_position = content.indexOf("%");
        content = content.slice(0, caret_position) + content.slice(caret_position + 1); // remove the "%"
        textarea_val = content;
        textarea_caret_pos = caret_position;
        $("#compose-textarea").trigger("focus");
    }

    function reset_test_state() {
        // Reset `raw_content` property of `selected_message`.
        delete selected_message.raw_content;

        // Reset compose-box state.
        textarea_val = "";
        textarea_caret_pos = 0;
        $("#compose-textarea").trigger("blur");
    }

    function override_with_quote_text(quote_text) {
        override(text_field_edit, "replace", (elt, old_syntax, new_syntax) => {
            assert.equal(elt, "compose-textarea");
            assert.equal(old_syntax, "translated: [Quoting…]");
            assert.equal(
                new_syntax(),
                "translated: @_**Steve Stephenson|90** [said](https://chat.zulip.org/#narrow/stream/92-learning/topic/Tornado):\n" +
                    "```quote\n" +
                    `${quote_text}\n` +
                    "```",
            );
        });
    }
    let quote_text = "Testing caret position";
    override_with_quote_text(quote_text);
    set_compose_content_with_caret("hello %there"); // "%" is used to encode/display position of focus before change
    compose_actions.quote_and_reply();

    success_function({
        raw_content: quote_text,
    });

    reset_test_state();

    // If the caret is initially positioned at 0, it should not
    // add newlines before the quoted message.
    override(text_field_edit, "insert", (elt, syntax) => {
        assert.equal(elt, "compose-textarea");
        assert.equal(syntax, "translated: [Quoting…]\n\n");
    });
    set_compose_content_with_caret("%hello there");
    compose_actions.quote_and_reply();

    quote_text = "Testing with caret initially positioned at 0.";
    override_with_quote_text(quote_text);
    success_function({
        raw_content: quote_text,
    });

    override_rewire(compose_actions, "respond_to_message", () => {
        // Reset compose state to replicate the re-opening of compose-box.
        textarea_val = "";
        textarea_caret_pos = 0;
        $("#compose-textarea").trigger("focus");
    });

    reset_test_state();

    // If the compose-box is close, or open with no content while
    // quoting a message, the quoted message should be placed
    // at the beginning of compose-box.
    compose_actions.quote_and_reply();

    quote_text = "Testing with compose-box closed initially.";
    override_with_quote_text(quote_text);
    success_function({
        raw_content: quote_text,
    });

    reset_test_state();

    // If the compose-box is already open while quoting a message,
    // but contains content like `\n\n  \n` (only whitespaces and
    // newlines), the compose-box should re-open and thus the quoted
    // message should start from the beginning of compose-box.
    set_compose_content_with_caret("  \n\n \n %");
    compose_actions.quote_and_reply();

    quote_text = "Testing with compose-box containing whitespaces and newlines only.";
    override_with_quote_text(quote_text);
    success_function({
        raw_content: quote_text,
    });

    reset_test_state();

    // When there is already 1 newline before and after the caret,
    // only 1 newline is added before and after the quoted message.
    override(text_field_edit, "insert", (elt, syntax) => {
        assert.equal(elt, "compose-textarea");
        assert.equal(syntax, "\ntranslated: [Quoting…]\n");
    });
    set_compose_content_with_caret("1st line\n%\n2nd line");
    compose_actions.quote_and_reply();

    quote_text = "Testing with caret on a new line between 2 lines of text.";
    override_with_quote_text(quote_text);
    success_function({
        raw_content: quote_text,
    });

    reset_test_state();

    // When there are many (>=2) newlines before and after the caret,
    // no newline is added before or after the quoted message.
    override(text_field_edit, "insert", (elt, syntax) => {
        assert.equal(elt, "compose-textarea");
        assert.equal(syntax, "translated: [Quoting…]");
    });
    set_compose_content_with_caret("lots of\n\n\n\n%\n\n\nnewlines");
    compose_actions.quote_and_reply();

    quote_text = "Testing with caret on a new line between many empty newlines.";
    override_with_quote_text(quote_text);
    success_function({
        raw_content: quote_text,
    });
});

run_test("set_compose_box_top", () => {
    let compose_top = "";
    $("#compose").css = (arg, val) => {
        assert.equal(arg, "top");
        compose_top = val;
    };

    $("#navbar-fixed-container").set_height(50);
    compose_ui.set_compose_box_top(true);
    assert.equal(compose_top, "50px");

    compose_ui.set_compose_box_top(false);
    assert.equal(compose_top, "");
});

run_test("test_compose_height_changes", ({override, override_rewire}) => {
    let autosize_destroyed = false;
    override(autosize, "destroy", () => {
        autosize_destroyed = true;
    });

    let compose_box_top_set = false;
    override_rewire(compose_ui, "set_compose_box_top", (set_top) => {
        compose_box_top_set = set_top;
    });

    compose_ui.make_compose_box_full_size();
    assert.ok($("#compose").hasClass("compose-fullscreen"));
    assert.ok(compose_ui.is_full_size());
    assert.ok(autosize_destroyed);
    assert.ok(compose_box_top_set);

    compose_ui.make_compose_box_original_size();
    assert.ok(!$("#compose").hasClass("compose-fullscreen"));
    assert.ok(!compose_ui.is_full_size());
    assert.ok(!compose_box_top_set);
});

run_test("format_text", ({override}) => {
    let set_text = "";
    let wrap_selection_called = false;
    let wrap_syntax = "";

    override(text_field_edit, "set", (_field, text) => {
        set_text = text;
    });
    override(text_field_edit, "wrapSelection", (_field, syntax) => {
        wrap_selection_called = true;
        wrap_syntax = syntax;
    });

    function reset_state() {
        set_text = "";
        wrap_selection_called = false;
        wrap_syntax = "";
    }

    const $textarea = $("#compose-textarea");
    $textarea.get = () => ({
        setSelectionRange() {},
    });

    function init_textarea(val, range) {
        $textarea.val = () => val;
        $textarea.range = () => range;
    }

    const italic_syntax = "*";
    const bold_syntax = "**";

    // Bold selected text
    reset_state();
    init_textarea("abc", {
        start: 0,
        end: 3,
        text: "abc",
        length: 3,
    });
    compose_ui.format_text($textarea, "bold");
    assert.equal(set_text, "");
    assert.equal(wrap_selection_called, true);
    assert.equal(wrap_syntax, bold_syntax);

    // Undo bold selected text, syntax not selected
    reset_state();
    init_textarea("**abc**", {
        start: 2,
        end: 5,
        text: "abc",
        length: 7,
    });
    compose_ui.format_text($textarea, "bold");
    assert.equal(set_text, "abc");
    assert.equal(wrap_selection_called, false);

    // Undo bold selected text, syntax selected
    reset_state();
    init_textarea("**abc**", {
        start: 0,
        end: 7,
        text: "**abc**",
        length: 7,
    });
    compose_ui.format_text($textarea, "bold");
    assert.equal(set_text, "abc");
    assert.equal(wrap_selection_called, false);

    // Italic selected text
    reset_state();
    init_textarea("abc", {
        start: 0,
        end: 3,
        text: "abc",
        length: 3,
    });
    compose_ui.format_text($textarea, "italic");
    assert.equal(set_text, "");
    assert.equal(wrap_selection_called, true);
    assert.equal(wrap_syntax, italic_syntax);

    // Undo italic selected text, syntax not selected
    reset_state();
    init_textarea("*abc*", {
        start: 1,
        end: 4,
        text: "abc",
        length: 3,
    });
    compose_ui.format_text($textarea, "italic");
    assert.equal(set_text, "abc");
    assert.equal(wrap_selection_called, false);

    // Undo italic selected text, syntax selected
    reset_state();
    init_textarea("*abc*", {
        start: 0,
        end: 5,
        text: "*abc*",
        length: 5,
    });
    compose_ui.format_text($textarea, "italic");
    assert.equal(set_text, "abc");
    assert.equal(wrap_selection_called, false);

    // Undo bold selected text, text is both italic and bold, syntax not selected.
    reset_state();
    init_textarea("***abc***", {
        start: 3,
        end: 6,
        text: "abc",
        length: 3,
    });
    compose_ui.format_text($textarea, "bold");
    assert.equal(set_text, "*abc*");
    assert.equal(wrap_selection_called, false);

    // Undo bold selected text, text is both italic and bold, syntax selected.
    reset_state();
    init_textarea("***abc***", {
        start: 0,
        end: 9,
        text: "***abc***",
        length: 9,
    });
    compose_ui.format_text($textarea, "bold");
    assert.equal(set_text, "*abc*");
    assert.equal(wrap_selection_called, false);

    // Undo italic selected text, text is both italic and bold, syntax not selected.
    reset_state();
    init_textarea("***abc***", {
        start: 3,
        end: 6,
        text: "abc",
        length: 3,
    });
    compose_ui.format_text($textarea, "italic");
    assert.equal(set_text, "**abc**");
    assert.equal(wrap_selection_called, false);

    // Undo italic selected text, text is both italic and bold, syntax selected.
    reset_state();
    init_textarea("***abc***", {
        start: 0,
        end: 9,
        text: "***abc***",
        length: 9,
    });
    compose_ui.format_text($textarea, "italic");
    assert.equal(set_text, "**abc**");
    assert.equal(wrap_selection_called, false);
});

run_test("markdown_shortcuts", ({override_rewire}) => {
    let format_text_type;
    override_rewire(compose_ui, "format_text", (_$textarea, type) => {
        format_text_type = type;
    });

    const event = {
        key: "b",
        target: {
            id: "compose-textarea",
        },
        stopPropagation: noop,
        preventDefault: noop,
    };

    function all_markdown_test(isCtrl, isCmd) {
        // Test bold:
        // Mac env = Cmd+b
        // Windows/Linux = Ctrl+b
        event.key = "b";
        event.ctrlKey = isCtrl;
        event.metaKey = isCmd;
        compose_ui.handle_keydown(event, $("#compose-textarea"));
        assert.equal(format_text_type, "bold");
        format_text_type = undefined;

        // Test italic:
        // Mac = Cmd+I
        // Windows/Linux = Ctrl+I
        // We use event.key = "I" to emulate user using Caps Lock key.
        event.key = "I";
        event.shiftKey = false;
        compose_ui.handle_keydown(event, $("#compose-textarea"));
        assert.equal(format_text_type, "italic");
        format_text_type = undefined;

        // Test link insertion:
        // Mac = Cmd+Shift+L
        // Windows/Linux = Ctrl+Shift+L
        event.key = "l";
        event.shiftKey = true;
        compose_ui.handle_keydown(event, $("#compose-textarea"));
        assert.equal(format_text_type, "link");
        format_text_type = undefined;
    }

    // This function cross tests the Cmd/Ctrl + Markdown shortcuts in
    // Mac and Linux/Windows environments.  So in short, this tests
    // that e.g. Cmd+B should be ignored on Linux/Windows and Ctrl+B
    // should be ignored on Mac.
    function os_specific_markdown_test(isCtrl, isCmd) {
        event.ctrlKey = isCtrl;
        event.metaKey = isCmd;

        event.key = "b";
        compose_ui.handle_keydown(event, $("#compose-textarea"));
        assert.equal(format_text_type, undefined);

        event.key = "i";
        event.shiftKey = false;
        compose_ui.handle_keydown(event, $("#compose-textarea"));
        assert.equal(format_text_type, undefined);

        event.key = "l";
        event.shiftKey = true;
        compose_ui.handle_keydown(event, $("#compose-textarea"));
        assert.equal(format_text_type, undefined);
    }

    // These keyboard shortcuts differ as to what key one should use
    // on MacOS vs. other platforms: Cmd (Mac) vs. Ctrl (non-Mac).

    // Default (Linux/Windows) userAgent tests:
    navigator.platform = "";

    // Check all the Ctrl + Markdown shortcuts work correctly
    all_markdown_test(true, false);
    // The Cmd + Markdown shortcuts should do nothing on Linux/Windows
    os_specific_markdown_test(false, true);

    // Setting following platform to test in mac env
    navigator.platform = "MacIntel";

    // Mac userAgent tests:
    // The Ctrl + Markdown shortcuts should do nothing on mac
    os_specific_markdown_test(true, false);
    // Check all the Cmd + Markdown shortcuts work correctly
    all_markdown_test(false, true);

    // Reset userAgent
    navigator.userAgent = "";
});

run_test("right-to-left", () => {
    const $textarea = $("#compose-textarea");

    const event = {
        key: "A",
    };

    assert.equal($textarea.hasClass("rtl"), false);

    $textarea.val("```quote\nمرحبا");
    compose_ui.handle_keyup(event, $("#compose-textarea"));

    assert.equal($textarea.hasClass("rtl"), true);

    $textarea.val("```quote foo");
    compose_ui.handle_keyup(event, $textarea);

    assert.equal($textarea.hasClass("rtl"), false);
});

const get_focus_area = compose_ui._get_focus_area;
run_test("get_focus_area", () => {
    assert.equal(get_focus_area("private", {}), "#private_message_recipient");
    assert.equal(
        get_focus_area("private", {
            private_message_recipient: "bob@example.com",
        }),
        "#compose-textarea",
    );
    assert.equal(get_focus_area("stream", {}), "#compose_select_recipient_widget_wrapper");
    assert.equal(
        get_focus_area("stream", {stream_name: "fun", stream_id: 4}),
        "#stream_message_recipient_topic",
    );
    assert.equal(
        get_focus_area("stream", {stream_name: "fun", stream_id: 4, topic: "more"}),
        "#compose-textarea",
    );
    assert.equal(
        get_focus_area("stream", {
            stream_id: 4,
            topic: "more",
            trigger: "new topic button",
        }),
        "#stream_message_recipient_topic",
    );
});
