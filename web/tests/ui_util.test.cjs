"use strict";

const assert = require("node:assert/strict");

const {set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");
const {$} = require("./lib/zjquery.cjs");

class InputEvent {
    constructor({inputType, data}) {
        this.inputType = inputType;
        this.data = data;
    }
}
set_global("InputEvent", InputEvent);
class ClipboardEvent {
    constructor({clipboardData}) {
        this.clipboardData = clipboardData;
    }
}
set_global("ClipboardEvent", ClipboardEvent);
class DragEvent {
    constructor({dataTransfer}) {
        this.dataTransfer = dataTransfer;
    }
}
set_global("DragEvent", DragEvent);

const ui_util = zrequire("ui_util");

run_test("potentially_collapse_quotes", ({override_rewire}) => {
    const $element = $.create("message-content");

    $element.set_children([
        $.create("normal paragraph 1")[0],
        $.create("blockquote")[0],
        $.create("normal paragraph 2")[0],
        $.create("user said paragraph")[0],
        $.create("message quote")[0],
        $.create("normal paragraph 3")[0],
    ]);
    override_rewire(ui_util, "get_collapsible_status_array", () => [
        false,
        true,
        false,
        true,
        true,
        false,
    ]);
    // When there are both collapsible and non-collapsible elements, for
    // multiple collapsible elements in a row, only the first element
    // should be collapsed, and the rest's text should be removed. Non-
    // collapsible elements should not be touched.
    let collapsed = ui_util.potentially_collapse_quotes($element);
    assert.equal(collapsed, true);
    let expected_texts = ["never-been-set", "[…]", "never-been-set", "[…]", "", "never-been-set"];
    assert.deepEqual(
        [...$element.children()].map((element) => element.textContent),
        expected_texts,
    );

    $element.set_children([
        $.create("normal paragraph 4")[0],
        $.create("normal paragraph 5")[0],
        $.create("normal paragraph 6")[0],
    ]);
    override_rewire(ui_util, "get_collapsible_status_array", () => [false, false, false]);
    // For all non-collapsible elements, none should be collapsed.
    collapsed = ui_util.potentially_collapse_quotes($element);
    assert.equal(collapsed, false);
    expected_texts = ["never-been-set", "never-been-set", "never-been-set"];
    assert.deepEqual(
        [...$element.children()].map((element) => element.textContent),
        expected_texts,
    );

    $element.set_children([
        $.create("blockquote 1")[0],
        $.create("blockquote 2")[0],
        $.create("blockquote 3")[0],
    ]);
    override_rewire(ui_util, "get_collapsible_status_array", () => [true, true, true]);
    // For all collapsible elements, none should be collapsed.
    collapsed = ui_util.potentially_collapse_quotes($element);
    assert.equal(collapsed, false);
    expected_texts = ["never-been-set", "never-been-set", "never-been-set"];
    assert.deepEqual(
        [...$element.children()].map((element) => element.textContent),
        expected_texts,
    );
});

run_test("topic search term parsing", ({override_rewire}) => {
    // get_left_sidebar_search_term() already trims, so each value
    // here stands in for an already-trimmed search input.
    function set_search_term(term) {
        override_rewire(ui_util, "get_left_sidebar_search_term", () => term);
    }

    // Without the "topic:" prefix, there is no topic search.
    set_search_term("foo");
    assert.equal(ui_util.get_left_sidebar_topic_search_term(), undefined);
    assert.equal(ui_util.is_topic_search(), false);

    // The "topic:" prefix yields the rest of the term as the query.
    set_search_term("topic:foo");
    assert.equal(ui_util.get_left_sidebar_topic_search_term(), "foo");
    assert.equal(ui_util.is_topic_search(), true);

    // Whitespace after the prefix is trimmed off the query.
    set_search_term("topic:   important");
    assert.equal(ui_util.get_left_sidebar_topic_search_term(), "important");

    // The prefix match is case-insensitive; the query keeps its case.
    set_search_term("TOPIC:Foo");
    assert.equal(ui_util.get_left_sidebar_topic_search_term(), "Foo");
    assert.equal(ui_util.is_topic_search(), true);

    // The prefix alone, with an empty query, still counts as a topic
    // search (so the sidebar switches to topic-filtering mode).
    set_search_term("topic:");
    assert.equal(ui_util.get_left_sidebar_topic_search_term(), "");
    assert.equal(ui_util.is_topic_search(), true);

    // "topic:" only counts as a prefix, not when it appears mid-term.
    set_search_term("mytopic:foo");
    assert.equal(ui_util.get_left_sidebar_topic_search_term(), undefined);
    assert.equal(ui_util.is_topic_search(), false);
});

run_test("replace_emoji_name_with_emoji_unicode", () => {
    const $emoji = $.create("span").attr("class", "emoji emoji-1f419");
    $emoji.set_matches("img", false);

    const octopus_emoji = "🐙";
    assert.equal(octopus_emoji, ui_util.convert_emoji_element_to_unicode($emoji));

    $emoji.attr("class", "emoji emoji-1f468-200d-1f373");
    const man_cook_emoji = "👨‍🍳";
    assert.equal(man_cook_emoji, ui_util.convert_emoji_element_to_unicode($emoji));

    // An invalid codepoint falls back to the element's text.
    $emoji.attr("class", "emoji emoji-1f468-110000-1f373");
    $emoji.text(":man_cook:");
    blueslip.expect("error", "Invalid unicode codepoint for emoji");
    assert.equal(ui_util.convert_emoji_element_to_unicode($emoji), ":man_cook:");
});

run_test("set_up_shake_on_length_limit", () => {
    const $input = $.create("length-limited-input");
    ui_util.set_up_shake_on_length_limit($input, 5);
    const shake_class = "input-validation-shake";

    function set_value(value, selection_start = value.length, selection_end = value.length) {
        $input.val(value);
        $input[0].setSelectionRange(selection_start, selection_end);
        $input.removeClass(shake_class);
    }

    function trigger(event_name, originalEvent) {
        let default_prevented = false;
        $input.get_on_handler(event_name)({
            originalEvent,
            preventDefault() {
                default_prevented = true;
            },
        });
        return {shaken: $input.hasClass(shake_class), default_prevented};
    }

    function insert_text(inputType, data) {
        return trigger("beforeinput", new InputEvent({inputType, data}));
    }

    function paste_text(text) {
        return trigger("paste", new ClipboardEvent({clipboardData: {getData: () => text}}));
    }

    function drop_text(text) {
        return trigger("drop", new DragEvent({dataTransfer: {getData: () => text}}));
    }

    const fits = {shaken: false, default_prevented: false};
    const truncated = {shaken: true, default_prevented: false};
    const no_room = {shaken: true, default_prevented: true};

    // Typing that fits, or that replaces a selection, doesn't shake.
    set_value("abc");
    assert.deepEqual(insert_text("insertText", "d"), fits);
    set_value("abcde", 0, 5);
    assert.deepEqual(insert_text("insertText", "f"), fits);
    set_value("abcde");
    assert.deepEqual(insert_text("insertText", "f"), no_room);

    // Other input types, and ones without data, are ignored.
    set_value("abcde");
    assert.deepEqual(insert_text("deleteContentBackward", null), fits);
    assert.deepEqual(insert_text("insertReplacementText", "f"), fits);
    assert.deepEqual(trigger("beforeinput", {}), fits);

    // A composition is measured against the text kept when it began.
    set_value("abc");
    $input.get_on_handler("compositionstart")();
    set_value("abcxy");
    assert.deepEqual(insert_text("insertCompositionText", "xy"), fits);
    assert.deepEqual(insert_text("insertCompositionText", "xyz"), truncated);
    set_value("abcde");
    $input.get_on_handler("compositionstart")();
    assert.deepEqual(insert_text("insertCompositionText", "x"), no_room);

    // A truncated paste shakes; one with no room left is cancelled.
    set_value("abc");
    assert.deepEqual(paste_text("de"), fits);
    set_value("abc");
    assert.deepEqual(paste_text("defg"), truncated);
    set_value("abcde");
    assert.deepEqual(paste_text("f"), no_room);
    set_value("abcde");
    assert.deepEqual(paste_text(""), fits);
    set_value("abcde");
    assert.deepEqual(trigger("paste", {}), fits);

    // A drop doesn't replace the selection.
    set_value("ab");
    assert.deepEqual(drop_text("c"), fits);
    set_value("abc");
    assert.deepEqual(drop_text("defg"), truncated);
    set_value("abcde", 0, 5);
    assert.deepEqual(drop_text("f"), no_room);
    set_value("abcde");
    assert.deepEqual(trigger("drop", {}), fits);

    // Dragging text within the input moves it, so it can't overflow.
    const drag_handler = $input.get_on_handler("dragstart dragend");
    drag_handler({type: "dragstart"});
    set_value("abcde");
    assert.deepEqual(drop_text("e"), fits);
    drag_handler({type: "dragend"});
    set_value("abcde");
    assert.deepEqual(drop_text("e"), no_room);

    $input.addClass(shake_class);
    $input.get_on_handler("animationend")();
    assert.ok(!$input.hasClass(shake_class));
});
