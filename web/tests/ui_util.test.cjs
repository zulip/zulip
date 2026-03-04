"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

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

run_test("replace_emoji_name_with_emoji_unicode", () => {
    const $emoji = $.create("span").attr("class", "emoji emoji-1f419");
    $emoji.set_matches("img", false);

    const octopus_emoji = "🐙";
    assert.equal(octopus_emoji, ui_util.convert_emoji_element_to_unicode($emoji));

    $emoji.attr("class", "emoji emoji-1f468-200d-1f373");
    const man_cook_emoji = "👨‍🍳";
    assert.equal(man_cook_emoji, ui_util.convert_emoji_element_to_unicode($emoji));
});
