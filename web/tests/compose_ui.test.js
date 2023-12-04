"use strict";

const {strict: assert} = require("assert");

const {$t} = require("./lib/i18n");
const {mock_esm, set_global, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");
const {page_params} = require("./lib/zpage_params");

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
const compose_reply = zrequire("compose_reply");
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

    $widget.trigger = noop;

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
    $("textarea#compose-textarea").val("xyz ");
    $("textarea#compose-textarea").caret = () => 4;
    $("textarea#compose-textarea")[0] = "compose-textarea";
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
        stream_id: undefined,
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
        stream_id: undefined,
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
        $t({defaultMessage: "Message Alice and Bob"}),
    );

    alice.is_guest = true;
    page_params.realm_enable_guest_user_indicator = true;
    assert.equal(
        compose_ui.compute_placeholder_text(opts),
        $t({defaultMessage: "Message translated: Alice (guest) and Bob"}),
    );

    page_params.realm_enable_guest_user_indicator = false;
    assert.equal(
        compose_ui.compute_placeholder_text(opts),
        $t({defaultMessage: "Message Alice and Bob"}),
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

    override(message_lists.current, "get", (id) => (id === 100 ? selected_message : undefined));

    let success_function;
    override(channel, "get", (opts) => {
        success_function = opts.success;
    });

    // zjquery does not simulate caret handling, so we provide
    // our own versions of val() and caret()
    let textarea_val = "";
    let textarea_caret_pos;

    $("textarea#compose-textarea").val = function () {
        return textarea_val;
    };

    $("textarea#compose-textarea").caret = function (arg) {
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
    $("textarea#compose-textarea")[0] = "compose-textarea";
    $("textarea#compose-textarea").attr("id", "compose-textarea");
    override(text_field_edit, "insert", (elt, syntax) => {
        assert.equal(elt, "compose-textarea");
        assert.equal(syntax, "\n\ntranslated: [Quoting…]\n\n");
    });

    function set_compose_content_with_caret(content) {
        const caret_position = content.indexOf("%");
        content = content.slice(0, caret_position) + content.slice(caret_position + 1); // remove the "%"
        textarea_val = content;
        textarea_caret_pos = caret_position;
        $("textarea#compose-textarea").trigger("focus");
    }

    function reset_test_state() {
        // Reset `raw_content` property of `selected_message`.
        delete selected_message.raw_content;

        // Reset compose-box state.
        textarea_val = "";
        textarea_caret_pos = 0;
        $("textarea#compose-textarea").trigger("blur");
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
    compose_reply.quote_and_reply({message_id: 100});

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
    compose_reply.quote_and_reply({message_id: 100});

    quote_text = "Testing with caret initially positioned at 0.";
    override_with_quote_text(quote_text);
    success_function({
        raw_content: quote_text,
    });

    override_rewire(compose_reply, "respond_to_message", () => {
        // Reset compose state to replicate the re-opening of compose-box.
        textarea_val = "";
        textarea_caret_pos = 0;
        $("textarea#compose-textarea").trigger("focus");
    });

    reset_test_state();

    // If the compose-box is close, or open with no content while
    // quoting a message, the quoted message should be placed
    // at the beginning of compose-box.
    override(message_lists.current, "selected_id", () => 100);
    compose_reply.quote_and_reply({});

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
    compose_reply.quote_and_reply({});

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
    compose_reply.quote_and_reply({});

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
    compose_reply.quote_and_reply({});

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

let set_text = "";
let wrap_selection_called = false;
let wrap_syntax_start = "";
let wrap_syntax_end = "";

function reset_state() {
    set_text = "";
    wrap_selection_called = false;
    wrap_syntax_start = "";
    wrap_syntax_end = "";
}

const $textarea = $("textarea#compose-textarea");
$textarea.get = () => ({
    setSelectionRange(start, end) {
        $textarea.range = () => ({
            start,
            end,
            text: $textarea.val().slice(start, end),
            length: end - start,
        });
    },
});

function init_textarea(val, range) {
    $textarea.val = () => val;
    $textarea.range = () => range;
}

run_test("format_text - bold and italic", ({override}) => {
    override(text_field_edit, "set", (_field, text) => {
        set_text = text;
    });
    override(text_field_edit, "wrapSelection", (_field, syntax_start, syntax_end) => {
        wrap_selection_called = true;
        wrap_syntax_start = syntax_start;
        wrap_syntax_end = syntax_end || syntax_start;
    });

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
    assert.equal(wrap_syntax_start, bold_syntax);
    assert.equal(wrap_syntax_end, bold_syntax);

    // Undo bold selected text, syntax not selected
    reset_state();
    init_textarea("**abc**", {
        start: 2,
        end: 5,
        text: "abc",
        length: 3,
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
    assert.equal(wrap_syntax_start, italic_syntax);
    assert.equal(wrap_syntax_end, italic_syntax);

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

    // Test bulleted list addition
    reset_state();
    init_textarea("first_item\nsecond_item", {
        start: 0,
        end: 22,
        text: "first_item\nsecond_item",
        length: 22,
    });
    compose_ui.format_text($textarea, "bulleted");
    assert.equal(set_text, "- first_item\n- second_item");
    assert.equal(wrap_selection_called, false);

    // Test bulleted list addition with newline at start
    reset_state();
    init_textarea("\nfirst_item\nsecond_item", {
        start: 0,
        end: 23,
        text: "\nfirst_item\nsecond_item",
        length: 23,
    });
    compose_ui.format_text($textarea, "bulleted");
    assert.equal(set_text, "- \n- first_item\n- second_item");
    assert.equal(wrap_selection_called, false);

    // Test bulleted list removal
    reset_state();
    init_textarea("- first_item\n- second_item", {
        start: 0,
        end: 26,
        text: "- first_item\n- second_item",
        length: 26,
    });
    compose_ui.format_text($textarea, "bulleted");
    assert.equal(set_text, "first_item\nsecond_item");
    assert.equal(wrap_selection_called, false);

    // Test bulleted list removal with *s
    reset_state();
    init_textarea("* first_item\n* second_item", {
        start: 0,
        end: 26,
        text: "* first_item\n* second_item",
        length: 26,
    });
    compose_ui.format_text($textarea, "bulleted");
    assert.equal(set_text, "first_item\nsecond_item");
    assert.equal(wrap_selection_called, false);

    // Test numbered list toggling on
    reset_state();
    init_textarea("first_item\nsecond_item", {
        start: 0,
        end: 22,
        text: "first_item\nsecond_item",
        length: 22,
    });
    compose_ui.format_text($textarea, "numbered");
    assert.equal(set_text, "1. first_item\n2. second_item");
    assert.equal(wrap_selection_called, false);

    // Test numbered list toggling off
    reset_state();
    init_textarea("1. first_item\n2. second_item", {
        start: 0,
        end: 28,
        text: "1. first_item\n2. second_item",
        length: 28,
    });
    compose_ui.format_text($textarea, "numbered");
    assert.equal(set_text, "first_item\nsecond_item");
    assert.equal(wrap_selection_called, false);

    // Test numbered list toggling with newline at end
    reset_state();
    init_textarea("first_item\nsecond_item\n", {
        start: 0,
        end: 23,
        text: "first_item\nsecond_item\n",
        length: 23,
    });
    compose_ui.format_text($textarea, "numbered");
    assert.equal(set_text, "1. first_item\n2. second_item\n");
    assert.equal(wrap_selection_called, false);

    // Test numbered list toggling on with partially selected lines
    reset_state();
    init_textarea("before_first\nfirst_item\nsecond_item\nafter_last", {
        start: 15,
        end: 33,
        text: "rst_item\nsecond_it",
        length: 18,
    });
    compose_ui.format_text($textarea, "numbered");
    // Notice the blank lines inserted right before and after the list to visually demarcate it.
    // Had the blank line after `second_item` not been inserted, `after_last` would have been
    // (wrongly) indented as part of the list's last item too.
    assert.equal(set_text, "before_first\n\n1. first_item\n2. second_item\n\nafter_last");
    assert.equal(wrap_selection_called, false);
});

run_test("format_text - strikethrough", ({override}) => {
    override(text_field_edit, "set", (_field, text) => {
        set_text = text;
    });
    override(text_field_edit, "wrapSelection", (_field, syntax_start, syntax_end) => {
        wrap_selection_called = true;
        wrap_syntax_start = syntax_start;
        wrap_syntax_end = syntax_end;
    });

    const strikethrough_syntax = "~~";

    // Strikethrough selected text
    reset_state();
    compose_ui.format_text($textarea, "strikethrough");
    assert.equal(set_text, "");
    assert.equal(wrap_selection_called, true);
    assert.equal(wrap_syntax_start, strikethrough_syntax);
    assert.equal(wrap_syntax_end, strikethrough_syntax);

    // Undo strikethrough selected text, syntax not selected
    reset_state();
    init_textarea("~~abc~~", {
        start: 2,
        end: 5,
        text: "abc",
        length: 3,
    });
    compose_ui.format_text($textarea, "strikethrough");
    assert.equal(set_text, "abc");
    assert.equal(wrap_selection_called, false);

    // Undo strikethrough selected text, syntax selected
    reset_state();
    init_textarea("~~abc~~", {
        start: 0,
        end: 7,
        text: "~~abc~~",
        length: 7,
    });
    compose_ui.format_text($textarea, "strikethrough");
    assert.equal(set_text, "abc");
});

run_test("format_text - latex", ({override}) => {
    override(text_field_edit, "set", (_field, text) => {
        set_text = text;
    });
    override(text_field_edit, "wrapSelection", (_field, syntax_start, syntax_end) => {
        wrap_selection_called = true;
        wrap_syntax_start = syntax_start;
        wrap_syntax_end = syntax_end;
    });

    const latex_syntax = "$$";
    const block_latex_syntax_start = "```math\n";
    const block_latex_syntax_end = "\n```";

    // Latex selected text
    reset_state();
    init_textarea("abc", {
        start: 0,
        end: 3,
        text: "abc",
        length: 3,
    });
    compose_ui.format_text($textarea, "latex");
    assert.equal(set_text, "");
    assert.equal(wrap_selection_called, true);
    assert.equal(wrap_syntax_start, latex_syntax);
    assert.equal(wrap_syntax_end, latex_syntax);

    reset_state();
    init_textarea("Before\nBefore this should\nbe math After\nAfter", {
        start: 14,
        end: 33,
        text: "this should\nbe math",
        length: 19,
    });
    compose_ui.format_text($textarea, "latex");
    assert.equal(set_text, "");
    assert.equal(wrap_selection_called, true);
    assert.equal(wrap_syntax_start, "\n" + block_latex_syntax_start);
    assert.equal(wrap_syntax_end, block_latex_syntax_end + "\n");

    reset_state();
    init_textarea("abc\ndef", {
        start: 0,
        end: 7,
        text: "abc\ndef",
        length: 7,
    });
    compose_ui.format_text($textarea, "latex");
    assert.equal(set_text, "");
    assert.equal(wrap_selection_called, true);
    assert.equal(wrap_syntax_start, block_latex_syntax_start);
    assert.equal(wrap_syntax_end, block_latex_syntax_end);

    // No text selected
    reset_state();
    init_textarea("", {
        start: 0,
        end: 0,
        text: "",
        length: 0,
    });
    compose_ui.format_text($textarea, "latex");
    assert.equal(set_text, "");
    assert.equal(wrap_selection_called, true);

    // Undo latex selected text, syntax not selected
    reset_state();
    init_textarea("$$abc$$", {
        start: 2,
        end: 5,
        text: "abc",
        length: 3,
    });
    compose_ui.format_text($textarea, "latex");
    assert.equal(set_text, "abc");
    assert.equal(wrap_selection_called, false);

    reset_state();
    init_textarea("```math\nabc\ndef\n```", {
        start: 8,
        end: 15,
        text: "abc\ndef",
        length: 7,
    });
    compose_ui.format_text($textarea, "latex");
    assert.equal(set_text, "abc\ndef");
    assert.equal(wrap_selection_called, false);

    reset_state();
    init_textarea("abc\n```math\nde\nf\n```\nghi", {
        start: 12,
        end: 16,
        text: "de\nf",
        length: 4,
    });
    compose_ui.format_text($textarea, "latex");
    assert.equal(set_text, "abc\nde\nf\nghi");
    assert.equal(wrap_selection_called, false);

    // Undo latex selected text, syntax selected
    reset_state();
    init_textarea("$$abc$$", {
        start: 0,
        end: 7,
        text: "$$abc$$",
        length: 7,
    });
    compose_ui.format_text($textarea, "latex");
    assert.equal(set_text, "abc");
    assert.equal(wrap_selection_called, false);

    reset_state();
    init_textarea("```math\nabc\ndef\n```", {
        start: 0,
        end: 19,
        text: "```math\nabc\ndef\n```",
        length: 19,
    });
    compose_ui.format_text($textarea, "latex");
    assert.equal(set_text, "abc\ndef");
    assert.equal(wrap_selection_called, false);

    reset_state();
    init_textarea("abc\n```math\nde\nf\n```\nghi", {
        start: 4,
        end: 20,
        text: "```math\nde\nf\n```",
        length: 16,
    });
    compose_ui.format_text($textarea, "latex");
    assert.equal(set_text, "abc\nde\nf\nghi");
    assert.equal(wrap_selection_called, false);
});

run_test("format_text - code", ({override}) => {
    override(text_field_edit, "set", (_field, text) => {
        set_text = text;
    });
    override(text_field_edit, "wrapSelection", (_field, syntax_start, syntax_end) => {
        wrap_selection_called = true;
        wrap_syntax_start = syntax_start;
        wrap_syntax_end = syntax_end;
    });

    const code_syntax = "`";
    const code_block_syntax_start = "```\n";
    const code_block_syntax_end = "\n```";

    // Code selected text
    reset_state();
    init_textarea("abc def", {
        start: 0,
        end: 3,
        text: "abc",
        length: 3,
    });
    compose_ui.format_text($textarea, "code");
    assert.equal(set_text, "");
    assert.equal(wrap_selection_called, true);
    assert.equal(wrap_syntax_start, code_syntax);
    assert.equal(wrap_syntax_end, code_syntax);

    reset_state();
    init_textarea("abc", {
        start: 0,
        end: 3,
        text: "abc",
        length: 3,
    });
    compose_ui.format_text($textarea, "code");
    assert.equal(set_text, "");
    assert.equal(wrap_selection_called, true);
    assert.equal(wrap_syntax_start, code_syntax);
    assert.equal(wrap_syntax_end, code_syntax);

    reset_state();
    init_textarea("abc\ndef\nghi\njkl", {
        start: 4,
        end: 11,
        text: "def\nghi",
        length: 7,
    });
    compose_ui.format_text($textarea, "code");
    assert.equal(set_text, "");
    assert.equal(wrap_selection_called, true);
    assert.equal(wrap_syntax_start, code_block_syntax_start);
    assert.equal(wrap_syntax_end, code_block_syntax_end);

    // No text selected
    reset_state();
    init_textarea("", {
        start: 0,
        end: 0,
        text: "",
        length: 0,
    });
    compose_ui.format_text($textarea, "code");
    assert.equal(set_text, "");
    assert.equal(wrap_selection_called, true);

    // Undo code selected text, syntax not selected
    reset_state();
    init_textarea("`abc`", {
        start: 1,
        end: 4,
        text: "abc",
        length: 3,
    });
    compose_ui.format_text($textarea, "code");
    assert.equal(set_text, "abc");
    assert.equal(wrap_selection_called, false);

    reset_state();
    init_textarea("```\nabc\n```", {
        start: 4,
        end: 7,
        text: "abc",
        length: 3,
    });
    compose_ui.format_text($textarea, "code");
    assert.equal(set_text, "abc");
    assert.equal(wrap_selection_called, false);

    reset_state();
    init_textarea("abc\n```\ndef\n```\nghi", {
        start: 8,
        end: 11,
        text: "abc",
        length: 3,
    });
    compose_ui.format_text($textarea, "code");
    assert.equal(set_text, "abc\ndef\nghi");
    assert.equal(wrap_selection_called, false);

    // Undo code selected text, syntax selected
    reset_state();
    init_textarea("`abc` def", {
        start: 0,
        end: 5,
        text: "`abc`",
        length: 5,
    });
    compose_ui.format_text($textarea, "code");
    assert.equal(set_text, "abc def");
    assert.equal(wrap_selection_called, false);

    reset_state();
    init_textarea("```\nabc\ndef\n```", {
        start: 0,
        end: 15,
        text: "```\nabc\ndef\n```",
        length: 15,
    });
    compose_ui.format_text($textarea, "code");
    assert.equal(set_text, "abc\ndef");
    assert.equal(wrap_selection_called, false);

    reset_state();
    init_textarea("abc\n```\ndef\n```\nghi", {
        start: 3,
        end: 16,
        text: "\n```\ndef\n```\n",
        length: 13,
    });
    compose_ui.format_text($textarea, "code");
    assert.equal(set_text, "abc\ndef\nghi");
    assert.equal(wrap_selection_called, false);
});

run_test("format_text - quote", ({override}) => {
    override(text_field_edit, "set", (_field, text) => {
        set_text = text;
    });
    override(text_field_edit, "wrapSelection", (_field, syntax_start, syntax_end) => {
        wrap_selection_called = true;
        wrap_syntax_start = syntax_start;
        wrap_syntax_end = syntax_end;
    });

    const quote_syntax_start = "```quote\n";
    const quote_syntax_end = "\n```";

    // Quote selected text
    reset_state();
    init_textarea("abc", {
        start: 0,
        end: 3,
        text: "abc",
        length: 3,
    });
    compose_ui.format_text($textarea, "quote");
    assert.equal(set_text, "");
    assert.equal(wrap_selection_called, true);
    assert.equal(wrap_syntax_start, quote_syntax_start);
    assert.equal(wrap_syntax_end, quote_syntax_end);

    reset_state();
    init_textarea("abc\ndef\nghi", {
        start: 4,
        end: 7,
        text: "def",
        length: 3,
    });
    compose_ui.format_text($textarea, "quote");
    assert.equal(set_text, "");
    assert.equal(wrap_selection_called, true);
    assert.equal(wrap_syntax_start, quote_syntax_start);
    assert.equal(wrap_syntax_end, quote_syntax_end);

    // Undo quote selected text, syntax not selected
    reset_state();
    init_textarea("```quote\nabc\n```", {
        start: 9,
        end: 12,
        text: "abc",
        length: 3,
    });
    compose_ui.format_text($textarea, "quote");
    assert.equal(set_text, "abc");
    assert.equal(wrap_selection_called, false);

    reset_state();
    init_textarea("abc\n```quote\ndef\n```\nghi", {
        start: 13,
        end: 16,
        text: "abc",
        length: 3,
    });
    compose_ui.format_text($textarea, "quote");
    assert.equal(set_text, "abc\ndef\nghi");
    assert.equal(wrap_selection_called, false);

    // Undo quote selected text, syntax selected
    reset_state();
    init_textarea("```quote\nabc\n```", {
        start: 0,
        end: 16,
        text: "```quote\nabc\n```",
        length: 16,
    });
    compose_ui.format_text($textarea, "quote");
    assert.equal(set_text, "abc");
    assert.equal(wrap_selection_called, false);

    reset_state();
    init_textarea("abc\n```quote\ndef\n```\nghi", {
        start: 4,
        end: 20,
        text: "```quote\ndef\n```",
        length: 16,
    });
    compose_ui.format_text($textarea, "quote");
    assert.equal(set_text, "abc\ndef\nghi");
    assert.equal(wrap_selection_called, false);
});

run_test("format_text - spoiler", ({override}) => {
    override(text_field_edit, "set", (_field, text) => {
        set_text = text;
    });
    override(text_field_edit, "wrapSelection", (_field, syntax_start, syntax_end) => {
        wrap_selection_called = true;
        wrap_syntax_start = syntax_start;
        wrap_syntax_end = syntax_end;
    });

    const spoiler_syntax_start_with_header = "```spoiler Header\n";
    const spoiler_syntax_end = "\n```";

    // Spoiler selected text
    reset_state();
    init_textarea("abc", {
        start: 0,
        end: 3,
        text: "abc",
        length: 3,
    });
    compose_ui.format_text($textarea, "spoiler");
    assert.equal(set_text, "");
    assert.equal(wrap_selection_called, true);
    assert.equal(wrap_syntax_start, spoiler_syntax_start_with_header);
    assert.equal(wrap_syntax_end, spoiler_syntax_end);

    // Undo spoiler, header selected
    reset_state();
    init_textarea("```spoiler Header\nabc\n```", {
        start: 11,
        end: 17,
        text: "Header",
        length: 6,
    });
    compose_ui.format_text($textarea, "spoiler");
    assert.equal(set_text, "Header\nabc");
    assert.equal(wrap_selection_called, false);

    reset_state();
    init_textarea("abc\n```spoiler \ndef\n```\nghi", {
        start: 15,
        end: 15,
        text: "",
        length: 0,
    });
    compose_ui.format_text($textarea, "spoiler");
    assert.equal(set_text, "abc\ndef\nghi");
    assert.equal(wrap_selection_called, false);

    // Undo spoiler selected text, only content selected
    reset_state();
    init_textarea("```spoiler \nabc\n```", {
        start: 12,
        end: 15,
        text: "abc",
        length: 3,
    });
    compose_ui.format_text($textarea, "spoiler");
    assert.equal(set_text, "abc");
    assert.equal(wrap_selection_called, false);

    reset_state();
    init_textarea("```spoiler abc\ndef\n```", {
        start: 15,
        end: 18,
        text: "def",
        length: 3,
    });
    compose_ui.format_text($textarea, "spoiler");
    assert.equal(set_text, "abc\ndef");
    assert.equal(wrap_selection_called, false);

    reset_state();
    init_textarea("abc\n```spoiler d\nef\n```\nghi", {
        start: 17,
        end: 19,
        text: "ef",
        length: 2,
    });
    compose_ui.format_text($textarea, "spoiler");
    assert.equal(set_text, "abc\nd\nef\nghi");
    assert.equal(wrap_selection_called, false);

    // Undo spoiler selected text, content and title selected
    reset_state();
    init_textarea("```spoiler abc\ndef\n```", {
        start: 11,
        end: 18,
        text: "abc\ndef",
        length: 7,
    });
    compose_ui.format_text($textarea, "spoiler");
    assert.equal(set_text, "abc\ndef");
    assert.equal(wrap_selection_called, false);

    reset_state();
    init_textarea("abc\n```spoiler d\nef\n```\nghi", {
        start: 15,
        end: 19,
        text: "d\nef",
        length: 4,
    });
    compose_ui.format_text($textarea, "spoiler");
    assert.equal(set_text, "abc\nd\nef\nghi");
    assert.equal(wrap_selection_called, false);

    // Undo spoiler selected text, syntax selected
    reset_state();
    init_textarea("```spoiler abc\ndef\n```", {
        start: 0,
        end: 22,
        text: "```spoiler abc\ndef\n```",
        length: 22,
    });
    compose_ui.format_text($textarea, "spoiler");
    assert.equal(set_text, "abc\ndef");
    assert.equal(wrap_selection_called, false);

    reset_state();
    init_textarea("abc\n```spoiler d\nef\n```\nghi", {
        start: 4,
        end: 23,
        text: "```spoiler d\nef\n```",
        length: 19,
    });
    compose_ui.format_text($textarea, "spoiler");
    assert.equal(set_text, "abc\nd\nef\nghi");
    assert.equal(wrap_selection_called, false);
});

run_test("format_text - link", ({override}) => {
    override(text_field_edit, "set", (_field, text) => {
        set_text = text;
    });
    override(text_field_edit, "wrapSelection", (_field, syntax_start, syntax_end) => {
        wrap_selection_called = true;
        wrap_syntax_start = syntax_start;
        wrap_syntax_end = syntax_end;
    });

    const link_syntax_start = "[";
    const link_syntax_end = "](url)";

    // Link selected text
    reset_state();
    init_textarea("abc", {
        start: 0,
        end: 3,
        text: "abc",
        length: 3,
    });
    compose_ui.format_text($textarea, "link");
    assert.equal(set_text, "");
    assert.equal(wrap_selection_called, true);
    assert.equal(wrap_syntax_start, link_syntax_start);
    assert.equal(wrap_syntax_end, link_syntax_end);

    // Undo link selected text, url selected
    reset_state();
    init_textarea("[abc](def)", {
        start: 6,
        end: 9,
        text: "def",
        length: 3,
    });
    compose_ui.format_text($textarea, "link");
    assert.equal(set_text, "abc def");
    assert.equal(wrap_selection_called, false);

    reset_state();
    init_textarea("[abc](url)", {
        start: 6,
        end: 9,
        text: "url",
        length: 3,
    });
    compose_ui.format_text($textarea, "link");
    assert.equal(set_text, "abc");
    assert.equal(wrap_selection_called, false);

    // Undo link selected text, description selected
    reset_state();
    init_textarea("[abc](def)", {
        start: 1,
        end: 4,
        text: "abc",
        length: 3,
    });
    compose_ui.format_text($textarea, "link");
    assert.equal(set_text, "abc def");
    assert.equal(wrap_selection_called, false);

    // Undo link selected text, description selected, without disturbing other links
    reset_state();
    init_textarea("[xyz](uvw) [abc](def)", {
        start: 12,
        end: 15,
        text: "abc",
        length: 3,
    });
    compose_ui.format_text($textarea, "link");
    assert.equal(set_text, "[xyz](uvw) abc def");
    assert.equal(wrap_selection_called, false);

    // Undo link selected text, syntax selected
    reset_state();
    init_textarea("[abc](def)", {
        start: 0,
        end: 10,
        text: "[abc](def)",
        length: 10,
    });
    compose_ui.format_text($textarea, "link");
    assert.equal(set_text, "abc def");
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
        compose_ui.handle_keydown(event, $("textarea#compose-textarea"));
        assert.equal(format_text_type, "bold");
        format_text_type = undefined;

        // Test italic:
        // Mac = Cmd+I
        // Windows/Linux = Ctrl+I
        // We use event.key = "I" to emulate user using Caps Lock key.
        event.key = "I";
        event.shiftKey = false;
        compose_ui.handle_keydown(event, $("textarea#compose-textarea"));
        assert.equal(format_text_type, "italic");
        format_text_type = undefined;

        // Test link insertion:
        // Mac = Cmd+Shift+L
        // Windows/Linux = Ctrl+Shift+L
        event.key = "l";
        event.shiftKey = true;
        compose_ui.handle_keydown(event, $("textarea#compose-textarea"));
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
        compose_ui.handle_keydown(event, $("textarea#compose-textarea"));
        assert.equal(format_text_type, undefined);

        event.key = "i";
        event.shiftKey = false;
        compose_ui.handle_keydown(event, $("textarea#compose-textarea"));
        assert.equal(format_text_type, undefined);

        event.key = "l";
        event.shiftKey = true;
        compose_ui.handle_keydown(event, $("textarea#compose-textarea"));
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
    const $textarea = $("textarea#compose-textarea");

    const event = {
        key: "A",
    };

    assert.equal($textarea.hasClass("rtl"), false);

    $textarea.val("```quote\nمرحبا");
    compose_ui.handle_keyup(event, $("textarea#compose-textarea"));

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
        "textarea#compose-textarea",
    );
    assert.equal(get_focus_area("stream", {}), "#compose_select_recipient_widget_wrapper");
    assert.equal(
        get_focus_area("stream", {stream_name: "fun", stream_id: 4}),
        "input#stream_message_recipient_topic",
    );
    assert.equal(
        get_focus_area("stream", {stream_name: "fun", stream_id: 4, topic: "more"}),
        "textarea#compose-textarea",
    );
    assert.equal(
        get_focus_area("stream", {
            stream_id: 4,
            topic: "more",
            trigger: "clear topic button",
        }),
        "input#stream_message_recipient_topic",
    );
});
